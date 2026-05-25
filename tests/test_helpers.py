from tests.helpers import normalize_for_comparison


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
