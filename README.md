# Fact Knowledge Layer — Superjoin VIT 2026 Assignment

A system that ingests arbitrary PDFs, extracts factual claims with grounded evidence, canonicalises them, and reasons about how facts relate across documents: **corroboration**, **contradiction**, **reconciled context**, or **uncertain**.

---

## 1. Setup and Run Instructions

### Prerequisites

- Python 3.11+
- A Google Gemini API key

### Install

```bash
git clone https://github.com/ac265640/Crosscheck.git
cd Crosscheck
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env and set your GOOGLE_API_KEY
```

### Run (backend + frontend together)

```bash
bash scripts/run_dev.sh
```

This starts:
- FastAPI backend on http://localhost:8000
- Streamlit frontend on http://localhost:8501

### Seed the demo dataset

In a separate terminal (after the servers are running):

```bash
python scripts/seed_demo.py
```

This ingests all 6 starter PDFs through the full pipeline and populates the database for demo.

### Evaluate

```bash
python eval/run_eval.py
```

Prints precision / recall / F1 against hand-curated ground-truth facts.

### Tests

```bash
pytest tests/ -v
```

---

## 2. Video Demo

🎥 [Demo video link — to be added after recording]

---

## 3. Approach

### Architecture

```
PDF Upload
  → PyMuPDF parsing (text spans with font-size / bbox)
  → Section-aware chunking (~800 tok, ~100 overlap)
  → pdfplumber table detection → markdown table chunks
  → Google Gemini fact extraction (open-schema JSON, Pydantic-validated, 1 retry)
  → rapidfuzz evidence verification (partial_ratio ≥ 85 → "verified")
  → sentence-transformers embedding (BAAI/bge-small-en-v1.5, CPU)
  → Cosine similarity canonicalisation (three-tier: auto / LLM tiebreak / new key)
  → BM25 + cosine hybrid retrieval (Reciprocal Rank Fusion)
  → Gemini relationship reasoning (corroboration / contradiction / reconciled_context / uncertain)
  → SQLite storage
  → FastAPI REST API
  → Streamlit UI
```

### Key decisions and trade-offs

| Decision | Alternative | Reason chosen |
|----------|-------------|---------------|
| **SQLite** | Postgres / graph DB | Zero infrastructure; numpy embedding blobs; brute-force cosine is fast enough at this scale |
| **Local sentence-transformers** | Hosted embeddings API | No extra API key or cost; runs on CPU |
| **No cross-encoder re-ranker** | ColBERT / monoT5 | Small candidate sets — LLM reasons over all of them directly |
| **Local JSONL trace log** | Langfuse | No extra dependency; human-readable; sufficient for demo |
| **Google Gemini** | Anthropic Claude | User-provided GOOGLE_API_KEY |

### AI tools used

- Google Gemini 1.5 Flash — fact extraction, canonicalisation tiebreak, relationship reasoning
- Antigravity (coding assistant) — code generation and scaffolding

---

## 4. Limitations and Next Steps

### Known failure modes

- Table extraction misses complex multi-header tables (falls back to text chunking)
- Entity disambiguation can create duplicate canonical keys for near-identical phrasings
- Dense financial tables may yield fewer facts than expected due to boilerplate pre-filter
- Uncertain relationships are expected when scope metadata is absent — this is correct behaviour

### Next steps

1. FAISS / pgvector vector index at higher scale
2. Cross-encoder re-ranker for candidate ranking
3. Richer table extraction (camelot / unstructured.io)
4. React frontend with annotation tools
5. Langfuse for production observability

---

## 5. Additional Notes

- All pipeline code in `backend/app/` is document-agnostic — no hardcoded facts or filenames.
- `eval/labeled_facts.json` contains 15 hand-curated ground-truth facts.
- `docs/decisions.md` has detailed trade-off reasoning.
- `.env` is gitignored; copy from `.env.example`.
