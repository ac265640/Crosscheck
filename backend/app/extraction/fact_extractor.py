"""
LLM-based fact extractor using Google Gemini.

Primary mode: BATCHED — sends EXTRACTION_BATCH_SIZE chunks per LLM call.
  - Reduces API calls ~6x vs one-per-chunk
  - Keeps per-PDF wall time under ~3 minutes on typical docs
  - Falls back to per-chunk mode if a batch fails twice

Single-chunk mode retained as fallback and for the per-chunk retry path.
Validates output against Pydantic ExtractedFact model.
Retries once on validation failure; marks extraction_failed if still invalid.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from backend.app.config import EXTRACTION_BATCH_SIZE, GEMINI_MODEL, GOOGLE_API_KEY
from backend.app.extraction.prompts import (
    FACT_EXTRACTION_BATCH_SYSTEM_PROMPT,
    FACT_EXTRACTION_SYSTEM_PROMPT,
    build_batch_extraction_user_message,
    build_extraction_user_message,
)
from backend.app.models.schema import Chunk, ExtractedFact, Fact
from backend.app.tracing.trace_log import log_llm_call

# Configure Gemini with REST transport to avoid gRPC deadlocks
genai.configure(api_key=GOOGLE_API_KEY, transport="rest")

_BOILERPLATE_PATTERNS = [
    r"(?i)safe\s+harbor",
    r"(?i)forward.looking\s+statement",
    r"(?i)table\s+of\s+contents",
    r"(?i)this\s+document\s+contains",
    r"(?i)disclaimer",
    r"(?i)page\s+\d+\s+of\s+\d+",
    r"(?i)confidential",
    r"(?i)^\s*\d+\s*$",  # page number only
]


def _is_boilerplate(text: str) -> bool:
    """
    Heuristic pre-filter: skip chunks that are clearly boilerplate.
    Does NOT use filename or document identity — purely text-content based.
    """
    if len(text.strip()) < 50:
        return True

    for pattern in _BOILERPLATE_PATTERNS:
        if re.search(pattern, text):
            return True

    # Low information density: very few digits/proper nouns relative to total chars
    digit_count = sum(1 for c in text if c.isdigit())
    upper_count = sum(1 for c in text if c.isupper())
    total = len(text)
    if total > 0 and (digit_count + upper_count) / total < 0.02 and len(text) < 200:
        return True

    return False


# ── Public entrypoint ──────────────────────────────────────────────────────────

def extract_facts_from_chunks(
    chunks: list[Chunk],
    document_filename: str,
) -> list[Fact]:
    """
    Extract facts from a list of chunks using batched LLM calls.

    Batching strategy:
      - Filter boilerplate chunks first (no LLM call needed)
      - Group remaining chunks into batches of EXTRACTION_BATCH_SIZE
      - One LLM call per batch → ~6x fewer API round-trips
      - Falls back to per-chunk extraction for any batch that fails twice

    Returns all facts with verification_status='unverified'
    (verification happens in the guardrail step).
    """
    # Filter out boilerplate chunks before any LLM call
    content_chunks = [c for c in chunks if not _is_boilerplate(c.text)]
    boilerplate_count = len(chunks) - len(content_chunks)

    if boilerplate_count:
        log_llm_call(
            call_type="boilerplate_filter",
            model="none",
            input_summary=f"{len(chunks)} chunks → {boilerplate_count} boilerplate filtered",
            output_summary=f"{len(content_chunks)} chunks queued for extraction",
            latency_ms=0,
            success=True,
        )

    if not content_chunks:
        return []

    all_facts: list[Fact] = []

    # Process in batches
    for batch_start in range(0, len(content_chunks), EXTRACTION_BATCH_SIZE):
        batch = content_chunks[batch_start: batch_start + EXTRACTION_BATCH_SIZE]
        batch_facts = _extract_batch(batch, document_filename)
        all_facts.extend(batch_facts)

    return all_facts


# Keep the old per-chunk API for backward compat (used by existing tests)
def extract_facts_from_chunk(
    chunk: Chunk,
    document_filename: str,
) -> list[Fact]:
    """Single-chunk extraction. Prefer extract_facts_from_chunks() for production."""
    return extract_facts_from_chunks([chunk], document_filename)


# ── Batch extraction ───────────────────────────────────────────────────────────

def _extract_batch(chunks: list[Chunk], document_filename: str) -> list[Fact]:
    """
    Send a batch of chunks in one LLM call.
    Returns facts with chunk_id correctly set from the chunk_index field.
    Falls back to per-chunk extraction if the batch fails twice.
    """
    from backend.app.config import FALLBACK_MODELS

    # Build the labelled chunk list: (index, section, page, text)
    labelled = [
        (i, c.section_title, c.page_number, c.text)
        for i, c in enumerate(chunks)
    ]

    active_model_name = GEMINI_MODEL
    model = genai.GenerativeModel(
        model_name=active_model_name,
        system_instruction=FACT_EXTRACTION_BATCH_SYSTEM_PROMPT,
    )

    last_error: Optional[str] = None
    raw_output: Optional[str] = None

    for attempt in range(3):
        user_message = build_batch_extraction_user_message(
            document_filename=document_filename,
            chunks=labelled,
            validation_error=last_error if (attempt > 0 and last_error and "429" not in last_error) else None,
        )

        t0 = time.monotonic()
        try:
            response = model.generate_content(
                user_message,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            raw_output = response.text
            latency_ms = (time.monotonic() - t0) * 1000

            facts = _parse_and_validate_batch(raw_output, chunks, document_filename)

            log_llm_call(
                call_type="fact_extraction_batch",
                model=active_model_name,
                input_summary=(
                    f"batch {len(chunks)} chunks "
                    f"(pages {chunks[0].page_number}–{chunks[-1].page_number}, "
                    f"{sum(len(c.text) for c in chunks)} chars)"
                ),
                output_summary=f"{len(facts)} facts extracted",
                latency_ms=latency_ms,
                success=True,
            )
            return facts

        except (json.JSONDecodeError, ValueError) as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction_batch",
                model=active_model_name,
                input_summary=f"batch {len(chunks)} chunks",
                output_summary=f"attempt {attempt + 1} validation failed: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if attempt >= 1:
                # Both schema attempts failed — fall back to per-chunk
                break

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction_batch",
                model=active_model_name,
                input_summary=f"batch {len(chunks)} chunks",
                output_summary=f"API error: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if "429" in last_error or "ResourceExhausted" in last_error:
                # Switch to next fallback model and retry
                active_model_name = FALLBACK_MODELS[(attempt + 1) % len(FALLBACK_MODELS)]
                model = genai.GenerativeModel(
                    model_name=active_model_name,
                    system_instruction=FACT_EXTRACTION_BATCH_SYSTEM_PROMPT,
                )
                time.sleep(3)
                continue
            break

    # Batch failed — fall back to per-chunk extraction for this batch
    log_llm_call(
        call_type="fact_extraction_batch",
        model=active_model_name,
        input_summary=f"batch of {len(chunks)} chunks",
        output_summary="batch failed; falling back to per-chunk extraction",
        latency_ms=0,
        success=False,
    )
    return _extract_per_chunk_fallback(chunks, document_filename)


def _extract_per_chunk_fallback(chunks: list[Chunk], document_filename: str) -> list[Fact]:
    """Per-chunk fallback when a batch fails. Uses the original single-chunk approach."""
    facts: list[Fact] = []
    for chunk in chunks:
        facts.extend(_extract_single_chunk(chunk, document_filename))
    return facts


def _extract_single_chunk(chunk: Chunk, document_filename: str) -> list[Fact]:
    """
    Original per-chunk extraction — used as fallback only.
    Returns a list of Fact objects with verification_status='unverified'.
    Returns empty list + logs failure if extraction fails twice.
    """
    from backend.app.config import FALLBACK_MODELS

    active_model_name = GEMINI_MODEL
    model = genai.GenerativeModel(
        model_name=active_model_name,
        system_instruction=FACT_EXTRACTION_SYSTEM_PROMPT,
    )

    last_error: Optional[str] = None
    raw_output: Optional[str] = None

    for attempt in range(3):
        user_message = build_extraction_user_message(
            document_filename=document_filename,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            chunk_text=chunk.text,
            validation_error=last_error if (attempt > 0 and "429" not in str(last_error)) else None,
        )

        t0 = time.monotonic()
        try:
            response = model.generate_content(
                user_message,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            raw_output = response.text
            latency_ms = (time.monotonic() - t0) * 1000

            facts = _parse_and_validate(raw_output, chunk, document_filename)

            log_llm_call(
                call_type="fact_extraction",
                model=active_model_name,
                input_summary=f"chunk {chunk.id[:8]} page {chunk.page_number} ({len(chunk.text)} chars)",
                output_summary=f"{len(facts)} facts extracted",
                latency_ms=latency_ms,
                success=True,
            )
            return facts

        except (json.JSONDecodeError, ValueError) as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction",
                model=active_model_name,
                input_summary=f"chunk {chunk.id[:8]} page {chunk.page_number}",
                output_summary=f"attempt {attempt + 1} failed: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if attempt >= 1:
                # Both schema attempts failed — return a single extraction_failed fact
                failed_fact = Fact(
                    id=str(uuid.uuid4()),
                    document_id=chunk.document_id,
                    chunk_id=chunk.id,
                    entity="EXTRACTION_FAILED",
                    attribute="extraction_failed",
                    value=raw_output[:200] if raw_output else "no output",
                    unit=None,
                    scope={},
                    verbatim_evidence=chunk.text[:200],
                    page_number=chunk.page_number,
                    bbox=chunk.bbox,
                    canonical_key=None,
                    confidence=0.0,
                    verification_status="extraction_failed",
                )
                return [failed_fact]

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction",
                model=active_model_name,
                input_summary=f"chunk {chunk.id[:8]}",
                output_summary=f"API error: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if "429" in last_error or "ResourceExhausted" in last_error:
                # Switch to next fallback model and retry
                active_model_name = FALLBACK_MODELS[(attempt + 1) % len(FALLBACK_MODELS)]
                model = genai.GenerativeModel(
                    model_name=active_model_name,
                    system_instruction=FACT_EXTRACTION_SYSTEM_PROMPT,
                )
                time.sleep(2)
                continue
            break

    return []


# ── JSON parsing ───────────────────────────────────────────────────────────────

def _parse_and_validate_batch(
    raw_output: str,
    chunks: list[Chunk],
    document_filename: str,
) -> list[Fact]:
    """Parse batched JSON output and map each fact back to its source chunk."""
    text = raw_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list, got {type(data)}")

    facts: list[Fact] = []
    for item in data:
        # chunk_index is required in batch mode; default to 0 if missing
        chunk_idx = int(item.pop("chunk_index", 0))
        chunk_idx = max(0, min(chunk_idx, len(chunks) - 1))
        chunk = chunks[chunk_idx]

        extracted = ExtractedFact.model_validate(item)
        fact = Fact(
            id=str(uuid.uuid4()),
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            entity=extracted.entity,
            attribute=extracted.attribute,
            value=extracted.value,
            unit=extracted.unit,
            scope=extracted.scope,
            verbatim_evidence=extracted.verbatim_evidence,
            page_number=chunk.page_number,
            bbox=chunk.bbox,
            canonical_key=None,
            confidence=1.0,
            verification_status="unverified",
        )
        facts.append(fact)

    return facts


def _parse_and_validate(
    raw_output: str, chunk: Chunk, document_filename: str
) -> list[Fact]:
    """Parse single-chunk JSON output and validate each extracted fact."""
    text = raw_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list, got {type(data)}")

    facts: list[Fact] = []
    for item in data:
        # Tolerate chunk_index if the LLM accidentally includes it
        item.pop("chunk_index", None)
        extracted = ExtractedFact.model_validate(item)
        fact = Fact(
            id=str(uuid.uuid4()),
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            entity=extracted.entity,
            attribute=extracted.attribute,
            value=extracted.value,
            unit=extracted.unit,
            scope=extracted.scope,
            verbatim_evidence=extracted.verbatim_evidence,
            page_number=chunk.page_number,
            bbox=chunk.bbox,
            canonical_key=None,
            confidence=1.0,
            verification_status="unverified",
        )
        facts.append(fact)

    return facts
