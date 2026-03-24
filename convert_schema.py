from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, List, Union, get_args, get_origin

from pydantic import BaseModel

from src.schema_access_control import AccessControlSchema


ROOT_MODEL = AccessControlSchema
RULES_PATH = Path("src/schema_rules.json")
OUTPUT_JSON_PATH = Path("json/schema_access_control.json")
OUTPUT_TXT_PATH = Path("prompts/access_control/schema_access_control.txt")


def load_rules() -> dict[str, Any]:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Union and type(None) in args:
        non_none_args = [a for a in args if a is not type(None)]
        if len(non_none_args) == 1:
            return non_none_args[0], True

    return annotation, False


def is_list_type(annotation: Any) -> bool:
    return get_origin(annotation) in (list, List)


def get_list_item_type(annotation: Any) -> Any:
    args = get_args(annotation)
    return args[0] if args else Any


def is_enum_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, Enum)


def is_model_type(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def render_scalar(annotation: Any, optional: bool, field_name: str, fixed_values: dict[str, str]) -> str:
    if field_name in fixed_values:
        return fixed_values[field_name]

    if is_enum_type(annotation):
        values = " | ".join(enum_values(annotation))
        return f"{values} | null" if optional else values

    if annotation is str:
        return "string or null" if optional else "string"

    if annotation is bool:
        return "true | false | null" if optional else "true | false"

    if annotation is int:
        if field_name == "door_count":
            return "integer from 1 to 99"
        return "integer or null" if optional else "integer"

    if annotation is float:
        return "number or null" if optional else "number"

    return "unknown"


def render_field(annotation: Any, field_name: str, fixed_values: dict[str, str]) -> Any:
    annotation, optional = unwrap_optional(annotation)

    if field_name in fixed_values:
        return fixed_values[field_name]

    if is_list_type(annotation):
        item_type = get_list_item_type(annotation)
        item_type, _ = unwrap_optional(item_type)

        if is_enum_type(item_type):
            return [render_scalar(item_type, False, field_name, fixed_values)]
        if item_type is str:
            return ["string", "string"]
        if item_type is int:
            return ["integer"]
        if is_model_type(item_type):
            return [render_model(item_type, fixed_values)]
        return ["unknown"]

    if is_model_type(annotation):
        return render_model(annotation, fixed_values)

    return render_scalar(annotation, optional, field_name, fixed_values)


def render_model(model_cls: type[BaseModel], fixed_values: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for field_name, field_info in model_cls.model_fields.items():
        result[field_name] = render_field(field_info.annotation, field_name, fixed_values)

    return result


def format_enum_rule(field_name: str, enum_cls: type[Enum], optional: bool) -> list[str]:
    lines = [f"{field_name} must be one of:"]
    for value in enum_values(enum_cls):
        lines.append(f"- {value}")
    if optional:
        lines.append("- null")
    return lines


def auto_field_rules(model_cls: type[BaseModel], prefix: str = "") -> list[str]:
    lines: list[str] = []

    for field_name, field_info in model_cls.model_fields.items():
        annotation, optional = unwrap_optional(field_info.annotation)
        full_name = f"{prefix}{field_name}"

        if is_list_type(annotation):
            item_type = get_list_item_type(annotation)
            item_type, item_optional = unwrap_optional(item_type)

            if is_model_type(item_type):
                lines.extend(auto_field_rules(item_type, prefix=""))
            elif is_enum_type(item_type):
                # List enums are usually clearer as a manual rule:
                # "reader_types must contain only allowed enum values."
                pass
            continue

        if is_model_type(annotation):
            lines.extend(auto_field_rules(annotation, prefix=""))
            continue

        if is_enum_type(annotation):
            lines.extend(format_enum_rule(full_name, annotation, optional))
            lines.append("")

    return lines


def build_text_output() -> str:
    rules = load_rules()
    fixed_values = rules.get("fixed_values", {})
    structure = render_model(ROOT_MODEL, fixed_values)

    lines: list[str] = []
    lines.append("JSON Structure")
    lines.append("")
    lines.append("The JSON must match this structure exactly:")
    lines.append("")
    lines.append(json.dumps(structure, indent=2, ensure_ascii=False))
    lines.append("")
    lines.append("Field Rules")
    lines.append("")

    # Fixed-value rules
    for field_name, value in fixed_values.items():
        lines.append(f'{field_name} must always be "{value}".')
        lines.append("")

    # Global rules
    for rule in rules.get("global_rules", []):
        lines.append(rule)
        lines.append("")

    # Auto-generated enum rules
    lines.extend(auto_field_rules(ROOT_MODEL))

    # Manual field rules
    for field_name, field_rules in rules.get("field_rules", {}).items():
        for rule in field_rules:
            lines.append(rule)
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_outputs() -> None:
    json_schema = ROOT_MODEL.model_json_schema()

    OUTPUT_JSON_PATH.write_text(
        json.dumps(json_schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    OUTPUT_TXT_PATH.write_text(
        build_text_output(),
        encoding="utf-8",
    )


def main() -> None:
    write_outputs()
    print(f"Written: {OUTPUT_JSON_PATH}")
    print(f"Written: {OUTPUT_TXT_PATH}")


if __name__ == "__main__":
    main()