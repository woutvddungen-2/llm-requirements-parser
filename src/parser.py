"""Requirement extraction with minimal prompts and RAG support.

Architecture:
- Minimal system prompt (instructions only)
- Schema definition (separate concern)
- Terminology (separate concern)
- RAG examples (dynamic, from knowledge base)
"""

from src.llm_client import generate_text, load_system_prompt
from src.llm_types import LLMResult

DEFAULT_MAX_TOKENS = 4096

# System prompt files
PROMPT_FILES_MINIMAL = [
    "prompts/system_core.txt",
    "prompts/access_control/schema_access_control.txt", 
    "prompts/access_control/terminology_access_control.txt",
    "prompts/logic_rules.txt",
]

# Old approach (kept for comparison/fallback)
PROMPT_FILES_FULL = [
    "prompts/system_core.txt",
    "prompts/access_control/schema_access_control.txt",
    "prompts/access_control/terminology_access_control.txt",
    "prompts/logic_rules.txt",
    "prompts/access_control/examples_access_control.txt",
]


def build_system_prompt(use_rag: bool = False) -> str:
    """
    Build system prompt based on whether RAG is used.
    
    With RAG: Minimal system prompt (instructions + schema + terminology)
    Without RAG: Full system prompt (includes examples and rules)
    
    Args:
        use_rag: If True, use minimal prompt. If False, use full prompt.
    
    Returns:
        System prompt string
    """
    if use_rag:
        return load_system_prompt(PROMPT_FILES_MINIMAL)
    else:
        return load_system_prompt(PROMPT_FILES_FULL)


def build_base_user_prompt(requirement_text: str, language: str = "Dutch") -> str:
    """
    Build base user prompt without RAG context.
    
    Args:
        requirement_text: Specification to extract
        language: Language of specification
    
    Returns:
        User prompt string
    """
    return f"""Convert the following {language} access control requirement text into JSON.

Requirement text:
{requirement_text}
"""


def build_rag_context_prompt(
    requirement_text: str,
    rag_context: str,
    language: str = "Dutch"
) -> str:
    """
    Build user prompt augmented with RAG context (similar examples).
    
    Args:
        requirement_text: Specification to extract
        rag_context: RAG context with similar examples
        language: Language of specification
    
    Returns:
        Augmented user prompt with RAG context
    """
    return f"""{rag_context}

Now extract the following {language} specification:

{requirement_text}
"""


def extract_requirements_json(
    requirement_text: str,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    language: str = "Dutch",
    rag_context: str = None,
) -> LLMResult:
    """
    Extract structured access control requirements using specified LLM.
    
    This is the main entry point. It orchestrates:
    1. System prompt selection (minimal vs full)
    2. User prompt building (with or without RAG)
    3. LLM call
    
    Args:
        requirement_text: Specification to extract
        model: LLM model (vendor:model_name format)
        max_tokens: Maximum tokens for generation
        language: Specification language (default: Dutch)
        rag_context: Optional RAG context with similar examples
        use_rag: If True, uses minimal system prompt for RAG mode
    
    Returns:
        LLMResult with extraction and metadata
    
    Raises:
        ValueError: If model name is invalid
    """
    if not model or not model.strip():
        raise ValueError("Model name must be provided and cannot be empty.")
    
    # Step 1: Build system prompt
    system_prompt = build_system_prompt(use_rag=(rag_context is not None))
    
    # Step 2: Build user prompt
    if rag_context:
        user_prompt = build_rag_context_prompt(
            requirement_text,
            rag_context,
            language=language
        )
    else:
        user_prompt = build_base_user_prompt(requirement_text, language=language)
    
    # Step 3: Call LLM
    return generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
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
        rag_context=rag_context,
    )