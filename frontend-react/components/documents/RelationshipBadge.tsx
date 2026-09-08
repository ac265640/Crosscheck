'use client';
import type { RelType } from '@/lib/types';

const REL_CONFIG: Record<RelType, { color: string; bg: string; border: string; label: string; icon: string }> = {
  corroboration:      { color: 'var(--success)',  bg: 'var(--success-bg)',  border: 'rgba(16,185,129,0.25)',  label: 'Corroboration',      icon: '✓' },
  contradiction:      { color: 'var(--danger)',   bg: 'var(--danger-bg)',   border: 'rgba(239,68,68,0.25)',   label: 'Contradiction',      icon: '✕' },
  reconciled_context: { color: 'var(--warning)',  bg: 'var(--warning-bg)',  border: 'rgba(245,158,11,0.25)',  label: 'Reconciled Context', icon: '~' },
  uncertain:          { color: 'var(--gray)',     bg: 'var(--gray-bg)',     border: 'rgba(107,114,128,0.25)', label: 'Uncertain',          icon: '?' },
};

export function RelationshipBadge({ type }: { type: RelType }) {
  const cfg = REL_CONFIG[type] ?? REL_CONFIG.uncertain;
  return (
    <span
      className="badge"
      style={{ color: cfg.color, background: cfg.bg, border: `1px solid ${cfg.border}` }}
    >
      {cfg.icon} {cfg.label}
    </span>
  );
}

export function relConfig(type: RelType) {
  return REL_CONFIG[type] ?? REL_CONFIG.uncertain;
}
