"""
DB repair script.
Fixes pipeline execution gaps from interrupted runs:

1. Detects and deletes document records with 0 facts (so seed_direct can re-ingest)
2. Detects document records that are NOT in the DB but have PDFs in uploads/
3. Re-canonicalizes facts that are missing canonical_keys
4. Re-runs relationship reasoning for newly-canonicalized facts

Usage:
    python3 scripts/repair_db.py
Then run:
    python3 scripts/seed_direct.py   (to re-ingest missing documents)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

from concurrent.futures import ThreadPoolExecutor

from backend.app.config import DB_PATH
from backend.app.storage.db import get_connection, init_db
from backend.app.storage.repository import (
    count_facts_for_document,
    delete_document,
    get_chunk,
    list_all_facts_with_embeddings,
    list_documents,
)
from backend.app.canonicalization.canonicalizer import canonicalize_fact
from backend.app.canonicalization.embedder import embed_text
from backend.app.reasoning.relationship_engine import reason_about_fact
from backend.app.storage.repository import insert_fact, insert_relationship
from backend.app.models.schema import Fact


def fix_empty_documents() -> list[str]:
    """Delete document records that have 0 facts so they can be re-ingested."""
    docs = list_documents(DB_PATH)
    deleted_names = []
    for doc in docs:
        counts = count_facts_for_document(doc.id, DB_PATH)
        total = sum(counts.values())
        if total == 0:
            print(f"  🗑  Deleting empty doc record: {doc.filename} (0 facts)")
            delete_document(doc.id, DB_PATH)
            deleted_names.append(doc.filename)
    return deleted_names


def fix_missing_canonical_keys() -> list[Fact]:
    """Re-canonicalize facts that are missing canonical_keys."""
    conn = get_connection(DB_PATH)
    rows = conn.execute(
        """SELECT f.id, f.chunk_id, f.document_id, f.entity, f.attribute, f.verification_status
           FROM facts f 
           WHERE f.canonical_key IS NULL 
             AND f.verification_status != 'extraction_failed'"""
    ).fetchall()
    conn.close()

    if not rows:
        print("  ✅ All facts already have canonical_keys.")
        return []

    print(f"  Found {len(rows)} facts missing canonical_keys. Re-canonicalizing...")

    # Get full fact objects
    all_pairs = list_all_facts_with_embeddings(DB_PATH)
    fact_by_id = {f.id: f for f, _ in all_pairs}

    facts_to_reason = []
    done = 0
    errors = 0

    for row in rows:
        fact_id = row["id"]
        fact = fact_by_id.get(fact_id)
        if not fact:
            continue

        try:
            # Get chunk text for context
            chunk = get_chunk(fact.chunk_id, DB_PATH)
            chunk_text = chunk.text if chunk else ""

            # Re-canonicalize (will update DB record)
            canonical_key = canonicalize_fact(fact, chunk_text)
            fact.canonical_key = canonical_key
            facts_to_reason.append(fact)
            done += 1

            if done % 50 == 0:
                print(f"    ... {done}/{len(rows)} canonicalized")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    ⚠️  Error canonicalizing {fact_id[:8]}: {e}")

    print(f"  ✅ Canonicalized {done} facts ({errors} errors).")
    return facts_to_reason


def fix_missing_relationships(facts: list[Fact]) -> int:
    """Run relationship reasoning for facts that now have canonical_keys."""
    if not facts:
        return 0

    print(f"  Running relationship reasoning for {len(facts)} newly-canonicalized facts...")
    new_rels = 0
    errors = 0

    # Use single-threaded to avoid DB lock issues during repair
    for i, fact in enumerate(facts):
        try:
            rels = reason_about_fact(fact, DB_PATH)
            new_rels += len(rels)
            if rels:
                time.sleep(0.2)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    ⚠️  Reasoning error for {fact.id[:8]}: {e}")

        if (i + 1) % 100 == 0:
            print(f"    ... {i+1}/{len(facts)} processed, {new_rels} relationships found so far")

    print(f"  ✅ Found {new_rels} new relationships ({errors} errors).")
    return new_rels


def check_uploads_vs_db() -> None:
    """Report PDFs in data/uploads that aren't in the DB."""
    uploads_dir = Path("data/uploads")
    if not uploads_dir.exists():
        return

    docs = list_documents(DB_PATH)
    doc_filenames = {d.filename for d in docs}

    pdfs_in_uploads = {p.name for p in uploads_dir.glob("*.pdf")}
    missing_from_db = pdfs_in_uploads - doc_filenames
    if missing_from_db:
        print(f"\n  ⚠️  PDFs in data/uploads NOT in DB (will be ingested by seed_direct.py):")
        for name in sorted(missing_from_db):
            print(f"     - {name}")
    else:
        print("  ✅ All uploads are in the DB.")


def main() -> None:
    print("=" * 60)
    print("DB REPAIR SCRIPT")
    print("=" * 60)

    init_db(DB_PATH)

    print(f"\nDB path: {DB_PATH}")
    conn = get_connection(DB_PATH)
    docs_cnt = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    facts_cnt = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    rels_cnt = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    conn.close()
    print(f"Current state: {docs_cnt} docs, {facts_cnt} facts, {rels_cnt} relationships")

    print("\n─── Step 1: Remove empty document records ───")
    deleted = fix_empty_documents()
    if deleted:
        print(f"  Deleted {len(deleted)} empty records: {', '.join(deleted)}")
        print("  → These will be re-ingested by seed_direct.py")
    else:
        print("  No empty documents found.")

    print("\n─── Step 2: Fix missing canonical_keys ───")
    newly_canonicalized = fix_missing_canonical_keys()

    print("\n─── Step 3: Run relationship reasoning for newly-canonicalized facts ───")
    new_rels = fix_missing_relationships(newly_canonicalized)

    print("\n─── Step 4: Check uploads vs DB ───")
    check_uploads_vs_db()

    print("\n" + "=" * 60)
    conn = get_connection(DB_PATH)
    docs_cnt = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    facts_cnt = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    rels_cnt = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    # Check relationship type distribution
    rel_rows = conn.execute(
        "SELECT relationship_type, COUNT(*) FROM relationships GROUP BY relationship_type"
    ).fetchall()
    conn.close()
    print(f"After repair: {docs_cnt} docs, {facts_cnt} facts, {rels_cnt} relationships")
    print("Relationship type distribution:")
    for r in rel_rows:
        print(f"  {r[0]}: {r[1]}")

    if deleted or newly_canonicalized:
        print("\nNext step: run `python3 scripts/seed_direct.py` to ingest missing documents.")

    print("\nRepair complete.")


if __name__ == "__main__":
    main()
