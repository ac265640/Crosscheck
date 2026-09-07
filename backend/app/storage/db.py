"""
SQLite schema creation and connection management.
Tables mirror the Pydantic models 1:1 with foreign key constraints.
Fact embeddings stored as BLOB (numpy.tobytes() / numpy.frombuffer()).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.config import DB_PATH


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with foreign keys enabled and row_factory set."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    conn = get_connection(Path(db_path))
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id            TEXT PRIMARY KEY,
                filename      TEXT NOT NULL,
                uploaded_at   TEXT NOT NULL,
                page_count    INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id            TEXT PRIMARY KEY,
                document_id   TEXT NOT NULL REFERENCES documents(id),
                page_number   INTEGER NOT NULL,
                bbox_x0       REAL,
                bbox_y0       REAL,
                bbox_x1       REAL,
                bbox_y1       REAL,
                text          TEXT NOT NULL,
                section_title TEXT
            );

            CREATE TABLE IF NOT EXISTS facts (
                id                  TEXT PRIMARY KEY,
                document_id         TEXT NOT NULL REFERENCES documents(id),
                chunk_id            TEXT NOT NULL REFERENCES chunks(id),
                entity              TEXT NOT NULL,
                attribute           TEXT NOT NULL,
                value               TEXT NOT NULL,
                unit                TEXT,
                scope               TEXT NOT NULL DEFAULT '{}',
                verbatim_evidence   TEXT NOT NULL,
                page_number         INTEGER NOT NULL,
                bbox_x0             REAL,
                bbox_y0             REAL,
                bbox_x1             REAL,
                bbox_y1             REAL,
                canonical_key       TEXT,
                confidence          REAL NOT NULL DEFAULT 1.0,
                verification_status TEXT NOT NULL DEFAULT 'unverified',
                embedding           BLOB
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id                TEXT PRIMARY KEY,
                fact_id_a         TEXT NOT NULL REFERENCES facts(id),
                fact_id_b         TEXT NOT NULL REFERENCES facts(id),
                relationship_type TEXT NOT NULL,
                explanation       TEXT NOT NULL,
                confidence        REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS canonical_keys (
                canonical_key TEXT PRIMARY KEY,
                entity        TEXT NOT NULL,
                attribute     TEXT NOT NULL,
                embedding     BLOB NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_id    ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_facts_document_id     ON facts(document_id);
            CREATE INDEX IF NOT EXISTS idx_facts_chunk_id        ON facts(chunk_id);
            CREATE INDEX IF NOT EXISTS idx_facts_canonical_key   ON facts(canonical_key);
            CREATE INDEX IF NOT EXISTS idx_relationships_fact_a  ON relationships(fact_id_a);
            CREATE INDEX IF NOT EXISTS idx_relationships_fact_b  ON relationships(fact_id_b);
            """
        )
    conn.close()
