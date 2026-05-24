import os
from datetime import UTC, datetime
from dotenv import load_dotenv
import google.genai as genai
from google.genai import types
from src.llm_types import LLMResult


def gemini_generate_text(
    system_prompt: str,
    user_prompt: str,
    model_name: str,
    max_tokens: int,
    temperature: float = 0.0,
) -> LLMResult:
    """
    Gemini-specific text generation using the Google GenAI SDK.
    Includes timing + token usage metadata.
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing.")

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",  # JSON mode
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
    except Exception as exc:
        if "quota" in str(exc).lower() or "rate" in str(exc).lower():
            raise RuntimeError("Gemini rate limit / quota error.") from exc
        raise

    usage = getattr(response, "usage_metadata", None)

    return LLMResult(
        text=response.text.strip(),
        vendor="gemini",
        model_name=model_name,
        input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
        output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
    )
