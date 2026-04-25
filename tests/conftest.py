"""Pytest configuration for requirement extraction tests.

Usage:
    pytest tests/ --models gemini:gemini-1.5-pro
    pytest tests/ --models gemini:gemini-1.5-pro,openai:gpt-4-turbo --use-rag both -v
    pytest tests/ --models gemini --use-rag both --count 3 -n auto -v
"""

import pytest


def pytest_addoption(parser):
    """Register custom command line options."""
    parser.addoption(
        "--models",
        action="store",
        default=None,
        help="Comma-separated list of models (format: vendor:model_name)",
    )
    parser.addoption(
        "--use-rag",
        action="store",
        default="standard",
        choices=["standard", "rag", "both"],
        help="Test methods: 'standard' (no RAG), 'rag' (with RAG), 'both' (default: standard)",
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
    
    # Parametrize 'use_rag'
    if "use_rag" in metafunc.fixturenames:
        rag_option = metafunc.config.getoption("use_rag")
        
        if rag_option == "standard":
            use_rag_values = [False]
            ids = ["no_rag"]
        elif rag_option == "rag":
            use_rag_values = [True]
            ids = ["with_rag"]
        elif rag_option == "both":
            use_rag_values = [False, True]
            ids = ["no_rag", "with_rag"]
        
        metafunc.parametrize("use_rag", use_rag_values, ids=ids)


@pytest.fixture
def rag_context(request):
    """Provide RAG context if available."""
    from pathlib import Path
    
    rag_kb_dir = Path("tests/rag_knowledge_base")
    if not rag_kb_dir.exists():
        return None
    
    try:
        from src.rag import RAGContext
        return RAGContext(rag_kb_dir)
    except ImportError:
        return None