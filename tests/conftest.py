"""Pytest configuration for requirement extraction tests.

Usage:
    pytest tests/ --models gemini:gemini-1.5-pro
    pytest tests/ --models gemini:gemini-1.5-pro,openai:gpt-4-turbo --use-few-shot both -v
    pytest tests/ --models gemini --use-few-shot both --count 3 -n auto -v
"""

import pytest
from pathlib import Path


def pytest_addoption(parser):
    """Register custom command line options."""
    parser.addoption(
        "--models",
        action="store",
        default=None,
        help="Comma-separated list of models (format: vendor:model_name)",
    )
    parser.addoption(
        "--use-few-shot",
        action="store",
        default="standard",
        choices=["standard", "few-shot", "both"],
        help="Test methods: 'standard' (no few-shot), 'few-shot' (with few-shot examples), 'both' (default: standard)",
    )


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests based on CLI options."""
    
    # Parametrize 'model'
    if "model" in metafunc.fixturenames:
        raw_models = metafunc.config.getoption("models")
        if not raw_models:
            raise ValueError(
                "No models specified. Use --models vendor:model_name[,vendor:model_name,...]"
            )
        models = [m.strip() for m in raw_models.split(",") if m.strip()]
        if not models:
            raise ValueError("No valid models specified")
        metafunc.parametrize("model", models, ids=models)
    
    # Parametrize 'use_few_shot'
    if "use_few_shot" in metafunc.fixturenames:
        few_shot_option = metafunc.config.getoption("use_few_shot")
        
        if few_shot_option == "standard":
            use_few_shot_values = [False]
            ids = ["no_few_shot"]
        elif few_shot_option == "few-shot":
            use_few_shot_values = [True]
            ids = ["with_few_shot"]
        elif few_shot_option == "both":
            use_few_shot_values = [False, True]
            ids = ["no_few_shot", "with_few_shot"]
        
        metafunc.parametrize("use_few_shot", use_few_shot_values, ids=ids)


@pytest.fixture(scope="session")
def few_shot_examples():
    """Load few-shot example cases from knowledge base directory."""
    from src.few_shot import load_knowledge_base
    
    kb_dir = Path("tests/knowledge_base")
    if not kb_dir.exists():
        return None
    
    return load_knowledge_base(kb_dir)


@pytest.fixture(scope="session")
def few_shot_embeddings(few_shot_examples):
    """Create embeddings for few-shot example cases."""
    if not few_shot_examples:
        return {}
    
    from src.few_shot import create_embeddings
    return create_embeddings(few_shot_examples)


# Backward compatibility aliases
@pytest.fixture(scope="session")
def rag_knowledge_base(few_shot_examples):
    """Deprecated: Use few_shot_examples instead."""
    return few_shot_examples


@pytest.fixture(scope="session")
def rag_embeddings(few_shot_embeddings):
    """Deprecated: Use few_shot_embeddings instead."""
    return few_shot_embeddings