from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class LLMResult:
    """
    Standardized result object for all LLM calls.

    This keeps parser/tests vendor-agnostic while still exposing
    useful research metrics.
    """
    text: str

    vendor: str
    model_name: str

    # Timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None

    # Token usage (if available from provider)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None