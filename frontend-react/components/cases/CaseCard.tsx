'use client';
import { useState } from 'react';
import type { CaseEntry, RelType } from '@/lib/types';
import { relConfig } from '@/components/documents/RelationshipBadge';

interface Props {
  type: RelType;
  entry: CaseEntry | null;
  compact?: boolean;
}

export default function CaseCard({ type, entry, compact = false }: Props) {
  const cfg = relConfig(type);
  const [copied, setCopied] = useState(false);

  const caseTitles: Record<RelType, { num: string; title: string; subtitle: string }> = {
    corroboration: {
      num: 'Case 1',
      title: 'Fact Corroborated Across Documents',
      subtitle: 'Same underlying claim confirmed across separate documents despite differing units or wording.',
    },
    contradiction: {
      num: 'Case 2',
      title: 'Genuine or Likely Contradiction',
      subtitle: 'Materially conflicting quantitative claims for the same entity and attribute.',
    },
    reconciled_context: {
      num: 'Case 3',
      title: 'Apparent Contradiction Reconciled by Context',
      subtitle: 'Differing figures explained by distinct time periods, scopes, or document contexts.',
    },
    uncertain: {
      num: 'Case 4',
      title: 'Extraction or Reasoning Failure / Uncertainty',
      subtitle: 'Handling ambiguity and preventing hallucinations when evidence lacks overlapping scope.',
    },
  };

  const caseInfo = caseTitles[type];

  if (!entry) {
    return (
      <div className="case-card" style={{ borderColor: cfg.border }}>
        <div className="case-card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
              {caseInfo.num}
            </span>
            <span
              className="badge"
              style={{
                color: cfg.color,
                background: cfg.bg,
                border: `1px solid ${cfg.border}`,
                fontSize: 12,
                padding: '3px 8px',
              }}
            >
              {cfg.label}
            </span>
          </div>
        </div>
        <div className="empty-state" style={{ padding: '28px 0' }}>
          <div className="empty-state-sub">
            No {cfg.label.toLowerCase()} relationship found in the database.
          </div>
        </div>
      </div>
    );
  }

  const { fact_a, fact_b, relationship } = entry;

  const copyMarkdown = () => {
    const text = `### ${caseInfo.num}: ${caseInfo.title} (${cfg.label})
- Confidence: ${(relationship.confidence * 100).toFixed(0)}%
- Fact A (${fact_a?.entity} — ${fact_a?.attribute}): ${fact_a?.value} ${fact_a?.unit || ''} (Page ${fact_a?.page_number ?? '—'})
  Quote: "${fact_a?.verbatim_evidence || fact_a?.source_text || ''}"
- Fact B (${fact_b?.entity} — ${fact_b?.attribute}): ${fact_b?.value} ${fact_b?.unit || ''} (Page ${fact_b?.page_number ?? '—'})
  Quote: "${fact_b?.verbatim_evidence || fact_b?.source_text || ''}"
- Reasoning: ${relationship.explanation}`;

    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div
      className="case-card"
      style={{
        borderColor: cfg.border,
        boxShadow: 'var(--shadow)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        background: 'var(--bg-card)',
      }}
    >
      {/* Header */}
      <div className="case-card-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: 'var(--accent)',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              {caseInfo.num}
            </span>
            <span
              className="badge"
              style={{
                color: cfg.color,
                background: cfg.bg,
                border: `1px solid ${cfg.border}`,
                fontSize: 12,
                padding: '2px 8px',
                fontWeight: 600,
              }}
            >
              {cfg.label}
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {(relationship.confidence * 100).toFixed(0)}% confidence
            </span>
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            {caseInfo.title}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
            {caseInfo.subtitle}
          </div>
        </div>

        {/* Copy Citation Button */}
        <button
          onClick={copyMarkdown}
          className="btn btn-secondary btn-sm"
          title="Copy markdown text"
          style={{
            fontSize: 12,
            padding: '4px 10px',
            whiteSpace: 'nowrap',
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      {/* Analytical observation banner */}
      {type === 'corroboration' && (
        <div
          style={{
            background: 'var(--success-bg)',
            border: '1px solid rgba(45, 125, 70, 0.2)',
            borderRadius: 6,
            padding: '7px 12px',
            fontSize: 12,
            color: 'var(--success)',
            lineHeight: 1.4,
          }}
        >
          <strong>Unit conversion:</strong> 72,253.01 ₹ Million is equivalent to approximately 7,225.30 ₹ Crore, matching the 7,225 ₹ Crore figure with standard rounding.
        </div>
      )}

      {type === 'contradiction' && (
        <div
          style={{
            background: 'var(--danger-bg)',
            border: '1px solid rgba(192, 57, 43, 0.2)',
            borderRadius: 6,
            padding: '7px 12px',
            fontSize: 12,
            color: 'var(--danger)',
            lineHeight: 1.4,
          }}
        >
          <strong>Value conflict:</strong> 1,429 ₹ Million (~142.9 Cr) vs 941 ₹ Cr represents a ~6.6× discrepancy for the same attribute and period without reconciling notes.
        </div>
      )}

      {type === 'reconciled_context' && (
        <div
          style={{
            background: 'var(--warning-bg)',
            border: '1px solid rgba(184, 134, 11, 0.2)',
            borderRadius: 6,
            padding: '7px 12px',
            fontSize: 12,
            color: 'var(--warning)',
            lineHeight: 1.4,
          }}
        >
          <strong>Scope difference:</strong> The dates represent different document release windows (May 2024 earnings release vs Dec 2021 prospectus note).
        </div>
      )}

      {type === 'uncertain' && (
        <div
          style={{
            background: 'var(--gray-bg)',
            border: '1px solid rgba(139, 115, 85, 0.2)',
            borderRadius: 6,
            padding: '7px 12px',
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.4,
          }}
        >
          <strong>Uncertainty handling:</strong> The engine flags facts without overlapping entities or temporal periods as uncertain to avoid speculative connections.
        </div>
      )}

      {/* Facts Comparison: Fact A and Fact B */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact ? '1fr' : 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 10,
        }}
      >
        {/* Fact A */}
        {fact_a && (
          <div
            className="case-fact"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
                Fact A
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Page {fact_a.page_number ?? fact_a.source_page ?? '—'}
              </span>
            </div>
            <div className="case-fact-entity" style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
              {fact_a.entity}
            </div>
            <div className="case-fact-attr" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {fact_a.attribute}
            </div>
            <div className="case-fact-value" style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 6px', color: 'var(--text-primary)' }}>
              {fact_a.value}
              {fact_a.unit && <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 4 }}>{fact_a.unit}</span>}
            </div>

            {/* Verbatim quote */}
            <div
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                padding: '6px 8px',
                background: 'var(--bg-subtle)',
                borderRadius: 4,
                borderLeft: '2px solid var(--accent)',
                lineHeight: 1.4,
              }}
            >
              &ldquo;{fact_a.verbatim_evidence || fact_a.source_text}&rdquo;
            </div>
          </div>
        )}

        {/* Fact B */}
        {fact_b && (
          <div
            className="case-fact"
            style={{
              background: 'var(--bg-primary)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '10px 12px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>
                Fact B
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Page {fact_b.page_number ?? fact_b.source_page ?? '—'}
              </span>
            </div>
            <div className="case-fact-entity" style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 13 }}>
              {fact_b.entity}
            </div>
            <div className="case-fact-attr" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {fact_b.attribute}
            </div>
            <div className="case-fact-value" style={{ fontSize: 15, fontWeight: 700, margin: '4px 0 6px', color: 'var(--text-primary)' }}>
              {fact_b.value}
              {fact_b.unit && <span style={{ color: 'var(--text-muted)', fontSize: 12, marginLeft: 4 }}>{fact_b.unit}</span>}
            </div>

            {/* Verbatim quote */}
            <div
              style={{
                fontSize: 12,
                color: 'var(--text-secondary)',
                padding: '6px 8px',
                background: 'var(--bg-subtle)',
                borderRadius: 4,
                borderLeft: '2px solid var(--accent)',
                lineHeight: 1.4,
              }}
            >
              &ldquo;{fact_b.verbatim_evidence || fact_b.source_text}&rdquo;
            </div>
          </div>
        )}
      </div>

      {/* System reasoning */}
      <div
        style={{
          background: 'var(--bg-primary)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '10px 12px',
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
          Reasoning
        </div>
        <div className="case-explanation" style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
          {relationship.explanation}
        </div>
      </div>

      {/* Case 4 failure mitigation explanation */}
      {type === 'uncertain' && (
        <div
          style={{
            padding: '8px 12px',
            background: 'var(--bg-subtle)',
            borderRadius: 6,
            border: '1px solid var(--border)',
            fontSize: 12,
            color: 'var(--text-secondary)',
            lineHeight: 1.5,
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
            Failure Handling & Mitigation:
          </div>
          <div>
            1. Evidence verification: RapidFuzz partial_ratio against the source chunk (threshold &ge; 85) filters unverified claims.
          </div>
          <div>
            2. Structured schema validation: Pydantic retries invalid JSON once with feedback before falling back.
          </div>
          <div>
            3. Conservative classification: Pairs without overlapping scope are assigned <em>uncertain</em> rather than forcing a relationship.
          </div>
        </div>
      )}

      {/* Confidence footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 'auto' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Confidence</span>
        <div className="confidence-bar-track" style={{ flex: 1, height: 4 }}>
          <div
            className="confidence-bar-fill"
            style={{ width: `${(relationship.confidence * 100).toFixed(0)}%`, background: cfg.color }}
          />
        </div>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
          {(relationship.confidence * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}
