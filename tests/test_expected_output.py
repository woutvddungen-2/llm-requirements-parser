from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from src.parser import extract_requirements_json
from tests.helpers import (
    load_text,
    load_json,
    normalize_for_comparison,
    focused_diff,
    validate_output,
)
from tests.result_logging import log_result, log_failure, get_run_id


CASES_DIR = Path("tests/cases")


def discover_cases() -> list[Path]:
    tests = sorted([p for p in CASES_DIR.iterdir() if p.is_dir()])
    return [p for p in tests if (p / "input.txt").exists() and (p / "expected.json").exists() and not p.name.startswith("ignore_")]


@pytest.mark.parametrize("case_dir", discover_cases(), ids=lambda p: p.name)
def test_extraction_matches_expected(case_dir: Path, model: str) -> None:
    input_path = case_dir / "input.txt"
    expected_path = case_dir / "expected.json"

    requirement_text = load_text(input_path)
    expected = load_json(expected_path)

    llm_result = extract_requirements_json(requirement_text, model=model)
    validated = validate_output(llm_result.text)

    actual = validated.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=False)

    actual_normalized = normalize_for_comparison(actual)
    expected_normalized = normalize_for_comparison(expected)

    actual_pretty = json.dumps(actual_normalized, indent=2, ensure_ascii=False, sort_keys=True)
    expected_pretty = json.dumps(expected_normalized, indent=2, ensure_ascii=False, sort_keys=True)

    diff = focused_diff(expected_pretty, actual_pretty, context=2)
    passed = actual_normalized == expected_normalized
    run_id = get_run_id()

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "case": case_dir.name,
        "model": model,
        "passed": passed,
        "input": requirement_text,
        "expected": expected,
        "actual": actual,
        "raw_output": llm_result.text,
        "diff": None if passed else diff,
        "started_at": llm_result.started_at,
        "completed_at": llm_result.completed_at,
        "duration_ms": llm_result.duration_ms,
        "input_tokens": llm_result.input_tokens,
        "output_tokens": llm_result.output_tokens,
    }

    log_result(entry)

    if not passed:
        log_failure(entry)
        pytest.fail(
            f"\nRUN_ID: {run_id}"
            f"\nMODEL: {model}"
            f"\nCASE: {case_dir.name}"
            f"\nDURATION_MS: {llm_result.duration_ms}"
            f"\nTOKENS: in={llm_result.input_tokens}, out={llm_result.output_tokens}"
            f"\n\nDIFF:\n{diff}",
            pytrace=False,
        )