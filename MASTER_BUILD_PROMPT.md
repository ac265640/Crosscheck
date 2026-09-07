# Master Build Prompt — Fact Knowledge Layer (Superjoin VIT 2026 Assignment)

You are building a complete, working software project end-to-end inside this repository.
The problem statement PDF (`superjoin-vit-2026-assignment.pdf`) and the starter datasets
(`starter-datasets/delhivery/`, `starter-datasets/india-macroeconomy/`) already exist in
this workspace. Read the assignment PDF first before writing any code. Everything below
is the full specification — follow it precisely, but use good engineering judgment on
implementation details that aren't pinned down explicitly.

This document is your single source of truth. Do not deviate from the architecture,
tech stack, or scope described here without a very good reason — and if you do deviate,
record why in `docs/decisions.md`.

**Current workspace state**: this project folder already contains
`superjoin-vit-2026-assignment.pdf` at the root and a `starter-datasets/` folder
containing `delhivery/` (three PDFs + README) and `india-macroeconomy/` (three PDFs +
README), plus a `starter-datasets.zip`. Do not re-create or move these — build the
`backend/`, `frontend/`, `eval/`, `scripts/`, `docs/`, and `tests/` directories
described below alongside what's already here. Read the assignment PDF and both
dataset READMEs in full before writing any code.

---

## 0. What we are building, in one paragraph

A system that ingests arbitrary PDFs, extracts factual claims from them (numbers,
statuses, dates, entities — whatever the document actually contains, not a fixed
schema), grounds every fact in an exact, verifiable quote from its source page, and
then reasons about how facts relate to each other across documents: do they
**corroborate** each other, **contradict** each other, or **appear to contradict but are
reconcilable** once you account for time period, scope, or units. The system must not
contain any hardcoded facts, filenames, or document-specific rules — it will be tested
against PDFs it has never seen.

The reasoning layer is the actual deliverable. Parsing, storage, and UI exist to
support it, not to be the point of the project.

---

## 1. Non-negotiable constraints

Read these twice. Violating any of them undermines the core grading criteria.

1. **No hardcoded facts, filenames, or per-document logic anywhere in the pipeline
   code.** Extraction, canonicalization, and reasoning must all generalize to any
   PDF. It is fine to reference the starter dataset in `scripts/`, `eval/`, or `docs/`
   for demoing and testing — it is not fine inside `backend/app/`.
2. **Every fact must carry a verbatim evidence quote plus its source location**
   (document, page, and ideally a bounding box) — no fact without grounding.
3. **Every extracted evidence quote must be programmatically verified** against the
   actual source text before the fact is trusted (see Guardrails, section 6). Facts
   that fail verification are not discarded — they are marked low-confidence and
   surfaced, not hidden. A hidden failure is worse than a visible one.
4. **The relationship reasoning (corroborate / contradict / reconcile / uncertain)
   must be a real reasoning step over evidence, not a rule keyed on entity names.**
   It's fine for an LLM to do this reasoning — that's expected — but it must be given
   both facts' actual evidence text and produce an explanation, not just a label.
5. **Keep the system runnable entirely locally with one documented command.** No
   requirement for a hosted deployment. See section 10.
6. **Keep dependencies minimal and every dependency justified.** Do not add a graph
   database, a hosted vector database, a re-ranking model, or an observability SaaS
   unless section 5 below tells you to. If you think one would help, write it into
   `docs/decisions.md` under "considered and rejected" with the reasoning, and mention
   it in the README's "Next Steps" instead of building it.
7. **A smaller, well-understood system beats a large, unclear one.** If you're ever
   choosing between adding a feature and making the existing pipeline more legible
   (better logs, better error messages, better README), choose legibility.

---

## 2. Tech stack (decided — do not re-litigate)

- **Language**: Python 3.11+
- **LLM**: Anthropic Claude API (`ANTHROPIC_API_KEY` from `.env`). Used for: fact
  extraction, ambiguous canonicalization judgments, and relationship reasoning.
  All LLM calls that need structured data must request tool-use / structured JSON
  output and validate the response against a Pydantic model. On validation failure,
  retry once with the validation error appended to the prompt; if it fails twice,
  log the failure and mark the item as `extraction_failed` rather than crashing.
- **Embeddings**: a local sentence-transformer (e.g. `BAAI/bge-small-en-v1.5` or
  `all-MiniLM-L6-v2` via the `sentence-transformers` package) — runs on CPU, no extra
  API key, no extra cost. Do not use a hosted embeddings API; it adds a dependency
  for no real benefit at this scale.
- **Lexical search**: `rank_bm25` (BM25Okapi) over fact text and chunk text.
- **Retrieval**: hybrid — BM25 + cosine similarity over local embeddings, combined
  with simple reciprocal rank fusion. No cross-encoder re-ranker (candidate sets are
  small enough that the LLM reasoning step can just judge all of them directly —
  document this trade-off in the README).
- **PDF parsing**: `PyMuPDF` (`fitz`) for text spans with font size/position (needed
  for section-aware chunking and for bounding boxes), plus `pdfplumber` specifically
  for table detection/extraction on pages where PyMuPDF's font-based heuristics
  detect a tabular layout.
- **Fuzzy text verification**: `rapidfuzz` for evidence-quote verification against
  source chunks (tolerant of whitespace/hyphenation differences from extraction).
- **Storage**: a single SQLite database file (`data/factstore.db`). No Postgres, no
  Docker requirement for the database. Store embeddings as serialized numpy blobs in
  a SQLite column; do brute-force cosine similarity in Python at query time — at this
  scale (hundreds to low thousands of facts) this is simpler and just as fast as a
  vector index, and it's easy to explain in the README. Note in "Next steps" that a
  real vector index (FAISS/pgvector) is the obvious upgrade path at higher scale.
- **Backend**: FastAPI, serving a REST API.
- **Frontend**: Streamlit, calling the FastAPI backend over HTTP. Streamlit is chosen
  over a React app because it lets you render a PDF page as an image (via PyMuPDF)
  with a drawn highlight rectangle over the evidence bounding box in a few lines —
  exactly the grounding UI this project needs — without building a separate frontend
  build pipeline. If time permits after the core system is fully working and
  demoed, a polished React frontend can be added as a stretch goal, but do not start
  it until everything below is done and the demo video is recordable.
- **Observability**: no Langfuse, no hosted tracing. Build a lightweight local trace
  log instead — every LLM call appends a JSON line to `data/traces.jsonl` with
  timestamp, call type, input, output, and latency. This is queryable and viewable
  in the Streamlit UI as a simple "reasoning trace" tab. It's free, it's local, and
  it directly demonstrates the auditability this problem domain cares about.
- **Testing**: `pytest` for unit tests on guardrails, canonicalization, and the
  reasoning classifier logic (using small synthetic fixtures, not the full dataset).
- **Env management**: `python-dotenv`, `.env.example` committed, `.env` gitignored.

---

## 3. Repository structure

```
.
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── superjoin-vit-2026-assignment.pdf        (already present)
├── starter-datasets/                        (already present)
│   ├── delhivery/
│   └── india-macroeconomy/
├── docs/
│   └── decisions.md                         (trade-offs, rejected alternatives)
├── backend/
│   └── app/
│       ├── main.py                          (FastAPI app entrypoint)
│       ├── config.py                        (env vars, constants, thresholds)
│       ├── models/
│       │   └── schema.py                    (Pydantic: Document, Chunk, Fact, Evidence, Relationship)
│       ├── ingestion/
│       │   ├── pdf_parser.py                (PyMuPDF text + bbox extraction)
│       │   ├── chunker.py                   (section-aware chunking)
│       │   └── table_extractor.py           (pdfplumber table detection)
│       ├── extraction/
│       │   ├── fact_extractor.py            (LLM call + schema validation)
│       │   └── prompts.py
│       ├── guardrails/
│       │   └── evidence_verifier.py         (rapidfuzz verification, confidence scoring)
│       ├── canonicalization/
│       │   ├── embedder.py                  (local embedding model wrapper)
│       │   └── canonicalizer.py             (similarity + LLM tie-break + schema registry)
│       ├── retrieval/
│       │   ├── bm25_index.py
│       │   ├── vector_index.py
│       │   └── hybrid_retriever.py          (reciprocal rank fusion)
│       ├── reasoning/
│       │   ├── relationship_engine.py       (corroborate/contradict/reconcile/uncertain)
│       │   └── prompts.py
│       ├── storage/
│       │   ├── db.py                        (SQLite schema + connection)
│       │   └── repository.py                (CRUD functions)
│       ├── tracing/
│       │   └── trace_log.py                 (JSONL call logger)
│       └── api/
│           └── routes.py
├── frontend/
│   └── streamlit_app.py
├── eval/
│   ├── labeled_facts.json                   (hand-curated ground truth, small)
│   └── run_eval.py                          (precision/recall/F1 against labeled_facts.json)
├── scripts/
│   ├── seed_demo.py                         (runs full pipeline over starter dataset)
│   └── run_dev.sh                           (starts backend + frontend together)
└── tests/
    ├── test_guardrails.py
    ├── test_canonicalization.py
    └── test_reasoning.py
```

---

## 4. Data model (implement exactly this shape in `backend/app/models/schema.py`)

```python
class Document(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    page_count: int

class Chunk(BaseModel):
    id: str
    document_id: str
    page_number: int
    bbox: tuple[float, float, float, float] | None
    text: str
    section_title: str | None      # from section-aware chunking, may be None

class Fact(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    entity: str                     # e.g. "Delhivery Limited", free text, LLM-proposed
    attribute: str                  # e.g. "revenue from services", free text, LLM-proposed
    value: str                      # keep as string; normalize downstream, don't force numeric
    unit: str | None                # e.g. "INR crore", "%", None for non-numeric facts
    scope: dict                     # free-form: {"period": "FY24", "basis": "consolidated", ...}
    verbatim_evidence: str          # exact quote, must appear in chunk text (verified)
    page_number: int
    bbox: tuple[float, float, float, float] | None
    canonical_key: str | None       # filled in by canonicalization step
    confidence: float               # combination of extraction + verification confidence
    verification_status: Literal["verified", "unverified", "extraction_failed"]

class Relationship(BaseModel):
    id: str
    fact_id_a: str
    fact_id_b: str
    relationship_type: Literal["corroboration", "contradiction", "reconciled_context", "uncertain"]
    explanation: str                # LLM-generated, must reference both evidences
    confidence: float
```

`scope` and `unit` are intentionally loose (dict / optional string) — this is what
keeps the schema open rather than hardcoded to "revenue" or "FY24"-shaped facts.
The canonicalization step (section 7) is what makes this open schema usable for
comparison rather than a pile of incompatible free text.

---

## 5. Explicitly rejected additions (do not build these; document why in README)

- Cross-encoder re-ranking — candidate sets per canonical key are small (single
  digits to low tens); handing all of them to the LLM directly is simpler and just
  as accurate at this scale. Mention as a scaling upgrade in "Next steps."
- Neo4j / any graph database — the assignment explicitly warns that a graph or
  visualization alone is not the solution; SQLite foreign keys represent the same
  fact→evidence→relationship structure without extra infra.
- Langfuse / hosted observability — replaced by the local JSONL trace log
  (section 2). Mention Langfuse as a natural upgrade path in "Next steps."
- Hosted deployment (Vercel, etc.) — not requested by the assignment; local run
  plus a demo video is the expected deliverable.

---

## 6. Pipeline stage details

### 6.1 Ingestion and section-aware chunking (`ingestion/`)

- Extract every text span via PyMuPDF along with its font size and page number.
- Use font-size discontinuities (a span meaningfully larger/bolder than surrounding
  body text) as a heuristic section-header detector. Chunk text so that a chunk
  never straddles two different detected sections when avoidable, and stays under
  a configurable max token length (start at ~800 tokens) with a small overlap
  (~100 tokens) at boundaries to avoid splitting a fact across chunks.
- Run `table_extractor.py` on pages where pdfplumber detects a table structure;
  represent extracted tables as markdown-style text (preserves row/column
  alignment) rather than flattening them into prose, and tag those chunks with
  `section_title` reflecting the nearest heading.
- Every chunk retains `page_number` and, where derivable, a `bbox` covering its
  text region — needed later for evidence highlighting in the UI.

### 6.2 Fact extraction (`extraction/`)

- For each chunk, call Claude with the exact prompt given in **Appendix A**
  (`extraction/prompts.py`), instructing it to extract zero or more factual
  claims as structured JSON matching the `Fact` fields.
- Skip chunks that are clearly boilerplate (disclaimers, headers/footers,
  table of contents) — a short heuristic pre-filter is fine here (e.g. very low
  numeric/proper-noun density), but do not skip based on filename or document
  identity.
- Use the exact prompt text in Appendix A verbatim as your starting point. Only
  modify it if you hit a concrete, observed failure mode during testing — and if
  you do, record the change and why in `docs/decisions.md`.

### 6.3 Guardrail: evidence verification (`guardrails/`)

- For every extracted fact, fuzzy-match `verbatim_evidence` against the actual
  source `chunk.text` using rapidfuzz (`partial_ratio`). Set a threshold (start
  at 85); at or above → `verification_status = "verified"`; below → mark
  `"unverified"` and lower `confidence` accordingly, but keep the fact in the
  store rather than dropping it — it should be visibly surfaced in the UI as
  needing review, not silently discarded.
- If the LLM's structured output fails Pydantic validation twice in a row for a
  given chunk, log the raw output and mark that chunk's extraction as
  `"extraction_failed"` in the trace log. This is your best natural source for
  the assignment's required "extraction/reasoning failure" case — do not
  fabricate one if a real one shows up in the trace log; use the real one and
  explain how you handled it (surfaced to the user, not hidden) plus what you'd
  improve.

### 6.4 Canonicalization (`canonicalization/`)

- Maintain a registry of canonical `(entity, attribute)` keys, each backed by an
  embedding of the concatenated entity+attribute string.
- For each new fact: embed its `entity + " " + attribute` string, compare
  against all existing canonical key embeddings via cosine similarity.
  - similarity ≥ 0.92 → auto-assign to that canonical key.
  - 0.75 ≤ similarity < 0.92 → ask Claude the tie-break judgment using the exact
    prompt in **Appendix B** before merging.
  - similarity < 0.75 → create a new canonical key. This is how the schema
    evolves dynamically without a predefined ontology — call this out
    explicitly in the README as satisfying the "schema evolves dynamically"
    brownie point.
- Do the same lightweight canonicalization for entity names alone (so "Suvir
  Suren Sujan" and "Mr. Suvir Suren Sujan" resolve to one entity) — this can
  reuse the same similarity + LLM-tiebreak mechanism.

### 6.5 Hybrid retrieval (`retrieval/`)

- Maintain a BM25 index and an embedding index over all stored facts (indexed on
  a synthetic "fact sentence" like `"{entity} {attribute}: {value} {unit} ({scope})"`).
- When looking for candidate facts to compare against a given fact, first
  restrict to facts sharing the same `canonical_key` (cheap, exact); then, for
  facts about the same real-world entity but with different attribute phrasing
  the canonicalizer didn't catch, additionally run a hybrid BM25+embedding query
  and merge via reciprocal rank fusion, so near-miss matches aren't lost purely
  to canonicalization failures.

### 6.6 Relationship reasoning engine (`reasoning/`)

- For each pair of candidate facts (same canonical key, different documents),
  call Claude using the exact prompt given in **Appendix C**, passing both
  facts' full evidence text, source document names, and scope metadata.
  Require structured output: `relationship_type`, `explanation`, `confidence`.
  The explanation must reference the specific values/wording from both
  evidences — this is enforced directly in the Appendix C prompt text; do not
  weaken that instruction.
- If the model cannot confidently classify the pair (conflicting/insufficient
  metadata to determine scope), it should return `"uncertain"` rather than
  guessing — this is a legitimate outcome, not a bug, and doubles as another
  valid instance of the required "reasoning failure" case if useful for the demo.

### 6.7 Storage (`storage/`)

- SQLite tables mirroring the Pydantic models 1:1, with foreign keys
  `Chunk.document_id → Document.id`, `Fact.chunk_id → Chunk.id`,
  `Relationship.fact_id_a/b → Fact.id`. Store fact embeddings as a BLOB column
  (`numpy.tobytes()` / `numpy.frombuffer()` on read).
- Ingesting a new document must never require reprocessing existing documents —
  only its own chunks/facts get extracted, and only its facts get compared
  against the existing store. This satisfies the "incremental ingestion" brownie
  point; make sure `seed_demo.py` demonstrates this by ingesting the six starter
  PDFs one at a time and showing that earlier documents aren't reprocessed.

---

## 7. API (`backend/app/api/routes.py`)

Minimum endpoints:

- `POST /documents` — upload a PDF, runs the full pipeline (ingest → extract →
  verify → canonicalize → index), returns `document_id` and summary counts.
- `GET /documents` — list ingested documents.
- `GET /documents/{id}/facts` — list facts for a document, with verification
  status and confidence.
- `GET /facts/{id}` — a single fact with its evidence, source page number, bbox.
- `GET /facts/{id}/relationships` — all relationships involving this fact, each
  with the linked fact and the explanation.
- `GET /documents/{id}/pages/{page_number}/image` — rendered page image (via
  PyMuPDF) for the evidence viewer, optionally with `?highlight_bbox=x0,y0,x1,y1`
  query params to draw the highlight server-side, or return raw + let the
  frontend draw it — either is fine, pick whichever is less code.
- `GET /trace` — recent entries from the local trace log (for the "reasoning
  trace" UI tab).

## 8. Frontend (`frontend/streamlit_app.py`)

- Upload tab: drag-and-drop a PDF, shows processing status, then a fact table
  (entity, attribute, value, unit, scope, confidence, verification status) with
  a filter for "needs review."
- Click a fact → side panel shows the rendered source page with the evidence
  region highlighted, plus a "linked facts" list showing every relationship for
  that fact, colored/labeled by type (corroboration / contradiction / reconciled
  / uncertain), each with its explanation shown inline.
- A "Four required cases" tab that, after the demo dataset has been seeded,
  surfaces one example of each required case directly (pulled from the actual
  relationship table by type, not hardcoded) — this is what you'll screen-record
  for the demo video.
- A "Reasoning trace" tab showing recent LLM calls from the trace log, for
  auditability.

## 9. Evaluation harness (`eval/`)

- `labeled_facts.json`: hand-write roughly 15–25 ground-truth facts across the
  starter dataset (a mix from both Delhivery and macro documents) in the same
  shape as the `Fact` model, with the correct canonical key and value.
- `run_eval.py`: runs the full pipeline over the source PDFs, matches extracted
  facts to labeled facts by canonical key + normalized value, and reports
  precision/recall/F1, plus a printed list of misses (labeled facts the pipeline
  didn't find) and false positives (if easily identifiable). Print a clean
  summary table to stdout — this is what you'll quote a number from in the
  README's Approach section instead of an unverifiable "it works well."

## 10. Setup, run, and demo requirements

- `requirements.txt` pinned to specific versions.
- `.env.example` with `ANTHROPIC_API_KEY=` and any configurable thresholds.
- `scripts/run_dev.sh` starts the FastAPI backend and the Streamlit frontend
  together (background one, foreground the other, or use a process manager —
  keep it to a single command).
- `scripts/seed_demo.py` ingests all six starter PDFs through the full pipeline
  in one run, so a reviewer (or you, before recording) can go from a fresh clone
  to a populated, demoable UI in one command plus one script run.
- The whole thing must work from `git clone` → `pip install -r requirements.txt`
  → set `.env` → `run_dev.sh` → `seed_demo.py`, with no other manual steps.

## 11. README.md — must contain exactly these sections (per assignment)

1. **Setup and Run Instructions** — the exact commands above.
2. **Video Demo** — link placeholder, to be filled in after recording.
3. **Approach** — architecture summary (ingestion → extraction → guardrail →
   canonicalization → hybrid retrieval → reasoning engine → storage → API/UI),
   key decisions and trade-offs (SQLite over Postgres/graph DB, local embeddings
   over hosted, no cross-encoder, local trace log over Langfuse — with brief
   reasoning for each), and which AI tools were used to build the project.
4. **Limitations and Next Steps** — be honest: known failure modes found via the
   eval harness and trace log, and what you'd build next (cross-encoder at
   scale, real vector index, hosted observability, richer table extraction,
   React frontend).
5. **Additional Notes** — anything else worth mentioning.

Also include a short `docs/decisions.md` with the same trade-off reasoning in
more detail, referenced from the README, for anyone who wants to go deeper.

---

## Appendix A — Fact extraction prompt (`extraction/prompts.py`)

Use this as the system prompt, verbatim:

```
You are a fact-extraction engine for a fact knowledge layer system. You will be
given a chunk of text extracted from a page of a PDF document, along with its
section title (if known), page number, and source document name. Your job is
to extract every distinct, checkable factual claim stated in the text as a
structured list.

Rules:

1. Do not force facts into any predefined category. Extract whatever the text
   actually states as a checkable claim: a financial figure, a date, a status
   change, a named person's role, a percentage, a count, an address, a policy
   figure — whatever is genuinely present as a verifiable statement.

2. Every fact must include a "verbatim_evidence" field that is an EXACT,
   character-for-character substring of the provided text. Do not paraphrase,
   do not fix typos or spacing, do not normalize numbers or wording. If you
   cannot find an exact quotable substring supporting a claim, do not extract
   that claim at all.

3. "entity": the real-world subject of the fact (a company, a person, a
   country, a specific line item's owner). Use the most complete, unambiguous
   name available in the text — prefer full names over pronouns or abbreviated
   references where the text provides them.

4. "attribute": what property or metric of the entity this fact describes, in
   your own concise words (examples: "revenue from services", "non-executive
   nominee director", "current account deficit as percent of GDP", "board
   membership status"). Be specific enough that this phrase alone tells someone
   what is being measured or stated.

5. "value": the stated value, always as a string, exactly as it should be
   compared later (examples: "8,142", "resigned", "1.2", "August 24, 2023").

6. "unit": the unit if applicable (examples: "INR crore", "%", "USD billion",
   "days"), or null if the fact has no unit (e.g. a status, a name, a date).

7. "scope": a JSON object capturing whatever qualifiers in the text affect
   whether this fact is comparable to another fact about the same attribute.
   Include only qualifiers actually present in the text — do not invent scope
   information that isn't stated. Typical keys you might use: "period" (e.g.
   "FY24", "Q2 FY25"), "basis" (e.g. "consolidated", "standalone"), "as_of"
   (a specific date), "geography", "estimate_type" (e.g. "projected",
   "actual", "provisional"). Use an empty object {} if no such qualifiers are
   stated.

8. If the same underlying fact is restated more than once in the chunk,
   extract it only once, using the clearest available quote as evidence.

9. Skip boilerplate: disclaimers, safe-harbor statements, tables of contents,
   page headers/footers, and pure formatting artifacts are not facts.

10. If the chunk contains no checkable factual claims at all, return an empty
    list. Returning nothing is correct and expected for many chunks — do not
    force an extraction to justify the call.

Output must be valid JSON only: a list of objects with exactly the fields
described above (entity, attribute, value, unit, scope, verbatim_evidence).
No prose, no markdown code fences, no commentary before or after the JSON.
```

User message template:

```
Document: {document_filename}
Section: {section_title_or_"unknown"}
Page: {page_number}

Text:
{chunk_text}

Extract all factual claims from this text following the system instructions.
```

Implementation note: pass this through Claude's structured/tool-use output
mode with a JSON schema matching the `Fact` extraction subset of fields
(entity, attribute, value, unit, scope, verbatim_evidence) so you get
schema-validated JSON back rather than parsing free text. Validate the
response with the Pydantic model; on failure, retry once with the validation
error appended to the user message ("Your previous response failed validation
with this error: {error}. Return corrected JSON only.").

---

## Appendix B — Canonicalization tie-break prompt (`canonicalization/canonicalizer.py`)

System prompt, verbatim:

```
You are judging whether two (entity, attribute) phrasings extracted from
different documents refer to the same underlying real-world concept, such
that their values could be meaningfully compared against each other.

You will be given two phrasings, each with a short snippet of the source
context it came from. Two phrasings are the same concept only if a fair,
apples-to-apples comparison between their values would be meaningful — not
merely because the words are similar. For example, "revenue from services"
and "revenue from operations including traded goods" may or may not be the
same concept depending on what each document's context actually says; decide
based on the source context, not surface wording alone.

Respond with strict JSON only: {"same_concept": true or false, "reasoning":
"one concise sentence explaining your judgment, referencing the context"}.
```

User message template:

```
Phrasing A: entity="{entity_a}", attribute="{attribute_a}"
Context A: "{context_snippet_a}"

Phrasing B: entity="{entity_b}", attribute="{attribute_b}"
Context B: "{context_snippet_b}"

Are these the same underlying concept for comparison purposes?
```

---

## Appendix C — Relationship reasoning prompt (`reasoning/prompts.py`)

System prompt, verbatim:

```
You are a fact-reconciliation analyst. You will be given two facts extracted
from documents, both mapped to the same canonical concept, along with their
full verbatim evidence, source document names, and scope metadata. Decide how
these two facts relate to each other.

Respond with strict JSON only: {"relationship_type": one of "corroboration",
"contradiction", "reconciled_context", "uncertain", "explanation": a string,
"confidence": a number between 0 and 1}.

Definitions:

- corroboration: the two facts state the same underlying value for what
  appears to be the same scope, allowing for unit conversion, rounding, or
  different phrasing of an equivalent figure.

- contradiction: the two facts state materially different values for what
  appears to be the SAME scope (same entity, same time period, same
  basis/unit, same measurement convention), with nothing in the provided
  scope metadata or evidence that would explain the difference.

- reconciled_context: the two facts appear to differ, but their scope
  metadata or evidence text plausibly explains the difference — for example,
  one is a quarterly figure and one is annual, one is standalone and one is
  consolidated, one is a projection and one is an actual outturn, one covers
  a different reporting period, or one uses a different accounting or
  measurement convention that the evidence text makes explicit.

- uncertain: there is not enough information in the evidence or scope
  metadata to confidently classify the relationship either way. This is a
  legitimate and expected outcome when context is genuinely insufficient —
  do not force a classification you cannot support. Do not default to
  "corroboration" or "contradiction" just to avoid returning "uncertain."

Your explanation must reference specific wording or values from BOTH
evidences you were given — a generic explanation that could apply to any pair
of facts is not acceptable. Someone should be able to verify your reasoning
is correct just by reading the two evidences alongside your explanation.
```

User message template:

```
Fact A:
Document: {document_a_filename}
Entity: {entity_a}
Attribute: {attribute_a}
Value: {value_a} {unit_a}
Scope: {scope_a_json}
Evidence: "{verbatim_evidence_a}"

Fact B:
Document: {document_b_filename}
Entity: {entity_b}
Attribute: {attribute_b}
Value: {value_b} {unit_b}
Scope: {scope_b_json}
Evidence: "{verbatim_evidence_b}"

Classify the relationship between Fact A and Fact B.
```

Implementation note: same structured-output + Pydantic validation pattern as
Appendix A. If validation fails twice, mark the pair `relationship_type =
"uncertain"` with `explanation = "reasoning engine failed to produce valid
output"` and log it to the trace log rather than crashing the pipeline — a
failed reasoning call should degrade gracefully, not take down ingestion.

---

## 12. Git workflow — commit at these checkpoints, nowhere else

Use meaningful, conventional commit messages. Do not commit after every file
edit; commit when a coherent unit of functionality is complete and working.
Target roughly this sequence (12–15 commits total):

1. `chore: initial repo scaffold, README skeleton, project structure`
2. `feat: PDF ingestion with section-aware chunking and bbox tracking`
3. `feat: LLM-based open-schema fact extraction`
4. `feat: evidence verification guardrail for extracted facts`
5. `feat: entity and attribute canonicalization with embedding similarity`
6. `feat: SQLite fact store with full provenance schema`
7. `feat: hybrid BM25 + semantic retrieval for candidate fact matching`
8. `feat: relationship reasoning engine (corroborate/contradict/reconcile/uncertain)`
9. `feat: FastAPI endpoints for documents, facts, relationships, page images`
10. `feat: Streamlit UI with evidence viewer and relationship panel`
11. `test: eval harness with labeled ground-truth set and accuracy report`
12. `feat: seed script running full pipeline over starter dataset`
13. `docs: complete README, decisions log, and demo prep`
14. `fix: polish, edge cases, and bug fixes ahead of demo recording`

After each commit, briefly self-check: does the repo still run end-to-end via
the section 10 instructions? Don't leave the repo in a broken state between
commits.

---

## 13. Definition of done

Before considering this finished, verify all four of these against the actual
running system (not from memory of the design):

1. A fact extracted from one document and corroborated by another is visible in
   the UI with both evidences shown side by side.
2. A genuine contradiction between two documents is visible with both evidences
   and an explanation of why they conflict.
3. An apparent contradiction that's explained by time/scope/unit differences is
   visible with an explanation naming the specific distinguishing factor (e.g.
   "quarterly vs. annual figure," "different reporting period," "standalone vs.
   consolidated basis").
4. A real extraction or reasoning failure, found via the guardrail or the
   `"uncertain"` relationship outcome, is documented with what happened and how
   the system handled or would improve it.

Plus: the eval harness runs and prints a precision/recall summary, the repo
runs from a clean clone in under the documented steps, and the git history
tells a coherent story of how the system was built.
