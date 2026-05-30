import json

from tests.helpers import focused_diff
from tests.helpers import load_case_input
from tests.helpers import matches_expected_output
from tests.helpers import normalize_for_comparison


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


def test_matches_expected_output_supports_any_of_for_areas():
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["HAL"],
                    "door_id": "DOOR_09",
                    "reader_types": ["CARD"],
                }
            ],
            "controller_rules": [],
        }
    }
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": {"any_of": [["SERVERRUIMTE"], ["HAL"]]},
                    "door_id": "DOOR_09",
                    "reader_types": ["CARD"],
                }
            ],
            "controller_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_matches_expected_output_supports_any_of_for_reader_types():
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "reader_types": ["CARD", "WIRELESS_KEYFOB"],
                }
            ],
            "controller_rules": [],
        }
    }
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "reader_types": {"any_of": [["CARD"], ["CARD", "WIRELESS_KEYFOB"]]},
                }
            ],
            "controller_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_matches_expected_output_supports_any_of_with_null():
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "lock_type": None,
                }
            ],
            "controller_rules": [],
        }
    }
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "lock_type": {"any_of": ["OTHER", None]},
                }
            ],
            "controller_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_matches_expected_output_supports_all_of_for_lists():
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "reader_types": ["CARD", "WIRELESS_KEYFOB", "NFC"],
                }
            ],
            "controller_rules": [],
        }
    }
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["SERVERRUIMTE"],
                    "door_id": "DOOR_09",
                    "reader_types": {"all_of": ["CARD", "WIRELESS_KEYFOB"]},
                }
            ],
            "controller_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_matches_expected_output_ignores_door_rule_order_with_any_of():
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["KANTINE"],
                    "door_id": "DOOR_05",
                    "reader_types": ["CARD"],
                },
                {
                    "areas": ["HAL"],
                    "door_id": "DOOR_04",
                    "reader_types": ["CARD"],
                },
            ],
            "controller_rules": [],
        }
    }
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": {"any_of": [["HAL"], ["ENTREE"]]},
                    "door_id": "DOOR_04",
                    "reader_types": ["CARD"],
                },
                {
                    "areas": {"any_of": [["KANTINE"], ["HAL"]]},
                    "door_id": "DOOR_05",
                    "reader_types": ["CARD"],
                },
            ],
            "controller_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_matches_expected_output_treats_missing_field_as_empty_or_null_when_allowed():
    actual = {
        "requirements": {
            "controller_rules": [
                {
                    "manages_door_areas": ["Entreehal", "Parkeergarage"],
                    "connection_type": "BUS",
                    "description": "De toegangscontrolecentrales worden middels een databus met elkaar doorverbonden",
                }
            ],
            "door_rules": [],
        }
    }
    expected = {
        "requirements": {
            "controller_rules": [
                {
                    "areas": {"any_of": [[], None]},
                    "manages_door_areas": ["Entreehal", "Parkeergarage"],
                    "connection_type": "BUS",
                }
            ],
            "door_rules": [],
        }
    }

    assert matches_expected_output(actual, expected)


def test_focused_diff_points_at_each_mismatched_field():
    expected = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["FIETSENSTALLING"],
                    "door_id": "FIETSENSTALLING_ENTRY",
                    "lock_type": "SOLENOID_LOCK",
                    "reader_types": ["CARD"],
                    "exit_device": "ELBOW_ACTUATED",
                },
                {
                    "areas": ["PARKING"],
                    "door_id": "PARKING_ENTRY",
                    "lock_type": "SOLENOID_LOCK",
                    "reader_types": ["CARD"],
                    "emergency_button": "STANDALONE",
                },
            ],
            "controller_rules": [],
        }
    }
    actual = {
        "requirements": {
            "door_rules": [
                {
                    "areas": ["FIETSENSTALLING"],
                    "door_id": "FIETSENSTALLING_ENTRY",
                    "lock_type": "OTHER",
                    "reader_types": ["CARD", "OTHER"],
                    "exit_device": "ELBOW_ACTUATED",
                },
                {
                    "areas": ["PARKING"],
                    "door_id": "PARKING_ENTRY",
                    "reader_types": ["CARD"],
                    "lock_type": "OTHER",
                    "reader_direction": "IN_ONLY",
                },
            ],
            "controller_rules": [],
        }
    }

    diff = focused_diff(
        json.dumps(expected, ensure_ascii=False),
        json.dumps(actual, ensure_ascii=False),
    )

    assert "requirements.door_rules[0].lock_type" in diff
    assert "requirements.door_rules[0].reader_types" in diff
    assert "requirements.door_rules[1].lock_type" in diff
    assert "requirements.door_rules[1].reader_direction" in diff
    assert "requirements.door_rules[1].emergency_button" in diff
