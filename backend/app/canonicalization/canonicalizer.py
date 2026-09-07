"""
Canonicalization engine.
Maintains a registry of (entity, attribute) canonical keys backed by embeddings.
Three-tier logic:
  >= CANON_AUTO_THRESHOLD   → auto-assign to existing key
  >= CANON_TIEBREAK_THRESHOLD → LLM tiebreak (Appendix B)
  < CANON_TIEBREAK_THRESHOLD  → create new canonical key

This allows the schema to evolve dynamically without a predefined ontology.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid

import google.generativeai as genai
import numpy as np

from backend.app.canonicalization.embedder import cosine_similarity, embed_text
from backend.app.config import (
    CANON_AUTO_THRESHOLD,
    CANON_TIEBREAK_THRESHOLD,
    GEMINI_MODEL,
    GOOGLE_API_KEY,
)
from backend.app.models.schema import CanonTieBreakResult, Fact
from backend.app.storage.repository import (
    insert_canonical_key,
    list_canonical_keys,
    update_fact_canonical_key,
)
from backend.app.tracing.trace_log import log_llm_call

genai.configure(api_key=GOOGLE_API_KEY)

CANON_TIEBREAK_SYSTEM = """You are judging whether two (entity, attribute) phrasings extracted from
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
"one concise sentence explaining your judgment, referencing the context"}."""


def canonicalize_fact(fact: Fact, chunk_text: str) -> str:
    """
    Assign a canonical_key to a fact.
    Returns the canonical_key string and updates the DB.
    """
    if fact.verification_status == "extraction_failed":
        return "EXTRACTION_FAILED"

    # Embed this fact's entity+attribute
    fact_text = f"{fact.entity} {fact.attribute}"
    fact_emb = embed_text(fact_text)

    # Load existing canonical keys from DB
    registry = list_canonical_keys()

    best_score = -1.0
    best_key = None
    best_key_entity = None
    best_key_attribute = None
    best_key_emb = None

    for canon_key, canon_entity, canon_attribute, canon_emb in registry:
        score = cosine_similarity(fact_emb, canon_emb)
        if score > best_score:
            best_score = score
            best_key = canon_key
            best_key_entity = canon_entity
            best_key_attribute = canon_attribute
            best_key_emb = canon_emb

    if best_key is None or best_score < CANON_TIEBREAK_THRESHOLD:
        # Create new canonical key
        new_key = _make_canonical_key(fact.entity, fact.attribute)
        insert_canonical_key(new_key, fact.entity, fact.attribute, fact_emb)
        update_fact_canonical_key(fact.id, new_key)
        return new_key

    if best_score >= CANON_AUTO_THRESHOLD:
        # Auto-assign
        update_fact_canonical_key(fact.id, best_key)
        return best_key

    # Tiebreak zone: ask the LLM
    same_concept = _llm_tiebreak(
        entity_a=best_key_entity,
        attribute_a=best_key_attribute,
        context_a=chunk_text[:300],
        entity_b=fact.entity,
        attribute_b=fact.attribute,
        context_b=chunk_text[:300],
    )

    if same_concept:
        update_fact_canonical_key(fact.id, best_key)
        return best_key
    else:
        new_key = _make_canonical_key(fact.entity, fact.attribute)
        insert_canonical_key(new_key, fact.entity, fact.attribute, fact_emb)
        update_fact_canonical_key(fact.id, new_key)
        return new_key


def _make_canonical_key(entity: str, attribute: str) -> str:
    """Create a stable, readable canonical key from entity+attribute."""
    raw = f"{entity.lower().strip()}::{attribute.lower().strip()}"
    h = hashlib.md5(raw.encode()).hexdigest()[:8]
    slug = raw[:60].replace(" ", "_").replace("/", "-")
    return f"{slug}_{h}"


def _llm_tiebreak(
    entity_a: str,
    attribute_a: str,
    context_a: str,
    entity_b: str,
    attribute_b: str,
    context_b: str,
) -> bool:
    """Ask Gemini whether two (entity, attribute) pairs refer to the same concept."""
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=CANON_TIEBREAK_SYSTEM,
    )
    user_msg = f"""Phrasing A: entity="{entity_a}", attribute="{attribute_a}"
Context A: "{context_a}"

Phrasing B: entity="{entity_b}", attribute="{attribute_b}"
Context B: "{context_b}"

Are these the same underlying concept for comparison purposes?"""

    t0 = time.monotonic()
    try:
        response = model.generate_content(
            user_msg,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        latency_ms = (time.monotonic() - t0) * 1000
        result = CanonTieBreakResult.model_validate_json(response.text)
        log_llm_call(
            call_type="canonicalization_tiebreak",
            model=GEMINI_MODEL,
            input_summary=f'"{entity_a}/{attribute_a}" vs "{entity_b}/{attribute_b}"',
            output_summary=f"same_concept={result.same_concept}: {result.reasoning[:80]}",
            latency_ms=latency_ms,
            success=True,
        )
        return result.same_concept
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        log_llm_call(
            call_type="canonicalization_tiebreak",
            model=GEMINI_MODEL,
            input_summary=f'"{entity_a}/{attribute_a}" vs "{entity_b}/{attribute_b}"',
            output_summary=f"tiebreak failed: {str(e)[:80]}",
            latency_ms=latency_ms,
            success=False,
        )
        # Default to NOT merging on failure — safer to create new key
        return False
