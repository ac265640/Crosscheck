'use client';
import { useEffect, useState } from 'react';
import { fetchFactRelationships } from '@/lib/api';
import type { Fact, FactRelationship, RelType } from '@/lib/types';
import EvidenceViewer from './EvidenceViewer';
import { RelationshipBadge } from './RelationshipBadge';

interface Props {
  fact: Fact;
  onClose: () => void;
}

export default function FactSidePanel({ fact, onClose }: Props) {
  const [rels, setRels] = useState<FactRelationship[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchFactRelationships(fact.id)
      .then(setRels)
      .catch(() => setRels([]))
      .finally(() => setLoading(false));
  }, [fact.id]);

  const statusColor =
    fact.verification_status === 'verified' ? 'var(--success)' :
    fact.verification_status === 'unverified' ? 'var(--warning)' : 'var(--danger)';

  return (
    <div className="side-panel">
      {/* Header */}
      <div className="side-panel-header">
        <div>
          <div className="side-panel-title">Fact Detail</div>
          <div style={{ fontSize: 11, color: statusColor, marginTop: 2, fontWeight: 600 }}>
            ● {fact.verification_status}
          </div>
        </div>
        <button
          onClick={onClose}
          className="btn btn-secondary btn-sm btn-icon"
          title="Close"
          style={{ fontSize: 16, lineHeight: 1 }}
        >
          ✕
        </button>
      </div>

      <div className="side-panel-body" style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 200px)' }}>
        {/* Fact info */}
        <div style={{ marginBottom: 16 }}>
          <div className="fact-entity">{fact.entity}</div>
          <div className="fact-attr">{fact.attribute}</div>
          <div className="fact-value" style={{ fontSize: 18, marginTop: 4 }}>
            {fact.value}
            {fact.unit && <span className="fact-unit" style={{ marginLeft: 6 }}>{fact.unit}</span>}
          </div>
          {fact.scope && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              Scope: {fact.scope}
            </div>
          )}
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
            Confidence: {(fact.confidence * 100).toFixed(0)}%
          </div>
        </div>

        <hr className="divider" />

        {/* Evidence */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8, fontWeight: 600 }}>
            Evidence
          </div>
          <EvidenceViewer fact={fact} />
        </div>

        <hr className="divider" />

        {/* Relationships */}
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8, fontWeight: 600 }}>
            Linked Relationships ({loading ? '…' : rels.length})
          </div>

          {loading && <div className="text-muted" style={{ fontSize: 13 }}>Loading…</div>}

          {!loading && rels.length === 0 && (
            <div className="text-muted" style={{ fontSize: 13 }}>
              No cross-document relationships for this fact yet.
            </div>
          )}

          {!loading && rels.map((r, i) => (
            <div key={i} className="rel-item">
              <div className="rel-header">
                <RelationshipBadge type={r.relationship.relationship_type as RelType} />
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
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
    </div>
  );
}
