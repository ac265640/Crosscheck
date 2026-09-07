"""
Local JSONL trace log for LLM calls.
Every LLM call appends one JSON line to data/traces.jsonl.
Queryable and viewable in the Streamlit UI as a "Reasoning Trace" tab.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.app.config import TRACE_LOG_PATH

_lock = threading.Lock()


def log_llm_call(
    call_type: str,
    model: str,
    input_summary: str,
    output_summary: str,
    latency_ms: float,
    success: bool,
    extra: dict | None = None,
) -> None:
    """Append a structured log entry to traces.jsonl (thread-safe)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_type": call_type,
        "model": model,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "latency_ms": round(latency_ms, 2),
        "success": success,
    }
    if extra:
        entry.update(extra)

    TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def read_recent_traces(n: int = 50) -> list[dict]:
    """Read the N most recent trace entries from traces.jsonl."""
    if not TRACE_LOG_PATH.exists():
        return []

    lines = []
    with open(TRACE_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lines.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return lines[-n:]
