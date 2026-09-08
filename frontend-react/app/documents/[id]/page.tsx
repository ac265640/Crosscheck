'use client';
import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchDocuments, fetchDocumentFacts, fetchDocumentRelationships } from '@/lib/api';
import type { DocumentSummary, Fact, FactRelationship, RelType } from '@/lib/types';
import FactsTable from '@/components/documents/FactsTable';
import FactSidePanel from '@/components/documents/FactSidePanel';
import RelationshipCard from '@/components/documents/RelationshipCard';

type Tab = 'facts' | 'relationships';
type RelFilter = 'all' | RelType;

export default function DocumentDetailPage() {
  const params = useParams();
  const docId = params.id as string;

  const [docSummary, setDocSummary] = useState<DocumentSummary | null>(null);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('facts');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Relationships tab state
  const [allRels, setAllRels] = useState<FactRelationship[]>([]);
  const [relsLoading, setRelsLoading] = useState(false);
  const [relFilter, setRelFilter] = useState<RelFilter>('all');

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

  // Load rich relationships for this document
  useEffect(() => {
    if (activeTab !== 'relationships' || allRels.length > 0) return;
    setRelsLoading(true);
    fetchDocumentRelationships(docId)
      .then(data => {
        // Deduplicate: backend may return both A→B and B→A for the same relationship
        const seen = new Set<string>();
        const deduped = data.filter(r => {
          const relId = r.relationship?.id || r.id;
          if (!relId || seen.has(relId)) return false;
          seen.add(relId);
          return true;
        });
        setAllRels(deduped);
      })
      .catch(() => setAllRels([]))
      .finally(() => setRelsLoading(false));
  }, [activeTab, docId, allRels.length]);

  const filteredRels = useMemo(() => {
    if (relFilter === 'all') return allRels;
    return allRels.filter(r => (r.relationship.relationship_type || r.relationship_type) === relFilter);
  }, [allRels, relFilter]);

  const relCounts = useMemo(() => {
    return {
      all: allRels.length,
      corroboration: allRels.filter(r => (r.relationship.relationship_type || r.relationship_type) === 'corroboration').length,
      contradiction: allRels.filter(r => (r.relationship.relationship_type || r.relationship_type) === 'contradiction').length,
      reconciled_context: allRels.filter(r => (r.relationship.relationship_type || r.relationship_type) === 'reconciled_context').length,
      uncertain: allRels.filter(r => (r.relationship.relationship_type || r.relationship_type) === 'uncertain').length,
    };
  }, [allRels]);

  const docName = docSummary?.document.filename ?? docId;

  if (loading) {
    return (
      <div>
        <div className="skeleton" style={{ height: 20, width: 200, marginBottom: 16, borderRadius: 4 }} />
        <div className="skeleton" style={{ height: 60, marginBottom: 16, borderRadius: 8 }} />
        <div className="skeleton" style={{ height: 300, borderRadius: 8 }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">Failed to load document</div>
        <div className="empty-state-sub">{error}</div>
        <Link href="/" className="btn btn-secondary" style={{ marginTop: 14 }}>
          Back to Documents
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div className="breadcrumb">
        <Link href="/">Documents</Link>
        <span className="breadcrumb-sep">/</span>
        <span style={{ color: 'var(--text-secondary)' }} className="truncate">{docName}</span>
      </div>

      {/* Page header */}
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-title" style={{ fontSize: 18 }}>{docName}</h1>
            {docSummary && (
              <p className="page-subtitle">
                {docSummary.document.page_count} pages ·{' '}
                {docSummary.fact_count.toLocaleString()} facts ·{' '}
                {docSummary.verified_count} verified
              </p>
            )}
          </div>
          <Link href="/" className="btn btn-secondary btn-sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Documents
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab${activeTab === 'facts' ? ' active' : ''}`}
          onClick={() => setActiveTab('facts')}
        >
          Extracted Facts ({facts.length})
        </button>
        <button
          className={`tab${activeTab === 'relationships' ? ' active' : ''}`}
          onClick={() => setActiveTab('relationships')}
        >
          Cross-Document Connections {allRels.length > 0 ? `(${allRels.length})` : ''}
        </button>
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
          {/* Sub-filters by relationship type */}
          <div className="filter-bar" style={{ marginBottom: 16 }}>
            {[
              { id: 'all', label: `All (${relCounts.all})` },
              { id: 'corroboration', label: `Corroboration (${relCounts.corroboration})` },
              { id: 'contradiction', label: `Contradiction (${relCounts.contradiction})` },
              { id: 'reconciled_context', label: `Reconciled Context (${relCounts.reconciled_context})` },
              { id: 'uncertain', label: `Uncertain (${relCounts.uncertain})` },
            ].map(tab => (
              <button
                key={tab.id}
                className={`filter-btn${relFilter === tab.id ? ' active' : ''}`}
                onClick={() => setRelFilter(tab.id as RelFilter)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {relsLoading && (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
              <span className="spinner" style={{ width: 20, height: 20 }} />
              <p style={{ marginTop: 10, fontSize: 13 }}>Loading cross-document relationships...</p>
            </div>
          )}

          {!relsLoading && filteredRels.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-title">No relationships found</div>
              <div className="empty-state-sub">
                {relFilter === 'all'
                  ? 'No cross-document connections were identified for this document.'
                  : `No ${relFilter.replace('_', ' ')} relationships found.`}
              </div>
            </div>
          )}

          {!relsLoading && filteredRels.length > 0 && (
            <div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                Showing <strong>{filteredRels.length}</strong> cross-document connections with exact page citations and verbatim evidence:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {filteredRels.map((r, i) => (
                  <RelationshipCard
                    key={r.id || i}
                    rel={r}
                    currentDocId={docId}
                    compact={false}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
