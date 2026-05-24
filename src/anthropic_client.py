import os
from datetime import UTC, datetime

from anthropic import Anthropic, RateLimitError
from dotenv import load_dotenv

from src.llm_types import LLMResult


def _extract_text(message) -> str:
    parts: list[str] = []

    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)

    return "".join(parts).strip()


def anthropic_generate_text(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    max_tokens: int,
    temperature: float = 0.0,
) -> LLMResult:
    """
    Anthropic-specific text generation using the Messages API.
    Includes timing + token usage metadata.
    """
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing.")

    client = Anthropic(api_key=api_key)

    started = datetime.now(UTC)

    try:
        message = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )
    except RateLimitError as exc:
        raise RuntimeError("Anthropic rate limit / quota error.") from exc

    completed = datetime.now(UTC)
    duration_ms = int((completed - started).total_seconds() * 1000)

    usage = getattr(message, "usage", None)

    return LLMResult(
        text=_extract_text(message),
        vendor="anthropic",
        model_name=model_name,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        duration_ms=duration_ms,
        input_tokens=getattr(usage, "input_tokens", None) if usage else None,
        output_tokens=getattr(usage, "output_tokens", None) if usage else None,
    )
