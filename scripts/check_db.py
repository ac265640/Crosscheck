"""Quick DB introspection script."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import DB_PATH

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

try:
    print("\ndocs:", conn.execute("SELECT count(*) FROM documents").fetchone()[0])
    print("chunks:", conn.execute("SELECT count(*) FROM chunks").fetchone()[0])
    print("facts:", conn.execute("SELECT count(*) FROM facts").fetchone()[0])
    print("rels:", conn.execute("SELECT count(*) FROM relationships").fetchone()[0])
    print("canon_keys:", conn.execute("SELECT count(*) FROM canonical_keys").fetchone()[0])

    print("\nFacts by status:")
    for row in conn.execute("SELECT verification_status, count(*) FROM facts GROUP BY verification_status"):
        print(f"  {row[0]}: {row[1]}")

    print("\nRelationships by type:")
    for row in conn.execute("SELECT relationship_type, count(*) FROM relationships GROUP BY relationship_type"):
        print(f"  {row[0]}: {row[1]}")

    print("\nDocuments ingested:")
    for row in conn.execute("SELECT filename, page_count, uploaded_at FROM documents"):
        print(f"  {row[0]} ({row[1]} pages, {row[2]})")

    print("\nSample facts (first 3):")
    for row in conn.execute("SELECT id, entity, attribute, value, unit, verification_status, canonical_key FROM facts LIMIT 3"):
        print(f"  [{row[5]}] {row[1]} / {row[2]} = {row[3]} {row[4] or ''} (key: {row[6]})")

    print("\nSample relationships (first 3):")
    for row in conn.execute("SELECT id, fact_id_a, fact_id_b, relationship_type, confidence FROM relationships LIMIT 3"):
        print(f"  {row[3]} (conf={row[4]:.2f}): {row[1][:8]} vs {row[2][:8]}")

    print("\nChunks bbox coverage:")
    total_chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    bbox_chunks = conn.execute("SELECT count(*) FROM chunks WHERE bbox_x0 IS NOT NULL").fetchone()[0]
    print(f"  {bbox_chunks}/{total_chunks} chunks have bbox")

    null_page = conn.execute("SELECT count(*) FROM chunks WHERE page_number IS NULL").fetchone()[0]
    print(f"  {null_page} chunks with null page_number")

except Exception as e:
    print(f"Error: {e}")

conn.close()
