import os
from datetime import UTC, datetime

from anthropic import Anthropic, RateLimitError, APIStatusError
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
    model names: https://docs.anthropic.com/claude/reference/models
    examples: anthropic:claude-haiku-4-5 claude-sonnet-4-6, anthropic:claude-opus-4-7
    """
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing.")

    client = Anthropic(api_key=api_key)

    started = datetime.now(UTC)

    try:
        kwargs = {
            "model": model_name,
            "max_tokens": max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        }
        if not model_name.startswith("claude-opus-4-7"):
            kwargs["temperature"] = temperature

        message = client.messages.create(**kwargs)
    except RateLimitError as exc:
        raise RuntimeError("Anthropic rate limit / quota error.") from exc
    except APIStatusError as exc:
        if exc.status_code == 400 and "credit balance is too low" in str(exc):
            raise RuntimeError("Anthropic billing error: insufficient credits.") from exc
        raise

    completed = datetime.now(UTC)
    duration_ms = int((completed - started).total_seconds() * 1000)
    
    usage = getattr(message, "usage", None)

    print(f"DEBUG usage: input={getattr(usage,'input_tokens',None)}, cache_read={getattr(usage,'cache_read_input_tokens',None)}, cache_create={getattr(usage,'cache_creation_input_tokens',None)}")

    return LLMResult(
        text=_extract_text(message),
        vendor="anthropic",
        model_name=model_name,
        started_at=started.isoformat(),
        completed_at=completed.isoformat(),
        duration_ms=duration_ms,
        input_tokens=getattr(usage, "input_tokens", 0) + 
                getattr(usage, "cache_read_input_tokens", 0) + 
                getattr(usage, "cache_creation_input_tokens", 0) if usage else None,
        output_tokens=getattr(usage, "output_tokens", 0) if usage else None,
    )
