"""
Pydantic data models for the Fact Knowledge Layer system.
Implements the exact schema from the assignment spec (section 4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    page_count: int


class Chunk(BaseModel):
    id: str
    document_id: str
    page_number: int
    bbox: tuple[float, float, float, float] | None = None
    text: str
    section_title: str | None = None  # from section-aware chunking, may be None


class Fact(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    entity: str                      # e.g. "Delhivery Limited", free text, LLM-proposed
    attribute: str                   # e.g. "revenue from services", free text, LLM-proposed
    value: str                       # keep as string; normalize downstream, don't force numeric
    unit: str | None = None          # e.g. "INR crore", "%", None for non-numeric facts
    scope: dict = Field(default_factory=dict)  # free-form: {"period": "FY24", "basis": "consolidated", ...}
    verbatim_evidence: str           # exact quote, must appear in chunk text (verified)
    page_number: int
    bbox: tuple[float, float, float, float] | None = None
    canonical_key: str | None = None  # filled in by canonicalization step
    confidence: float = 1.0          # combination of extraction + verification confidence
    verification_status: Literal["verified", "unverified", "extraction_failed"] = "unverified"


class Relationship(BaseModel):
    id: str
    fact_id_a: str
    fact_id_b: str
    relationship_type: Literal["corroboration", "contradiction", "reconciled_context", "uncertain"]
    explanation: str                 # LLM-generated, must reference both evidences
    confidence: float


# ── Extraction-only model (LLM output before DB insertion) ─────────────────────

class ExtractedFact(BaseModel):
    """Subset of Fact returned by the LLM extraction step.
    Additional fields (id, document_id, chunk_id, page_number, bbox,
    canonical_key, confidence, verification_status) are filled in downstream.
    """
    entity: str
    attribute: str
    value: str
    unit: str | None = None
    scope: dict = Field(default_factory=dict)
    verbatim_evidence: str


class CanonTieBreakResult(BaseModel):
    """LLM response for canonicalization tie-break (Appendix B)."""
    same_concept: bool
    reasoning: str


class RelationshipResult(BaseModel):
    """LLM response for relationship reasoning (Appendix C)."""
    relationship_type: Literal["corroboration", "contradiction", "reconciled_context", "uncertain"]
    explanation: str
    confidence: float


# ── API response shapes ────────────────────────────────────────────────────────

class DocumentSummary(BaseModel):
    document: Document
    chunk_count: int
    fact_count: int
    verified_count: int
    unverified_count: int
    failed_count: int


class FactWithRelationships(BaseModel):
    fact: Fact
    relationships: list[RelationshipDetail]


class RelationshipDetail(BaseModel):
    relationship: Relationship
    linked_fact: Fact


class TraceEntry(BaseModel):
    timestamp: str
    call_type: str
    model: str
    input_summary: str
    output_summary: str
    latency_ms: float
    success: bool
