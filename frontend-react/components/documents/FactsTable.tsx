'use client';
import { useMemo, useState } from 'react';
import type { Fact } from '@/lib/types';

interface Props {
  facts: Fact[];
  selectedId: string | null;
  onSelect: (f: Fact) => void;
}

type StatusFilter = 'all' | 'verified' | 'unverified' | 'extraction_failed';

const STATUS_COLORS: Record<string, string> = {
  verified: 'badge-success',
  unverified: 'badge-warning',
  extraction_failed: 'badge-danger',
};

export default function FactsTable({ facts, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  const filtered = useMemo(() => {
    return facts.filter(f => {
      if (statusFilter !== 'all' && f.verification_status !== statusFilter) return false;
      if (query) {
        const q = query.toLowerCase();
        return (
          f.entity.toLowerCase().includes(q) ||
          f.attribute.toLowerCase().includes(q) ||
          f.value.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [facts, query, statusFilter]);

  const counts = useMemo(() => {
    return {
      all: facts.length,
      verified: facts.filter(f => f.verification_status === 'verified').length,
      unverified: facts.filter(f => f.verification_status === 'unverified').length,
      extraction_failed: facts.filter(f => f.verification_status === 'extraction_failed').length,
    };
  }, [facts]);

  return (
    <div>
      <div className="filter-bar">
        <div className="search-wrapper">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            className="search-input"
            placeholder="Search entity, attribute, value…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>
        {(['all', 'verified', 'unverified', 'extraction_failed'] as StatusFilter[]).map(s => (
          <button
            key={s}
            className={`filter-btn${statusFilter === s ? ' active' : ''}`}
            onClick={() => setStatusFilter(s)}
          >
            {s === 'extraction_failed' ? 'Failed' : s.charAt(0).toUpperCase() + s.slice(1)}
            {' '}({counts[s]})
          </button>
        ))}
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Entity</th>
              <th>Attribute</th>
              <th>Value</th>
              <th>Unit</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Page</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No facts match this filter.
                </td>
              </tr>
            )}
            {filtered.map(fact => (
              <tr
                key={fact.id}
                onClick={() => onSelect(fact)}
                className={selectedId === fact.id ? 'selected' : ''}
              >
                <td className="truncate-cell" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>
                  {fact.entity}
                </td>
                <td className="truncate-cell" style={{ color: 'var(--text-muted)' }}>
                  {fact.attribute}
                </td>
                <td className="truncate-cell" style={{ fontWeight: 500 }}>
                  {fact.value}
                </td>
                <td>{fact.unit ?? '—'}</td>
                <td>
                  <div className="conf-bar">
                    <div
                      className="conf-pip"
                      style={{ opacity: fact.confidence }}
                    />
                    {(fact.confidence * 100).toFixed(0)}%
                  </div>
                </td>
                <td>
                  <span className={`badge ${STATUS_COLORS[fact.verification_status] ?? 'badge-gray'}`}>
                    {fact.verification_status === 'extraction_failed' ? 'Failed' :
                     fact.verification_status.charAt(0).toUpperCase() + fact.verification_status.slice(1)}
                  </span>
                </td>
                <td>{fact.page_number ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
