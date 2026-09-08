"""
Relationship reasoning engine.
For each pair of candidate facts (same canonical key, different documents),
calls Groq LLM to classify: corroboration / contradiction / reconciled_context / uncertain.
Gracefully degrades on validation failure — marks uncertain, logs to trace.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from backend.app.canonicalization.embedder import cosine_similarity, embed_text
from backend.app.canonicalization.canonicalizer import is_same_entity
from backend.app.config import DB_PATH, GROQ_MODEL
from backend.app.llm_client import call_llm
from backend.app.models.schema import Fact, Relationship, RelationshipResult
from backend.app.reasoning.prompts import (
    RELATIONSHIP_REASONING_SYSTEM_PROMPT,
    build_reasoning_user_message,
)
from backend.app.retrieval.hybrid_retriever import find_candidate_facts
from backend.app.storage.repository import (
    get_document,
    get_fact,
    get_relationships_for_fact,
    insert_relationship,
    list_facts_for_canonical_key,
    list_all_facts_with_embeddings,
)
from backend.app.tracing.trace_log import log_llm_call

# Minimum cosine similarity required for a near-miss (hybrid-search) candidate
# to be considered worth reasoning about. Exact canonical-key matches bypass this.
NEAR_MISS_MIN_SIMILARITY = 0.65


def reason_about_fact(
    fact: Fact,
    db_path: Path = DB_PATH,
) -> list[Relationship]:
    """
    Find candidate facts from other documents and reason about their relationship.
    Returns a list of new Relationship objects (also persisted to DB).
    """
    if fact.verification_status == "extraction_failed":
        return []
    if not fact.canonical_key:
        from backend.app.storage.repository import get_fact
        db_fact = get_fact(fact.id, db_path)
        if db_fact and db_fact.canonical_key:
            fact.canonical_key = db_fact.canonical_key
        else:
            return []

    # Find candidates: same canonical key from OTHER documents
    all_same_key = list_facts_for_canonical_key(fact.canonical_key, db_path)
    candidates = [
        f for f, _ in all_same_key
        if f.document_id != fact.document_id and f.id != fact.id
    ]

    # If few exact matches, also include top hybrid near-miss candidates
    if len(candidates) < 2:
        query_text = f"{fact.entity} {fact.attribute}: {fact.value}"
        try:
            query_emb = embed_text(query_text)
        except Exception:
            query_emb = None

        near_miss = find_candidate_facts(fact, db_path, top_k=10, exclude_document_id=fact.document_id)
        candidate_ids = {c.id for c in candidates}

        all_facts_with_emb = {f.id: emb for f, emb in list_all_facts_with_embeddings(db_path)}

        for c in near_miss:
            if c.id in candidate_ids:
                continue
            if len(candidates) >= 3:
                break
            if not is_same_entity(fact.entity, c.entity):
                continue
            if query_emb is not None:
                cand_emb = all_facts_with_emb.get(c.id)
                if cand_emb is not None:
                    sim = cosine_similarity(query_emb, cand_emb)
                    if sim < NEAR_MISS_MIN_SIMILARITY:
                        continue
            candidates.append(c)
            candidate_ids.add(c.id)

    relationships: list[Relationship] = []

    for candidate in candidates:
        existing = get_relationships_for_fact(fact.id, db_path)
        already_done = any(
            (r.fact_id_a == fact.id and r.fact_id_b == candidate.id) or
            (r.fact_id_a == candidate.id and r.fact_id_b == fact.id)
            for r in existing
        )
        if already_done:
            continue

        rel = _call_reasoning_engine(fact, candidate, db_path)
        if rel:
            insert_relationship(rel, db_path)
            relationships.append(rel)

    return relationships


def _call_reasoning_engine(
    fact_a: Fact,
    fact_b: Fact,
    db_path: Path = DB_PATH,
) -> Relationship | None:
    """Call Groq to classify the relationship between two facts."""
    doc_a = get_document(fact_a.document_id, db_path)
    doc_b = get_document(fact_b.document_id, db_path)
    doc_a_name = doc_a.filename if doc_a else fact_a.document_id
    doc_b_name = doc_b.filename if doc_b else fact_b.document_id

    user_msg = build_reasoning_user_message(
        doc_a_filename=doc_a_name,
        entity_a=fact_a.entity,
        attribute_a=fact_a.attribute,
        value_a=fact_a.value,
        unit_a=fact_a.unit,
        scope_a=fact_a.scope,
        evidence_a=fact_a.verbatim_evidence,
        doc_b_filename=doc_b_name,
        entity_b=fact_b.entity,
        attribute_b=fact_b.attribute,
        value_b=fact_b.value,
        unit_b=fact_b.unit,
        scope_b=fact_b.scope,
        evidence_b=fact_b.verbatim_evidence,
    )

    last_error: str | None = None
    t0 = time.monotonic()
    try:
        raw = call_llm(
            system_prompt=RELATIONSHIP_REASONING_SYSTEM_PROMPT,
            user_message=user_msg,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        result = RelationshipResult.model_validate_json(raw)

        log_llm_call(
            call_type="relationship_reasoning",
            model=GROQ_MODEL,
            input_summary=f"{fact_a.id[:8]} vs {fact_b.id[:8]}",
            output_summary=f"{result.relationship_type} (conf={result.confidence:.2f})",
            latency_ms=latency_ms,
            success=True,
        )

        return Relationship(
            id=str(uuid.uuid4()),
            fact_id_a=fact_a.id,
            fact_id_b=fact_b.id,
            relationship_type=result.relationship_type,
            explanation=result.explanation,
            confidence=result.confidence,
        )

    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        last_error = str(e)
        log_llm_call(
            call_type="relationship_reasoning",
            model=GROQ_MODEL,
            input_summary=f"{fact_a.id[:8]} vs {fact_b.id[:8]}",
            output_summary=f"reasoning failed: {last_error[:80]}",
            latency_ms=latency_ms,
            success=False,
        )

    # Degrade gracefully
    return Relationship(
        id=str(uuid.uuid4()),
        fact_id_a=fact_a.id,
        fact_id_b=fact_b.id,
        relationship_type="uncertain",
        explanation=f"Reasoning engine failed: {last_error or 'unknown error'}",
        confidence=0.0,
    )
