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
            <p className="page-subtitle">LLM call log — extraction, canonicalization, and relationship reasoning</p>
          </div>
          <button className="btn btn-secondary" onClick={load}>↻ Refresh</button>
        </div>
      </div>

      {/* Mini stats */}
      {!loading && entries.length > 0 && (
        <div className="stats-strip" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 20 }}>
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
            <div className="stat-value">{avgLatency}</div>
            <div className="stat-sub">ms</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar" style={{ marginBottom: 16 }}>
        {CALL_TYPES.map(t => (
          <button
            key={t}
            className={`filter-btn${filter === t ? ' active' : ''}`}
            onClick={() => setFilter(t)}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Show last</span>
          {[50, 100, 200, 500].map(n => (
            <button
              key={n}
              className={`filter-btn${limit === n ? ' active' : ''}`}
              onClick={() => setLimit(n)}
              style={{ padding: '5px 10px' }}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="skeleton" style={{ height: 60, borderRadius: 8 }} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-icon">⚠️</div>
          <div className="empty-state-title">Could not load trace</div>
          <div className="empty-state-sub">{error}</div>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <div className="empty-state-title">No trace entries</div>
          <div className="empty-state-sub">Trace entries appear after ingesting documents and running reasoning.</div>
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
