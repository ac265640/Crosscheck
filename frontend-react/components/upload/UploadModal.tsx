'use client';
import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadDocument } from '@/lib/api';
import ProgressStream from './ProgressStream';

interface Props { onClose: () => void; }

export default function UploadModal({ onClose }: Props) {
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (f: File) => {
    if (!f.name.endsWith('.pdf')) {
      setError('Only PDF files are supported.');
      return;
    }
    setFile(f);
    setError(null);
    setUploading(true);
    try {
      const res = await uploadDocument(f);
      setJobId(res.job_id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const onDone = (docId: string | null) => {
    if (docId) {
      setTimeout(() => {
        onClose();
        router.push(`/documents/${docId}`);
      }, 1200);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-title">Upload PDF</div>
        <div className="modal-sub">Drag and drop a PDF to ingest it into the knowledge layer</div>

        {!jobId && !uploading && (
          <div
            className={`dropzone${dragging ? ' dragging' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <div className="dropzone-icon" style={{ display: 'flex', justifyContent: 'center' }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" style={{ color: 'var(--accent)' }}>
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="dropzone-text">
              {dragging ? 'Drop PDF here' : 'Drag a PDF here or click to browse'}
            </div>
            <div className="dropzone-sub">Max size: 100 MB · PDF only</div>
            <input
              id="file-input"
              type="file"
              accept=".pdf"
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
          </div>
        )}

        {uploading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            <span className="spinner" style={{ width: 24, height: 24 }} />
            <p style={{ marginTop: 12 }}>Uploading {file?.name}…</p>
          </div>
        )}

        {jobId && (
          <div>
            <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-muted)' }}>
              File: <strong style={{ color: 'var(--text-primary)' }}>{file?.name}</strong>
            </div>
            <ProgressStream jobId={jobId} onDone={onDone} />
          </div>
        )}

        {error && (
          <div className="progress-error" style={{ marginTop: 12 }}>{error}</div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24, gap: 10 }}>
          <button className="btn btn-secondary" onClick={onClose}>
            {jobId ? 'Close' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}
