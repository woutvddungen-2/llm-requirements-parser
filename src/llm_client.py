from datetime import UTC, datetime
from pathlib import Path

from src.openai_client import openai_generate_text
from src.anthropic_client import anthropic_generate_text
from src.gemini_client import gemini_generate_text
from src.deepseek_client import deepseek_generate_text
from src.llm_types import LLMResult

def load_system_prompt(prompt_files: list[str]) -> str:
    """
    Load and concatenate multiple prompt files into a single system prompt.
    """
    
    parts: list[str] = []

    for prompt_file in prompt_files:
        path = Path(prompt_file)

        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path.resolve()}")

        parts.append(path.read_text(encoding="utf-8").strip())

    return "\n\n".join(parts)


def parse_model_spec(model: str) -> tuple[str, str]:
    """
    Parse model spec in format: 'vendor:model_name'.
    Example: 'openai:gpt-4.1-mini'
    """
    if not model or not model.strip():
        raise ValueError("Model must be specified in format 'vendor:model_name'.")

    raw = model.strip()

    if ":" not in raw:
        raise ValueError(f"Invalid model '{raw}'. Expected format: 'vendor:model_name'.")

    vendor, model_name = raw.split(":", 1)
    vendor = vendor.strip().lower()
    model_name = model_name.strip()

    if not vendor or not model_name:
        raise ValueError(f"Invalid model '{raw}'. Expected format: 'vendor:model_name'.")

    return vendor, model_name


def generate_text(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> LLMResult:
    """
    Route generation to the correct vendor-specific implementation.
    """
    started = datetime.now(UTC)
    vendor, model_name = parse_model_spec(model)
    result: LLMResult
    if vendor == "openai":
        result = openai_generate_text(system_prompt, user_prompt, model_name, max_tokens)
    elif vendor == "anthropic":
        result = anthropic_generate_text(system_prompt, user_prompt, model_name, max_tokens)
    elif vendor == "gemini":
        result = gemini_generate_text(system_prompt, user_prompt, model_name, max_tokens)
    elif vendor == "deepseek":
        result = deepseek_generate_text(system_prompt, user_prompt, model_name, max_tokens)
    else:
        raise ValueError(f"Unsupported vendor: {vendor}")
    result.started_at = started
    result.completed_at = datetime.now(UTC)
    result.duration_ms = int((result.completed_at - result.started_at).total_seconds() * 1000)
    return result
    