"""
Direct seeding script — bypasses HTTP and runs the pipeline in-process.
Use this instead of seed_demo.py when the HTTP timeout is too short for
large PDFs or heavy LLM quota limits.

Usage:
    python3.11 scripts/seed_direct.py
"""

from __future__ import annotations

import sys
import time
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.canonicalization.canonicalizer import canonicalize_fact
from backend.app.canonicalization.embedder import embed_text
from backend.app.config import DB_PATH
from backend.app.extraction.fact_extractor import extract_facts_from_chunks
from backend.app.guardrails.evidence_verifier import verify_fact_evidence
from backend.app.ingestion.chunker import chunk_document
from backend.app.ingestion.pdf_parser import parse_pdf
from backend.app.ingestion.table_extractor import (
    build_section_map_from_pages,
    extract_tables_from_pdf,
)
from backend.app.models.schema import Document
from backend.app.reasoning.relationship_engine import reason_about_fact
from backend.app.storage.db import init_db
from backend.app.storage.repository import (
    count_facts_for_document,
    delete_document,
    document_exists,
    get_chunk,
    get_chunks_for_document,
    get_document_by_filename,
    insert_chunk,
    insert_document,
    insert_fact,
)

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

STARTER_PDFS = [
    Path("starter-datasets/delhivery/03-delhivery-q4-fy24-earnings-presentation.pdf"),
    Path("starter-datasets/india-macroeconomy/02-rbi-annual-report-2024-25-excerpt.pdf"),
    Path("starter-datasets/india-macroeconomy/03-imf-india-2025-article-iv-excerpt.pdf"),
    Path("starter-datasets/india-macroeconomy/01-india-economic-survey-2024-25-excerpt.pdf"),
    Path("starter-datasets/delhivery/01-delhivery-prospectus-2022-excerpt.pdf"),
    Path("starter-datasets/delhivery/02-delhivery-annual-report-fy24-excerpt.pdf"),
]


def ingest_pdf(pdf_path: Path) -> dict:
    filename = pdf_path.name
    print(f"\n-> Ingesting: {filename}")

    if not pdf_path.exists():
        print(f"  SKIP — file not found: {pdf_path}")
        return {}

    if document_exists(filename, DB_PATH):
        existing_doc = get_document_by_filename(filename, DB_PATH)
        if existing_doc:
            counts = count_facts_for_document(existing_doc.id, DB_PATH)
            total_facts = (
                counts.get("verified", 0)
                + counts.get("unverified", 0)
                + counts.get("extraction_failed", 0)
            )
            if total_facts > 0:
                print(f"  SKIP — already ingested with {total_facts} facts.")
                return {}
            else:
                print(f"  Existing document record for {filename} has 0 facts. Cleaning up to re-ingest...")
                delete_document(existing_doc.id, DB_PATH)

    # Copy PDF to upload dir for page-image serving
    dest = UPLOAD_DIR / filename
    if not dest.exists():
        dest.write_bytes(pdf_path.read_bytes())

    t0 = time.monotonic()

    # 1. Parse
    print("  Parsing PDF …")
    pages, page_count = parse_pdf(dest)

    # 2. Create document record
    doc_id = str(uuid.uuid4())
    doc = Document(
        id=doc_id,
        filename=filename,
        uploaded_at=datetime.now(timezone.utc),
        page_count=page_count,
    )
    insert_document(doc, DB_PATH)

    # 3. Table extraction + text chunking
    section_map = build_section_map_from_pages(pages)
    table_chunks, table_bboxes = extract_tables_from_pdf(dest, doc_id, section_map)
    text_chunks = chunk_document(pages, doc_id, table_bboxes)
    all_chunks = text_chunks + table_chunks
    for chunk in all_chunks:
        insert_chunk(chunk, DB_PATH)
    chunk_text_map = {c.id: c.text for c in all_chunks}
    print(f"  {len(all_chunks)} chunks created.")

    # 4. Fact extraction (batched — fewer LLM calls, faster)
    print("  Extracting facts (batched LLM calls)...")
    all_facts = []
    chunk_facts = extract_facts_from_chunks(all_chunks, filename)
    for fact in chunk_facts:
        fact = verify_fact_evidence(fact, chunk_text_map.get(fact.chunk_id, ""))
        if fact.verification_status != "extraction_failed":
            emb = embed_text(f"{fact.entity} {fact.attribute}: {fact.value}")
        else:
            emb = None
        insert_fact(fact, emb, DB_PATH)
        all_facts.append(fact)
    print(f"  {len(all_facts)} facts extracted.")

    # 5. Canonicalize
    print("  Canonicalizing...")
    for fact in all_facts:
        if fact.verification_status != "extraction_failed":
            chunk = get_chunk(fact.chunk_id, DB_PATH)
            chunk_text = chunk.text if chunk else ""
            fact.canonical_key = canonicalize_fact(fact, chunk_text)

    # 6. Relationship reasoning
    print("  Reasoning about cross-document relationships...")
    valid_facts = [f for f in all_facts if f.verification_status != "extraction_failed"]
    with ThreadPoolExecutor(max_workers=3) as executor:
        rel_lists = list(executor.map(lambda f: reason_about_fact(f, DB_PATH), valid_facts))
    new_rels = [r for rl in rel_lists for r in rl]
    print(f"  {len(new_rels)} new relationships found.")

    elapsed = time.monotonic() - t0
    counts = count_facts_for_document(doc_id, DB_PATH)
    print(
        f"  DONE in {elapsed:.1f}s | facts={len(all_facts)} "
        f"(verified={counts.get('verified',0)}, unverified={counts.get('unverified',0)}, "
        f"failed={counts.get('extraction_failed',0)}) | relationships={len(new_rels)}"
    )
    return {"facts": len(all_facts), "relationships": len(new_rels)}


def main() -> None:
    init_db(DB_PATH)
    project_root = Path(__file__).resolve().parents[1]
    print(f"Seeding {len(STARTER_PDFS)} PDFs from {project_root}...")

    totals = {"facts": 0, "relationships": 0}
    for rel_pdf in STARTER_PDFS:
        abs_path = project_root / rel_pdf
        result = ingest_pdf(abs_path)
        totals["facts"] += result.get("facts", 0)
        totals["relationships"] += result.get("relationships", 0)

    print(f"\n{'='*60}")
    print("Seeding complete.")
    print(f"  Total facts extracted  : {totals['facts']}")
    print(f"  Total relationships    : {totals['relationships']}")
    print(f"\nOpen http://localhost:8501 to explore the results.")


if __name__ == "__main__":
    main()
