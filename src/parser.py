from src.llm_client import generate_text, load_system_prompt
from src.llm_types import LLMResult

DEFAULT_MAX_TOKENS = 4096

PROMPT_FILES = [
    "prompts/system_core.txt",
    "prompts/access_control/schema_access_control.txt",
    "prompts/access_control/terminology_access_control.txt",
    "prompts/logic_rules.txt",
    "prompts/access_control/examples_access_control.txt",
]


def build_user_prompt(requirement_text: str) -> str:
    """
    Build the user prompt from the raw requirement text.
    """
    return f"""Convert the following Dutch access control requirement text into JSON.

Requirement text:
{requirement_text}
"""


def extract_requirements_json(
    requirement_text: str,
    model: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    prompt_files: list[str] = PROMPT_FILES,    
) -> LLMResult:
    """
    Extract structured access control requirements using the specified LLM.

    Returns:
        LLMResult containing:
        - raw model output (text)
        - timing metadata
        - token usage (if available)
    """
    if not model or not model.strip():
        raise ValueError("Model name must be provided and cannot be empty.")

    system_prompt = load_system_prompt(prompt_files)
    user_prompt = build_user_prompt(requirement_text)

    return generate_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        max_tokens=max_tokens,
    )