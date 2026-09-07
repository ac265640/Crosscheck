"""
Seed demo script.
Ingests all 6 starter PDFs through the full pipeline in one run.
Usage:
    python scripts/seed_demo.py

The FastAPI backend must be running (bash scripts/run_dev.sh) before calling this.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

BACKEND_URL = "http://localhost:8000"

STARTER_PDFS = [
    Path("starter-datasets/delhivery/01-delhivery-prospectus-2022-excerpt.pdf"),
    Path("starter-datasets/delhivery/02-delhivery-annual-report-fy24-excerpt.pdf"),
    Path("starter-datasets/delhivery/03-delhivery-q4-fy24-earnings-presentation.pdf"),
    Path("starter-datasets/india-macroeconomy/01-india-economic-survey-2024-25-excerpt.pdf"),
    Path("starter-datasets/india-macroeconomy/02-rbi-annual-report-2024-25-excerpt.pdf"),
    Path("starter-datasets/india-macroeconomy/03-imf-india-2025-article-iv-excerpt.pdf"),
]


def wait_for_backend(timeout: int = 30) -> None:
    print(f"Waiting for backend at {BACKEND_URL} ...")
    for _ in range(timeout):
        try:
            r = requests.get(f"{BACKEND_URL}/documents", timeout=2)
            if r.status_code == 200:
                print("Backend is ready.")
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(1)
    print(f"ERROR: Backend did not respond within {timeout}s. Is it running?")
    sys.exit(1)


def ingest_pdf(pdf_path: Path) -> dict:
    print(f"\n→ Ingesting: {pdf_path.name}")
    if not pdf_path.exists():
        print(f"  SKIP — file not found: {pdf_path}")
        return {}
    t0 = time.monotonic()
    with open(pdf_path, "rb") as f:
        response = requests.post(
            f"{BACKEND_URL}/documents",
            files={"file": (pdf_path.name, f, "application/pdf")},
            timeout=300,  # fact extraction + reasoning can take a while
        )
    elapsed = time.monotonic() - t0

    if response.status_code == 409:
        print(f"  Already ingested — skipping.")
        return {}
    if response.status_code != 200:
        print(f"  ERROR {response.status_code}: {response.text[:300]}")
        return {}

    result = response.json()
    print(
        f"  ✓ {result.get('fact_count', 0)} facts extracted "
        f"({result.get('verified', 0)} verified, "
        f"{result.get('unverified', 0)} unverified, "
        f"{result.get('extraction_failed', 0)} failed) | "
        f"{result.get('new_relationships', 0)} new relationships | "
        f"{elapsed:.1f}s"
    )
    return result


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]

    wait_for_backend()
    print(f"\nSeeding {len(STARTER_PDFS)} PDFs from {project_root} ...")

    totals = {"facts": 0, "verified": 0, "relationships": 0}
    for pdf_path in STARTER_PDFS:
        abs_path = project_root / pdf_path
        result = ingest_pdf(abs_path)
        if result:
            totals["facts"] += result.get("fact_count", 0)
            totals["verified"] += result.get("verified", 0)
            totals["relationships"] += result.get("new_relationships", 0)

    print(f"\n{'='*60}")
    print(f"Seeding complete.")
    print(f"  Total facts extracted : {totals['facts']}")
    print(f"  Total verified        : {totals['verified']}")
    print(f"  Total relationships   : {totals['relationships']}")
    print(f"\nOpen http://localhost:8501 to explore the results.")


if __name__ == "__main__":
    main()
