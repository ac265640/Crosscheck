'use client';
import { useEffect, useState } from 'react';
import { fetchFactRelationships } from '@/lib/api';
import type { Fact, FactRelationship, RelType } from '@/lib/types';
import EvidenceViewer from './EvidenceViewer';
import { RelationshipBadge } from './RelationshipBadge';
import RelationshipCard from './RelationshipCard';

interface Props {
  fact: Fact;
  onClose: () => void;
}

export default function FactSidePanel({ fact, onClose }: Props) {
  const [rels, setRels] = useState<FactRelationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchFactRelationships(fact.id)
      .then(data => {
        const seen = new Set<string>();
        const deduped = data.filter(r => {
          const relId = r.relationship?.id || r.id;
          if (!relId || seen.has(relId)) return false;
          seen.add(relId);
          return true;
        });
        setRels(deduped);
      })
      .catch(() => setRels([]))
      .finally(() => setLoading(false));
  }, [fact.id]);

  const copyCitation = () => {
    const quote = fact.verbatim_evidence || fact.verbatim_quote || '';
    const text = `[${fact.entity} — ${fact.attribute}: ${fact.value} ${fact.unit || ''}] "${quote}" (Page ${fact.page_number ?? fact.source_page ?? '?'})`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const statusColor =
    fact.verification_status === 'verified'
      ? 'var(--success)'
      : fact.verification_status === 'unverified'
      ? 'var(--warning)'
      : 'var(--danger)';

  return (
    <div className="side-panel">
      {/* Header */}
      <div className="side-panel-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="side-panel-title">Grounded Fact Inspector</div>
          <div style={{ fontSize: 11, color: statusColor, marginTop: 2, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: statusColor, display: 'inline-block' }} />
            <span style={{ textTransform: 'capitalize' }}>
              {fact.verification_status === 'extraction_failed' ? 'Failed' : fact.verification_status}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            onClick={copyCitation}
            className="btn btn-secondary btn-sm"
            title="Copy citation"
            style={{ fontSize: 11, padding: '3px 8px' }}
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={onClose}
            className="btn btn-secondary btn-sm btn-icon"
            title="Close"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px' }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      <div className="side-panel-body" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 160px)', padding: '16px 20px' }}>
        {/* Fact info */}
        <div style={{ marginBottom: 18 }}>
          <div className="fact-entity" style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            {fact.entity}
          </div>
          <div className="fact-attr" style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
            {fact.attribute}
          </div>
          <div className="fact-value" style={{ fontSize: 22, fontWeight: 800, marginTop: 6, color: 'var(--accent)' }}>
            {fact.value}
            {fact.unit && <span className="fact-unit" style={{ marginLeft: 8, fontSize: 14, color: 'var(--text-secondary)' }}>{fact.unit}</span>}
          </div>

          {/* Scope chips */}
          {fact.scope && typeof fact.scope === 'object' && Object.keys(fact.scope).length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
              {Object.entries(fact.scope).map(([k, v]) => (
                <span
                  key={k}
                  className="badge"
                  style={{
                    fontSize: 11,
                    background: 'rgba(180, 130, 90, 0.1)',
                    border: '1px solid var(--border)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <strong style={{ color: 'var(--text-primary)' }}>{k}:</strong> {String(v)}
                </span>
              ))}
            </div>
          )}

          {fact.canonical_key && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontFamily: 'monospace' }}>
              Canonical: {fact.canonical_key}
            </div>
          )}

          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
            Confidence score: {fact.confidence ? (fact.confidence * 100).toFixed(0) : 100}%
          </div>
        </div>

        <hr className="divider" style={{ margin: '14px 0' }} />

        {/* Evidence viewer */}
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8, fontWeight: 700 }}>
            Source Document Evidence
          </div>
          <EvidenceViewer fact={fact} />
        </div>

        <hr className="divider" style={{ margin: '14px 0' }} />

        {/* Relationships */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10, fontWeight: 700 }}>
            Cross-Document Connections ({loading ? '…' : rels.length})
          </div>

          {loading && <div className="text-muted" style={{ fontSize: 13 }}>Looking up relationships…</div>}

          {!loading && rels.length === 0 && (
            <div className="text-muted" style={{ fontSize: 13, padding: '12px 0' }}>
              No other document in the knowledge base shares this exact canonical entity/metric.
            </div>
          )}

          {!loading && rels.map((r, i) => (
            <RelationshipCard
              key={r.id || i}
              rel={r}
              currentDocId={fact.document_id}
              compact={true}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
