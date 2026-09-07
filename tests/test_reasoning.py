"""
Unit tests for reasoning engine prompt builders and schema validation.
Tests prompt construction and Pydantic model validation without LLM calls.
"""

from __future__ import annotations

import json
import uuid

import pytest

from backend.app.models.schema import Fact, RelationshipResult
from backend.app.reasoning.prompts import (
    RELATIONSHIP_REASONING_SYSTEM_PROMPT,
    build_reasoning_user_message,
)


def _make_fact(entity: str, attribute: str, value: str, unit: str | None = None, **kwargs) -> Fact:
    return Fact(
        id=str(uuid.uuid4()),
        document_id=kwargs.get("document_id", "doc-1"),
        chunk_id=str(uuid.uuid4()),
        entity=entity,
        attribute=attribute,
        value=value,
        unit=unit,
        scope=kwargs.get("scope", {}),
        verbatim_evidence=kwargs.get("verbatim_evidence", f"{entity} {attribute} was {value}"),
        page_number=kwargs.get("page_number", 1),
        bbox=None,
        canonical_key=kwargs.get("canonical_key", "test::canon_key"),
        confidence=1.0,
        verification_status="verified",
    )


class TestReasoningPrompts:
    def test_system_prompt_contains_required_labels(self):
        required = ["corroboration", "contradiction", "reconciled_context", "uncertain"]
        for label in required:
            assert label in RELATIONSHIP_REASONING_SYSTEM_PROMPT, (
                f"System prompt missing required label: {label}"
            )

    def test_system_prompt_requires_explanation_references_both_evidences(self):
        assert "BOTH" in RELATIONSHIP_REASONING_SYSTEM_PROMPT

    def test_build_reasoning_user_message_includes_both_facts(self):
        fact_a = _make_fact(
            "Delhivery Limited", "revenue from services", "8,142", "INR crore",
            scope={"period": "FY24", "basis": "consolidated"},
            verbatim_evidence="revenue from services was 8,142 INR crore",
            document_id="doc-1",
        )
        fact_b = _make_fact(
            "Delhivery Ltd", "services revenue", "8142", "INR crore",
            scope={"period": "FY24"},
            verbatim_evidence="services revenue 8142 crore INR",
            document_id="doc-2",
        )
        msg = build_reasoning_user_message(
            doc_a_filename="delhivery_annual_fy24.pdf",
            entity_a=fact_a.entity,
            attribute_a=fact_a.attribute,
            value_a=fact_a.value,
            unit_a=fact_a.unit,
            scope_a=fact_a.scope,
            evidence_a=fact_a.verbatim_evidence,
            doc_b_filename="delhivery_prospectus.pdf",
            entity_b=fact_b.entity,
            attribute_b=fact_b.attribute,
            value_b=fact_b.value,
            unit_b=fact_b.unit,
            scope_b=fact_b.scope,
            evidence_b=fact_b.verbatim_evidence,
        )
        assert "Delhivery Limited" in msg
        assert "8,142" in msg
        assert "Delhivery Ltd" in msg
        assert "8142" in msg
        assert "delhivery_annual_fy24.pdf" in msg
        assert "delhivery_prospectus.pdf" in msg

    def test_build_reasoning_user_message_includes_scope(self):
        fact_a = _make_fact(
            "India", "GDP growth rate", "6.4", "%",
            scope={"period": "FY25", "estimate_type": "projected"},
        )
        fact_b = _make_fact(
            "India", "GDP growth", "6.5", "%",
            scope={"period": "FY25", "estimate_type": "actual"},
        )
        msg = build_reasoning_user_message(
            doc_a_filename="economic_survey.pdf",
            entity_a=fact_a.entity,
            attribute_a=fact_a.attribute,
            value_a=fact_a.value,
            unit_a=fact_a.unit,
            scope_a=fact_a.scope,
            evidence_a=fact_a.verbatim_evidence,
            doc_b_filename="rbi_report.pdf",
            entity_b=fact_b.entity,
            attribute_b=fact_b.attribute,
            value_b=fact_b.value,
            unit_b=fact_b.unit,
            scope_b=fact_b.scope,
            evidence_b=fact_b.verbatim_evidence,
        )
        assert "projected" in msg or "FY25" in msg


class TestRelationshipResultValidation:
    def test_valid_corroboration_parses(self):
        raw = json.dumps({
            "relationship_type": "corroboration",
            "explanation": "Both documents state 8,142 INR crore revenue for FY24.",
            "confidence": 0.95,
        })
        result = RelationshipResult.model_validate_json(raw)
        assert result.relationship_type == "corroboration"
        assert result.confidence == 0.95

    def test_valid_contradiction_parses(self):
        raw = json.dumps({
            "relationship_type": "contradiction",
            "explanation": "Fact A states 6.4% while Fact B states 8.2% for the same period.",
            "confidence": 0.88,
        })
        result = RelationshipResult.model_validate_json(raw)
        assert result.relationship_type == "contradiction"

    def test_valid_reconciled_context_parses(self):
        raw = json.dumps({
            "relationship_type": "reconciled_context",
            "explanation": "Fact A is quarterly (Q4), Fact B is annual (FY24) — different periods.",
            "confidence": 0.82,
        })
        result = RelationshipResult.model_validate_json(raw)
        assert result.relationship_type == "reconciled_context"

    def test_valid_uncertain_parses(self):
        raw = json.dumps({
            "relationship_type": "uncertain",
            "explanation": "Insufficient scope metadata to classify reliably.",
            "confidence": 0.3,
        })
        result = RelationshipResult.model_validate_json(raw)
        assert result.relationship_type == "uncertain"

    def test_invalid_relationship_type_raises(self):
        raw = json.dumps({
            "relationship_type": "unknown_type",
            "explanation": "test",
            "confidence": 0.5,
        })
        with pytest.raises(Exception):
            RelationshipResult.model_validate_json(raw)

    def test_confidence_stored_as_float(self):
        raw = json.dumps({
            "relationship_type": "uncertain",
            "explanation": "Not enough context.",
            "confidence": 0.5,
        })
        result = RelationshipResult.model_validate_json(raw)
        assert isinstance(result.confidence, float)
