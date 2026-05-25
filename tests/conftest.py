"""Pytest configuration for requirement extraction tests.

Usage:
    pytest tests/ --models gemini:gemini-1.5-pro
    pytest tests/ --models gemini:gemini-1.5-pro,openai:gpt-4-turbo --use-few-shot both -v
    pytest tests/ --models gemini --use-few-shot both --count 3 -n auto -v
"""

from datetime import UTC, datetime
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
        default="false",
        choices=["false", "true", "both"],
        help="Test methods: 'false' (no few-shot), 'true' (with few-shot examples), 'both' (default: standard)",
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
        
        if few_shot_option == "false":
            use_few_shot_values = [False]
            ids = ["no_few_shot"]
        elif few_shot_option == "true":
            use_few_shot_values = [True]
            ids = ["with_few_shot"]
        elif few_shot_option == "both":
            use_few_shot_values = [False, True]
            ids = ["no_few_shot", "with_few_shot"]
        
        metafunc.parametrize("use_few_shot", use_few_shot_values, ids=ids)


def pytest_configure(config):
    """Prime the few-shot embedding cache once in the controller process."""
    if getattr(config, "workerinput", None) is not None:
        return

    from tests.result_logging import set_run_id

    set_run_id(datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"))

    if config.getoption("use_few_shot") == "false":
        return

    from pathlib import Path

    from src.few_shot import create_embeddings, load_knowledge_base

    kb_dir = Path("tests/knowledge_base")
    if not kb_dir.exists():
        return

    knowledge_base = load_knowledge_base(kb_dir)
    if knowledge_base:
        create_embeddings(knowledge_base)


def pytest_sessionfinish(session, exitstatus):
    """Remove the shared run-id marker after the full session finishes."""
    if getattr(session.config, "workerinput", None) is not None:
        return

    from tests.result_logging import clear_run_id

    clear_run_id()


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
