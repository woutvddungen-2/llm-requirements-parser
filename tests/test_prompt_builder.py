from src.llm_types import LLMResult
from src.prompt_builder import PromptBuilder
from src.parser import extract_requirements_json


def test_prompt_builder_without_floorplan_context():
    prompt = PromptBuilder(language="Dutch").build("serverruimte krijgt een paslezer.")

    assert "Available spaces in this floorplan:" not in prompt
    assert "Available doors in this floorplan:" not in prompt
    assert "Requirement text:" in prompt
    assert "serverruimte krijgt een paslezer." in prompt


def test_prompt_builder_with_spaces_and_doors():
    prompt = PromptBuilder(
        language="Dutch",
        available_spaces=["0.2 Hal", "Entree"],
        available_doors=[
            {
                "door_id": "door_12",
                "space_a": "0.2 Hal",
                "space_b": "Entree",
                "is_external": False,
            },
            {
                "door_id": "door_15",
                "space_a": None,
                "space_b": "Entree",
                "is_external": True,
            },
        ],
    ).build("De deur van Entree naar 0.2 Hal krijgt een kaartlezer.")

    assert "Available spaces in this floorplan:" in prompt
    assert "- 0.2 Hal" in prompt
    assert "- Entree" in prompt
    assert "Available doors in this floorplan:" in prompt
    assert "door_12: 0.2 Hal <-> Entree, external=false" in prompt
    assert "door_15: OUTSIDE <-> Entree, external=true" in prompt
    assert "Use ONLY these door IDs when specifying door_id." in prompt
    assert "For 'door from X to Y' / 'deur van X naar Y'" in prompt


def test_extract_requirements_appends_validation_feedback(monkeypatch):
    captured = {}

    def fake_generate_text(system_prompt, user_prompt, model, max_tokens, temperature=0.0):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        captured["model"] = model
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return LLMResult(text='{"ok": true}', vendor="test", model_name="stub")

    monkeypatch.setattr("src.parser.generate_text", fake_generate_text)

    extract_requirements_json(
        "serverruimte krijgt een paslezer.",
        model="openai:gpt-4.1-mini",
        available_spaces=["serverruimte"],
        available_doors=[{"door_id": "door_1", "space_a": "serverruimte", "space_b": "OUTSIDE", "is_external": True}],
        validation_feedback="Missing door_id",
    )

    assert "Available spaces in this floorplan:" in captured["user_prompt"]
    assert "Available doors in this floorplan:" in captured["user_prompt"]
    assert "The previous JSON output failed validation." in captured["user_prompt"]
    assert "Missing door_id" in captured["user_prompt"]
    assert captured["model"] == "openai:gpt-4.1-mini"
