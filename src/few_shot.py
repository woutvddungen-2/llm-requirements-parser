"""Few-shot prompting utilities for requirement extraction.

Provides functionality to load example cases and build context strings
for few-shot learning, where the LLM is given similar past examples
to improve extraction accuracy.
"""

import json
from pathlib import Path
from typing import List, Tuple
import numpy as np

# Global embeddings cache
_embeddings_cache = {}
_embedding_model = None


def _load_embedding_model():
    """Load sentence-transformers model (lazy load)."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return _embedding_model
    except ImportError:
        return None


def load_knowledge_base(knowledge_base_dir: Path) -> dict:
    """
    Load all example cases from knowledge base directory.
    
    Args:
        knowledge_base_dir: Path to directory with example cases (input.txt + expected.json)
    
    Returns:
        Dictionary mapping case_name to {spec, expected}
    """
    kb = {}
    
    for case_dir in sorted(knowledge_base_dir.glob('*')):
        if not case_dir.is_dir() or case_dir.name.startswith('ignore_'):
            continue
        
        input_json_file = case_dir / 'input.json'
        input_file = case_dir / 'input.txt'
        expected_file = case_dir / 'expected.json'

        if expected_file.exists() and (input_json_file.exists() or input_file.exists()):
            if input_json_file.exists():
                with open(input_json_file, 'r', encoding='utf-8') as f:
                    input_payload = json.load(f)
                spec = input_payload.get('requirement_text', '')
            else:
                with open(input_file, 'r', encoding='utf-8') as f:
                    spec = f.read()

            with open(expected_file, 'r', encoding='utf-8') as f:
                expected = json.load(f)
            
            kb[case_dir.name] = {
                'spec': spec,
                'expected': expected,
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
    model = _load_embedding_model()
    if not model:
        return {}
    
    embeddings = {}
    for case_name, case_data in knowledge_base.items():
        spec = case_data['spec']
        embedding = model.encode(spec)
        embeddings[case_name] = embedding
    
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
    
    query_embedding = model.encode(query_spec)
    
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
    query_words = set(query_spec.lower().split())
    
    similarities = {}
    for case_name, case_data in knowledge_base.items():
        spec_words = set(case_data['spec'].lower().split())
        overlap = len(query_words & spec_words)
        similarity = overlap / max(len(query_words), len(spec_words))
        similarities[case_name] = similarity
    
    # Return top k sorted by similarity
    sorted_cases = sorted(similarities.items(), key=lambda x: x[1], reverse=True)
    return [(name, score) for name, score in sorted_cases[:k] if score > 0]


def find_similar(
    query_spec: str,
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
        context += f"Extracted JSON:\n{json.dumps(case_data['expected'], indent=2)}\n"
        context += "-" * 70 + "\n"
    
    return context
