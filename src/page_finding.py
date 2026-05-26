from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from src.llm_client import generate_text
from src.llm_types import LLMResult
from src.page_finding_ac_config import (
    AC_KEYWORDS,
    HIGH_SCORE_THRESHOLD,
    NEIGHBOR_THRESHOLD,
    PAGE_FINDER_PROMPT,
    PAGE_FINDER_SYSTEM_PROMPT,
    SCORE_THRESHOLD,
)
from src.pdf_utils import load_pdf_page_texts, load_pdf_toc

DEFAULT_PAGE_FINDER_MAX_TOKENS = 2048
PAGE_FINDER_STRATEGIES = ("toc", "keyword", "llm")


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

    page_scores = {
        i: sum(score for kw, score in AC_KEYWORDS.items() if kw in text.lower())
        for i, text in page_texts.items()
    }

    if strategy == "toc":
        toc_pages = _find_from_toc(toc, AC_KEYWORDS)
        if toc_pages:
            return PageSelection(
                method="TOC",
                relevant_pages=toc_pages,
                page_scores=page_scores,
                page_texts=page_texts,
            )
        raise ValueError(f"No relevant pages found via TOC for {pdf_path}.")

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
