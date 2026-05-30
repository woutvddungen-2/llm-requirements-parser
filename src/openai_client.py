import os
from datetime import UTC, datetime

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

from src.llm_types import LLMResult


def _is_unsupported_temperature_error(exc: Exception) -> bool:
    """
    Return True when OpenAI rejected the request because temperature is unsupported.

    Some model families accept temperature, while others reject it with a 400.
    We prefer to try with temperature first and only fall back when the API
    explicitly says the parameter is unsupported.
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    return "temperature" in text and "unsupported parameter" in text


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

    base_kwargs = {
        "model": model_name,
        "max_output_tokens": max_tokens,
        "text": {"format": {"type": "json_object"}},
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
    }

    try:
        response = client.responses.create(
            **base_kwargs,
            temperature=temperature,
        )
    except RateLimitError as exc:
        raise RuntimeError("OpenAI rate limit / quota error.") from exc
    except Exception as exc:
        if not _is_unsupported_temperature_error(exc):
            raise

        try:
            response = client.responses.create(
                **base_kwargs,
            )
        except RateLimitError as retry_exc:
            raise RuntimeError("OpenAI rate limit / quota error.") from retry_exc

    usage = getattr(response, "usage", None)

    return LLMResult(
        text=response.output_text.strip(),
        vendor="openai",
        model_name=model_name,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
    )
