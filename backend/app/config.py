"""
Configuration — loads .env and exposes typed constants.
All thresholds and model names live here, not scattered across modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# Disable gRPC fork support to avoid deadlocks on macOS / multithreaded servers
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

from dotenv import load_dotenv

# Project root (two levels up from this file: backend/app/config.py → project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


# ── Google Gemini ──────────────────────────────────────────────────────────────
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Fallback chain: if primary model hits quota (429), try these in order
# All must be valid Gemini model IDs; configurable via env
_fallback_env = os.getenv("FALLBACK_MODELS", "")
FALLBACK_MODELS: list[str] = (
    [m.strip() for m in _fallback_env.split(",") if m.strip()]
    if _fallback_env
    else [GEMINI_MODEL, "gemini-2.5-flash", "gemini-2.5-flash-lite"]
)

# ── Embedding model (local, CPU) ───────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# ── Chunking ───────────────────────────────────────────────────────────────────
MAX_CHUNK_TOKENS: int = int(os.getenv("MAX_CHUNK_TOKENS", "800"))
CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "100"))

# ── Extraction batching ────────────────────────────────────────────────────────
# How many chunks to send in a single LLM call.
# Higher = fewer API calls (faster, less quota pressure); lower = smaller prompts.
# 6 is a safe default: ~4800 tokens of chunk text + prompt fits well within limits.
EXTRACTION_BATCH_SIZE: int = int(os.getenv("EXTRACTION_BATCH_SIZE", "6"))

# ── Canonicalization thresholds ────────────────────────────────────────────────
CANON_AUTO_THRESHOLD: float = float(os.getenv("CANON_AUTO_THRESHOLD", "0.92"))
CANON_TIEBREAK_THRESHOLD: float = float(os.getenv("CANON_TIEBREAK_THRESHOLD", "0.75"))

# ── Evidence verification ──────────────────────────────────────────────────────
EVIDENCE_VERIFICATION_THRESHOLD: int = int(os.getenv("EVIDENCE_VERIFICATION_THRESHOLD", "85"))

# ── Storage ────────────────────────────────────────────────────────────────────
_raw_db = Path(os.getenv("DB_PATH", "data/factstore.db"))
DB_PATH: Path = _raw_db if _raw_db.is_absolute() else (PROJECT_ROOT / _raw_db).resolve()

_raw_trace = Path(os.getenv("TRACE_LOG_PATH", "data/traces.jsonl"))
TRACE_LOG_PATH: Path = _raw_trace if _raw_trace.is_absolute() else (PROJECT_ROOT / _raw_trace).resolve()

# ── Server ─────────────────────────────────────────────────────────────────────
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "8501"))

# Ensure data directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

