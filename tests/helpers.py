import json
import difflib
from pathlib import Path
from typing import Any

from src.schema_access_control import AccessControlSchema


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_output(raw_text: str) -> AccessControlSchema:
    return AccessControlSchema.model_validate_json(raw_text)


def normalize_for_comparison(data: Any) -> Any:
    """
    Normalize output so semantically identical JSON compares equal.
    - removes description fields
    - sorts dict keys recursively
    - sorts string lists
    - sorts rule lists by areas
    """
    if isinstance(data, dict):
        return {
            key: normalize_for_comparison(value)
            for key, value in sorted(data.items())
            if key != "description"
        }

    if isinstance(data, list):
        normalized_list = [normalize_for_comparison(item) for item in data]

        # sort simple string lists
        if all(isinstance(x, str) for x in normalized_list):
            return sorted(normalized_list)

        # sort rule lists by areas
        if all(isinstance(x, dict) for x in normalized_list):
            return sorted(
                normalized_list,
                key=lambda x: "|".join(sorted(x.get("areas", [])))
            )
        return normalized_list
    
    # normalize strings to uppercase
    if isinstance(data, str):
        return data.upper()
    return data


def focused_diff(expected_text: str, actual_text: str, context: int = 2) -> str:
    """
    Return a compact unified diff showing only changed lines
    with a few context lines around them.
    """
    diff_lines = list(
        difflib.unified_diff(
            expected_text.splitlines(),
            actual_text.splitlines(),
            fromfile="expected.json",
            tofile="actual.json",
            lineterm="",
            n=context,
        )
    )

    if not diff_lines:
        return "No differences."

    return "\n".join(diff_lines)