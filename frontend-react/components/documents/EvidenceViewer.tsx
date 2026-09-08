'use client';
import { getPageImageUrl } from '@/lib/api';
import type { Fact } from '@/lib/types';

export default function EvidenceViewer({ fact }: { fact: Fact }) {
  const imageUrl = fact.page_number != null
    ? getPageImageUrl(fact.document_id, fact.page_number, fact.bbox ?? undefined)
    : null;

  return (
    <div>
      {fact.verbatim_quote && (
        <div className="evidence-quote">
          &ldquo;{fact.verbatim_quote}&rdquo;
        </div>
      )}
      {imageUrl && (
        <div className="page-image-wrapper" style={{ marginTop: 12 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={`Page ${fact.page_number} evidence`}
            loading="lazy"
          />
        </div>
      )}
      {!imageUrl && !fact.verbatim_quote && (
        <div className="text-muted" style={{ fontSize: 13, padding: '16px 0' }}>
          No evidence available for this fact.
        </div>
      )}
      {fact.page_number != null && (
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
          Page {fact.page_number}
          {fact.bbox && ` · bbox: [${fact.bbox.map(n => n.toFixed(1)).join(', ')}]`}
        </div>
      )}
    </div>
  );
}
