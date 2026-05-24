import json
import difflib
from pathlib import Path
import re
from typing import Any

from src.schema_access_control import AccessControlSchema


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_case_input(case_dir: Path) -> dict[str, Any]:
    """
    Load benchmark input in the same shape as the main API usage.

    Preferred format:
      input.json -> {"requirement_text": "...", "available_spaces": [...], "available_doors": [...]}

    Legacy fallback:
      input.txt -> plain requirement text
    """
    input_json = case_dir / "input.json"
    input_txt = case_dir / "input.txt"

    if input_json.exists():
        payload = load_json(input_json)
        if not isinstance(payload, dict):
            raise ValueError(f"{input_json} must contain a JSON object.")
        if "requirement_text" not in payload:
            raise ValueError(f"{input_json} must include 'requirement_text'.")
        return {
            "requirement_text": str(payload["requirement_text"]).strip(),
            "language": payload.get("language", "Dutch"),
            "available_spaces": payload.get("available_spaces"),
            "available_doors": payload.get("available_doors"),
        }

    if input_txt.exists():
        return {
            "requirement_text": load_text(input_txt),
            "language": "Dutch",
            "available_spaces": None,
            "available_doors": None,
        }

    raise FileNotFoundError(f"No input.json or input.txt found in {case_dir}")


def validate_output(raw_text: str) -> AccessControlSchema:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*`+$", "", raw_text.strip())
    return AccessControlSchema.model_validate_json(cleaned)


def normalize_for_comparison(data: Any) -> Any:
    """
    Normalize output so semantically identical JSON compares equal.
    - removes description fields
    - sorts dict keys recursively
    - sorts string lists
    - sorts rule lists by areas
    """
    if isinstance(data, dict):
        filtered = {k: v for k, v in data.items() if k != "description"}
        # connects_to_areas is redundant when door_id is set — strip it before comparing
        if "door_id" in filtered:
            filtered.pop("connects_to_areas", None)
        return {
            key: normalize_for_comparison(value)
            for key, value in sorted(filtered.items())
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
