"""Few-shot prompting utilities for requirement extraction.

Provides functionality to load example cases and build context strings
for few-shot learning, where the LLM is given similar past examples
to improve extraction accuracy.
"""

import contextlib
import io
import json
import os
import hashlib
import tempfile
from pathlib import Path
from typing import List, Tuple
import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Global embeddings cache
_embeddings_cache = {}
_embedding_model = None
EMBEDDINGS_CACHE_FILE = Path(__file__).resolve().parents[1] / ".cache" / "few_shot_embeddings.json"


def _load_case_payload(case_dir: Path) -> dict | None:
    """Load a case from input.json."""
    input_json_file = case_dir / "input.json"

    if input_json_file.exists():
        with open(input_json_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        return payload
    return None


def _normalize_case_payload(payload: dict) -> dict:
    """Normalize a case payload to the structure used by the benchmark."""
    return {
        "requirement_text": str(payload.get("requirement_text", "")).strip(),
        "language": payload.get("language", "Dutch"),
        "available_spaces": payload.get("available_spaces") or [],
        "available_doors": payload.get("available_doors") or [],
    }


def _format_available_spaces(available_spaces: list[str] | None) -> str:
    if not available_spaces:
        return ""
    return "Available spaces:\n" + "\n".join(f"- {space}" for space in available_spaces)


def _format_available_doors(available_doors: list[dict] | None) -> str:
    if not available_doors:
        return ""

    lines = ["Available doors:"]
    for door in available_doors:
        door_id = door.get("door_id") or door.get("name") or "UNKNOWN_DOOR"
        space_a = door.get("space_a") or "UNKNOWN_SPACE"
        space_b = door.get("space_b") or "UNKNOWN_SPACE"
        is_external = bool(door.get("is_external", False))
        lines.append(f"- {door_id}: {space_a} <-> {space_b}, external={'true' if is_external else 'false'}")
    return "\n".join(lines)


def _build_example_text(case_data: dict) -> str:
    """Build the text shown in few-shot examples."""
    parts = [case_data["requirement_text"]]

    spaces_block = _format_available_spaces(case_data.get("available_spaces"))
    if spaces_block:
        parts.append(spaces_block)

    doors_block = _format_available_doors(case_data.get("available_doors"))
    if doors_block:
        parts.append(doors_block)

    return "\n\n".join(parts).strip()


def _load_embedding_model():
    """Load sentence-transformers model (lazy load)."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        from dotenv import load_dotenv
        from sentence_transformers import SentenceTransformer
        load_dotenv()

        hf_token = os.getenv("HF_TOKEN")
        if hf_token and not os.getenv("HUGGING_FACE_HUB_TOKEN"):
            os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return _embedding_model
    except ImportError:
        return None


def _knowledge_base_fingerprint(knowledge_base: dict) -> str:
    """Build a stable fingerprint for the knowledge base specs."""
    payload = [
        (case_name, str(case_data.get("spec", "")).strip())
        for case_name, case_data in sorted(knowledge_base.items())
    ]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_embeddings_cache() -> dict | None:
    if not EMBEDDINGS_CACHE_FILE.exists():
        return None

    try:
        with EMBEDDINGS_CACHE_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, dict):
        return None

    return payload


def _save_embeddings_cache(fingerprint: str, embeddings: dict) -> None:
    EMBEDDINGS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "fingerprint": fingerprint,
        "embeddings": {
            case_name: embedding.tolist()
            for case_name, embedding in embeddings.items()
        },
    }
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=EMBEDDINGS_CACHE_FILE.parent,
        prefix=f"{EMBEDDINGS_CACHE_FILE.stem}.",
        suffix=".tmp",
        delete=False,
    ) as tmp_file:
        json.dump(serializable, tmp_file, ensure_ascii=False)
        tmp_name = tmp_file.name

    os.replace(tmp_name, EMBEDDINGS_CACHE_FILE)


def preload_embedding_model() -> bool:
    """
    Preload the embedding model once, typically during app or test boot.

    Returns True when the model was loaded or already available.
    """
    return _load_embedding_model() is not None


def load_knowledge_base(knowledge_base_dir: Path) -> dict:
    """
    Load all example cases from knowledge base directory.
    
    Args:
        knowledge_base_dir: Path to directory with example cases (input.json + expected.json)
    
    Returns:
        Dictionary mapping case_name to {spec, expected, available_spaces, available_doors}
    """
    kb = {}

    for case_dir in sorted(knowledge_base_dir.glob('*')):
        if not case_dir.is_dir() or case_dir.name.startswith('ignore_'):
            continue

        expected_file = case_dir / 'expected.json'

        input_payload = _load_case_payload(case_dir)
        if expected_file.exists() and input_payload is not None:
            normalized_input = _normalize_case_payload(input_payload)
            spec = normalized_input["requirement_text"]

            with open(expected_file, 'r', encoding='utf-8') as f:
                expected = json.load(f)

            kb[case_dir.name] = {
                "spec": spec,
                "expected": expected,
                "available_spaces": normalized_input["available_spaces"],
                "available_doors": normalized_input["available_doors"],
                "language": normalized_input["language"],
            }

    return kb


def create_embeddings(knowledge_base: dict) -> dict:
    """
    Create embeddings for all specs in knowledge base.
    
    Args:
        knowledge_base: Dictionary of example cases
    
    Returns:
        Dictionary mapping case_name to embedding vector
    """
    fingerprint = _knowledge_base_fingerprint(knowledge_base)
    cached = _load_embeddings_cache()
    if cached and cached.get("fingerprint") == fingerprint:
        return {
            case_name: np.array(vector, dtype=np.float32)
            for case_name, vector in cached["embeddings"].items()
        }

    model = _load_embedding_model()
    if not model:
        return {}

    cached = _load_embeddings_cache()
    if cached and cached.get("fingerprint") == fingerprint:
        return {
            case_name: np.array(vector, dtype=np.float32)
            for case_name, vector in cached["embeddings"].items()
        }

    embeddings = {}
    for case_name, case_data in knowledge_base.items():
        embedding = model.encode(case_data["spec"])
        embeddings[case_name] = embedding

    _save_embeddings_cache(fingerprint, embeddings)
    return embeddings


def find_similar_semantic(
    query_spec: str,
    knowledge_base: dict,
    embeddings: dict,
    k: int = 2
) -> List[Tuple[str, float]]:
    """Find similar specs using semantic similarity."""
    model = _load_embedding_model()
    if not model:
        return []
    
    query_embedding = model.encode(_build_query_text(query_spec))
    
    similarities = {}
    for case_name, embedding in embeddings.items():
        # Cosine similarity
        sim = np.dot(query_embedding, embedding) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
        )
        similarities[case_name] = float(sim)
    
    # Return top k sorted by similarity
    sorted_cases = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
    return [(name, score) for name, score in sorted_cases[:k] if score > 0]


def find_similar_keyword(
    query_spec: str,
    knowledge_base: dict,
    k: int = 2
) -> List[Tuple[str, float]]:
    """Find similar specs using keyword overlap."""
    query_words = set(_build_query_text(query_spec).lower().split())
    
    similarities = {}
    for case_name, case_data in knowledge_base.items():
        spec_words = set(case_data["spec"].lower().split())
        overlap = len(query_words & spec_words)
        similarity = overlap / max(len(query_words), len(spec_words))
        similarities[case_name] = similarity
    
    # Return top k sorted by similarity
    sorted_cases = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
    return [(name, score) for name, score in sorted_cases[:k] if score > 0]


def find_similar(
    query_spec: str | dict,
    knowledge_base: dict,
    embeddings: dict,
    k: int = 2
) -> List[Tuple[str, float]]:
    """
    Find k most similar example specs from knowledge base.
    
    Uses semantic similarity if embeddings available, falls back to keyword matching.
    
    Args:
        query_spec: Specification to find similar examples for
        knowledge_base: Dictionary of example cases
        embeddings: Precomputed embeddings (or empty dict for keyword-only)
        k: Number of similar cases to return
    
    Returns:
        List of (case_name, similarity_score) tuples
    """
    if embeddings:
        return find_similar_semantic(query_spec, knowledge_base, embeddings, k)
    else:
        return find_similar_keyword(query_spec, knowledge_base, k)


def build_context(
    similar_cases: List[Tuple[str, float]],
    knowledge_base: dict
) -> str:
    """
    Build few-shot context string from similar example cases.
    
    Args:
        similar_cases: List of (case_name, similarity_score) tuples
        knowledge_base: Dictionary of example cases
    
    Returns:
        Context string with examples to include in prompt for few-shot learning
    """
    if not similar_cases:
        return ""
    
    context = "REFERENCE EXAMPLES (similar previous extractions):\n"
    context += "=" * 70 + "\n"
    
    for i, (case_name, similarity) in enumerate(similar_cases, 1):
        case_data = knowledge_base.get(case_name)
        if not case_data:
            continue
        
        context += f"\nEXAMPLE {i} ({similarity:.0%} similar):\n"
        context += f"Input specification:\n{case_data['spec']}\n\n"
        if case_data.get("available_spaces"):
            context += "Available spaces:\n"
            context += "\n".join(f"- {space}" for space in case_data["available_spaces"]) + "\n\n"
        if case_data.get("available_doors"):
            context += "Available doors:\n"
            for door in case_data["available_doors"]:
                door_id = door.get("door_id") or door.get("name") or "UNKNOWN_DOOR"
                space_a = door.get("space_a") or "UNKNOWN_SPACE"
                space_b = door.get("space_b") or "UNKNOWN_SPACE"
                is_external = bool(door.get("is_external", False))
                context += f"- {door_id}: {space_a} <-> {space_b}, external={'true' if is_external else 'false'}\n"
            context += "\n"
        context += f"Extracted JSON:\n{json.dumps(case_data['expected'], indent=2)}\n"
        context += "-" * 70 + "\n"
    
    return context


def _build_query_text(query_spec: str | dict) -> str:
    """Build a similarity query string from raw text or an input.json payload."""
    if isinstance(query_spec, dict):
        normalized = _normalize_case_payload(query_spec)
        return normalized["requirement_text"]

    return str(query_spec)
