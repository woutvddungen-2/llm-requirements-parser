from tests.helpers import normalize_for_comparison
from tests.helpers import load_case_input


def test_load_case_input_text_mode(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        '{"requirement_text": "Demo text", "available_spaces": ["A"], "available_doors": []}',
        encoding="utf-8",
    )

    loaded = load_case_input(case_dir)

    assert loaded["requirement_text"] == "Demo text"
    assert loaded["input_source_mode"] == "text"


def test_load_case_input_prefers_requirement_text_when_present(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "input.json").write_text(
        '{"requirement_text": "Demo text", "pdf_path": "demo.pdf", "available_spaces": ["A"], "available_doors": []}',
        encoding="utf-8",
    )

    loaded = load_case_input(case_dir)

    assert loaded["requirement_text"] == "Demo text"
    assert loaded["input_source_mode"] == "text"


def test_normalize_for_comparison_merges_duplicate_door_rules():
    data = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["Fietsenstalling"],
                    "door_id": "door_01",
                    "reader_types": ["CARD"],
                },
                {
                    "areas": ["Fietsenstalling"],
                    "door_id": "door_01",
                    "lock_type": "OTHER",
                    "door_sensor": True,
                },
            ],
            "controller_rules": [],
        }
    }

    normalized = normalize_for_comparison(data)
    door_rules = normalized["requirements"]["door_rules"]

    assert len(door_rules) == 1
    assert door_rules[0]["areas"] == ["FIETSENSTALLING"]
    assert door_rules[0]["door_id"] == "DOOR_01"
    assert door_rules[0]["reader_types"] == ["CARD"]
    assert door_rules[0]["lock_type"] == "OTHER"
    assert door_rules[0]["door_sensor"] is True


def test_normalize_for_comparison_does_not_merge_different_doors():
    data = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["Fietsenstalling"],
                    "door_id": "door_01",
                    "reader_types": ["CARD"],
                },
                {
                    "areas": ["Fietsenstalling"],
                    "door_id": "door_02",
                    "reader_types": ["INTERCOM"],
                },
            ],
            "controller_rules": [],
        }
    }

    normalized = normalize_for_comparison(data)
    door_rules = normalized["requirements"]["door_rules"]

    assert len(door_rules) == 2
    assert [rule["door_id"] for rule in door_rules] == ["DOOR_01", "DOOR_02"]
