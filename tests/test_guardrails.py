"""
Unit tests for the evidence verification guardrail.
Tests rapidfuzz-based evidence matching without any LLM calls.
"""

from __future__ import annotations

import uuid

import pytest

from backend.app.guardrails.evidence_verifier import verify_fact_evidence
from backend.app.models.schema import Fact


def _make_fact(verbatim_evidence: str, **kwargs) -> Fact:
    return Fact(
        id=str(uuid.uuid4()),
        document_id="doc-1",
        chunk_id="chunk-1",
        entity=kwargs.get("entity", "Test Entity"),
        attribute=kwargs.get("attribute", "test attribute"),
        value=kwargs.get("value", "42"),
        unit=None,
        scope={},
        verbatim_evidence=verbatim_evidence,
        page_number=1,
        bbox=None,
        canonical_key=None,
        confidence=1.0,
        verification_status="unverified",
    )


class TestEvidenceVerifier:
    def test_exact_match_is_verified(self):
        chunk_text = "Revenue from services was 8,142 INR crore in FY24."
        fact = _make_fact("Revenue from services was 8,142 INR crore in FY24.")
        result = verify_fact_evidence(fact, chunk_text)
        assert result.verification_status == "verified"
        assert result.confidence > 0.8

    def test_substring_match_is_verified(self):
        chunk_text = (
            "In FY24, Delhivery reported revenue from services was 8,142 INR crore "
            "on a consolidated basis."
        )
        fact = _make_fact("revenue from services was 8,142 INR crore")
        result = verify_fact_evidence(fact, chunk_text)
        assert result.verification_status == "verified"

    def test_minor_whitespace_differences_are_verified(self):
        chunk_text = "GDP growth rate: 6.4%"
        fact = _make_fact("GDP growth rate:  6.4%")  # extra space
        result = verify_fact_evidence(fact, chunk_text)
        assert result.verification_status == "verified"

    def test_completely_fabricated_evidence_is_unverified(self):
        chunk_text = "Inflation was 4.2% in March 2025."
        fact = _make_fact("Unemployment rate was 15% in December 2024.")
        result = verify_fact_evidence(fact, chunk_text)
        assert result.verification_status == "unverified"
        assert result.confidence < 0.5

    def test_extraction_failed_fact_is_passed_through(self):
        chunk_text = "Some text here."
        fact = _make_fact("EXTRACTION_FAILED")
        fact = fact.model_copy(update={"verification_status": "extraction_failed", "confidence": 0.0})
        result = verify_fact_evidence(fact, chunk_text)
        # Should not re-verify extraction_failed facts
        assert result.verification_status == "extraction_failed"

    def test_empty_chunk_text_is_unverified(self):
        fact = _make_fact("Some specific evidence quote.")
        result = verify_fact_evidence(fact, "")
        assert result.verification_status == "unverified"

    def test_empty_evidence_is_unverified(self):
        chunk_text = "Some real text from the document."
        fact = _make_fact("")
        result = verify_fact_evidence(fact, chunk_text)
        assert result.verification_status == "unverified"
