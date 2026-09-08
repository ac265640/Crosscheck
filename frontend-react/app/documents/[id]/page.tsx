'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchDocuments, fetchDocumentFacts, fetchFactRelationships } from '@/lib/api';
import type { DocumentSummary, Fact, FactRelationship, RelType } from '@/lib/types';
import FactsTable from '@/components/documents/FactsTable';
import FactSidePanel from '@/components/documents/FactSidePanel';
import { RelationshipBadge } from '@/components/documents/RelationshipBadge';
import TraceEntryRow from '@/components/trace/TraceEntry';

type Tab = 'facts' | 'relationships' | 'trace';

export default function DocumentDetailPage() {
  const params = useParams();
  const docId = params.id as string;

  const [docSummary, setDocSummary] = useState<DocumentSummary | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('facts');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // For relationships tab
  const [relFacts, setRelFacts] = useState<Fact[]>([]);
  const [relMap, setRelMap] = useState<Record<string, FactRelationship[]>>({});
  const [relsLoading, setRelsLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchDocuments(), fetchDocumentFacts(docId)])
      .then(([docs, f]) => {
        const found = docs.find(d => d.document.id === docId) || null;
        setDocSummary(found);
        setFacts(f);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [docId]);

  // Load relationships when that tab is opened
  useEffect(() => {
    if (activeTab !== 'relationships' || relFacts.length > 0) return;
    setRelsLoading(true);
    // Sample up to 30 verified facts to show relationships
    const sample = facts.filter(f => f.verification_status === 'verified').slice(0, 30);
    setRelFacts(sample);
    Promise.all(sample.map(f => fetchFactRelationships(f.id).then(rels => ({ id: f.id, rels }))))
      .then(results => {
        const map: Record<string, FactRelationship[]> = {};
        results.forEach(r => { map[r.id] = r.rels; });
        setRelMap(map);
      })
      .finally(() => setRelsLoading(false));
  }, [activeTab, facts]);

  const allRels = Object.values(relMap).flat();
  const byType = {
    corroboration:      allRels.filter(r => r.relationship.relationship_type === 'corroboration'),
    contradiction:      allRels.filter(r => r.relationship.relationship_type === 'contradiction'),
    reconciled_context: allRels.filter(r => r.relationship.relationship_type === 'reconciled_context'),
    uncertain:          allRels.filter(r => r.relationship.relationship_type === 'uncertain'),
  };

  const docName = docSummary?.document.filename ?? docId;

  if (loading) {
    return (
      <div>
        <div className="skeleton" style={{ height: 24, width: 280, marginBottom: 24, borderRadius: 6 }} />
        <div className="skeleton" style={{ height: 40, width: 400, marginBottom: 8, borderRadius: 8 }} />
        <div className="skeleton" style={{ height: 200, borderRadius: 12 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚠️</div>
        <div className="empty-state-title">Failed to load document</div>
        <div className="empty-state-sub">{error}</div>
        <Link href="/" className="btn btn-secondary" style={{ marginTop: 16, display: 'inline-flex' }}>← Back</Link>
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link href="/">Dashboard</Link>
        <span className="breadcrumb-sep">›</span>
        <span style={{ color: 'var(--text-secondary)' }} className="truncate">{docName}</span>
      </div>

      {/* Page header */}
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-title" style={{ fontSize: 22 }}>📄 {docName}</h1>
            {docSummary && (
              <p className="page-subtitle">
                {docSummary.document.page_count} pages ·{' '}
                {docSummary.fact_count.toLocaleString()} facts ·{' '}
                {docSummary.verified_count} verified
              </p>
            )}
          </div>
          <Link href="/" className="btn btn-secondary">← Dashboard</Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {(['facts', 'relationships', 'trace'] as Tab[]).map(t => (
          <button
            key={t}
            className={`tab${activeTab === t ? ' active' : ''}`}
            onClick={() => setActiveTab(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'facts' && ` (${facts.length})`}
            {t === 'relationships' && allRels.length > 0 && ` (${allRels.length})`}
          </button>
        ))}
      </div>

      {/* Facts Tab */}
      {activeTab === 'facts' && (
        <div className={selectedFact ? 'detail-layout' : ''}>
          <div>
            <FactsTable
              facts={facts}
              selectedId={selectedFact?.id ?? null}
              onSelect={f => setSelectedFact(f)}
            />
          </div>
          {selectedFact && (
            <FactSidePanel
              fact={selectedFact}
              onClose={() => setSelectedFact(null)}
            />
          )}
        </div>
      )}

      {/* Relationships Tab */}
      {activeTab === 'relationships' && (
        <div>
          {relsLoading && (
            <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
              <span className="spinner" style={{ width: 28, height: 28 }} />
              <p style={{ marginTop: 12 }}>Loading relationships…</p>
            </div>
          )}
          {!relsLoading && allRels.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-icon">🔗</div>
              <div className="empty-state-title">No relationships yet</div>
              <div className="empty-state-sub">Cross-document relationships appear after ingesting multiple documents.</div>
            </div>
          )}
          {!relsLoading && (['corroboration', 'contradiction', 'reconciled_context', 'uncertain'] as RelType[]).map(type => {
            const rels = byType[type];
            if (!rels.length) return null;
            return (
              <div key={type} style={{ marginBottom: 28 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                  <RelationshipBadge type={type} />
                  <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{rels.length} found</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {rels.map((r, i) => (
                    <div key={i} className="rel-item">
                      <div className="rel-header">
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {(r.relationship.confidence * 100).toFixed(0)}% confidence
                        </span>
                      </div>
                      {r.linked_fact && (
                        <div className="rel-fact-value">
                          <span className="fact-entity">{r.linked_fact.entity}</span>
                          {' · '}
                          <span className="fact-attr">{r.linked_fact.attribute}</span>
                          {': '}
                          <span className="fact-value">{r.linked_fact.value}</span>
                        </div>
                      )}
                      <div className="rel-explanation">{r.relationship.explanation}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Trace Tab — shows global trace, filtered notice */}
      {activeTab === 'trace' && (
        <div>
          <div style={{ marginBottom: 16, fontSize: 13, color: 'var(--text-muted)' }}>
            Showing the 50 most recent LLM calls across all documents.{' '}
            <Link href="/trace" style={{ color: 'var(--accent-cyan)' }}>View full trace →</Link>
          </div>
          <GlobalTraceSection />
        </div>
      )}
    </div>
  );
}

function GlobalTraceSection() {
  const [entries, setEntries] = useState<import('@/lib/types').TraceEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    import('@/lib/api').then(({ fetchTrace }) => {
      fetchTrace(50).then(setEntries).finally(() => setLoading(false));
    });
  }, []);

  if (loading) return <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading trace…</div>;
  if (!entries.length) return <div className="empty-state"><div className="empty-state-sub">No trace entries yet.</div></div>;

  return (
    <div className="trace-list">
      {entries.map((e, i) => <TraceEntryRow key={i} entry={e} />)}
    </div>
  );
}
