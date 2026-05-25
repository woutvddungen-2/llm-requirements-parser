"""Requirement extraction with composable prompts and RAG support."""

from src.llm_client import generate_text, load_system_prompt
from src.prompt_builder import PromptBuilder
from src.llm_types import LLMResult

DEFAULT_MAX_TOKENS = 4096

BASE_PROMPT_FILES = [
    "prompts/system_core.txt",
    "prompts/access_control/schema_access_control.txt",
    "prompts/access_control/terminology_access_control.txt",
    "prompts/logic_rules.txt",
]

STATIC_EXAMPLE_FILES = [
    "prompts/access_control/examples_access_control.txt",
]


def build_system_prompt(rag_context: str | None = None) -> str:
    """Build the system prompt used for requirement extraction.

    When rag_context is provided, it replaces the static example block.
    """
    base_prompt = load_system_prompt(BASE_PROMPT_FILES)

    if rag_context:
        return f"{base_prompt}\n\n{rag_context}"

    return load_system_prompt(BASE_PROMPT_FILES + STATIC_EXAMPLE_FILES)


def build_user_prompt(
    requirement_text: str,
    language: str = "Dutch"
) -> str:
    """Build the default user prompt for text-only extraction."""
    return PromptBuilder(language=language).build(requirement_text)


def extract_requirements_json(
    requirement_text: str,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    language: str = "Dutch",
    available_spaces: list[str] | None = None,
    available_doors: list[dict] | None = None,
    validation_feedback: str | None = None,
    rag_context: str | None = None,
    temperature: float = 0.0,
) -> LLMResult:
    if not model or not model.strip():
        raise ValueError("Model name must be provided and cannot be empty.")

    system_prompt = build_system_prompt(rag_context=rag_context)
    user_prompt = PromptBuilder(
        language=language,
        available_spaces=available_spaces,
        available_doors=available_doors,
    ).build(requirement_text)

    if validation_feedback:
        user_prompt += (
            "\n\nThe previous JSON output failed validation. "
            "Return a corrected JSON object only, using the same schema and enum values.\n"
            f"{validation_feedback}\n"
        )

    return generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def extract_with_rag(
    requirement_text: str,
    model: str,
    rag_context: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    language: str = "Dutch",
) -> LLMResult:
    """
    Convenience function extraction.
    
    Args:
        requirement_text: Specification to extract
        model: LLM model (vendor:model_name format)
        rag_context: RAG context with similar examples
        max_tokens: Maximum tokens for generation
        language: Specification language
    
    Returns:
        LLMResult with extraction and metadata
    """
    return extract_requirements_json(
        requirement_text,
        model,
        max_tokens=max_tokens,
        language=language,
        available_spaces=None,
        available_doors=None,
        rag_context=rag_context,
    )
