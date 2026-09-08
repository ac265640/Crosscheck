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
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);

  // Top entities for quick filter chips
  const topEntities = useMemo(() => {
    const counts: Record<string, number> = {};
    facts.forEach(f => {
      if (f.entity) counts[f.entity] = (counts[f.entity] || 0) + 1;
    });
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([entity, count]) => ({ entity, count }));
  }, [facts]);

  const filtered = useMemo(() => {
    return facts.filter(f => {
      if (statusFilter !== 'all' && f.verification_status !== statusFilter) return false;
      if (selectedEntity && f.entity !== selectedEntity) return false;
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
  }, [facts, query, statusFilter, selectedEntity]);

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
      {/* Search & Status Filters */}
      <div className="filter-bar" style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', marginBottom: 12 }}>
        <div className="search-wrapper" style={{ flex: '1 1 240px', minWidth: 200 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <input
            className="search-input"
            placeholder="Search entity, attribute, value…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
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
      </div>

      {/* Top Entity Filter Chips */}
      {topEntities.length > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Filter by Entity:
          </span>
          <button
            onClick={() => setSelectedEntity(null)}
            className={`filter-btn${selectedEntity === null ? ' active' : ''}`}
            style={{ fontSize: 11, padding: '3px 8px' }}
          >
            All Entities
          </button>
          {topEntities.map(({ entity, count }) => (
            <button
              key={entity}
              onClick={() => setSelectedEntity(selectedEntity === entity ? null : entity)}
              className={`filter-btn${selectedEntity === entity ? ' active' : ''}`}
              style={{ fontSize: 11, padding: '3px 8px' }}
              title={`${entity} (${count} facts)`}
            >
              <span className="truncate" style={{ maxWidth: 140, display: 'inline-block', verticalAlign: 'bottom' }}>
                {entity}
              </span>
              {' '}<span style={{ opacity: 0.7 }}>({count})</span>
            </button>
          ))}
        </div>
      )}

      {/* Result stats summary */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, fontSize: 12, color: 'var(--text-muted)' }}>
        <span>
          Showing <strong>{filtered.length}</strong> of {facts.length} extracted claims
          {selectedEntity && ` for "${selectedEntity}"`}
        </span>
        <span style={{ fontSize: 11 }}>Click any fact row to inspect grounded PDF evidence</span>
      </div>

      {/* Table */}
      <div className="table-wrapper" style={{ maxHeight: '600px', overflowY: 'auto' }}>
        <table>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-secondary)', zIndex: 5 }}>
            <tr>
              <th style={{ width: '20%' }}>Entity</th>
              <th style={{ width: '24%' }}>Attribute</th>
              <th style={{ width: '16%' }}>Value</th>
              <th style={{ width: '9%' }}>Unit</th>
              <th style={{ width: '11%' }}>Grounding</th>
              <th style={{ width: '9%' }}>Conf.</th>
              <th style={{ width: '11%' }}>Page</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No facts match your search or filter criteria.
                </td>
              </tr>
            )}
            {filtered.map(fact => (
              <tr
                key={fact.id}
                onClick={() => onSelect(fact)}
                className={selectedId === fact.id ? 'selected' : ''}
                style={{ cursor: 'pointer', transition: 'background 0.1s ease' }}
              >
                <td className="truncate-cell" style={{ color: 'var(--accent)', fontWeight: 600 }}>
                  {fact.entity}
                </td>
                <td className="truncate-cell" style={{ color: 'var(--text-secondary)' }}>
                  <div>{fact.attribute}</div>
                  {fact.scope && typeof fact.scope === 'object' && Object.keys(fact.scope).length > 0 && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                      {Object.entries(fact.scope).map(([k, v]) => `${k}:${v}`).join(' · ')}
                    </div>
                  )}
                </td>
                <td className="truncate-cell" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                  {fact.value}
                </td>
                <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  {fact.unit ?? '—'}
                </td>
                <td>
                  <span className={`badge ${STATUS_COLORS[fact.verification_status] ?? 'badge-gray'}`} style={{ fontSize: 11 }}>
                    {fact.verification_status === 'extraction_failed' ? 'Failed' :
                     fact.verification_status.charAt(0).toUpperCase() + fact.verification_status.slice(1)}
                  </span>
                </td>
                <td>
                  {(() => {
                    const pct = fact.confidence != null ? Math.round(fact.confidence * 100) : 100;
                    const col = pct >= 80 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--text-muted)';
                    return (
                      <span style={{ fontSize: 12, fontWeight: 600, color: col, fontVariantNumeric: 'tabular-nums' }}>
                        {pct}%
                      </span>
                    );
                  })()}
                </td>
                <td>
                  <span className="badge" style={{ fontSize: 11, background: 'rgba(180,130,90,0.1)', color: 'var(--text-secondary)' }}>
                    P. {fact.page_number ?? '—'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
