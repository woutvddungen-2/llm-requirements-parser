import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def load_system_prompt(prompt_files: list[str]) -> str:
    parts: list[str] = []

    for prompt_file in prompt_files:
        path = Path(prompt_file)

        if not path.exists():
            raise FileNotFoundError(f"Prompt file not found: {path.resolve()}")

        parts.append(path.read_text(encoding="utf-8").strip())

    return "\n\n".join(parts)


def get_client() -> OpenAI:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from your environment or .env file.")

    return OpenAI(api_key=api_key)