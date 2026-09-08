"""
Regression tests against the curated golden dataset (eval/golden_dataset.json).

Tests:
1. Golden dataset schema integrity & Pydantic Fact model adherence.
2. Evidence verification guardrail behavior on golden evidence.
3. Canonicalization and entity resolution behavior on golden entity/attribute pairs.
4. Prompt construction & structured result validation for the Four Required Cases:
   - corroboration
   - contradiction
   - reconciled_context
   - uncertain
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from backend.app.models.schema import Fact, Relationship, RelationshipResult
from backend.app.guardrails.evidence_verifier import verify_fact_evidence
from backend.app.canonicalization.canonicalizer import is_same_entity
from backend.app.reasoning.prompts import (
    RELATIONSHIP_REASONING_SYSTEM_PROMPT,
    build_reasoning_user_message,
)

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "eval" / "golden_dataset.json"


@pytest.fixture(scope="module")
def golden_data():
    assert GOLDEN_PATH.exists(), f"Golden dataset not found at {GOLDEN_PATH}"
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestGoldenDatasetSchema:
    def test_golden_dataset_file_exists_and_loads(self, golden_data):
        assert isinstance(golden_data, dict)
        assert "facts" in golden_data
        assert "relationship_cases" in golden_data

    def test_golden_dataset_fact_count_in_range(self, golden_data):
        facts = golden_data["facts"]
        # Assignment spec: roughly 15–25 ground-truth facts
        assert 15 <= len(facts) <= 25, f"Expected 15-25 facts, got {len(facts)}"

    def test_all_facts_conform_to_schema(self, golden_data):
        for fact_dict in golden_data["facts"]:
            fact = Fact(
                id=fact_dict["id"],
                document_id="doc-golden",
                chunk_id="chunk-golden",
                entity=fact_dict["entity"],
                attribute=fact_dict["attribute"],
                value=fact_dict["value"],
                unit=fact_dict.get("unit"),
                scope=fact_dict.get("scope", {}),
                verbatim_evidence=fact_dict["verbatim_evidence"],
                page_number=fact_dict["page_number"],
                bbox=None,
                canonical_key=fact_dict["canonical_key"],
                confidence=1.0,
                verification_status="verified",
            )
            assert fact.id.startswith("gold-fact-")
            assert len(fact.verbatim_evidence) > 10
            assert fact.page_number >= 1

    def test_four_required_relationship_cases_present(self, golden_data):
        cases = golden_data["relationship_cases"]
        required = ["corroboration", "contradiction", "reconciled_context", "uncertain"]
        for req in required:
            assert req in cases, f"Missing required relationship case: {req}"
            case = cases[req]
            assert case["relationship_type"] == req
            assert "fact_a_id" in case
            assert "fact_b_id" in case
            assert len(case["expected_reasoning"]) > 20


class TestGoldenGuardrails:
    def test_golden_facts_evidence_passes_exact_and_fuzzy_verification(self, golden_data):
        for fact_dict in golden_data["facts"]:
            evidence = fact_dict["verbatim_evidence"]
            surrounding_chunk = f"Context before: In the reviewed filing, {evidence}. Additional notes follow."
            fact = Fact(
                id=fact_dict["id"],
                document_id="doc-1",
                chunk_id="chk-1",
                entity=fact_dict["entity"],
                attribute=fact_dict["attribute"],
                value=fact_dict["value"],
                unit=fact_dict.get("unit"),
                scope=fact_dict.get("scope", {}),
                verbatim_evidence=evidence,
                page_number=fact_dict["page_number"],
                bbox=None,
                canonical_key=fact_dict["canonical_key"],
                confidence=1.0,
                verification_status="unverified",
            )
            verified_fact = verify_fact_evidence(fact, surrounding_chunk)
            assert verified_fact.verification_status == "verified", (
                f"Fact {fact.id} failed verification against surrounding chunk"
            )

    def test_tampered_golden_evidence_is_marked_unverified(self, golden_data):
        fact_dict = golden_data["facts"][0]
        fact = Fact(
            id=fact_dict["id"],
            document_id="doc-1",
            chunk_id="chk-1",
            entity=fact_dict["entity"],
            attribute=fact_dict["attribute"],
            value=fact_dict["value"],
            unit=fact_dict.get("unit"),
            scope=fact_dict.get("scope", {}),
            verbatim_evidence="Completely fabricated statement that does not appear in any report.",
            page_number=fact_dict["page_number"],
            bbox=None,
            canonical_key=fact_dict["canonical_key"],
            confidence=1.0,
            verification_status="unverified",
        )
        verified_fact = verify_fact_evidence(fact, "Revenue from contracts was 8,142 Cr.")
        assert verified_fact.verification_status == "unverified"
        assert verified_fact.confidence < 0.6


class TestGoldenCanonicalization:
    def test_golden_entity_variations_resolve_to_same_entity(self):
        variations = [
            ("Delhivery Limited", "Delhivery Ltd"),
            ("Delhivery Ltd", "Delhivery"),
            ("Reserve Bank of India", "RBI"),
            ("Government of India", "India"),
        ]
        for ent_a, ent_b in variations:
            assert is_same_entity(ent_a, ent_b), f"Failed to match entity variation: {ent_a} vs {ent_b}"

    def test_distinct_entities_are_not_merged(self):
        distinct = [
            ("Delhivery Limited", "India"),
            ("Reserve Bank of India", "International Monetary Fund"),
            ("Delhivery", "Ministry of Finance"),
        ]
        for ent_a, ent_b in distinct:
            assert not is_same_entity(ent_a, ent_b), f"Incorrectly merged distinct entities: {ent_a} vs {ent_b}"


class TestGoldenFourCasesReasoning:
    @pytest.mark.parametrize("case_key", ["corroboration", "contradiction", "reconciled_context", "uncertain"])
    def test_build_reasoning_prompt_for_golden_cases(self, golden_data, case_key):
        case = golden_data["relationship_cases"][case_key]
        facts_by_id = {f["id"]: f for f in golden_data["facts"]}
        fa = facts_by_id[case["fact_a_id"]]
        fb = facts_by_id[case["fact_b_id"]]

        user_msg = build_reasoning_user_message(
            doc_a_filename=fa["document_filename"],
            entity_a=fa["entity"],
            attribute_a=fa["attribute"],
            value_a=fa["value"],
            unit_a=fa.get("unit"),
            scope_a=fa.get("scope", {}),
            evidence_a=fa["verbatim_evidence"],
            doc_b_filename=fb["document_filename"],
            entity_b=fb["entity"],
            attribute_b=fb["attribute"],
            value_b=fb["value"],
            unit_b=fb.get("unit"),
            scope_b=fb.get("scope", {}),
            evidence_b=fb["verbatim_evidence"],
        )

        assert fa["document_filename"] in user_msg
        assert fb["document_filename"] in user_msg
        assert fa["value"] in user_msg
        assert fb["value"] in user_msg
        assert fa["verbatim_evidence"] in user_msg
        assert fb["verbatim_evidence"] in user_msg

    @pytest.mark.parametrize("case_key", ["corroboration", "contradiction", "reconciled_context", "uncertain"])
    def test_relationship_result_model_validation_for_cases(self, golden_data, case_key):
        case = golden_data["relationship_cases"][case_key]
        result = RelationshipResult(
            relationship_type=case["expected_outcome"],
            explanation=case["expected_reasoning"],
            confidence=0.95 if case_key != "uncertain" else 0.50,
        )
        assert result.relationship_type == case_key
        assert len(result.explanation) > 20
        assert 0.0 <= result.confidence <= 1.0
