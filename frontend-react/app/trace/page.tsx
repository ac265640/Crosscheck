'use client';
import { useEffect, useMemo, useState } from 'react';
import { fetchTrace } from '@/lib/api';
import type { TraceEntry } from '@/lib/types';
import TraceEntryRow from '@/components/trace/TraceEntry';

const CALL_TYPES = ['all', 'extraction', 'canonicalization', 'reasoning'];

export default function TracePage() {
  const [entries, setEntries] = useState<TraceEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const [limit, setLimit] = useState(100);

  const load = () => {
    setLoading(true);
    fetchTrace(limit)
      .then(setEntries)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [limit]);

  const filtered = useMemo(() => {
    if (filter === 'all') return entries;
    return entries.filter(e => e.call_type?.toLowerCase().includes(filter));
  }, [entries, filter]);

  const successCount = entries.filter(e => e.success).length;
  const failCount = entries.filter(e => !e.success).length;
  const avgLatency = entries.length > 0
    ? Math.round(entries.reduce((a, e) => a + (e.latency_ms ?? 0), 0) / entries.length)
    : 0;

  return (
    <>
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-title">Reasoning Trace</h1>
            <p className="page-subtitle">LLM execution log — extraction, canonicalization, and cross-document reasoning</p>
          </div>
          <button className="btn btn-secondary" onClick={load}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Mini stats */}
      {!loading && entries.length > 0 && (
        <div className="stats-strip" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
          <div className="stat-card">
            <div className="stat-label">Total Calls</div>
            <div className="stat-value">{entries.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Successful</div>
            <div className="stat-value" style={{ color: 'var(--success)' }}>{successCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value" style={{ color: failCount > 0 ? 'var(--danger)' : 'var(--text-muted)' }}>{failCount}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Latency</div>
            <div className="stat-value">{avgLatency} <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)' }}>ms</span></div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar" style={{ marginBottom: 14 }}>
        {CALL_TYPES.map(t => (
          <button
            key={t}
            className={`filter-btn${filter === t ? ' active' : ''}`}
            onClick={() => setFilter(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Limit:</span>
          {[50, 100, 200, 500].map(n => (
            <button
              key={n}
              className={`filter-btn${limit === n ? ' active' : ''}`}
              onClick={() => setLimit(n)}
              style={{ padding: '4px 8px', fontSize: 11 }}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="skeleton" style={{ height: 50, borderRadius: 6 }} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-title">Could not load trace</div>
          <div className="empty-state-sub">{error}</div>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-title">No trace entries</div>
          <div className="empty-state-sub">Trace records will appear as documents are ingested and verified.</div>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="trace-list">
          {filtered.map((e, i) => <TraceEntryRow key={i} entry={e} />)}
        </div>
      )}
    </>
  );
}
