import os

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError


def openai_generate_text(system_prompt: str, user_prompt: str, model_name: str) -> str:
    """
    OpenAI-specific text generation using the Responses API.
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model_name,
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
        raise RuntimeError("OpenAI rate limit / quota error.") from exc

    return response.output_text.strip()