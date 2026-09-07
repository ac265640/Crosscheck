"""
Evidence verification guardrail.
Uses rapidfuzz to fuzzy-match verbatim_evidence against the source chunk text.
Facts that fail verification are kept but marked 'unverified' and get lower confidence.
Never silently drops facts — visible failure is better than hidden failure.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from backend.app.config import EVIDENCE_VERIFICATION_THRESHOLD
from backend.app.models.schema import Fact


def verify_fact_evidence(fact: Fact, chunk_text: str) -> Fact:
    """
    Fuzzy-match fact.verbatim_evidence against chunk_text.
    Returns a new Fact with updated verification_status and confidence.
    """
    # Skip facts already marked as extraction failures
    if fact.verification_status == "extraction_failed":
        return fact

    score = fuzz.partial_ratio(fact.verbatim_evidence, chunk_text)

    if score >= EVIDENCE_VERIFICATION_THRESHOLD:
        return fact.model_copy(
            update={
                "verification_status": "verified",
                "confidence": fact.confidence * (score / 100.0),
            }
        )
    else:
        # Still keep the fact — surface it for review, don't discard
        confidence_penalty = score / 100.0 * 0.5  # halved for low-match evidence
        return fact.model_copy(
            update={
                "verification_status": "unverified",
                "confidence": fact.confidence * confidence_penalty,
            }
        )


def verify_facts_batch(
    facts: list[Fact], chunk_text_map: dict[str, str]
) -> list[Fact]:
    """
    Verify a list of facts against their source chunks.
    chunk_text_map: {chunk_id -> chunk text}
    """
    verified = []
    for fact in facts:
        chunk_text = chunk_text_map.get(fact.chunk_id, "")
        verified.append(verify_fact_evidence(fact, chunk_text))
    return verified
