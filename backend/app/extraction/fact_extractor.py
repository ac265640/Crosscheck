"""
LLM-based fact extractor using Groq (qwen/qwen3.8-27b).
One chunk per LLM call for reliable extraction quality.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Optional

from backend.app.config import GROQ_MODEL
from backend.app.extraction.prompts import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)
from backend.app.llm_client import call_llm
from backend.app.models.schema import Chunk, ExtractedFact, Fact
from backend.app.tracing.trace_log import log_llm_call

# Keep for pipeline import compatibility
BATCH_SIZE = 1

_BOILERPLATE_PATTERNS = [
    r"(?i)safe\s+harbor",
    r"(?i)forward.looking\s+statement",
    r"(?i)table\s+of\s+contents",
    r"(?i)disclaimer",
    r"(?i)page\s+\d+\s+of\s+\d+",
    r"(?i)confidential",
    r"(?i)^\s*\d+\s*$",
]


def _is_boilerplate(text: str) -> bool:
    if len(text.strip()) < 80:
        return True
    for pattern in _BOILERPLATE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def extract_facts_from_chunks(chunks: list[Chunk], document_filename: str) -> list[Fact]:
    """Extract facts from a list of chunks (processes each individually)."""
    facts = []
    for chunk in chunks:
        facts.extend(extract_facts_from_chunk(chunk, document_filename))
    return facts


def extract_facts_from_chunk(chunk: Chunk, document_filename: str) -> list[Fact]:
    """Extract facts from a single chunk via one LLM call."""
    if _is_boilerplate(chunk.text):
        return []

    last_error: Optional[str] = None
    raw_output: Optional[str] = None

    for attempt in range(3):
        user_message = build_extraction_user_message(
            document_filename=document_filename,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            chunk_text=chunk.text,
            validation_error=last_error if attempt > 0 else None,
        )

        t0 = time.monotonic()
        try:
            raw_output = call_llm(
                system_prompt=FACT_EXTRACTION_SYSTEM_PROMPT,
                user_message=user_message,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            facts = _parse_and_validate(raw_output, chunk, document_filename)
            log_llm_call(
                call_type="fact_extraction",
                model=GROQ_MODEL,
                input_summary=f"chunk {chunk.id[:8]} p{chunk.page_number} ({len(chunk.text)}c)",
                output_summary=f"{len(facts)} facts",
                latency_ms=latency_ms,
                success=True,
            )
            return facts

        except (json.JSONDecodeError, ValueError) as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction",
                model=GROQ_MODEL,
                input_summary=f"chunk {chunk.id[:8]}",
                output_summary=f"parse err attempt {attempt+1}: {last_error[:80]}",
                latency_ms=latency_ms,
                success=False,
            )
            if attempt >= 2:
                return [_make_failed_fact(chunk, raw_output)]

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            last_error = str(e)
            log_llm_call(
                call_type="fact_extraction",
                model=GROQ_MODEL,
                input_summary=f"chunk {chunk.id[:8]}",
                output_summary=f"API error: {last_error[:80]}",
                latency_ms=latency_ms,
                success=False,
            )
            break

    return []


def _parse_and_validate(raw_output: str, chunk: Chunk, document_filename: str) -> list[Fact]:
    text = raw_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    data = json.loads(text)
    if isinstance(data, dict):
        for key in ("facts", "items", "results", "data"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            if "entity" in data:
                data = [data]
            else:
                raise ValueError(f"Unexpected JSON structure: {list(data.keys())}")

    if not isinstance(data, list):
        raise ValueError(f"Expected list, got {type(data)}")

    facts = []
    for item in data:
        extracted = ExtractedFact.model_validate(item)
        facts.append(Fact(
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
        ))
    return facts


def _make_failed_fact(chunk: Chunk, raw_output: Optional[str]) -> Fact:
    return Fact(
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
