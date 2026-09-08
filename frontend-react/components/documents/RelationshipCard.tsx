'use client';
import { useState } from 'react';
import type { FactRelationship, RelType } from '@/lib/types';
import { RelationshipBadge } from './RelationshipBadge';

interface Props {
  rel: FactRelationship;
  currentDocId?: string;
  compact?: boolean;
}

export default function RelationshipCard({ rel, currentDocId, compact = false }: Props) {
  const [copied, setCopied] = useState(false);

  const relationship = rel.relationship;
  const relType = (relationship.relationship_type || rel.relationship_type || 'uncertain') as RelType;
  const confidence = relationship.confidence ?? rel.confidence ?? 1.0;
  const explanation = relationship.explanation || rel.explanation || '';

  // Order facts so current document's fact is Fact A
  let factA = rel.fact_a;
  let factB = rel.fact_b || rel.linked_fact;

  if (currentDocId && factB && factB.document_id === currentDocId && factA && factA.document_id !== currentDocId) {
    const temp = factA;
    factA = factB;
    factB = temp;
  }

  const quoteA = factA?.verbatim_evidence || factA?.verbatim_quote || factA?.source_text || '';
  const quoteB = factB?.verbatim_evidence || factB?.verbatim_quote || factB?.source_text || '';

  const copyMarkdown = () => {
    const text = `### Relationship: ${relType.toUpperCase()} (${(confidence * 100).toFixed(0)}% confidence)
- Fact A: ${factA?.entity} — ${factA?.attribute}: ${factA?.value} ${factA?.unit || ''} (Page ${factA?.page_number ?? '—'}) [${factA?.document_filename || 'Source Document'}]
  Quote: "${quoteA}"
- Fact B: ${factB?.entity} — ${factB?.attribute}: ${factB?.value} ${factB?.unit || ''} (Page ${factB?.page_number ?? '—'}) [${factB?.document_filename || 'Linked Document'}]
  Quote: "${quoteB}"
- Reasoning: ${explanation}`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div
      className="card"
      style={{
        padding: '16px 18px',
        marginBottom: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <RelationshipBadge type={relType} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {(confidence * 100).toFixed(0)}% confidence
          </span>
        </div>
        <button
          onClick={copyMarkdown}
          className="btn btn-secondary btn-sm"
          title="Copy comparison citation"
          style={{ fontSize: 11, padding: '3px 8px' }}
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Facts Side-by-Side Comparison */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 10,
        }}
      >
        {/* Fact A */}
        {factA && (
          <div
            className="case-fact"
            style={{
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Fact A {factA.document_filename && `· ${factA.document_filename}`}
              </span>
              <span className="badge" style={{ fontSize: 10, background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                Page {factA.page_number ?? '—'}
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {factA.entity}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {factA.attribute}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 6px', color: 'var(--text-primary)' }}>
              {factA.value}
              {factA.unit && <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 4 }}>{factA.unit}</span>}
            </div>

            {/* Verbatim quote from PDF */}
            {quoteA && (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  padding: '6px 8px',
                  background: 'var(--bg-card)',
                  borderRadius: 4,
                  borderLeft: '2px solid var(--accent)',
                  lineHeight: 1.4,
                  fontStyle: 'italic',
                }}
              >
                &ldquo;{quoteA}&rdquo;
              </div>
            )}
          </div>
        )}

        {/* Fact B */}
        {factB && (
          <div
            className="case-fact"
            style={{
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Fact B {factB.document_filename && `· ${factB.document_filename}`}
              </span>
              <span className="badge" style={{ fontSize: 10, background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                Page {factB.page_number ?? '—'}
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {factB.entity}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {factB.attribute}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 6px', color: 'var(--text-primary)' }}>
              {factB.value}
              {factB.unit && <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 4 }}>{factB.unit}</span>}
            </div>

            {/* Verbatim quote from PDF */}
            {quoteB && (
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--text-secondary)',
                  padding: '6px 8px',
                  background: 'var(--bg-card)',
                  borderRadius: 4,
                  borderLeft: '2px solid var(--accent)',
                  lineHeight: 1.4,
                  fontStyle: 'italic',
                }}
              >
                &ldquo;{quoteB}&rdquo;
              </div>
            )}
          </div>
        )}
      </div>

      {/* Analytical Reasoning Explanation */}
      <div
        style={{
          background: 'var(--bg-subtle)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '8px 12px',
        }}
      >
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>
          Reasoning & Reconciliation
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>
          {explanation}
        </div>
      </div>
    </div>
  );
}
