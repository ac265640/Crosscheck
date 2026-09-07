"""
LLM-based fact extractor using Google Gemini.
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

from backend.app.config import GEMINI_MODEL, GOOGLE_API_KEY
from backend.app.extraction.prompts import (
    FACT_EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_message,
)
from backend.app.models.schema import Chunk, ExtractedFact, Fact
from backend.app.tracing.trace_log import log_llm_call

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

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


def extract_facts_from_chunk(
    chunk: Chunk,
    document_filename: str,
) -> list[Fact]:
    """
    Call Gemini to extract facts from a single chunk.
    Returns a list of Fact objects with verification_status='unverified'
    (verification happens in the guardrail step).
    Returns empty list + logs failure if extraction fails twice.
    """
    if _is_boilerplate(chunk.text):
        return []

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=FACT_EXTRACTION_SYSTEM_PROMPT,
    )

    last_error: Optional[str] = None
    raw_output: Optional[str] = None

    for attempt in range(2):
        user_message = build_extraction_user_message(
            document_filename=document_filename,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            chunk_text=chunk.text,
            validation_error=last_error if attempt > 0 else None,
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
                model=GEMINI_MODEL,
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
                model=GEMINI_MODEL,
                input_summary=f"chunk {chunk.id[:8]} page {chunk.page_number}",
                output_summary=f"attempt {attempt + 1} failed: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if attempt == 1:
                # Both attempts failed — return a single extraction_failed fact
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
                model=GEMINI_MODEL,
                input_summary=f"chunk {chunk.id[:8]}",
                output_summary=f"API error: {last_error[:100]}",
                latency_ms=latency_ms,
                success=False,
            )
            if "429" in last_error or "ResourceExhausted" in last_error:
                time.sleep(4)
                continue
            break

    return []


def _parse_and_validate(
    raw_output: str, chunk: Chunk, document_filename: str
) -> list[Fact]:
    """Parse JSON output and validate each extracted fact."""
    # Strip markdown fences if present
    text = raw_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list, got {type(data)}")

    facts: list[Fact] = []
    for item in data:
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
