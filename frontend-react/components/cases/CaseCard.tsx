'use client';
import type { CaseEntry, RelType } from '@/lib/types';
import { relConfig } from '@/components/documents/RelationshipBadge';

interface Props { type: RelType; entry: CaseEntry | null; }

export default function CaseCard({ type, entry }: Props) {
  const cfg = relConfig(type);
  const label = cfg.label;

  if (!entry) {
    return (
      <div className="case-card" style={{ borderColor: cfg.border }}>
        <div className="case-card-header">
          <span
            className="badge"
            style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`, fontSize: 13, padding: '5px 12px' }}
          >
            {cfg.icon} {label}
          </span>
        </div>
        <div className="empty-state" style={{ padding: '32px 0' }}>
          <div className="empty-state-icon" style={{ fontSize: 32 }}>∅</div>
          <div className="empty-state-sub">No {label.toLowerCase()} found yet. Ingest more documents to seed this case.</div>
        </div>
      </div>
    );
  }

  const { fact_a, fact_b, relationship } = entry;

  return (
    <div className="case-card" style={{ borderColor: cfg.border }}>
      <div className="case-card-header">
        <span
          className="badge"
          style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}`, fontSize: 13, padding: '5px 12px' }}
        >
          {cfg.icon} {label}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {(relationship.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      {fact_a && (
        <div className="case-fact">
          <div className="case-fact-label">Fact A</div>
          <div className="case-fact-entity">{fact_a.entity}</div>
          <div className="case-fact-attr">{fact_a.attribute}</div>
          <div className="case-fact-value">
            {fact_a.value}
            {fact_a.unit && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{fact_a.unit}</span>}
          </div>
        </div>
      )}

      {fact_b && (
        <div className="case-fact">
          <div className="case-fact-label">Fact B</div>
          <div className="case-fact-entity">{fact_b.entity}</div>
          <div className="case-fact-attr">{fact_b.attribute}</div>
          <div className="case-fact-value">
            {fact_b.value}
            {fact_b.unit && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{fact_b.unit}</span>}
          </div>
        </div>
      )}

      <div className="case-explanation">{relationship.explanation}</div>

      <div className="confidence-bar-track" style={{ marginTop: 12 }}>
        <div
          className="confidence-bar-fill"
          style={{ width: `${(relationship.confidence * 100).toFixed(0)}%`, background: cfg.color }}
        />
      </div>
    </div>
  );
}
