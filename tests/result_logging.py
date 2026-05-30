from datetime import UTC, datetime
import json
import os
from pathlib import Path


LOG_DIR = Path(os.getenv("LLM_LOGS_DIR", "tests/logs"))
RUN_ID_ENV = "LLM_REQ_RUN_ID"
RUN_ID_FILE = LOG_DIR / "current_run_id.txt"
_RUN_ID_CACHE: str | None = None


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def set_run_id(run_id: str) -> None:
    global _RUN_ID_CACHE
    _RUN_ID_CACHE = run_id
    os.environ[RUN_ID_ENV] = run_id
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUN_ID_FILE.write_text(run_id, encoding="utf-8")


def clear_run_id() -> None:
    global _RUN_ID_CACHE
    _RUN_ID_CACHE = None
    os.environ.pop(RUN_ID_ENV, None)
    if RUN_ID_FILE.exists():
        RUN_ID_FILE.unlink()


def _generate_run_id() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _resolve_run_id() -> str:
    global _RUN_ID_CACHE
    if _RUN_ID_CACHE:
        return _RUN_ID_CACHE

    env_run_id = os.getenv(RUN_ID_ENV)
    if env_run_id:
        _RUN_ID_CACHE = env_run_id
        return env_run_id

    if RUN_ID_FILE.exists():
        run_id = RUN_ID_FILE.read_text(encoding="utf-8").strip()
        if run_id:
            _RUN_ID_CACHE = run_id
            return run_id

    run_id = _generate_run_id()
    set_run_id(run_id)
    return run_id


def get_run_id() -> str:
    return _resolve_run_id()


def _results_file() -> Path:
    return LOG_DIR / f"{get_run_id()}_results.jsonl"


def _failures_file() -> Path:
    return LOG_DIR / f"{get_run_id()}_failures.jsonl"


def _pending_file() -> Path:
    return LOG_DIR / f"{get_run_id()}_pending.jsonl"


def _append_jsonl(path: Path, entry: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, cls=DateTimeEncoder) + "\n")


def log_result(entry: dict) -> None:
    _append_jsonl(_results_file(), entry)


def log_failure(entry: dict) -> None:
    _append_jsonl(_failures_file(), entry)


def log_pending(entry: dict) -> None:
    _append_jsonl(_pending_file(), entry)


def read_jsonl(path: Path) -> list[dict]:
    entries: list[dict] = []
    if not path.exists():
        return entries

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))

    return entries
