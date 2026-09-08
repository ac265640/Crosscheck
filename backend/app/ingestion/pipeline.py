"""
Full ingestion pipeline extracted from routes.py.
Accepts a job object so the caller (background task) can stream events.

Speed-optimised version:
  - Extraction: 20 parallel threads (was 5) → ~4× faster
  - Embedding: batched parallel execution (was serial)
  - Canonicalization: skips LLM via raised auto-threshold (config)
  - Reasoning: capped at 15 pairs (was 50), 10 threads
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.canonicalization.canonicalizer import canonicalize_fact
from backend.app.canonicalization.embedder import embed_text
from backend.app.config import DB_PATH, PROJECT_ROOT, RELATIONSHIP_REASONING_MAX_PAIRS
from backend.app.extraction.fact_extractor import extract_facts_from_chunk, BATCH_SIZE
from backend.app.guardrails.evidence_verifier import verify_fact_evidence
from backend.app.ingestion.chunker import chunk_document
from backend.app.ingestion.pdf_parser import parse_pdf
from backend.app.ingestion.table_extractor import (
    build_section_map_from_pages,
    extract_tables_from_pdf,
)
from backend.app.models.schema import Document, Fact, Relationship
from backend.app.reasoning.relationship_engine import reason_about_fact
from backend.app.storage.db import init_db
from backend.app.storage.repository import (
    count_facts_for_document,
    get_chunk,
    insert_chunk,
    insert_document,
    insert_fact,
)

_UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Tunable parallelism ───────────────────────────────────────────────────────
# Groq free tier has TPM limits — more threads = queuing = slower.
# 2 threads: ~2x over sequential while staying below TPM ceiling.
_EXTRACTION_WORKERS = 2
_REASONING_WORKERS  = 3


def run_pipeline(
    pdf_path: Path,
    filename: str,
    job: Any,  # Job object from backend.app.api.jobs
    db_path: Path = DB_PATH,
) -> str:
    """
    Run the full ingestion pipeline for one PDF.
    Emits progress via job.push(stage, pct, msg).
    Returns the document_id on success.
    """
    init_db(db_path)

    # ── 1. Parse PDF ──────────────────────────────────────────────────────────
    job.push("parsing", 5, f"Parsing {filename}...")
    pages, page_count = parse_pdf(pdf_path)
    job.push("parsing", 12, f"Parsed {page_count} pages.")

    # ── 2. Create document record ─────────────────────────────────────────────
    doc_id = str(uuid.uuid4())
    job.document_id = doc_id
    doc = Document(
        id=doc_id,
        filename=filename,
        uploaded_at=datetime.now(timezone.utc),
        page_count=page_count,
    )
    insert_document(doc, db_path)
    job.push("parsing", 14, f"Document registered.", doc_id=doc_id)

    # ── 3. Table extraction + text chunking ───────────────────────────────────
    job.push("chunking", 15, "Detecting tables and chunking text...")
    section_map = build_section_map_from_pages(pages)
    table_chunks, table_bboxes = extract_tables_from_pdf(pdf_path, doc_id, section_map)
    text_chunks = chunk_document(pages, doc_id, table_bboxes)
    all_chunks = text_chunks + table_chunks
    for chunk in all_chunks:
        insert_chunk(chunk, db_path)
    chunk_text_map = {c.id: c.text for c in all_chunks}
    job.push("chunking", 20, f"Created {len(all_chunks)} chunks ({len(table_chunks)} tables, {len(text_chunks)} text).")

    # ── 4. Fact extraction (2 threads — Groq TPM limit, more = queuing = slower) ──
    job.push("extracting", 22, f"Extracting facts from {len(all_chunks)} chunks...")
    completed = 0
    all_batch_facts: dict[str, list[Fact]] = {}

    with ThreadPoolExecutor(max_workers=_EXTRACTION_WORKERS) as executor:
        future_to_chunk = {
            executor.submit(extract_facts_from_chunk, c, filename): c
            for c in all_chunks
        }
        for future in as_completed(future_to_chunk):
            c = future_to_chunk[future]
            try:
                all_batch_facts[c.id] = future.result()
            except Exception:
                all_batch_facts[c.id] = []
            completed += 1
            if completed % 15 == 0 or completed == len(all_chunks):
                pct = 22 + int((completed / len(all_chunks)) * 28)
                job.push("extracting", min(pct, 49), f"Extracted {completed}/{len(all_chunks)} chunks...")

    # ── 5. Verify + embed (parallel embed, serial DB writes) ──────────────────
    job.push("verifying", 50, "Verifying evidence and embedding facts...")
    all_facts: list[Fact] = []
    facts_to_embed: list[Fact] = []

    # Flatten results in original chunk order
    for chunk in all_chunks:
        for fact in all_batch_facts.get(chunk.id, []):
            fact = verify_fact_evidence(fact, chunk_text_map.get(fact.chunk_id, ""))
            all_facts.append(fact)
            if fact.verification_status != "extraction_failed":
                facts_to_embed.append(fact)

    # Embed in parallel
    embeddings: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_fact = {
            executor.submit(embed_text, f"{f.entity} {f.attribute}: {f.value}"): f
            for f in facts_to_embed
        }
        for future in as_completed(future_to_fact):
            f = future_to_fact[future]
            try:
                embeddings[f.id] = future.result()
            except Exception:
                embeddings[f.id] = None

    # DB writes (must be serial for SQLite)
    for fact in all_facts:
        insert_fact(fact, embeddings.get(fact.id), db_path)

    n_facts = len(all_facts)
    n_verified = sum(1 for f in all_facts if f.verification_status == "verified")
    job.push("verifying", 55, f"Extracted {n_facts} facts ({n_verified} verified).")

    # ── 6. Canonicalize (serial — embeds cached, LLM mostly skipped by threshold) ─
    job.push("canonicalizing", 58, f"Canonicalizing {n_facts} facts...")
    valid_facts = [f for f in all_facts if f.verification_status != "extraction_failed"]
    for i, fact in enumerate(valid_facts):
        chunk_text = chunk_text_map.get(fact.chunk_id, "")
        fact.canonical_key = canonicalize_fact(fact, chunk_text)
        if i % 25 == 0 and i > 0:
            pct = 58 + int((i / max(len(valid_facts), 1)) * 15)
            job.push("canonicalizing", min(pct, 73), f"Canonicalized {i}/{len(valid_facts)} facts...")
    job.push("canonicalizing", 74, "Canonicalization complete.")

    # ── 7. Relationship reasoning (capped, parallel) ──────────────────────────
    max_pairs = RELATIONSHIP_REASONING_MAX_PAIRS
    job.push("reasoning", 76, f"Cross-document reasoning ({max_pairs} facts, {_REASONING_WORKERS} threads)...")
    reasoning_facts = valid_facts[:max_pairs]
    new_relationships: list[Relationship] = []

    with ThreadPoolExecutor(max_workers=_REASONING_WORKERS) as executor:
        rel_lists = list(
            executor.map(lambda f: reason_about_fact(f, db_path), reasoning_facts)
        )
    for rels in rel_lists:
        new_relationships.extend(rels)

    n_rels = len(new_relationships)
    job.push("reasoning", 95, f"Reasoning complete: {n_rels} relationships found.")

    # ── 8. Done ───────────────────────────────────────────────────────────────
    counts = count_facts_for_document(doc_id, db_path)
    job.push(
        "done",
        100,
        (
            f"Done! {counts.get('verified', 0)} verified + "
            f"{counts.get('unverified', 0)} unverified facts, "
            f"{n_rels} relationships."
        ),
        doc_id=doc_id,
    )
    return doc_id
