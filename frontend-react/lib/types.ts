// ── Core domain types mirroring backend Pydantic models ──────────────────────

export interface Document {
  id: string;
  filename: string;
  page_count: number;
  uploaded_at: string;
}

export interface DocumentSummary {
  document: Document;
  chunk_count: number;
  fact_count: number;
  verified_count: number;
  unverified_count: number;
  failed_count: number;
}

export interface Fact {
  id: string;
  document_id: string;
  chunk_id: string;
  entity: string;
  attribute: string;
  value: string;
  unit?: string | null;
  date_context?: string | null;
  source_text: string;
  source_page?: number | null;
  bbox?: [number, number, number, number] | null;
  verification_status: 'verified' | 'unverified' | 'extraction_failed';
  confidence?: number | null;
}

export type RelType =
  | 'corroboration'
  | 'contradiction'
  | 'reconciled_context'
  | 'uncertain';

export interface Relationship {
  id: string;
  fact_id_a: string;
  fact_id_b: string;
  relationship_type: RelType;
  confidence: number;
  explanation: string;
}

export interface FactRelationship {
  relationship: Relationship;
  linked_fact: Fact | null;
}

// ── Cases ─────────────────────────────────────────────────────────────────────

export interface CaseEntry {
  relationship: Relationship;
  fact_a: Fact | null;
  fact_b: Fact | null;
}

export type CasesData = Record<RelType, CaseEntry | null>;

// ── Trace ─────────────────────────────────────────────────────────────────────

export interface TraceEntry {
  ts: string;
  call_type: string;
  model: string;
  success: boolean;
  latency_ms?: number | null;
  input_summary?: string | null;
  output_summary?: string | null;
  error?: string | null;
}

// ── Upload / Jobs ─────────────────────────────────────────────────────────────

export interface UploadResponse {
  job_id: string;
  filename: string;
  status: string;
  message: string;
}

// ── Job / SSE Progress ────────────────────────────────────────────────────────

export interface ProgressEvent {
  stage: string;
  pct: number;
  msg: string;
  document_id: string | null;
  ts: number;
}
