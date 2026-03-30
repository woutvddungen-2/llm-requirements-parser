from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, List, Union, get_args, get_origin, Literal

from pydantic import BaseModel

from src.schema_access_control import AccessControlSchema, DoorRule, ControllerRule


ROOT_MODEL = AccessControlSchema
OUTPUT_JSON_PATH = Path("json/schema_access_control.json")
OUTPUT_TXT_PATH = Path("prompts/access_control/schema_access_control.txt")


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


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_cls]


def format_union(values: list[str]) -> str:
    return " | ".join(values)


def render_single(annotation: Any, field_name: str) -> str:
    origin = get_origin(annotation)

    if origin is Literal:
        values = [repr(v) if isinstance(v, str) else str(v) for v in get_args(annotation)]
        return f"Single[{format_union(values)}]"

    if is_enum_type(annotation):
        values = enum_values(annotation)
        return f"Single[{format_union(values)}]"

    if annotation is str:
        return "Single[string]"

    if annotation is bool:
        return "Single[true | false]"

    if annotation is int:
        if field_name == "door_count":
            return "Single[integer 1..99]"
        return "Single[integer]"

    return "Single[unknown]"


def render_type(annotation: Any, field_name: str) -> str:
    annotation, _optional = unwrap_optional(annotation)

    if is_list_type(annotation):
        item_type = get_list_item_type(annotation)
        item_type, _item_optional = unwrap_optional(item_type)

        if get_origin(item_type) is Literal:
            values = [repr(v) if isinstance(v, str) else str(v) for v in get_args(item_type)]
            return f"List[{format_union(values)}]"

        if is_enum_type(item_type):
            return f"List[{format_union(enum_values(item_type))}]"

        if item_type is str:
            return "List[string]"
        if item_type is int:
            return "List[integer]"
        if item_type is bool:
            return "List[true | false]"
        return "List[unknown]"

    return render_single(annotation, field_name)


def render_model_block(title: str, model_cls: type[BaseModel]) -> list[str]:
    lines = [f"{title}:"]
    for field_name, field_info in model_cls.model_fields.items():
        lines.append(f"- {field_name}: {render_type(field_info.annotation, field_name)}")
    lines.append("")
    return lines


def build_text_output() -> str:
    lines: list[str] = []

    lines.append("Schema")
    lines.append("")
    lines.append("Root:")
    lines.append('- system_type: Single["ACCESS_CONTROL"]')
    lines.append('- version: Single["1.0"]')
    lines.append("- requirements:")
    lines.append("  - door_rules: List[DoorRule]")
    lines.append("  - controller_rules: List[ControllerRule]")
    lines.append("")

    lines.extend(render_model_block("DoorRule", DoorRule))
    lines.extend(render_model_block("ControllerRule", ControllerRule))

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