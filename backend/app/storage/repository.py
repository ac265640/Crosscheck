"""
CRUD repository layer.
All DB access goes through these functions — no raw SQL in business logic.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from backend.app.config import DB_PATH
from backend.app.models.schema import Chunk, Document, Fact, Relationship
from backend.app.storage.db import get_connection


# ── Documents ──────────────────────────────────────────────────────────────────

def insert_document(doc: Document, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO documents (id, filename, uploaded_at, page_count) VALUES (?,?,?,?)",
            (doc.id, doc.filename, doc.uploaded_at.isoformat(), doc.page_count),
        )
    conn.close()


def get_document(doc_id: str, db_path: Path = DB_PATH) -> Optional[Document]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return Document(
        id=row["id"],
        filename=row["filename"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        page_count=row["page_count"],
    )


def list_documents(db_path: Path = DB_PATH) -> list[Document]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()
    conn.close()
    return [
        Document(
            id=r["id"],
            filename=r["filename"],
            uploaded_at=datetime.fromisoformat(r["uploaded_at"]),
            page_count=r["page_count"],
        )
        for r in rows
    ]


def document_exists(filename: str, db_path: Path = DB_PATH) -> bool:
    conn = get_connection(db_path)
    row = conn.execute("SELECT id FROM documents WHERE filename = ?", (filename,)).fetchone()
    conn.close()
    return row is not None


def get_document_by_filename(filename: str, db_path: Path = DB_PATH) -> Optional[Document]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM documents WHERE filename = ?", (filename,)).fetchone()
    conn.close()
    if row is None:
        return None
    return Document(
        id=row["id"],
        filename=row["filename"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        page_count=row["page_count"],
    )


def delete_document(doc_id: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """DELETE FROM relationships 
               WHERE fact_id_a IN (SELECT id FROM facts WHERE document_id = ?)
                  OR fact_id_b IN (SELECT id FROM facts WHERE document_id = ?)""",
            (doc_id, doc_id),
        )
        conn.execute("DELETE FROM facts WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.close()


# ── Chunks ─────────────────────────────────────────────────────────────────────

def insert_chunk(chunk: Chunk, db_path: Path = DB_PATH) -> None:
    bbox = chunk.bbox
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO chunks
               (id, document_id, page_number, bbox_x0, bbox_y0, bbox_x1, bbox_y1, text, section_title)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                chunk.id,
                chunk.document_id,
                chunk.page_number,
                bbox[0] if bbox else None,
                bbox[1] if bbox else None,
                bbox[2] if bbox else None,
                bbox[3] if bbox else None,
                chunk.text,
                chunk.section_title,
            ),
        )
    conn.close()


def get_chunk(chunk_id: str, db_path: Path = DB_PATH) -> Optional[Chunk]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_chunk(row)


def get_chunks_for_document(doc_id: str, db_path: Path = DB_PATH) -> list[Chunk]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM chunks WHERE document_id = ? ORDER BY page_number", (doc_id,)
    ).fetchall()
    conn.close()
    return [_row_to_chunk(r) for r in rows]


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    bbox = None
    if row["bbox_x0"] is not None:
        bbox = (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"])
    return Chunk(
        id=row["id"],
        document_id=row["document_id"],
        page_number=row["page_number"],
        bbox=bbox,
        text=row["text"],
        section_title=row["section_title"],
    )


# ── Facts ──────────────────────────────────────────────────────────────────────

def insert_fact(fact: Fact, embedding: Optional[np.ndarray] = None, db_path: Path = DB_PATH) -> None:
    bbox = fact.bbox
    emb_blob = embedding.tobytes() if embedding is not None else None
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO facts
               (id, document_id, chunk_id, entity, attribute, value, unit, scope,
                verbatim_evidence, page_number, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
                canonical_key, confidence, verification_status, embedding)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fact.id,
                fact.document_id,
                fact.chunk_id,
                fact.entity,
                fact.attribute,
                fact.value,
                fact.unit,
                json.dumps(fact.scope),
                fact.verbatim_evidence,
                fact.page_number,
                bbox[0] if bbox else None,
                bbox[1] if bbox else None,
                bbox[2] if bbox else None,
                bbox[3] if bbox else None,
                fact.canonical_key,
                fact.confidence,
                fact.verification_status,
                emb_blob,
            ),
        )
    conn.close()


def update_fact_canonical_key(fact_id: str, canonical_key: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            "UPDATE facts SET canonical_key = ? WHERE id = ?", (canonical_key, fact_id)
        )
    conn.close()


def get_fact(fact_id: str, db_path: Path = DB_PATH) -> Optional[Fact]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_fact(row)


def list_facts_for_document(doc_id: str, db_path: Path = DB_PATH) -> list[Fact]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM facts WHERE document_id = ? ORDER BY page_number", (doc_id,)
    ).fetchall()
    conn.close()
    return [_row_to_fact(r) for r in rows]


def list_facts_for_canonical_key(
    canonical_key: str, db_path: Path = DB_PATH
) -> list[tuple[Fact, Optional[np.ndarray]]]:
    """Return (fact, embedding) pairs for a canonical key."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM facts WHERE canonical_key = ?", (canonical_key,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        emb = np.frombuffer(r["embedding"], dtype=np.float32) if r["embedding"] else None
        result.append((_row_to_fact(r), emb))
    return result


def list_all_facts_with_embeddings(
    db_path: Path = DB_PATH,
) -> list[tuple[Fact, Optional[np.ndarray]]]:
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM facts").fetchall()
    conn.close()
    result = []
    for r in rows:
        emb = np.frombuffer(r["embedding"], dtype=np.float32) if r["embedding"] else None
        result.append((_row_to_fact(r), emb))
    return result


def count_facts_for_document(doc_id: str, db_path: Path = DB_PATH) -> dict:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT verification_status, COUNT(*) as cnt
           FROM facts WHERE document_id = ?
           GROUP BY verification_status""",
        (doc_id,),
    ).fetchall()
    conn.close()
    counts = {"verified": 0, "unverified": 0, "extraction_failed": 0}
    for r in rows:
        counts[r["verification_status"]] = r["cnt"]
    return counts


def _row_to_fact(row: sqlite3.Row) -> Fact:
    bbox = None
    if row["bbox_x0"] is not None:
        bbox = (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"])
    return Fact(
        id=row["id"],
        document_id=row["document_id"],
        chunk_id=row["chunk_id"],
        entity=row["entity"],
        attribute=row["attribute"],
        value=row["value"],
        unit=row["unit"],
        scope=json.loads(row["scope"]),
        verbatim_evidence=row["verbatim_evidence"],
        page_number=row["page_number"],
        bbox=bbox,
        canonical_key=row["canonical_key"],
        confidence=row["confidence"],
        verification_status=row["verification_status"],
    )


# ── Relationships ──────────────────────────────────────────────────────────────

def insert_relationship(rel: Relationship, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO relationships
               (id, fact_id_a, fact_id_b, relationship_type, explanation, confidence)
               VALUES (?,?,?,?,?,?)""",
            (rel.id, rel.fact_id_a, rel.fact_id_b, rel.relationship_type, rel.explanation, rel.confidence),
        )
    conn.close()


def get_relationships_for_fact(fact_id: str, db_path: Path = DB_PATH) -> list[Relationship]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM relationships WHERE fact_id_a = ? OR fact_id_b = ?",
        (fact_id, fact_id),
    ).fetchall()
    conn.close()
    return [_row_to_relationship(r) for r in rows]


def list_relationships_by_type(
    rel_type: str, limit: int = 10, db_path: Path = DB_PATH
) -> list[Relationship]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM relationships WHERE relationship_type = ? LIMIT ?", (rel_type, limit)
    ).fetchall()
    conn.close()
    return [_row_to_relationship(r) for r in rows]


def _row_to_relationship(row: sqlite3.Row) -> Relationship:
    return Relationship(
        id=row["id"],
        fact_id_a=row["fact_id_a"],
        fact_id_b=row["fact_id_b"],
        relationship_type=row["relationship_type"],
        explanation=row["explanation"],
        confidence=row["confidence"],
    )


# ── Canonical key registry ─────────────────────────────────────────────────────

def insert_canonical_key(
    canonical_key: str,
    entity: str,
    attribute: str,
    embedding: np.ndarray,
    db_path: Path = DB_PATH,
) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO canonical_keys (canonical_key, entity, attribute, embedding)
               VALUES (?,?,?,?)""",
            (canonical_key, entity, attribute, embedding.tobytes()),
        )
    conn.close()


def list_canonical_keys(
    db_path: Path = DB_PATH,
) -> list[tuple[str, str, str, np.ndarray]]:
    """Returns list of (canonical_key, entity, attribute, embedding)."""
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM canonical_keys").fetchall()
    conn.close()
    return [
        (r["canonical_key"], r["entity"], r["attribute"], np.frombuffer(r["embedding"], dtype=np.float32))
        for r in rows
    ]
