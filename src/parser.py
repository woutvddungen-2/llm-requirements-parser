from openai import RateLimitError

from src.llm_client import get_client, load_system_prompt

MODEL_NAME = "gpt-4.1-mini"

PROMPT_FILES = [
    "prompts/system_core.txt",
    "prompts/access_control/schema_access_control.txt",
    "prompts/formatting_rules.txt",
    "prompts/access_control/terminology_access_control.txt",
    "prompts/normalization_rules.txt",
    "prompts/conflict_rules.txt",
    "prompts/access_control/examples_access_control.txt",
]


def build_user_prompt(requirement_text: str) -> str:
    return f"""Convert the following Dutch access control requirement text into JSON.

Requirement text:
{requirement_text}
"""


def extract_requirements_json(
    requirement_text: str,
    prompt_files: list[str] = PROMPT_FILES,
    model: str = MODEL_NAME,
) -> str:
    client = get_client()
    system_prompt = load_system_prompt(prompt_files)
    user_prompt = build_user_prompt(requirement_text)

    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        )
    except RateLimitError as exc:
        raise RuntimeError(
            "OpenAI API quota/rate-limit error. Check billing, credits, and whether this API key belongs to the correct project."
        ) from exc

    return response.output_text.strip()