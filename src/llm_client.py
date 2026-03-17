import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def load_system_prompt(prompt_path: str = "system_prompt.txt") -> str:
    path = Path(prompt_path)
    if not path.exists():
        raise FileNotFoundError(f"System prompt not found: {path.resolve()}")
    return path.read_text(encoding="utf-8")


def get_client() -> OpenAI:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from your environment or .env file.")

    return OpenAI(api_key=api_key)