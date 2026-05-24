import os
from datetime import UTC, datetime
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from src.llm_types import LLMResult


def deepseek_generate_text(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    max_tokens: int,
    temperature: float = 0.0,
) -> LLMResult:
    """
    DeepSeek-specific text generation using the OpenAI-compatible API.
    Includes timing + token usage metadata.
    """
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is missing.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},  # JSON mode
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except RateLimitError as exc:
        raise RuntimeError("DeepSeek rate limit / quota error.") from exc

    usage = getattr(response, "usage", None)

    return LLMResult(
        text=response.choices[0].message.content.strip(),
        vendor="deepseek",
        model_name=model_name,
        input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
        output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
    )
