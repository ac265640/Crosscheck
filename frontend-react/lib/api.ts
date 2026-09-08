import type {
  DocumentSummary,
  Fact,
  FactRelationship,
  CasesData,
  TraceEntry,
  UploadResponse,
} from '@/lib/types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ── Documents ─────────────────────────────────────────────────────────────────

export function fetchDocuments(): Promise<DocumentSummary[]> {
  return apiFetch<DocumentSummary[]>('/documents');
}

export function computeStats(docs: DocumentSummary[]) {
  const totalDocs = docs.length;
  const totalFacts = docs.reduce((s, d) => s + d.fact_count, 0);
  const totalVerified = docs.reduce((s, d) => s + d.verified_count, 0);
  const verifiedRate =
    totalFacts > 0 ? Math.round((totalVerified / totalFacts) * 100) : 0;
  return { totalDocs, totalFacts, totalVerified, verifiedRate };
}

// ── Document Facts ────────────────────────────────────────────────────────────

export function fetchDocumentFacts(
  docId: string,
  status?: string,
): Promise<Fact[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  return apiFetch<Fact[]>(`/documents/${encodeURIComponent(docId)}/facts${qs}`);
}

// ── Fact relationships ────────────────────────────────────────────────────────

export function fetchFactRelationships(
  factId: string,
): Promise<FactRelationship[]> {
  return apiFetch<FactRelationship[]>(
    `/facts/${encodeURIComponent(factId)}/relationships`,
  );
}

// ── Cases ─────────────────────────────────────────────────────────────────────

export function fetchCases(): Promise<CasesData> {
  return apiFetch<CasesData>('/relationships/cases');
}

// ── Trace ─────────────────────────────────────────────────────────────────────

export function fetchTrace(n = 50): Promise<TraceEntry[]> {
  return apiFetch<TraceEntry[]>(`/trace?n=${n}`);
}

// ── Upload ─────────────────────────────────────────────────────────

// Returns the SSE stream URL for a given job (used with EventSource)
export function getJobStreamUrl(jobId: string): string {
  return `${BASE_URL}/jobs/${encodeURIComponent(jobId)}/stream`;
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE_URL}/documents`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json() as Promise<UploadResponse>;
}
