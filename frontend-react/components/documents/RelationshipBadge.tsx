'use client';
import type { RelType } from '@/lib/types';

const REL_CONFIG: Record<RelType, { color: string; bg: string; border: string; label: string; dot: string }> = {
  corroboration: {
    color: 'var(--success)',
    bg: 'var(--success-bg)',
    border: 'var(--success-border)',
    label: 'Corroboration',
    dot: '#059669',
  },
  contradiction: {
    color: 'var(--danger)',
    bg: 'var(--danger-bg)',
    border: 'var(--danger-border)',
    label: 'Contradiction',
    dot: '#DC2626',
  },
  reconciled_context: {
    color: 'var(--warning)',
    bg: 'var(--warning-bg)',
    border: 'var(--warning-border)',
    label: 'Reconciled Context',
    dot: '#D97706',
  },
  uncertain: {
    color: 'var(--gray)',
    bg: 'var(--gray-bg)',
    border: 'var(--gray-border)',
    label: 'Uncertain',
    dot: '#64748B',
  },
};

export function RelationshipBadge({ type }: { type: RelType }) {
  const cfg = REL_CONFIG[type] ?? REL_CONFIG.uncertain;
  return (
    <span
      className="badge"
      style={{
        color: cfg.color,
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          backgroundColor: cfg.dot,
          display: 'inline-block',
        }}
      />
      {cfg.label}
    </span>
  );
}

export function relConfig(type: RelType) {
  return REL_CONFIG[type] ?? REL_CONFIG.uncertain;
}
