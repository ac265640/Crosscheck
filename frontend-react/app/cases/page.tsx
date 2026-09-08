'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchCases } from '@/lib/api';
import type { CasesData, RelType } from '@/lib/types';
import CaseCard from '@/components/cases/CaseCard';

const TYPES: RelType[] = ['corroboration', 'contradiction', 'reconciled_context', 'uncertain'];

export default function CasesPage() {
  const [data, setData] = useState<CasesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCases()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <div className="page-header-row">
          <div>
            <h1 className="page-title">Four Core Evaluation Cases</h1>
            <p className="page-subtitle">
              Verified cross-document corroboration, contradiction, contextual reconciliation, and uncertainty handling.
            </p>
          </div>
          <Link href="/" className="btn btn-secondary btn-sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Documents
          </Link>
        </div>
      </div>

      {loading && (
        <div className="cases-grid">
          {TYPES.map(t => (
            <div key={t} className="skeleton" style={{ height: 280, borderRadius: 8 }} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-title">Could not load evaluation cases</div>
          <div className="empty-state-sub">{error}</div>
        </div>
      )}

      {!loading && !error && data && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
            gap: 16,
          }}
        >
          {TYPES.map(type => (
            <CaseCard
              key={type}
              type={type}
              entry={data[type]}
              compact={false}
            />
          ))}
        </div>
      )}
    </>
  );
}
