import json
from typing import Any

from openai import RateLimitError
from pydantic import ValidationError

from src.llm_client import get_client, load_system_prompt
from src.schema import AccessControlExtraction

MODEL_NAME = "gpt-4.1-mini"
SYSTEM_PROMPT = "system_prompt.txt"

def build_user_prompt(requirement_text: str) -> str:
    return f"""Convert the following Dutch access control requirement text into JSON.

Requirement text:
{requirement_text}
"""


def extract_requirements_json(
    requirement_text: str,
    system_prompt_path: str = SYSTEM_PROMPT,
    model: str = MODEL_NAME
):
    client = get_client()
    system_prompt = load_system_prompt(system_prompt_path)
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

    response_text = response.output_text.strip()
    return response_text