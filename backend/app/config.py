"""
Configuration — loads .env and exposes typed constants.
All thresholds and model names live here, not scattered across modules.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")


# ── Google Gemini ──────────────────────────────────────────────────────────────
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# ── Embedding model (local, CPU) ───────────────────────────────────────────────
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# ── Chunking ───────────────────────────────────────────────────────────────────
MAX_CHUNK_TOKENS: int = int(os.getenv("MAX_CHUNK_TOKENS", "800"))
CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "100"))

# ── Canonicalization thresholds ────────────────────────────────────────────────
CANON_AUTO_THRESHOLD: float = float(os.getenv("CANON_AUTO_THRESHOLD", "0.92"))
CANON_TIEBREAK_THRESHOLD: float = float(os.getenv("CANON_TIEBREAK_THRESHOLD", "0.75"))

# ── Evidence verification ──────────────────────────────────────────────────────
EVIDENCE_VERIFICATION_THRESHOLD: int = int(os.getenv("EVIDENCE_VERIFICATION_THRESHOLD", "85"))

# ── Storage ────────────────────────────────────────────────────────────────────
DB_PATH: Path = Path(os.getenv("DB_PATH", "data/factstore.db"))
TRACE_LOG_PATH: Path = Path(os.getenv("TRACE_LOG_PATH", "data/traces.jsonl"))

# ── Server ─────────────────────────────────────────────────────────────────────
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "8501"))

# Ensure data directory exists
(DB_PATH.parent if not DB_PATH.parent.exists() else DB_PATH.parent).mkdir(
    parents=True, exist_ok=True
)
TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
