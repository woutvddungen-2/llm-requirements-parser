"""Pytest configuration for requirement extraction tests.

Usage:
    # Single model with single strategy
    pytest tests/test_expected_output.py --models anthropic:claude-sonnet-4-6 --pdf-strategy hybrid

    # Multiple models, multiple strategies, multiple runs with parallel execution
    pytest tests/test_expected_output.py \
      --models anthropic:claude-sonnet-4-6,anthropic:claude-haiku-4-5-20251001 \
      --use-few-shot both \
      --count 3 \
      -n auto \
      -v

    # Test all PDF strategies against a test case
    pytest tests/test_expected_output.py \
      --models anthropic:claude-sonnet-4-6 \
      --pdf-strategy toc,keyword,regex,hybrid \
      -k 052_fietsenstalling_toegang \
      --count 2 \
      -n auto

    # Cost-effective: simple models on simple cases, powerful models on complex ones
    pytest tests/test_expected_output.py \
      --models anthropic:claude-haiku-4-5-20251001,anthropic:claude-sonnet-4-6 \
      --pdf-strategy hybrid,keyword \
      -k "051 or 052" \
      --count 3 \
      -n auto
"""

from datetime import UTC, datetime
import pytest
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass

from tests.result_logging import read_jsonl

load_dotenv()

CASES_DIR = Path("tests/cases")
LOG_DIR = Path("tests/logs")


@dataclass(frozen=True)
class TestRunSpec:
    case_dir: Path
    model: str
    use_few_shot: bool
    pdf_strategy: str

    @property
    def node_id(self) -> str:
        few_shot_id = "with_few_shot" if self.use_few_shot else "no_few_shot"
        return f"{self.case_dir.name}-{few_shot_id}-{self.pdf_strategy}-{self.model}"


def discover_cases() -> list[Path]:
    """Discover all benchmark cases with inputs and expected output."""
    tests = sorted([p for p in CASES_DIR.iterdir() if p.is_dir()])
    return [
        p for p in tests
        if (p / "input.json").exists()
        and (p / "expected.json").exists()
        and not p.name.startswith("ignore_")
    ]


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
    parser.addoption(
        "--pdf-strategy",
        action="store",
        default="hybrid",
        help="Page selection strategy for PDF-backed cases (comma-separated for multiple: toc,keyword,regex,hybrid,category,llm).",
    )
    parser.addoption(
        "--rerun",
        action="store",
        default=None,
        help="Rerun tests from a logged JSONL file, such as tests/logs/<run_id>_pending.jsonl.",
    )


def _resolve_rerun_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.exists():
        return path

    fallback = LOG_DIR / raw_path
    if fallback.exists():
        return fallback

    raise FileNotFoundError(f"Rerun file not found: {raw_path}")


def _load_rerun_specs(raw_path: str) -> list[TestRunSpec]:
    path = _resolve_rerun_path(raw_path)
    entries = read_jsonl(path)
    if not entries:
        raise ValueError(f"No entries found in rerun file: {path}")

    specs: list[TestRunSpec] = []
    for entry in entries:
        case_name = entry.get("case")
        model = entry.get("model")
        use_few_shot = entry.get("use_few_shot")
        pdf_strategy = entry.get("pdf_strategy") or entry.get("page_finder_strategy") or "hybrid"

        if case_name is None or model is None or use_few_shot is None:
            raise ValueError(f"Invalid rerun entry missing required fields: {entry}")

        case_dir = CASES_DIR / str(case_name)
        if not case_dir.exists():
            raise ValueError(f"Rerun case directory does not exist: {case_dir}")

        if not isinstance(use_few_shot, bool):
            raise ValueError(f"Invalid rerun use_few_shot value: {use_few_shot!r}")

        specs.append(
            TestRunSpec(
                case_dir=case_dir,
                model=str(model),
                use_few_shot=use_few_shot,
                pdf_strategy=str(pdf_strategy),
            )
        )

    return specs


def pytest_generate_tests(metafunc):
    """Dynamically parametrize tests based on CLI options."""
    if "run_spec" not in metafunc.fixturenames:
        return

    rerun_path = metafunc.config.getoption("rerun")
    if rerun_path:
        run_specs = _load_rerun_specs(rerun_path)
    else:
        raw_models = metafunc.config.getoption("models")
        if not raw_models:
            raise ValueError(
                "No models specified. Use --models vendor:model_name[,vendor:model_name,...]"
            )
        models = [m.strip() for m in raw_models.split(",") if m.strip()]
        if not models:
            raise ValueError("No valid models specified")

        few_shot_option = metafunc.config.getoption("use_few_shot")
        if few_shot_option == "false":
            use_few_shot_values = [False]
        elif few_shot_option == "true":
            use_few_shot_values = [True]
        elif few_shot_option == "both":
            use_few_shot_values = [False, True]
        else:
            raise ValueError(f"Invalid use-few-shot value: {few_shot_option}")

        raw_strategies = metafunc.config.getoption("pdf_strategy")
        valid_strategies = {"toc", "keyword", "regex", "hybrid", "category", "llm"}
        strategies = [s.strip() for s in raw_strategies.split(",") if s.strip()]

        invalid = [s for s in strategies if s not in valid_strategies]
        if invalid:
            raise ValueError(f"Invalid pdf-strategy values: {invalid}. Valid choices: {valid_strategies}")

        if not strategies:
            strategies = ["hybrid"]  # default

        run_specs = [
            TestRunSpec(case_dir=case_dir, model=model, use_few_shot=use_few_shot, pdf_strategy=pdf_strategy)
            for case_dir in discover_cases()
            for use_few_shot in use_few_shot_values
            for pdf_strategy in strategies
            for model in models
        ]

    metafunc.parametrize("run_spec", run_specs, ids=lambda spec: spec.node_id)


def pytest_configure(config):
    """Prime the few-shot embedding cache once in the controller process."""
    if getattr(config, "workerinput", None) is not None:
        return

    from tests.result_logging import set_run_id

    set_run_id(datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"))

    rerun_path = config.getoption("rerun")
    needs_few_shot = config.getoption("use_few_shot") != "false"
    if rerun_path:
        needs_few_shot = any(spec.use_few_shot for spec in _load_rerun_specs(rerun_path))

    if not needs_few_shot:
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
