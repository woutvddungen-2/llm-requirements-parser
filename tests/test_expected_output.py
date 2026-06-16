"""Test extraction accuracy with optional few-shot prompting."""

from datetime import UTC, datetime
import json
from time import perf_counter, sleep
import pytest
from src.parser import extract_requirements_json
from src.few_shot import find_similar, build_context
from tests.helpers import (
    load_case_input,
    load_json,
    normalize_for_comparison,
    focused_diff,
    matches_expected_output,
    validate_output,
)
from tests.result_logging import log_result, log_failure, log_pending, get_run_id


RATE_LIMIT_RETRY_ATTEMPTS = 4
RATE_LIMIT_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
RATE_LIMIT_ERROR_MARKERS = (
    "rate limit",
    "rate-limited",
    "rate limited",
    "quota",
    "too many requests",
    "429",
    "503",
    "unavailable",
    "high demand",
    "resource exhausted",
    "server overloaded",
    "try again later",
)


class RateLimitRetriesExceeded(Exception):
    def __init__(self, last_error: Exception, attempts: int):
        super().__init__(str(last_error))
        self.last_error = last_error
        self.attempts = attempts


def _exception_chain_text(ex: Exception) -> str:
    parts = []
    seen_ids = set()
    current: Exception | None = ex

    while current is not None and id(current) not in seen_ids:
        seen_ids.add(id(current))
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__ or current.__context__

    return " | ".join(parts).lower()


def _is_rate_limited_error(ex: Exception) -> bool:
    text = _exception_chain_text(ex)
    return any(marker in text for marker in RATE_LIMIT_ERROR_MARKERS)


def _extract_requirements_with_retry(
    requirement_text: str,
    *,
    model: str,
    language: str,
    available_spaces,
    available_doors,
    rag_context,
):
    last_error: Exception | None = None

    for attempt in range(1, RATE_LIMIT_RETRY_ATTEMPTS + 1):
        try:
            return extract_requirements_json(
                requirement_text,
                model=model,
                language=language,
                available_spaces=available_spaces,
                available_doors=available_doors,
                rag_context=rag_context,
            ), attempt
        except Exception as ex:
            if not _is_rate_limited_error(ex):
                raise

            last_error = ex
            if attempt >= RATE_LIMIT_RETRY_ATTEMPTS:
                raise RateLimitRetriesExceeded(ex, attempt) from ex

            sleep(RATE_LIMIT_BACKOFF_SECONDS[attempt - 1])

    assert last_error is not None
    raise RateLimitRetriesExceeded(last_error, RATE_LIMIT_RETRY_ATTEMPTS)


def test_extraction_matches_expected(
    run_spec,
    request,
) -> None:
    """Test extraction accuracy with optional few-shot prompting.
    
    Parameters:
        run_spec: Single test run configuration from pytest collection
        request: Pytest request object used to lazily load few-shot fixtures
    
    Usage:
        pytest tests/test_expected_output.py --models openai:gpt-5.4 -v
        pytest tests/test_expected_output.py --models openai:gpt-5.4,anthropic:claude-sonnet-4-5 --use-few-shot both --count 3 -n auto -v
        pytest tests/test_expected_output.py --models openai:gpt-5.4 --pdf-strategy hybrid -k 051_real_test_1 -v
        pytest tests/test_expected_output.py --rerun tests/logs/<run_id>_pending.jsonl -n auto
    """
    case_dir = run_spec.case_dir
    model = run_spec.model
    use_few_shot = run_spec.use_few_shot
    pdf_strategy = run_spec.pdf_strategy

    total_started = perf_counter()
    llm_result = None
    expected_path = case_dir / "expected.json"
    run_id = get_run_id()

    try:
        case_input = load_case_input(
            case_dir,
            page_finder_strategy=pdf_strategy,
            page_finder_model=model if pdf_strategy == "llm" else None,
        )
    except Exception as ex:
        total_duration_ms = int((perf_counter() - total_started) * 1000)
        expected = load_json(expected_path)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "case": case_dir.name,
            "model": model,
            "use_few_shot": False,
            "source_mode": "page_finder",
            "passed": False,
            "input": "",
            "expected": expected,
            "actual": None,
            "raw_output": None,
            "diff": None,
            "pdf_strategy": pdf_strategy,
            "page_selection_method": None,
            "selected_pages": [],
            "source_pdf_path": "",
            "total_duration_ms": total_duration_ms,
            "error": f"Page extraction error: {str(ex)}",
        }
        log_result(entry)

        rag_str = " (with few-shot)" if False else ""
        pytest.fail(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}{rag_str}"
            f"\nCASE: {case_dir.name}"
            f"\nPAGE_EXTRACTION_ERROR: {ex}",
            pytrace=False,
        )

    requirement_text = case_input["requirement_text"]
    expected = load_json(expected_path)
    
    # Build few-shot context if requested
    few_shot_context_str = None
    similar_cases = []
    few_shot_setup_ms = 0
    if use_few_shot:
        setup_started = perf_counter()
        few_shot_examples = request.getfixturevalue("few_shot_examples")
        few_shot_embeddings = request.getfixturevalue("few_shot_embeddings")

        if few_shot_examples:
            similar_cases = find_similar(
                requirement_text,
                few_shot_examples,
                few_shot_embeddings or {},
                k=4
            )
            few_shot_context_str = build_context(similar_cases, few_shot_examples)

        few_shot_setup_ms = int((perf_counter() - setup_started) * 1000)

    llm_attempts = 1
    try:
        llm_result, llm_attempts = _extract_requirements_with_retry(
            requirement_text,
            model=model,
            language=case_input.get("language", "Dutch"),
            available_spaces=case_input.get("available_spaces"),
            available_doors=case_input.get("available_doors"),
            rag_context=few_shot_context_str,
        )
    except RateLimitRetriesExceeded as ex:
        total_duration_ms = int((perf_counter() - total_started) * 1000)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "case": case_dir.name,
            "model": model,
            "use_few_shot": use_few_shot,
            "source_mode": case_input.get("input_source_mode"),
            "pdf_strategy": pdf_strategy,
            "attempts": ex.attempts,
            "max_attempts": RATE_LIMIT_RETRY_ATTEMPTS,
            "reason": "rate_limited",
            "error": str(ex.last_error),
            "input": requirement_text,
            "expected": expected,
            "selected_pages": case_input.get("selected_pages"),
            "page_selection_method": case_input.get("page_selection_method"),
            "page_finder_strategy": case_input.get("page_finder_strategy"),
            "source_pdf_path": case_input.get("source_pdf_path"),
            "total_duration_ms": total_duration_ms,
        }
        log_pending(entry)

        rag_str = " (with few-shot)" if use_few_shot else ""
        pytest.skip(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}{rag_str}"
            f"\nCASE: {case_dir.name}"
            f"\nRATE_LIMIT: retried {ex.attempts} times, moved to pending",
        )
    except RuntimeError as ex:
        if "billing error" in str(ex).lower() or "insufficient credits" in str(ex).lower():
            total_duration_ms = int((perf_counter() - total_started) * 1000)
            entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "run_id": run_id,
                "case": case_dir.name,
                "model": model,
                "use_few_shot": use_few_shot,
                "source_mode": case_input.get("input_source_mode"),
                "pdf_strategy": pdf_strategy,
                "reason": "billing_error",
                "error": str(ex),
                "input": requirement_text,
                "expected": expected,
                "selected_pages": case_input.get("selected_pages"),
                "page_selection_method": case_input.get("page_selection_method"),
                "page_finder_strategy": case_input.get("page_finder_strategy"),
                "source_pdf_path": case_input.get("source_pdf_path"),
                "total_duration_ms": total_duration_ms,
            }
            log_pending(entry)

            rag_str = " (with few-shot)" if use_few_shot else ""
            pytest.skip(
                f"\nRUN_ID: {run_id}"
                f"\nMODEL: {model}{rag_str}"
                f"\nCASE: {case_dir.name}"
                f"\nBILLING ERROR: insufficient credits - skipped",
            )
        raise
    except Exception as ex:
        total_duration_ms = int((perf_counter() - total_started) * 1000)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "case": case_dir.name,
            "model": model,
            "use_few_shot": use_few_shot,
            "source_mode": case_input.get("input_source_mode"),
            "passed": False,
            "input": requirement_text,
            "expected": expected,
            "actual": None,
            "raw_output": getattr(llm_result, "text", None),
            "diff": None,
            "similar_cases": [name for name, score in similar_cases],
            "llm_attempts": llm_attempts,
            "started_at": getattr(llm_result, "started_at", None),
            "completed_at": getattr(llm_result, "completed_at", None),
            "duration_ms": getattr(llm_result, "duration_ms", None),
            "pdf_extraction_ms": case_input.get("pdf_extraction_ms", 0),
            "few_shot_setup_ms": few_shot_setup_ms,
            "total_duration_ms": total_duration_ms,
            "input_tokens": getattr(llm_result, "input_tokens", None),
            "output_tokens": getattr(llm_result, "output_tokens", None),
            "selected_pages": case_input.get("selected_pages"),
            "page_selection_method": case_input.get("page_selection_method"),
            "page_finder_strategy": case_input.get("page_finder_strategy"),
            "source_pdf_path": case_input.get("source_pdf_path"),
            "error": str(ex),
        }
        log_result(entry)

        rag_str = " (with few-shot)" if use_few_shot else ""
        pytest.fail(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}{rag_str}"
            f"\nCASE: {case_dir.name}"
            f"\nEXTRACTION ERROR: {ex}",
            pytrace=False,
        )

    # Validate JSON
    try:
        validated = validate_output(llm_result.text)
    except Exception as ex:
        total_duration_ms = int((perf_counter() - total_started) * 1000)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": run_id,
            "case": case_dir.name,
            "model": model,
            "use_few_shot": use_few_shot,
            "source_mode": case_input.get("input_source_mode"),
            "passed": False,
            "input": requirement_text,
            "expected": expected,
            "actual": None,
            "raw_output": llm_result.text,
            "diff": None,
            "similar_cases": [name for name, score in similar_cases],
            "llm_attempts": llm_attempts,
            "started_at": llm_result.started_at,
            "completed_at": llm_result.completed_at,
            "duration_ms": llm_result.duration_ms,
            "pdf_extraction_ms": case_input.get("pdf_extraction_ms", 0),
            "few_shot_setup_ms": few_shot_setup_ms,
            "total_duration_ms": total_duration_ms,
            "input_tokens": llm_result.input_tokens,
            "output_tokens": llm_result.output_tokens,
            "selected_pages": case_input.get("selected_pages"),
            "page_selection_method": case_input.get("page_selection_method"),
            "page_finder_strategy": case_input.get("page_finder_strategy"),
            "source_pdf_path": case_input.get("source_pdf_path"),
            "error": str(ex),
        }
        log_result(entry)
        log_failure(entry)
        
        rag_str = " (with few-shot)" if use_few_shot else ""
        pytest.fail(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}{rag_str}"
            f"\nCASE: {case_dir.name}"
            f"\nVALIDATION ERROR: {ex}"
            f"\n\nRAW OUTPUT:\n{llm_result.text}",
            pytrace=False,
        )

    actual = validated.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=False)

    actual_normalized = normalize_for_comparison(actual)
    expected_normalized = normalize_for_comparison(expected)

    actual_pretty = json.dumps(actual_normalized, indent=2, ensure_ascii=False, sort_keys=True)
    expected_pretty = json.dumps(expected_normalized, indent=2, ensure_ascii=False, sort_keys=True)

    diff = focused_diff(expected_pretty, actual_pretty, context=2)
    passed = matches_expected_output(actual, expected)
    total_duration_ms = int((perf_counter() - total_started) * 1000)

    # Log result
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "case": case_dir.name,
        "model": model,
        "use_few_shot": use_few_shot,
        "source_mode": case_input.get("input_source_mode"),
        "passed": passed,
        "input": requirement_text,
        "expected": expected,
        "actual": actual,
        "raw_output": llm_result.text,
        "diff": diff,
        "similar_cases": [name for name, score in similar_cases],
        "llm_attempts": llm_attempts,
        "started_at": llm_result.started_at,
        "completed_at": llm_result.completed_at,
        "duration_ms": llm_result.duration_ms,
        "pdf_extraction_ms": case_input.get("pdf_extraction_ms", 0),
        "few_shot_setup_ms": few_shot_setup_ms,
        "total_duration_ms": total_duration_ms,
        "input_tokens": llm_result.input_tokens,
        "output_tokens": llm_result.output_tokens,
        "selected_pages": case_input.get("selected_pages"),
        "page_selection_method": case_input.get("page_selection_method"),
        "page_finder_strategy": case_input.get("page_finder_strategy"),
        "source_pdf_path": case_input.get("source_pdf_path"),
    }
    log_result(entry)

    if not passed:
        log_failure(entry)
        
        rag_str = " (with few-shot)" if use_few_shot else ""
        pytest.fail(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}{rag_str}"
            f"\nCASE: {case_dir.name}"
            f"\nDURATION_MS: pdf_extraction={case_input.get('pdf_extraction_ms', 0)}, llm={llm_result.duration_ms}, few_shot_setup={few_shot_setup_ms}, total={total_duration_ms}"
            f"\nTOKENS: in={llm_result.input_tokens}, out={llm_result.output_tokens}"
            f"\n\nDIFF:\n{diff}",
            pytrace=False,
        )
