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

import numpy as np

from backend.app.canonicalization.embedder import cosine_similarity, embed_text
from backend.app.config import (
    CANON_AUTO_THRESHOLD,
    CANON_TIEBREAK_THRESHOLD,
    GROQ_MODEL,
)
from backend.app.models.schema import CanonTieBreakResult, Fact
from backend.app.storage.repository import (
    insert_canonical_key,
    list_canonical_keys,
    update_fact_canonical_key,
)
from backend.app.tracing.trace_log import log_llm_call


import re
from rapidfuzz import fuzz

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


def is_same_entity(e1: str, e2: str) -> bool:
    """Check if two entity names plausibly refer to the same real-world entity.

    Uses three generic strategies (no hardcoded entity names):
    1. Exact match after normalization
    2. Suffix stripping (Ltd, Inc, Corp, etc.) + substring containment
    3. Fuzzy token-set ratio >= 80 as final fallback
    """
    if not e1 or not e2:
        return False
    e1_norm = re.sub(r"[^\w\s]", "", e1.lower()).strip()
    e2_norm = re.sub(r"[^\w\s]", "", e2.lower()).strip()
    if e1_norm == e2_norm:
        return True

    # Generic legal-form suffixes that don't change entity identity
    suffixes = {"limited", "ltd", "corporation", "corp", "inc", "incorporated",
                "private", "pvt", "llc", "plc", "company", "co", "group",
                "holdings", "enterprises", "solutions", "services", "technologies"}

    def strip_sfx(s: str) -> str:
        words = [w for w in s.split() if w not in suffixes]
        return " ".join(words)

    s1, s2 = strip_sfx(e1_norm), strip_sfx(e2_norm)
    if s1 and s2 and (s1 == s2 or s1 in s2 or s2 in s1):
        return True

    # Generic acronym check: e.g. "rbi" matches "reserve bank of india"
    # Works for any entity — checks if one string is the initials of the other's meaningful words
    _stop_words = {"of", "the", "and", "for", "in", "at", "by", "to", "a", "an"}

    def is_acronym_of(short: str, full: str) -> bool:
        if len(short) < 2 or " " in short:
            return False
        # Only use meaningful words (not suffixes or stop words) for acronym building
        words = [w for w in full.split()
                 if w not in suffixes and w not in _stop_words and len(w) > 0]
        if len(words) < 2:
            return False
        return len(short) == len(words) and short == "".join(w[0] for w in words)

    if is_acronym_of(s1, s2) or is_acronym_of(s2, s1):
        return True

    # Generic self-referential document pronouns — any entity document may use these
    self_referential = {"the company", "our company", "your company", "the issuer",
                        "the entity", "the firm", "the organization", "the group"}
    if e1_norm in self_referential or e2_norm in self_referential:
        # Can't resolve self-referential without context; conservative: use fuzzy
        pass

    # Fuzzy ratio fallback — generic, works for any entity names
    ratio = fuzz.token_set_ratio(e1_norm, e2_norm)
    return ratio >= 80


_registry_cache: list[tuple[str, str, str, np.ndarray]] | None = None
_tiebreak_cache: dict[tuple[str, str, str, str], bool] = {}


def get_canonical_registry(refresh: bool = False) -> list[tuple[str, str, str, np.ndarray]]:
    """Get the cached canonical keys registry, loading from DB if needed."""
    global _registry_cache
    if _registry_cache is None or refresh:
        _registry_cache = list_canonical_keys()
    return _registry_cache


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

    # Load existing canonical keys from cached registry
    registry = get_canonical_registry()

    best_score = -1.0
    best_key = None
    best_key_entity = None
    best_key_attribute = None
    best_key_emb = None

    for canon_key, canon_entity, canon_attribute, canon_emb in registry:
        # Check entity compatibility first: don't compare across completely different entities
        if not is_same_entity(fact.entity, canon_entity):
            continue
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
        registry.append((new_key, fact.entity, fact.attribute, fact_emb))
        update_fact_canonical_key(fact.id, new_key)
        fact.canonical_key = new_key
        return new_key

    if best_score >= CANON_AUTO_THRESHOLD:
        # Auto-assign
        update_fact_canonical_key(fact.id, best_key)
        fact.canonical_key = best_key
        return best_key

    # If attributes share very little lexical vocabulary (<55), they are distinct concepts
    attr_ratio = fuzz.token_set_ratio(fact.attribute.lower(), best_key_attribute.lower())
    if attr_ratio < 55:
        new_key = _make_canonical_key(fact.entity, fact.attribute)
        insert_canonical_key(new_key, fact.entity, fact.attribute, fact_emb)
        registry.append((new_key, fact.entity, fact.attribute, fact_emb))
        update_fact_canonical_key(fact.id, new_key)
        fact.canonical_key = new_key
        return new_key

    # Tiebreak zone: check cache first, then ask LLM
    cache_key = (
        best_key_entity.lower().strip(),
        best_key_attribute.lower().strip(),
        fact.entity.lower().strip(),
        fact.attribute.lower().strip(),
    )
    rev_cache_key = (cache_key[2], cache_key[3], cache_key[0], cache_key[1])

    if cache_key in _tiebreak_cache:
        same_concept = _tiebreak_cache[cache_key]
    elif rev_cache_key in _tiebreak_cache:
        same_concept = _tiebreak_cache[rev_cache_key]
    else:
        same_concept = _llm_tiebreak(
            entity_a=best_key_entity,
            attribute_a=best_key_attribute,
            context_a=chunk_text[:300],
            entity_b=fact.entity,
            attribute_b=fact.attribute,
            context_b=chunk_text[:300],
        )
        _tiebreak_cache[cache_key] = same_concept

    if same_concept:
        update_fact_canonical_key(fact.id, best_key)
        fact.canonical_key = best_key
        return best_key
    else:
        new_key = _make_canonical_key(fact.entity, fact.attribute)
        insert_canonical_key(new_key, fact.entity, fact.attribute, fact_emb)
        registry.append((new_key, fact.entity, fact.attribute, fact_emb))
        update_fact_canonical_key(fact.id, new_key)
        fact.canonical_key = new_key
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
    """Ask Groq whether two (entity, attribute) pairs refer to the same concept."""
    from backend.app.llm_client import call_llm
    user_msg = f"""Phrasing A: entity="{entity_a}", attribute="{attribute_a}"
Context A: "{context_a}"

Phrasing B: entity="{entity_b}", attribute="{attribute_b}"
Context B: "{context_b}"

Are these the same underlying concept for comparison purposes?"""

    t0 = time.monotonic()
    try:
        raw = call_llm(
            system_prompt=CANON_TIEBREAK_SYSTEM,
            user_message=user_msg,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        result = CanonTieBreakResult.model_validate_json(raw)
        log_llm_call(
            call_type="canonicalization_tiebreak",
            model=GROQ_MODEL,
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
            model=GROQ_MODEL,
            input_summary=f'"{entity_a}/{attribute_a}" vs "{entity_b}/{attribute_b}"',
            output_summary=f"tiebreak failed: {str(e)[:80]}",
            latency_ms=latency_ms,
            success=False,
        )
        return False
