'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { fetchDocuments, computeStats, deleteDocument } from '@/lib/api';
import type { DocumentSummary } from '@/lib/types';
import UploadModal from '@/components/upload/UploadModal';

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch { return iso; }
}

function getCategory(filename: string): { label: string; color: string } {
  const f = filename.toLowerCase();
  if (f.includes('delhivery')) {
    if (f.includes('prospectus')) return { label: 'Prospectus', color: '#818cf8' };
    if (f.includes('annual'))    return { label: 'Annual Report', color: '#a78bfa' };
    return                               { label: 'Earnings', color: '#a78bfa' };
  }
  if (f.includes('bluedart')) return { label: 'Investor Deck', color: '#38bdf8' };
  if (f.includes('rbi') || f.includes('economic') || f.includes('imf'))
    return { label: 'Macro Survey', color: '#34d399' };
  return { label: 'PDF Document', color: '#94a3b8' };
}

type CategoryFilter = 'all' | 'delhivery' | 'macro' | 'bluedart';
type SortOption = 'facts' | 'verified' | 'pages' | 'name';

export default function DashboardPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [sortBy, setSortBy] = useState<SortOption>('facts');
  const [docToDelete, setDocToDelete] = useState<DocumentSummary | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetchDocuments()
      .then(setDocs)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const stats = computeStats(docs);

  const filteredDocs = useMemo(() => {
    let list = [...docs];
    if (categoryFilter !== 'all') {
      list = list.filter(d => {
        const fn = d.document.filename.toLowerCase();
        if (categoryFilter === 'delhivery') return fn.includes('delhivery');
        if (categoryFilter === 'macro') return fn.includes('rbi') || fn.includes('economic') || fn.includes('imf');
        if (categoryFilter === 'bluedart') return fn.includes('bluedart');
        return true;
      });
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(d => d.document.filename.toLowerCase().includes(q));
    }
    list.sort((a, b) => {
      if (sortBy === 'facts')    return b.fact_count - a.fact_count;
      if (sortBy === 'verified') {
        const rA = a.fact_count > 0 ? a.verified_count / a.fact_count : 0;
        const rB = b.fact_count > 0 ? b.verified_count / b.fact_count : 0;
        return rB - rA;
      }
      if (sortBy === 'pages') return b.document.page_count - a.document.page_count;
      if (sortBy === 'name')  return a.document.filename.localeCompare(b.document.filename);
      return 0;
    });
    return list;
  }, [docs, search, categoryFilter, sortBy]);

  const handleDelete = async () => {
    if (!docToDelete) return;
    setDeleting(true);
    try {
      await deleteDocument(docToDelete.document.id);
      setDocToDelete(null);
      load();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete document');
    } finally { setDeleting(false); }
  };

  return (
    <>
      {showUpload && (
        <UploadModal onClose={() => { setShowUpload(false); load(); }} />
      )}

      {/* Delete modal */}
      {docToDelete && (
        <div className="modal-overlay" onClick={() => !deleting && setDocToDelete(null)}>
          <div className="modal" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="modal-title" style={{ fontSize: 16 }}>Remove document</div>
            <div className="modal-sub" style={{ marginTop: 8 }}>
              Permanently remove <strong style={{ color: 'var(--text-primary)' }}>{docToDelete.document.filename}</strong>?
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 10, lineHeight: 1.6 }}>
              This removes the file, all {docToDelete.fact_count.toLocaleString()} facts, and relationships from the local database.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 22 }}>
              <button className="btn btn-secondary" disabled={deleting} onClick={() => setDocToDelete(null)}>Cancel</button>
              <button className="btn" style={{ background: 'var(--danger)', color: '#fff', border: 'none' }} disabled={deleting} onClick={handleDelete}>
                {deleting ? 'Removing…' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Page header ───────────────────────────────────────── */}
      <div className="dash-header">
        <div>
          <div className="dash-breadcrumb">Corpus Intelligence</div>
          <h1 className="dash-title" style={{ display: 'flex', alignItems: 'center' }}>
            Documents
            {!loading && docs.length > 0 && (
              <span style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-muted)',
                background: 'var(--bg-subtle)',
                padding: '3px 10px',
                borderRadius: 20,
                border: '1px solid var(--border)',
                marginLeft: 12,
                letterSpacing: 0,
              }}>
                {docs.length} active
              </span>
            )}
          </h1>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link href="/cases" className="btn btn-secondary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2" />
              <polyline points="2 17 12 22 22 17" />
              <polyline points="2 12 12 17 22 12" />
            </svg>
            Four Cases
          </Link>
          <button className="btn btn-primary btn-sm" onClick={() => setShowUpload(true)}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload PDF
          </button>
        </div>
      </div>

      {/* ── Stats strip ───────────────────────────────────────── */}
      <div className="dash-stats">
        {[
          { label: 'Documents', value: stats.totalDocs, sub: 'active corpus' },
          { label: 'Facts extracted', value: stats.totalFacts.toLocaleString(), sub: 'verifiable claims' },
          { label: 'Verified evidence', value: stats.totalVerified.toLocaleString(), sub: 'grounded in chunks', accent: true },
          { label: 'Corpus precision', value: `${stats.verifiedRate}%`, sub: 'cross-verified rate' },
        ].map((s, i) => (
          <div key={i} className="dash-stat">
            <div className="dash-stat-label">{s.label}</div>
            <div className={`dash-stat-value${s.accent ? ' accent' : ''}`}>{s.value}</div>
            <div className="dash-stat-sub">{s.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Cross-doc callout ─────────────────────────────────── */}
      <div className="dash-callout">
        <div>
          <div className="dash-callout-title">Cross-Document Evidence & Reasoning</div>
          <div className="dash-callout-sub">Corroborations, contradictions, contextual reconciliations, and uncertainty — sourced to exact lines and bounding boxes.</div>
        </div>
        <Link href="/cases" className="btn btn-secondary btn-sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
          Explore Four Cases →
        </Link>
      </div>

      {/* ── Toolbar ───────────────────────────────────────────── */}
      <div className="dash-toolbar">
        <div className="dash-filters">
          {(['all', 'delhivery', 'macro', 'bluedart'] as CategoryFilter[]).map(id => {
            const labels: Record<CategoryFilter, string> = { all: 'All', delhivery: 'Delhivery', macro: 'Macroeconomy', bluedart: 'Blue Dart' };
            return (
              <button
                key={id}
                className={`filter-chip${categoryFilter === id ? ' active' : ''}`}
                onClick={() => setCategoryFilter(id)}
              >{labels[id]}</button>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div className="search-wrapper">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <input
              className="search-input"
              placeholder="Search document…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: '0 2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                title="Clear"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            )}
          </div>
          <select className="sort-select" value={sortBy} onChange={e => setSortBy(e.target.value as SortOption)}>
            <option value="facts">Most facts</option>
            <option value="verified">Verification rate</option>
            <option value="pages">Page count</option>
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      {/* ── Results count ─────────────────────────────────────── */}
      {!loading && !error && (
        <div className="dash-count">
          {filteredDocs.length} {filteredDocs.length === 1 ? 'document' : 'documents'}
          {search && <span className="dash-count-query"> matching &ldquo;{search}&rdquo;</span>}
        </div>
      )}

      {/* ── Loading skeletons ─────────────────────────────────── */}
      {loading && (
        <div className="docs-grid">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="skeleton" style={{ height: 168, borderRadius: 10 }} />
          ))}
        </div>
      )}

      {/* ── Error ─────────────────────────────────────────────── */}
      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-title">Could not connect</div>
          <div className="empty-state-sub">{error}</div>
          <button className="btn btn-secondary" style={{ marginTop: 14 }} onClick={load}>Retry</button>
        </div>
      )}

      {/* ── Empty ─────────────────────────────────────────────── */}
      {!loading && !error && filteredDocs.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">{search ? 'No matches' : 'No documents yet'}</div>
          <div className="empty-state-sub">{search ? `Nothing matched "${search}".` : 'Upload a PDF to begin extraction.'}</div>
          {search
            ? <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={() => setSearch('')}>Clear search</button>
            : <button className="btn btn-primary" style={{ marginTop: 14 }} onClick={() => setShowUpload(true)}>Upload PDF</button>
          }
        </div>
      )}

      {/* ── Document grid ─────────────────────────────────────── */}
      {!loading && !error && filteredDocs.length > 0 && (
        <div className="docs-grid">
          {filteredDocs.map(d => {
            const rate = d.fact_count > 0 ? Math.round((d.verified_count / d.fact_count) * 100) : 0;
            const cat  = getCategory(d.document.filename);
            const isHov = hoveredCard === d.document.id;

            return (
              <div
                key={d.document.id}
                className="doc-card-v2"
                style={{ cursor: 'pointer' }}
                onClick={() => router.push(`/documents/${d.document.id}`)}
                onMouseEnter={() => setHoveredCard(d.document.id)}
                onMouseLeave={() => setHoveredCard(null)}
              >
                {/* Category stripe */}
                <div className="doc-card-stripe" style={{ background: cat.color }} />

                {/* Top row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span className="doc-cat-label" style={{ color: cat.color, borderColor: `${cat.color}30` }}>
                    {cat.label}
                  </span>
                  <button
                    className="doc-trash-btn"
                    onClick={e => { e.stopPropagation(); setDocToDelete(d); }}
                    title="Remove"
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                    </svg>
                  </button>
                </div>

                {/* Filename */}
                <div className="doc-card-name-v2" title={d.document.filename}>
                  {d.document.filename.replace(/\.pdf$/i, '')}
                </div>

                {/* Meta */}
                <div className="doc-card-meta-row">
                  <span>{d.document.page_count} pg</span>
                  <span className="dot">·</span>
                  <span>{d.chunk_count} chunks</span>
                  <span className="dot">·</span>
                  <span>{formatDate(d.document.uploaded_at)}</span>
                </div>

                {/* Progress bar */}
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 5 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Verified evidence</span>
                    <span style={{ fontWeight: 600, color: rate >= 70 ? 'var(--success)' : 'var(--text-secondary)' }}>{rate}%</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${rate}%`, background: rate >= 70 ? 'var(--success)' : 'var(--accent)' }} />
                  </div>
                </div>

                {/* Footer */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <span className="doc-pill">{d.fact_count.toLocaleString()} facts</span>
                    <span className="doc-pill success">{d.verified_count} verified</span>
                  </div>
                  <span className="doc-inspect" style={{ opacity: isHov ? 1 : 0, transform: isHov ? 'translateX(0)' : 'translateX(-4px)', transition: 'all 0.18s ease' }}>
                    Inspect →
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
