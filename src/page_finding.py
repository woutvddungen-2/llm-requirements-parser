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
)
from src.pdf_utils import load_pdf_page_texts, load_pdf_toc

DEFAULT_PAGE_FINDER_MAX_TOKENS = 2048
PAGE_FINDER_STRATEGIES = ("toc", "keyword", "regex", "llm")
TEXT_TOC_SCAN_LIMIT = 20
TEXT_TOC_MIN_TOCISH_LINES = 5
TEXT_TOC_MAX_PAGE_NUMBER = 500


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


def find_relevant_pages(
    pdf_path: str | Path,
    strategy: str,
    model: str | None = None,
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
    """Join selected pages into one extraction input."""
    selected = []
    for page_index in sorted(set(relevant_pages)):
        text = page_texts.get(page_index, "").strip()
        if text:
            selected.append(text)
    return "\n\n".join(selected).strip()


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
