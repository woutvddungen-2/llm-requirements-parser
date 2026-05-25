import json
import difflib
from pathlib import Path
import re
from typing import Any


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


def validate_output(raw_text: str) -> "AccessControlSchema":
    from src.schema_access_control import AccessControlSchema

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
            normalized_list = _merge_duplicate_door_rules(normalized_list)
            return sorted(
                normalized_list,
                key=lambda x: (
                    "|".join(sorted(x.get("areas", []))),
                    str(x.get("door_id", "")),
                )
            )
        return normalized_list
    
    # normalize strings to uppercase
    if isinstance(data, str):
        return data.upper()
    return data


def _merge_duplicate_door_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Merge duplicate door rules only when both the target areas and door_id match.

    This keeps comparison strict for semantic differences while allowing the
    benchmark to treat additive rule fragments for the same physical door as one.
    """
    merged: list[dict[str, Any]] = []
    index: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}

    for rule in rules:
        areas = rule.get("areas")
        door_id = rule.get("door_id")

        if not isinstance(areas, list) or not door_id or not all(isinstance(a, str) for a in areas):
            merged.append(rule)
            continue

        key = (tuple(sorted(areas)), str(door_id))
        existing = index.get(key)
        if existing is None:
            index[key] = rule
            merged.append(rule)
            continue

        if _can_merge_rules(existing, rule):
            index[key] = _merge_rule_dicts(existing, rule)
            merged[indexed_position(merged, existing)] = index[key]
        else:
            merged.append(rule)

    return merged


def _can_merge_rules(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Return True when two rules can be merged without losing information."""
    for key in set(left) | set(right):
        if key in {"areas", "door_id"}:
            continue

        if key not in left or key not in right:
            continue

        left_value = left[key]
        right_value = right[key]

        if left_value == right_value:
            continue

        if isinstance(left_value, list) and isinstance(right_value, list):
            continue

        return False

    return True


def _merge_rule_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merge two additive door rules with the same areas and door_id."""
    merged: dict[str, Any] = dict(left)
    for key, value in right.items():
        if key in {"areas", "door_id"}:
            continue

        if key not in merged:
            merged[key] = value
            continue

        if merged[key] == value:
            continue

        if isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = _merge_list_values(merged[key], value)
            continue

        # Conflicts are intentionally not merged; the caller should have checked.
        merged[key] = merged[key]

    return merged


def _merge_list_values(left: list[Any], right: list[Any]) -> list[Any]:
    """Union two lists while preserving stable order."""
    merged: list[Any] = []
    seen: set[Any] = set()
    for item in left + right:
        marker = _freeze_for_set(item)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(item)
    return merged


def _freeze_for_set(value: Any) -> Any:
    """Convert nested values into a hashable marker for de-duplication."""
    if isinstance(value, list):
        return tuple(_freeze_for_set(item) for item in value)
    if isinstance(value, dict):
        return tuple((key, _freeze_for_set(val)) for key, val in sorted(value.items()))
    return value


def indexed_position(items: list[dict[str, Any]], target: dict[str, Any]) -> int:
    """Return the first index of target by object identity."""
    for idx, item in enumerate(items):
        if item is target:
            return idx
    raise ValueError("Target rule not found in merged list.")


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
