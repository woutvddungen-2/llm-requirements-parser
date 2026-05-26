import os
from datetime import UTC, datetime

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from src.llm_types import LLMResult


def openai_generate_text(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    max_tokens: int,
    temperature: float = 0.0,
) -> LLMResult:
    """
    OpenAI-specific text generation using the Responses API.
    Includes timing + token usage metadata.
    model names: https://developers.openai.com/api/docs/models/all
    examples: openai:gpt-4o openai:gpt-5.1-mini
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model_name,
            max_output_tokens=max_tokens,
            temperature=temperature,
            text={"format": {"type": "json_object"}},
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

    usage = getattr(response, "usage", None)

    return LLMResult(
        text=response.output_text.strip(),
        vendor="openai",
        model_name=model_name,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
    )
