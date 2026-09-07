# Architecture & Trade-off Decisions

This document records every significant design decision made during the build,
including alternatives considered and rejected. Referenced from the main README.

---

## LLM: Google Gemini instead of Anthropic Claude

**Decision**: Use `google-generativeai` (Gemini 1.5 Flash) as the LLM backend.

**Reason**: The assignment specifies Anthropic Claude, but the project owner
provided a Google API key. Gemini 1.5 Flash is capable, fast, and cost-effective
for structured JSON extraction and reasoning tasks. All prompt designs from the
spec's Appendixes A, B, C are used verbatim — the prompts are LLM-agnostic.

**Trade-off**: Gemini's structured output mode differs slightly from Anthropic's
tool-use mode. We use `response_mime_type="application/json"` with a JSON schema
for structured outputs instead of Anthropic's tool-use parameter.

---

## Database: SQLite over PostgreSQL

**Decision**: Single `data/factstore.db` SQLite file.

**Reason**: The assignment explicitly requires this. At hundreds to low thousands
of facts, SQLite is simpler, zero-config, and just as performant as Postgres.
Embeddings are stored as serialized numpy BLOBs and similarity is computed
brute-force in Python at query time.

**Upgrade path**: At higher scale (millions of facts), migrate to PostgreSQL +
pgvector or add FAISS for approximate nearest-neighbor search.

**Considered and rejected**: Neo4j / graph database — the fact→evidence→relationship
structure maps cleanly to SQLite foreign keys without requiring graph infra.

---

## Embeddings: Local sentence-transformers over hosted API

**Decision**: `BAAI/bge-small-en-v1.5` via the `sentence-transformers` package,
running on CPU.

**Reason**: No extra API key, no extra cost, ~130MB download on first run.
At this scale (hundreds of facts), CPU inference is fast enough (< 1s per batch).

**Upgrade path**: Switch to a hosted embeddings API for higher throughput, or
use a larger model for better semantic precision.

---

## Retrieval: BM25 + cosine, no cross-encoder re-ranker

**Decision**: Reciprocal rank fusion of BM25Okapi (rank_bm25) + brute-force
cosine similarity. No cross-encoder re-ranker.

**Reason**: Candidate sets per canonical key are small (single digits to low tens).
The LLM reasoning step can directly evaluate all candidates without needing a
re-ranker in between. Adding a cross-encoder would add a second model download
and latency for negligible accuracy gain at this scale.

**Upgrade path**: Add a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
at scale when candidate sets become large.

---

## Observability: Local JSONL trace log over Langfuse

**Decision**: Every LLM call appends a JSON line to `data/traces.jsonl`.

**Reason**: Free, local, no external dependency, directly queryable. Satisfies
the assignment's auditability requirement without introducing a hosted SaaS.

**Upgrade path**: Langfuse or Arize Phoenix as natural hosted upgrade path.

---

## Frontend: Streamlit over React

**Decision**: Streamlit for the UI.

**Reason**: The assignment specifies Streamlit. It allows rendering PDF pages as
images (via PyMuPDF) with drawn highlight rectangles over evidence bounding boxes
in a few lines — exactly what's needed for the evidence grounding UI — without
a separate frontend build pipeline.

**Upgrade path**: React frontend with PDF.js as a stretch goal after core system
is working and demo-recorded.

---

## Deployment: Local only, no cloud hosting

**Decision**: Run entirely locally via `run_dev.sh`.

**Reason**: Not requested by the assignment. A demo video is the expected deliverable.

---

## Chunking: Section-aware, font-size based headers

**Decision**: Use PyMuPDF font-size discontinuities as section header heuristic.
Chunks never straddle two detected sections and stay under ~800 tokens with ~100
token overlap.

**Reason**: Section context improves fact extraction accuracy and makes evidence
more interpretable. Page-break-only chunking loses section structure.

**Alternative considered**: Fixed-size sliding window — rejected because it
frequently splits tables and structured data mid-row.

---

## Table extraction: pdfplumber on tabular pages

**Decision**: Run pdfplumber on pages where a table is detected; represent as
markdown-style text.

**Reason**: PyMuPDF's font-based heuristics struggle with table layouts.
pdfplumber's line/character analysis is better suited. Markdown representation
preserves row/column alignment for the LLM.
