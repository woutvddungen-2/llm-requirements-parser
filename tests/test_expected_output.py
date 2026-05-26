"""Test extraction accuracy with optional few-shot prompting."""

from datetime import UTC, datetime
import json
from pathlib import Path
from time import perf_counter
import pytest
from src.parser import extract_requirements_json
from src.few_shot import find_similar, build_context
from tests.helpers import (
    load_case_input,
    load_json,
    normalize_for_comparison,
    focused_diff,
    validate_output,
)
from tests.result_logging import log_result, log_failure, get_run_id

CASES_DIR = Path("tests/cases")


def discover_cases() -> list[Path]:
    """Discover all test cases."""
    tests = sorted([p for p in CASES_DIR.iterdir() if p.is_dir()])
    return [
        p for p in tests
        if (p / "input.json").exists()
        and (p / "expected.json").exists()
        and not p.name.startswith("ignore_")
    ]


@pytest.mark.parametrize("case_dir", discover_cases(), ids=lambda p: p.name)
def test_extraction_matches_expected(
    case_dir: Path,
    model: str,
    use_few_shot,
    pdf_strategy: str,
    request,
) -> None:
    """Test extraction accuracy with optional few-shot prompting.
    
    Parameters:
        case_dir: Test case directory
        model: LLM model to use (vendor:model_name)
        use_few_shot: Whether to include dynamic few-shot examples
        pdf_strategy: Explicit PDF selection strategy for PDF-backed cases
        request: Pytest request object used to lazily load few-shot fixtures
    
    Usage:
        pytest tests/test_expected_output.py --models openai:gpt-5.4 -v
        pytest tests/test_expected_output.py --models openai:gpt-5.4,anthropic:claude-sonnet-4-5 --use-few-shot both --count 3 -n auto -v
        pytest tests/test_expected_output.py --models openai:gpt-5.4 --pdf-strategy keyword -k 051_real_test_1 -v
    """
    total_started = perf_counter()
    expected_path = case_dir / "expected.json"
    case_input = load_case_input(
        case_dir,
        page_finder_strategy=pdf_strategy,
        page_finder_model=model if pdf_strategy == "llm" else None,
    )
    requirement_text = case_input["requirement_text"]
    expected = load_json(expected_path)
    run_id = get_run_id()
    
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

    # Run extraction
    llm_result = extract_requirements_json(
        requirement_text,
        model=model,
        language=case_input.get("language", "Dutch"),
        available_spaces=case_input.get("available_spaces"),
        available_doors=case_input.get("available_doors"),
        rag_context=few_shot_context_str,
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
    passed = actual_normalized == expected_normalized
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
