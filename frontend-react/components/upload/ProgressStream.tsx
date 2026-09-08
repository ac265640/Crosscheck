'use client';
import { useEffect, useRef, useState } from 'react';
import { getJobStreamUrl } from '@/lib/api';
import type { ProgressEvent } from '@/lib/types';

interface Props {
  jobId: string;
  onDone: (docId: string | null) => void;
}

const STAGE_LABELS: Record<string, string> = {
  parsing: 'Parsing document structure',
  chunking: 'Segmenting text chunks',
  extracting: 'Extracting candidate facts',
  verifying: 'Grounding facts with source chunks',
  canonicalizing: 'Canonicalizing entities and attributes',
  reasoning: 'Analyzing cross-document relationships',
  done: 'Ingestion complete',
  error: 'Processing error',
};

export default function ProgressStream({ jobId, onDone }: Props) {
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [latest, setLatest] = useState<ProgressEvent | null>(null);
  const [finished, setFinished] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const url = getJobStreamUrl(jobId);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const evt: ProgressEvent & { stage: string } = JSON.parse(e.data);
        if (evt.stage === 'closed') { es.close(); return; }
        setLatest(evt as ProgressEvent);
        setEvents(prev => [...prev, evt as ProgressEvent]);
        if (evt.stage === 'done') {
          setFinished(true);
          es.close();
          onDone(evt.document_id);
        }
        if (evt.stage === 'error') {
          setErrMsg(evt.msg);
          setFinished(true);
          es.close();
        }
      } catch {}
    };

    es.onerror = () => {
      es.close();
      if (!finished) setErrMsg('Server connection interrupted. Please check backend status.');
    };

    return () => { es.close(); };
  }, [jobId]);

  const pct = latest?.pct ?? 0;
  const stage = latest?.stage ?? 'queued';
  const stageLabel = STAGE_LABELS[stage] ?? stage;

  return (
    <div className="progress-container">
      <div className="progress-stage">
        {!finished && !errMsg && <span className="spinner" style={{ width: 14, height: 14 }} />}
        <span className="progress-stage-name">{stageLabel}</span>
        <span className="progress-pct">{Math.max(0, pct)}%</span>
      </div>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${Math.max(0, pct)}%` }}
        />
      </div>
      <div className="progress-msg">{latest?.msg ?? 'Initializing job...'}</div>
      {finished && !errMsg && (
        <div className="progress-done" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="badge badge-success" style={{ fontSize: 12 }}>Completed</span>
          <span style={{ fontSize: 13, color: 'var(--success)' }}>Document successfully indexed</span>
        </div>
      )}
      {errMsg && (
        <div className="progress-error" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="badge badge-danger" style={{ fontSize: 12 }}>Failed</span>
          <span>{errMsg}</span>
        </div>
      )}
    </div>
  );
}
