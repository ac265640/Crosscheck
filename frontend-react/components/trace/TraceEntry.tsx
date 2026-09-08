'use client';
import { useState } from 'react';
import type { TraceEntry } from '@/lib/types';

export default function TraceEntryRow({ entry }: { entry: TraceEntry }) {
  const [expanded, setExpanded] = useState(false);
  
  const rawTs = entry.timestamp || entry.ts;
  let ts = '—';
  if (rawTs) {
    try {
      const d = new Date(rawTs);
      ts = isNaN(d.getTime()) ? String(rawTs) : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      ts = String(rawTs);
    }
  }

  const latency = entry.latency_ms != null ? `${Math.round(entry.latency_ms)} ms` : '—';

  return (
    <div
      className="trace-entry"
      onClick={() => setExpanded(p => !p)}
      style={{ cursor: 'pointer' }}
    >
      <div className="trace-header">
        <span
          className={`badge ${entry.success ? 'badge-success' : 'badge-danger'}`}
          style={{ fontSize: 11, fontWeight: 600 }}
        >
          {entry.success ? 'Success' : 'Error'}
        </span>
        <span className="trace-call-type">{entry.call_type}</span>
        <span className="trace-model">{entry.model}</span>
        <span className="trace-latency">{latency}</span>
        <span className="trace-ts">{ts}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            marginLeft: 8,
            color: 'var(--text-muted)',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          {entry.input_summary && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
                Prompt / Input Payload
              </div>
              <div className="trace-detail">{entry.input_summary}</div>
            </div>
          )}
          {entry.output_summary && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
                Parsed Output
              </div>
              <div className="trace-detail">{entry.output_summary}</div>
            </div>
          )}
          {entry.error && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--danger)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
                Error Details
              </div>
              <div className="trace-detail" style={{ color: 'var(--danger)', background: 'var(--danger-bg)', borderColor: 'var(--danger-border)' }}>
                {entry.error}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
