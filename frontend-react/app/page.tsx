'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchDocuments, computeStats } from '@/lib/api';
import type { DocumentSummary } from '@/lib/types';
import UploadModal from '@/components/upload/UploadModal';

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso; }
}

function VerifiedBadge({ rate }: { rate: number }) {
  const cls = rate >= 90 ? 'badge-success' : rate >= 70 ? 'badge-warning' : 'badge-danger';
  return <span className={`badge ${cls}`}>{rate}% verified</span>;
}

export default function DashboardPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetchDocuments()
      .then(setDocs)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const stats = computeStats(docs);

  return (
    <>
      {showUpload && (
        <UploadModal
          onClose={() => { setShowUpload(false); load(); }}
        />
      )}

      {/* Header */}
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-title">Documents</h1>
            <p className="page-subtitle">Ingested PDFs and their extracted facts</p>
          </div>
          <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            Upload PDF
          </button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="stats-strip">
        <div className="stat-card">
          <div className="stat-label">Documents</div>
          <div className="stat-value">{stats.totalDocs}</div>
          <div className="stat-sub">ingested PDFs</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Facts</div>
          <div className="stat-value">{stats.totalFacts.toLocaleString()}</div>
          <div className="stat-sub">extracted claims</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Verified</div>
          <div className="stat-value">{stats.totalVerified.toLocaleString()}</div>
          <div className="stat-sub">evidence-backed</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Verified Rate</div>
          <div className="stat-value">{stats.verifiedRate}%</div>
          <div className="stat-sub">across all docs</div>
        </div>
      </div>

      {/* Docs grid */}
      {loading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 140, borderRadius: 12 }} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-icon">⚠️</div>
          <div className="empty-state-title">Could not load documents</div>
          <div className="empty-state-sub">{error}</div>
          <button className="btn btn-secondary" style={{ marginTop: 16 }} onClick={load}>Retry</button>
        </div>
      )}

      {!loading && !error && docs.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📂</div>
          <div className="empty-state-title">No documents yet</div>
          <div className="empty-state-sub">Upload your first PDF to start extracting facts and reasoning across documents.</div>
          <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => setShowUpload(true)}>
            Upload your first PDF
          </button>
        </div>
      )}

      {!loading && !error && docs.length > 0 && (
        <div className="documents-grid">
          {docs.map(d => {
            const verifiedRate = d.fact_count > 0 ? Math.round((d.verified_count / d.fact_count) * 100) : 0;
            return (
              <div
                key={d.document.id}
                className="doc-card"
                onClick={() => router.push(`/documents/${d.document.id}`)}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  <span style={{ fontSize: 28, flexShrink: 0 }}>📄</span>
                  <div style={{ overflow: 'hidden', flex: 1 }}>
                    <div className="doc-card-name">{d.document.filename}</div>
                    <div className="doc-card-meta">
                      <span>{d.document.page_count} pages</span>
                      <span>·</span>
                      <span>{formatDate(d.document.uploaded_at)}</span>
                    </div>
                  </div>
                </div>
                <div className="doc-card-stats">
                  <span className="badge badge-purple">{d.fact_count.toLocaleString()} facts</span>
                  <span className="badge badge-info">{d.chunk_count} chunks</span>
                  <VerifiedBadge rate={verifiedRate} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
