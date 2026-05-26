from __future__ import annotations


class PromptBuilder:
    def __init__(
        self,
        language: str = "Dutch",
        available_spaces: list[str] | None = None,
        available_doors: list[dict] | None = None,
    ):
        self.language = language
        self.available_spaces = available_spaces
        self.available_doors = available_doors

    def _normalize_space_label(self, value: str | None, is_external: bool) -> str:
        if value is None:
            return "OUTSIDE" if is_external else "UNKNOWN_SPACE"

        text = str(value).strip()
        if not text:
            return "OUTSIDE" if is_external else "UNKNOWN_SPACE"

        if text.upper() in {"UNKNOWN", "UNKNOWN_SPACE"}:
            return "OUTSIDE" if is_external else "UNKNOWN_SPACE"

        return text

    def _build_spaces_context(self) -> str:
        if not self.available_spaces:
            return ""

        spaces_list = "\n".join(f"- {space}" for space in self.available_spaces)
        return (
            "\n\nAvailable spaces in this floorplan:\n"
            f"{spaces_list}"
            "\n\nUse ONLY these space names when specifying areas, if an available space name matches the text. If no available space name matches, the list may be incomplete — still emit the rule using the text names. Never suppress a rule just because no matching space was found.\n\n"
        )

    def _build_doors_context(self) -> str:
        if not self.available_doors:
            return ""

        door_lines = []
        for door in self.available_doors:
            door_id = door.get("door_id") or door.get("name") or "UNKNOWN_DOOR"
            is_external = bool(door.get("is_external", False))
            space_a = self._normalize_space_label(door.get("space_a"), is_external)
            space_b = self._normalize_space_label(door.get("space_b"), is_external)
            door_lines.append(
                f"- {door_id}: {space_a} <-> {space_b}, external={'true' if is_external else 'false'}"
            )

        doors_list = "\n".join(door_lines)
        return (
            "\n\nAvailable doors in this floorplan:\n"
            f"{doors_list}"
            f"{self._build_derived_door_hints()}"
            "\n\nUse ONLY these door IDs when specifying door_id."
            "\nEach rule targets exactly one door — use door_id (singular string), not an array."
            "\nFor external doors (is_external=true): ALWAYS set connects_to_areas=[\"OUTSIDE\"] when door_id is set."
            "\nFor internal doors (is_external=false): NEVER set connects_to_areas when door_id is set."
            "\nFor 'door from X to Y' / 'deur van X naar Y' without door_id: X is unsafe/source and goes in connects_to_areas; Y is safe/protected and goes in areas."
            "\nWhen text names two spaces, choose a door from this list that actually connects those spaces."
            "\nIf one named space is generic or ambiguous (for example 'hal'), use the other named space to disambiguate from the door list."
            "\nDo not choose a similarly named space if no listed door connects it to the other named space."
            "\nIf no door in this list connects the named spaces, the list may be incomplete — still emit the rule using areas and connects_to_areas without door_id. Never suppress a rule just because no matching door was found."
            "\nOnly use placement side hint fields (exit_device_side_hint, emergency_button_side_hint) when the text explicitly states the side. Never infer or default these."
            "\nWhen a rule targets a specific door (using door_id), set areas to the space name(s) from the requirement text — not both sides from the door map.\n\n"
        )

    def _build_derived_door_hints(self) -> str:
        if not self.available_doors:
            return ""

        exterior_access = []
        residential_unit_doors = []
        shared_internal_doors = []
        for door in self.available_doors:
            door_id = door.get("door_id") or door.get("name") or "UNKNOWN_DOOR"
            is_external = bool(door.get("is_external", False))
            space_a = self._normalize_space_label(door.get("space_a"), is_external)
            space_b = self._normalize_space_label(door.get("space_b"), is_external)

            if is_external:
                protected = space_b if space_a == "OUTSIDE" else space_a
                exterior_access.append(f"{door_id} -> {protected}")
                continue

            lower_a = space_a.lower()
            lower_b = space_b.lower()
            if any(term in lower_a or term in lower_b for term in ("studio", "woning", "appartement", "unit")):
                residential_unit_doors.append(f"{door_id}: {space_a} <-> {space_b}")
            elif any(term in lower_a or term in lower_b for term in ("gemeenschappelijk", "algemeen", "hal", "entree", "corridor", "gang", "lobby")):
                shared_internal_doors.append(f"{door_id}: {space_a} <-> {space_b}")

        if not exterior_access and not residential_unit_doors and not shared_internal_doors:
            return ""

        hints = (
            "\n\nDerived targeting hints from this floorplan:\n"
        )
        if exterior_access:
            hints += (
                f"- Exterior access doors from OUTSIDE: {'; '.join(exterior_access)}\n"
                "- When the text says personentoegang, toegangsdeur, toegangsdeuren, personeelsingang, bezoekerstoegang, or entree without naming a different interior boundary, prefer one of these exterior access doors.\n"
            )
        if shared_internal_doors:
            hints += f"- Shared internal circulation doors: {'; '.join(shared_internal_doors)}\n"
        if residential_unit_doors:
            hints += (
                f"- Individual unit doors: {'; '.join(residential_unit_doors)}\n"
                "- CRITICAL: If the text says individual units open with mechanical keys (sleutels, cilinder) or ordinary locks, DO NOT create access-control rules for these unit doors.\n"
                "- This system ONLY extracts electronic access-control systems (card readers, intercom, badge readers, electric locks, etc.). Mechanical keys are not electronic access control.\n"
                "- If the specification has a main/shared entrance with electronic access (e.g., intercom for visitors, card for residents) AND individual unit doors with keys, extract ONLY the main entrance rule.\n"
            )
        return hints

    def build(self, requirement_text: str) -> str:
        spaces_context = self._build_spaces_context()
        doors_context = self._build_doors_context()
        return (
            f"Convert the following {self.language} access control requirement text into JSON."
            f"{spaces_context}{doors_context}Requirement text:\n{requirement_text}\n"
        )
