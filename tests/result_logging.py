from datetime import UTC, datetime
import json
from pathlib import Path


LOG_DIR = Path("tests/logs")
RUN_ID = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")

RESULTS_FILE = LOG_DIR / f"{RUN_ID}_results.jsonl"
FAILURES_FILE = LOG_DIR / f"{RUN_ID}_failures.jsonl"


def get_run_id() -> str:
    return RUN_ID


def log_result(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with RESULTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_failure(entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with FAILURES_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")