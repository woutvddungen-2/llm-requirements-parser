import json
from pathlib import Path

import pytest

from src.parser import extract_requirements_json
from tests.helpers import load_text, load_json, normalize_for_comparison, focused_diff, validate_output

CASES_DIR = Path("tests/cases")

def discover_cases() -> list[Path]:
    return sorted([p for p in CASES_DIR.iterdir() if p.is_dir()])

@pytest.mark.parametrize("case_dir", discover_cases(), ids=lambda p: p.name)
def test_extraction_matches_expected(case_dir: Path) -> None:
    input_path = case_dir / "input.txt"
    expected_path = case_dir / "expected.json"

    requirement_text = load_text(input_path)
    expected = load_json(expected_path)

    raw_output = extract_requirements_json(requirement_text)
    validated = validate_output(raw_output)

    actual = json.loads(validated.model_dump_json())

    actual_normalized = normalize_for_comparison(actual)
    expected_normalized = normalize_for_comparison(expected)

    actual_pretty = json.dumps(actual_normalized, indent=2, ensure_ascii=False, sort_keys=True)
    expected_pretty = json.dumps(expected_normalized, indent=2, ensure_ascii=False, sort_keys=True)

    diff = focused_diff(expected_pretty, actual_pretty, context=2)

    if actual_normalized != expected_normalized:
        pytest.fail(
            f"\nCASE: {case_dir.name}"
            f"\n\nDIFF:\n{diff}",
            pytrace=False,
        )