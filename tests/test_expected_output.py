from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from src.parser import extract_requirements_json
from tests.helpers import load_text, load_json, normalize_for_comparison, focused_diff, validate_output

CASES_DIR = Path("tests/cases")
LOG_DIR = Path("tests/logs")
LOG_FILE = LOG_DIR / "extraction_failures.jsonl"

def discover_cases() -> list[Path]:
    tests = sorted([p for p in CASES_DIR.iterdir() if p.is_dir()])
    return [p for p in tests if (p / "input.txt").exists() and (p / "expected.json").exists() and not p.name.startswith("ignore_")]

def log_failure(case_name: str, model: str, requirement_text: str, expected: dict, actual: dict, diff: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "case": case_name,
        "model": model,
        "input": requirement_text,
        "expected": expected,
        "actual": actual,
        "diff": diff,
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

@pytest.mark.parametrize("case_dir", discover_cases(), ids=lambda p: p.name)
def test_extraction_matches_expected(case_dir: Path, model: str) -> None:
    input_path = case_dir / "input.txt"
    expected_path = case_dir / "expected.json"

    requirement_text = load_text(input_path)
    expected = load_json(expected_path)

    raw_output = extract_requirements_json(requirement_text, model=model)
    validated = validate_output(raw_output)

    actual = validated.model_dump(exclude_none=True, exclude_unset=True, exclude_defaults=False)

    actual_normalized = normalize_for_comparison(actual)
    expected_normalized = normalize_for_comparison(expected)

    actual_pretty = json.dumps(actual_normalized, indent=2, ensure_ascii=False, sort_keys=True)
    expected_pretty = json.dumps(expected_normalized, indent=2, ensure_ascii=False, sort_keys=True)

    diff = focused_diff(expected_pretty, actual_pretty, context=2)

    if actual_normalized != expected_normalized:
        log_failure(
            case_name=case_dir.name,
            model=model,
            requirement_text=requirement_text,
            expected=expected,
            actual=actual,
            diff=diff,
        )
        pytest.fail(
            f"\nCASE: {case_dir.name}"
            f"\n\nDIFF:\n{diff}",
            pytrace=False,
        )