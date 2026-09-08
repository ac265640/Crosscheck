'use client';
import { useEffect, useState } from 'react';
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
      <div className="page-header">
        <h1 className="page-title">Four Required Cases</h1>
        <p className="page-subtitle">
          One example of each cross-document relationship type — corroboration, contradiction, reconciled context, and uncertain.
        </p>
      </div>

      {loading && (
        <div className="cases-grid">
          {TYPES.map(t => (
            <div key={t} className="skeleton" style={{ height: 320, borderRadius: 12 }} />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="empty-state">
          <div className="empty-state-icon">⚠️</div>
          <div className="empty-state-title">Could not load cases</div>
          <div className="empty-state-sub">{error}</div>
        </div>
      )}

      {!loading && !error && data && (
        <div className="cases-grid">
          {TYPES.map(type => (
            <CaseCard key={type} type={type} entry={data[type]} />
          ))}
        </div>
      )}
    </>
  );
}
