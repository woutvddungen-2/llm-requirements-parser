from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from src.llm_client import generate_text
from src.llm_types import LLMResult
from src.page_finding_ac_config import (
    AC_KEYWORDS,
    AC_REGEX_PATTERNS,
    HIGH_SCORE_THRESHOLD,
    NEIGHBOR_THRESHOLD,
    PAGE_FINDER_PROMPT,
    PAGE_FINDER_SYSTEM_PROMPT,
    REGEX_HIGH_SCORE_THRESHOLD,
    REGEX_NEIGHBOR_THRESHOLD,
    REGEX_SCORE_THRESHOLD,
    SCORE_THRESHOLD,
    SECTION_CATEGORIES,
    PageCategoryScores,
)
from src.pdf_utils import load_pdf_page_texts, load_pdf_toc

DEFAULT_PAGE_FINDER_MAX_TOKENS = 2048
PAGE_FINDER_STRATEGIES = ("toc", "keyword", "regex", "hybrid", "category", "llm")
TEXT_TOC_SCAN_LIMIT = 20
TEXT_TOC_MIN_TOCISH_LINES = 5
TEXT_TOC_MAX_PAGE_NUMBER = 500
BLOCK_SCORE_THRESHOLD = 8
BLOCK_ACTION_HINTS = (
    "wordt",
    "worden",
    "zal",
    "zullen",
    "dient",
    "dienen",
    "voorzien",
    "geplaatst",
    "gerealiseerd",
    "uitgevoerd",
    "geopend",
    "ontgrendelen",
    "ontgrendeld",
    "aangesloten",
    "aangebracht",
    "kunnen",
    "moet",
    "moeten",
)


@dataclass
class PageFinderResult(LLMResult):
    page_numbers: list[int] | None = None


@dataclass
class PageSelection:
    method: str
    relevant_pages: list[int]
    page_scores: dict[int, int]
    page_texts: dict[int, str]
    primary_pages: list[int] | None = None
    neighbor_pages: list[int] | None = None
    page_result: PageFinderResult | None = None
    category_scores: dict[int, PageCategoryScores] | None = None
    extracted_content: str | None = None  # For category-based extraction


def score_pages_by_category(page_texts: Mapping[int, str]) -> dict[int, PageCategoryScores]:
    """Score each page across all section categories (ACCESS, HVAC, FIRE, etc).

    Returns a dict mapping page number to CategoryScores with scores for each category.
    """
    results = {}

    for page_num, text in page_texts.items():
        scores = {}

        for category_name, category_config in SECTION_CATEGORIES.items():
            category_score = 0

            # Score by keywords
            for keyword, weight in category_config["keywords"].items():
                if keyword.lower() in text.lower():
                    category_score += weight

            # Score by regex patterns
            for pattern_str, weight in category_config["regex"]:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(text):
                    category_score += weight

            scores[category_name] = category_score

        results[page_num] = PageCategoryScores(page_num=page_num, scores=scores)

    return results


def _extract_paragraphs(text: str) -> list[str]:
    """Extract paragraphs from text using double-newline and section breaks.

    Tries to find the cleanest breaks:
    1. Double newlines (most common paragraph breaks)
    2. Lines starting with numbers/bullets (section breaks)
    3. Falls back to single newlines if text is dense

    Returns non-empty paragraphs with whitespace normalized.
    """
    # First try: split on double newlines (most reliable for structured docs)
    parts = text.split('\n\n')
    if len(parts) > 1:
        paragraphs = [p.strip() for p in parts if p.strip()]
        if paragraphs:
            return paragraphs

    # Second try: look for section starts (4.12.21, 65.5, etc. or bullet points)
    # This handles documents where paragraphs aren't clearly separated
    section_pattern = re.compile(r'^[\s]*(?:\d+\.[\d.]*|[•\-\*])\s+', re.MULTILINE)
    section_starts = [(m.start(), m.end()) for m in section_pattern.finditer(text)]

    if len(section_starts) > 1:
        # Extract content between section starts
        paragraphs = []
        for i, (start, end) in enumerate(section_starts):
            next_start = section_starts[i + 1][0] if i + 1 < len(section_starts) else len(text)
            section_text = text[start:next_start].strip()
            if section_text:
                paragraphs.append(section_text)
        if paragraphs:
            return paragraphs

    # Fallback: split on single newlines if text is sparse enough
    lines = text.split('\n')
    paragraphs = []
    current = []
    for line in lines:
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))

    return [p for p in paragraphs if p]


def _score_text_on_categories(text: str) -> dict[str, int]:
    """Score a piece of text on all 6 categories.

    Returns dict of {category_name: score}.
    """
    scores = {}
    text_lower = text.lower()

    for category_name, category_config in SECTION_CATEGORIES.items():
        category_score = 0

        # Score by keywords
        for keyword, weight in category_config["keywords"].items():
            if keyword.lower() in text_lower:
                category_score += weight

        # Score by regex patterns
        for pattern_str, weight in category_config["regex"]:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            if pattern.search(text):
                category_score += weight

        scores[category_name] = category_score

    return scores


def extract_content_by_category(
    pdf_path: str | Path,
    target_category: str = "ACCESS",
    contamination_threshold: float = 0.25,
) -> tuple[str, dict[int, PageCategoryScores]]:
    """Extract clean content for a specific category from a PDF.

    Args:
        pdf_path: Path to PDF
        target_category: Which category to extract (e.g., "ACCESS")
        contamination_threshold: If other categories score > this fraction of target,
                                 reject the paragraph (0.25 = 25%)

    Returns:
        (clean_content_text, page_category_scores_for_debugging)

    The algorithm:
    1. Score every page on all categories
    2. For pure pages (target dominates), include all content
    3. For mixed pages, split into paragraphs and include only clean ones
    4. A paragraph is clean if other categories < 25% of target category score
    """
    page_texts = load_pdf_page_texts(pdf_path)
    page_scores = score_pages_by_category(page_texts)

    content_segments = []

    for page_num in sorted(page_texts.keys()):
        page_text = page_texts[page_num]
        page_cs = page_scores[page_num]

        target_score = page_cs.scores.get(target_category, 0)
        other_scores = [s for cat, s in page_cs.scores.items() if cat != target_category]
        max_other = max(other_scores) if other_scores else 0

        # Pure page: target dominates significantly
        if max_other < target_score * contamination_threshold:
            content_segments.append(page_text)
            continue

        # Mixed page: extract paragraphs and filter
        if target_score > 0:
            paragraphs = _extract_paragraphs(page_text)
            for para in paragraphs:
                para_scores = _score_text_on_categories(para)
                para_target = para_scores.get(target_category, 0)
                para_others = [s for cat, s in para_scores.items() if cat != target_category]
                para_max_other = max(para_others) if para_others else 0

                # Include if paragraph is clean (target dominates)
                if para_target > 0 and para_max_other < para_target * contamination_threshold:
                    content_segments.append(para)

    # Concatenate all clean segments
    clean_content = "\n\n".join(content_segments)

    return clean_content, page_scores


def find_relevant_pages(
    pdf_path: str | Path,
    strategy: str,
    model: str | None = None,
    category: str = "ACCESS",
    contamination_threshold: float = 0.25,
) -> PageSelection:
    """Select relevant access-control pages using one explicit strategy."""
    if strategy not in PAGE_FINDER_STRATEGIES:
        raise ValueError(
            f"Unknown page-finder strategy '{strategy}'. "
            f"Expected one of: {', '.join(PAGE_FINDER_STRATEGIES)}."
        )

    page_texts = load_pdf_page_texts(pdf_path)
    toc = load_pdf_toc(pdf_path)

    page_scores = _score_pages_by_keywords(page_texts, AC_KEYWORDS)

    if strategy == "toc":
        toc_pages = _find_from_toc(toc, AC_KEYWORDS)
        if toc_pages:
            return PageSelection(
                method="Embedded TOC",
                relevant_pages=toc_pages,
                page_scores=page_scores,
                page_texts=page_texts,
            )
        text_toc_method, text_toc_pages = _find_from_text_toc(page_texts, AC_KEYWORDS, page_scores)
        if text_toc_pages:
            return PageSelection(
                method=text_toc_method,
                relevant_pages=text_toc_pages,
                page_scores=page_scores,
                page_texts=page_texts,
            )
        raise ValueError(f"No relevant pages found via embedded TOC or text TOC for {pdf_path}.")

    if strategy == "keyword":
        relevant_pages, primary_pages, neighbor_pages = _find_from_scores(
            page_scores,
            SCORE_THRESHOLD,
            NEIGHBOR_THRESHOLD,
            HIGH_SCORE_THRESHOLD,
        )
        if relevant_pages:
            return PageSelection(
                method="Keyword scoring",
                relevant_pages=relevant_pages,
                page_scores=page_scores,
                primary_pages=primary_pages,
                neighbor_pages=neighbor_pages,
                page_texts=page_texts,
            )
        raise ValueError(f"No relevant pages found via keyword scoring for {pdf_path}.")

    if strategy == "regex":
        regex_scores = _score_pages_by_regex(page_texts, AC_REGEX_PATTERNS)
        relevant_pages, primary_pages, neighbor_pages = _find_from_scores(
            regex_scores,
            REGEX_SCORE_THRESHOLD,
            REGEX_NEIGHBOR_THRESHOLD,
            REGEX_HIGH_SCORE_THRESHOLD,
        )
        if relevant_pages:
            return PageSelection(
                method="Regex scoring",
                relevant_pages=relevant_pages,
                page_scores=regex_scores,
                primary_pages=primary_pages,
                neighbor_pages=neighbor_pages,
                page_texts=page_texts,
            )
        raise ValueError(f"No relevant pages found via regex scoring for {pdf_path}.")

    if strategy == "hybrid":
        regex_scores = _score_pages_by_regex(page_texts, AC_REGEX_PATTERNS)
        kw_relevant, kw_primary, _ = _find_from_scores(
            page_scores,
            SCORE_THRESHOLD,
            NEIGHBOR_THRESHOLD,
            HIGH_SCORE_THRESHOLD,
        )
        rx_relevant, rx_primary, _ = _find_from_scores(
            regex_scores,
            REGEX_SCORE_THRESHOLD,
            REGEX_NEIGHBOR_THRESHOLD,
            REGEX_HIGH_SCORE_THRESHOLD,
        )
        combined_scores = {
            page_index: page_scores.get(page_index, 0) + regex_scores.get(page_index, 0)
            for page_index in page_texts
        }
        relevant_pages, primary_pages, neighbor_pages = _find_hybrid_pages(
            kw_relevant=kw_relevant,
            kw_primary=kw_primary,
            rx_relevant=rx_relevant,
            rx_primary=rx_primary,
            combined_scores=combined_scores,
        )
        if relevant_pages:
            return PageSelection(
                method="Keyword+regex consensus",
                relevant_pages=relevant_pages,
                page_scores=combined_scores,
                primary_pages=primary_pages,
                neighbor_pages=neighbor_pages,
                page_texts=page_texts,
            )
        raise ValueError(f"No relevant pages found via hybrid scoring for {pdf_path}.")

    if strategy == "category":
        extracted_content, category_scores = extract_content_by_category(
            pdf_path,
            target_category=category,
            contamination_threshold=contamination_threshold,
        )
        if extracted_content.strip():
            return PageSelection(
                method=f"Category-based content extraction ({category}, contamination_threshold={contamination_threshold})",
                relevant_pages=[],  # Not used for content-based extraction
                page_scores={},
                page_texts=page_texts,
                category_scores=category_scores,
                extracted_content=extracted_content,
            )
        raise ValueError(f"No clean {category} content found via category filtering for {pdf_path}.")

    if not model:
        raise ValueError(
            "LLM page selection requires a model. "
            "Provide 'page_finder_model' in the case input when using the 'llm' strategy."
        )

    page_result = _find_via_llm(page_texts, model)
    return PageSelection(
        method="LLM fallback",
        relevant_pages=sorted({p - 1 for p in page_result.page_numbers or []}),
        page_scores=page_scores,
        page_texts=page_texts,
        page_result=page_result,
    )


def build_requirement_text_from_pages(
    page_texts: Mapping[int, str],
    relevant_pages: Iterable[int],
) -> str:
    """Join selected pages into one extraction input.

    For noisy PDF pages, keep only the blocks that look like actionable
    access-control requirements so the extractor sees less inventory-style text.
    """
    selected = []
    for page_index in sorted(set(relevant_pages)):
        text = page_texts.get(page_index, "").strip()
        if text:
            excerpt = _extract_relevant_excerpt(text)
            selected.append(excerpt or text)
    return "\n\n".join(selected).strip()


def _extract_relevant_excerpt(text: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    if not blocks:
        return ""

    kept: list[str] = []
    for idx, block in enumerate(blocks):
        block_score = _score_text_block(block)
        if block_score < BLOCK_SCORE_THRESHOLD:
            continue

        if _looks_like_inventory_block(block):
            continue

        if idx > 0 and _looks_like_heading_block(blocks[idx - 1]):
            heading = blocks[idx - 1].strip()
            if not kept or kept[-1] != heading:
                kept.append(heading)

        kept.append(block)

    excerpt = "\n\n".join(kept).strip()
    original_score = _score_text_block(text)
    excerpt_score = _score_text_block(excerpt) if excerpt else 0

    if (
        excerpt
        and len(excerpt) <= int(len(text) * 0.9)
        and len(excerpt) >= int(len(text) * 0.2)
        and _retains_enough_signal(excerpt_score, original_score)
    ):
        return excerpt

    line_excerpt = _extract_relevant_line_windows(text)
    line_score = _score_text_block(line_excerpt) if line_excerpt else 0
    if (
        line_excerpt
        and len(line_excerpt) < len(text)
        and len(line_excerpt) >= int(len(text) * 0.2)
        and _retains_enough_signal(line_score, original_score)
    ):
        return line_excerpt

    return text


def _retains_enough_signal(candidate_score: int, original_score: int) -> bool:
    if original_score <= 0:
        return bool(candidate_score)
    return candidate_score >= max(8, int(original_score * 0.45))


def _extract_relevant_line_windows(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines:
        return ""

    candidate_indexes: set[int] = set()
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        if _contains_actionable_door_sentence(line):
            candidate_indexes.update(range(max(0, idx - 1), min(len(lines), idx + 3)))
            continue

        if _looks_like_heading_block(line):
            lookahead = " ".join(lines[idx:min(len(lines), idx + 4)])
            if _contains_actionable_door_sentence(lookahead):
                candidate_indexes.update(range(idx, min(len(lines), idx + 5)))
            continue

    if not candidate_indexes:
        return ""

    selected_lines: list[str] = []
    previous_idx = -2
    for idx in sorted(candidate_indexes):
        line = lines[idx].strip()
        if not line:
            continue
        if idx - previous_idx > 1 and selected_lines:
            selected_lines.append("")
        selected_lines.append(line)
        previous_idx = idx

    return "\n".join(selected_lines).strip()


def _score_text_block(text: str) -> int:
    lower = text.lower()
    keyword_score = sum(score for kw, score in AC_KEYWORDS.items() if _text_contains_keyword(lower, kw))
    regex_score = 0
    for pattern, weight in AC_REGEX_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            regex_score += weight * len(matches)
    return keyword_score + regex_score


def _looks_like_inventory_block(text: str) -> bool:
    lower = text.lower()
    if any(re.search(rf"\b{re.escape(hint)}\b", lower) for hint in BLOCK_ACTION_HINTS):
        if _contains_actionable_door_sentence(text):
            return False

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False

    short_lines = sum(1 for line in lines if len(line) <= 80)
    bulletish_lines = sum(1 for line in lines if line.startswith(("-", "•", "o ")))
    if short_lines >= max(3, len(lines) // 2) or bulletish_lines >= max(2, len(lines) // 2):
        return not _contains_actionable_door_sentence(text)

    return False


def _contains_actionable_door_sentence(text: str) -> bool:
    patterns = (
        r"\bdeur(?:en)?\b.{0,80}\b(wordt|worden|zal|zullen|dient|dienen|voorzien|geplaatst|gerealiseerd|geopend|ontgrendeld)\b",
        r"\b(kaartlezers?|paslezers?|intercom|videofoon|handmelder|groene melder|elleboogschakelaar|elektrisch slot|sluitsysteem)\b.{0,80}\b(wordt|worden|zal|zullen|dient|dienen|voorzien|geplaatst|gerealiseerd|geopend|ontgrendeld)\b",
    )
    return any(re.search(pattern, text, re.IGNORECASE | re.DOTALL) for pattern in patterns)


def _looks_like_heading_block(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized or len(normalized) > 120:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 2:
        return False
    if any(ch in normalized for ch in ".:;"):
        return False
    return bool(re.search(r"(toegang|toegangscontrole|intercom|beveilig|communicatie|systeem|handmelders?)", normalized, re.IGNORECASE))


def _find_from_toc(
    toc: Iterable[tuple[int, str, int]],
    keywords: Mapping[str, int],
) -> list[int]:
    keyword_terms = tuple(keywords.keys())
    return sorted(
        {
            page_number - 1
            for _, title, page_number in toc
            if any(kw in title.lower() for kw in keyword_terms)
        }
    )


def _find_from_text_toc(
    page_texts: Mapping[int, str],
    keywords: Mapping[str, int],
    page_scores: Mapping[int, int],
) -> tuple[str, list[int]]:
    toc_pages = _find_text_toc_page_range(page_texts)
    if not toc_pages:
        return "Text TOC", []

    keyword_terms = tuple(keywords.keys())
    direct_pages: set[int] = set()
    contextual_pages: set[int] = set()
    for page_index in toc_pages:
        entries = _extract_toc_entries(page_texts[page_index])
        direct_pages.update(_select_direct_toc_pages(entries, keyword_terms, page_texts))
        contextual_pages.update(_select_contextual_toc_pages(entries, page_scores, page_texts))

    selected_pages = sorted(page for page in (direct_pages | contextual_pages) if page in page_texts)
    if contextual_pages - direct_pages:
        return "Text TOC + keyword context", selected_pages
    return "Text TOC", selected_pages


def _find_text_toc_page_range(page_texts: Mapping[int, str]) -> list[int]:
    max_page = min(TEXT_TOC_SCAN_LIMIT, len(page_texts))
    marker_pages = [
        page_index
        for page_index in range(max_page)
        if _contains_toc_marker(page_texts.get(page_index, ""))
    ]

    if marker_pages:
        candidate_pages: list[int] = []
        start_page = marker_pages[0]
        for page_index in range(start_page, max_page):
            text = page_texts.get(page_index, "")
            if _contains_toc_marker(text) or _looks_like_toc_page(text) or _count_toc_entries(text) >= 8:
                candidate_pages.append(page_index)
            elif candidate_pages:
                break
        return candidate_pages

    candidate_pages: list[int] = []
    for page_index in range(max_page):
        text = page_texts.get(page_index, "")
        if _looks_like_toc_page(text):
            candidate_pages.append(page_index)
        elif candidate_pages:
            break

    return candidate_pages


def _looks_like_toc_page(text: str) -> bool:
    tocish_lines = _count_toc_entries(text)
    return tocish_lines >= TEXT_TOC_MIN_TOCISH_LINES


def _count_toc_entries(text: str) -> int:
    return len(_extract_toc_entries(text))


def _contains_toc_marker(text: str) -> bool:
    lower_text = text.lower()
    return "inhoudsopgave" in lower_text or re.search(r"^\s*inhoud\s*$", lower_text, re.MULTILINE) is not None


def _extract_relevant_pages_from_toc_text(
    text: str,
    keyword_terms: tuple[str, ...],
) -> set[int]:
    entries = _extract_toc_entries(text)
    return _select_direct_toc_pages(entries, keyword_terms, {})


def _extract_toc_entries(text: str) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    merged_lines = _merge_toc_lines(text.splitlines())

    for line in merged_lines:
        normalized = " ".join(line.split())
        match = re.match(r"^(?P<title>.+?)\s+\.{2,}\s*(?P<page>\d{1,3})$", normalized)
        if not match:
            match = re.match(r"^(?P<title>.+?)\s+(?P<page>\d{1,3})$", normalized)
        if not match:
            continue

        title = match.group("title").strip()
        page_number = int(match.group("page"))
        if page_number > TEXT_TOC_MAX_PAGE_NUMBER:
            continue
        entries.append((title, page_number - 1))

    return entries


def _select_direct_toc_pages(
    entries: Iterable[tuple[str, int]],
    keyword_terms: tuple[str, ...],
    page_texts: Mapping[int, str],
) -> set[int]:
    selected_pages: set[int] = set()
    for title, page_index in entries:
        title_lower = title.lower()
        if any(_text_contains_keyword(title_lower, term) for term in keyword_terms):
            if not page_texts or page_index in page_texts:
                selected_pages.add(page_index)
    return selected_pages


def _select_contextual_toc_pages(
    entries: list[tuple[str, int]],
    page_scores: Mapping[int, int],
    page_texts: Mapping[int, str],
) -> set[int]:
    selected_pages: set[int] = set()
    max_page_index = max(page_texts) if page_texts else -1

    for title, page_index in entries:
        if page_index < 0 or page_index > max_page_index:
            continue
        window = range(page_index, min(page_index + 5, max_page_index + 1))
        local_score = sum(page_scores.get(i, 0) for i in window)
        if local_score < SCORE_THRESHOLD:
            continue

        title_lower = title.lower()
        if "install" not in title_lower and "toegang" not in title_lower and "beveilig" not in title_lower:
            continue

        for neighbor in window:
            if page_scores.get(neighbor, 0) > 0:
                selected_pages.add(neighbor)

    return selected_pages


def _merge_toc_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""

    for line in lines:
        stripped = " ".join(line.split())
        if not stripped:
            continue

        if re.match(r"^\d{1,3}$", stripped) and buffer:
            merged.append(f"{buffer} {stripped}")
            buffer = ""
            continue

        if re.match(r"^.+?(?:\.{2,}\s*)?\d{1,3}$", stripped):
            if buffer:
                merged.append(f"{buffer} {stripped}")
                buffer = ""
            else:
                merged.append(stripped)
            continue

        if buffer:
            buffer = f"{buffer} {stripped}"
        else:
            buffer = stripped

    if buffer:
        merged.append(buffer)

    return merged


def _text_contains_keyword(text: str, keyword: str) -> bool:
    if keyword == "tag":
        return re.search(r"\btag\b", text) is not None
    return keyword in text


def _score_pages_by_keywords(
    page_texts: Mapping[int, str],
    keywords: Mapping[str, int],
) -> dict[int, int]:
    return {
        i: sum(score for kw, score in keywords.items() if _text_contains_keyword(text.lower(), kw))
        for i, text in page_texts.items()
    }


def _score_pages_by_regex(
    page_texts: Mapping[int, str],
    patterns: Iterable[tuple[object, int]],
) -> dict[int, int]:
    scores: dict[int, int] = {}
    for page_index, text in page_texts.items():
        total = 0
        for pattern, weight in patterns:
            matches = pattern.findall(text)
            if matches:
                total += weight * len(matches)
        scores[page_index] = total
    return scores


def _find_from_scores(
    page_scores: Mapping[int, int],
    score_threshold: int,
    neighbor_threshold: int,
    high_score_threshold: int = 0,
) -> tuple[list[int], list[int], list[int]]:
    primary = {i for i, s in page_scores.items() if s >= score_threshold}
    neighbors = {
        i + delta
        for i in primary
        if page_scores[i] >= high_score_threshold
        for delta in (-1, 1)
        if i + delta in page_scores and page_scores[i + delta] >= neighbor_threshold
    }
    return sorted(primary | neighbors), sorted(primary), sorted(neighbors - primary)


def _find_hybrid_pages(
    *,
    kw_relevant: list[int],
    kw_primary: list[int],
    rx_relevant: list[int],
    rx_primary: list[int],
    combined_scores: Mapping[int, int],
) -> tuple[list[int], list[int], list[int]]:
    kw_set = set(kw_relevant)
    rx_set = set(rx_relevant)
    primary_overlap = set(kw_primary) & set(rx_primary)
    overlap = kw_set & rx_set

    core = primary_overlap or overlap or (set(kw_primary) | set(rx_primary)) or (kw_set | rx_set)
    if not core:
        return [], [], []

    expanded = set(core)
    union_pages = sorted(kw_set | rx_set)
    for page in union_pages:
        if page in expanded:
            continue
        if combined_scores.get(page, 0) < max(5, NEIGHBOR_THRESHOLD + REGEX_NEIGHBOR_THRESHOLD):
            continue
        if any(abs(page - core_page) == 1 for core_page in expanded):
            expanded.add(page)

    pruned = _prune_to_dominant_clusters(sorted(expanded), combined_scores)
    return pruned, sorted(core), sorted(set(pruned) - set(core))


def _prune_to_dominant_clusters(
    pages: list[int],
    page_scores: Mapping[int, int],
    keep_ratio: float = 0.6,
) -> list[int]:
    if not pages:
        return []

    clusters: list[list[int]] = []
    current = [pages[0]]
    for page in pages[1:]:
        if page == current[-1] + 1:
            current.append(page)
        else:
            clusters.append(current)
            current = [page]
    clusters.append(current)

    if len(clusters) <= 1:
        return pages

    cluster_scores = [sum(page_scores.get(page, 0) for page in cluster) for cluster in clusters]
    top_score = max(cluster_scores)
    kept_clusters = [
        cluster
        for cluster, score in zip(clusters, cluster_scores, strict=True)
        if score >= top_score * keep_ratio
    ]
    return sorted(page for cluster in kept_clusters for page in cluster)


def _find_via_llm(
    page_texts: dict[int, str],
    model: str,
) -> PageFinderResult:
    page_summary = "\n".join(
        f"Page {i + 1}: {text[:500]}" for i, text in page_texts.items()
    )
    result = generate_text(
        system_prompt=PAGE_FINDER_SYSTEM_PROMPT,
        user_prompt=PAGE_FINDER_PROMPT.format(page_summary=page_summary),
        model=model,
        max_tokens=DEFAULT_PAGE_FINDER_MAX_TOKENS,
    )
    parsed = json.loads(result.text)
    page_numbers = parsed.get("page_numbers", [])
    if not isinstance(page_numbers, list):
        raise ValueError("Expected 'page_numbers' to be a list.")

    return PageFinderResult(
        **result.__dict__,
        page_numbers=[int(p) for p in page_numbers],
    )


