'use client';
import { useState } from 'react';
import type { TraceEntry } from '@/lib/types';

export default function TraceEntryRow({ entry }: { entry: TraceEntry }) {
  const [expanded, setExpanded] = useState(false);
  const ts = new Date(entry.ts).toLocaleTimeString();
  const latency = entry.latency_ms != null ? `${entry.latency_ms}ms` : '—';

  return (
    <div className="trace-entry" onClick={() => setExpanded(p => !p)} style={{ cursor: 'pointer' }}>
      <div className="trace-header">
        <span className={`badge ${entry.success ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: 10 }}>
          {entry.success ? '✓' : '✕'}
        </span>
        <span className="trace-call-type">{entry.call_type}</span>
        <span className="trace-model">{entry.model}</span>
        <span className="trace-latency">{latency}</span>
        <span className="trace-ts">{ts}</span>
        <span style={{ marginLeft: 8, color: 'var(--text-muted)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 8 }}>
          {entry.input_summary && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>INPUT</div>
              <div className="trace-detail">{entry.input_summary}</div>
            </div>
          )}
          {entry.output_summary && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>OUTPUT</div>
              <div className="trace-detail">{entry.output_summary}</div>
            </div>
          )}
          {entry.error && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: 'var(--danger)', marginBottom: 4 }}>ERROR</div>
              <div className="trace-detail" style={{ color: 'var(--danger)' }}>{entry.error}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
