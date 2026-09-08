'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const Galaxy = dynamic(() => import('@/components/Galaxy'), { ssr: false });

const FEATURES = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 12l2 2 4-4" />
        <path d="M21 12c0 4.97-4.03 9-9 9S3 16.97 3 12 7.03 3 12 3s9 4.03 9 9z" />
      </svg>
    ),
    title: 'Claim Verification',
    desc: 'Every extracted fact is cross-referenced to its exact page and line across all ingested documents. Total transparency.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
    title: 'Cross-Doc Reasoning',
    desc: 'Surface corroborations, contradictions, and reconciled contexts spanning multiple PDFs simultaneously.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
    title: 'Confidence Scoring',
    desc: 'Each relationship is scored with fuzzy-match confidence so you know exactly how strong each link is.',
  },
];

export default function LandingPage() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 80);
    return () => clearTimeout(t);
  }, []);

  return (
    <div style={S.root}>
      {/* Galaxy WebGL — full screen */}
      <Galaxy
        mouseRepulsion
        mouseInteraction
        density={1.5}
        glowIntensity={0.55}
        saturation={0.0}
        hueShift={0}
        twinkleIntensity={0.4}
        rotationSpeed={0.04}
        speed={0.8}
        transparent
      />

      {/* ── Top nav ── */}
      <div style={S.nav}>
        <div style={S.navLogo}>
          {/* Red crown/logo icon matching FinRAG style */}
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="7" fill="#e53935" opacity="0.15"/>
            <rect width="32" height="32" rx="7" stroke="#e53935" strokeWidth="1" fill="none"/>
            <path d="M7 22 L10 12 L16 18 L22 8 L25 22 Z" fill="#e53935" stroke="#e53935" strokeWidth="1" strokeLinejoin="round"/>
            <circle cx="10" cy="12" r="1.5" fill="#ff6659"/>
            <circle cx="22" cy="8" r="1.5" fill="#ff6659"/>
            <circle cx="7" cy="22" r="1.5" fill="#ff6659"/>
            <circle cx="25" cy="22" r="1.5" fill="#ff6659"/>
          </svg>
          <span style={S.navLogoText}>Crosscheck</span>
        </div>
        <Link href="/" style={{ textDecoration: 'none' }}>
          <button style={S.navBtn} id="nav-enter-btn">Enter Platform</button>
        </Link>
      </div>

      {/* ── Hero ── */}
      <div
        style={{
          ...S.hero,
          opacity: visible ? 1 : 0,
          transform: visible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'opacity 0.85s cubic-bezier(0.16,1,0.3,1), transform 0.85s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        <h1 style={S.heroTitle}>Fact Verification.</h1>
        <p style={S.heroSub}>
          Crosscheck is an enterprise-grade document intelligence platform.<br />
          Ingest financial PDFs, extract verifiable claims, and reason about<br />
          cross-document corroborations and contradictions with provenance.
        </p>
        <Link href="/" style={{ textDecoration: 'none' }}>
          <button style={S.heroCta} id="enter-platform-btn">
            Open Dashboard
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </button>
        </Link>
      </div>

      {/* ── Feature cards — floating, not edge-pinned ── */}
      <div
        style={{
          ...S.cardsWrapper,
          opacity: visible ? 1 : 0,
          transform: visible ? 'translateY(0)' : 'translateY(28px)',
          transition: 'opacity 1s 0.3s cubic-bezier(0.16,1,0.3,1), transform 1s 0.3s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        {FEATURES.map((f, i) => (
          <div key={f.title} style={{ ...S.card, ...(i < FEATURES.length - 1 ? S.cardBorder : {}) }}>
            <div style={S.cardIcon}>{f.icon}</div>
            <div style={S.cardTitle}>{f.title}</div>
            <div style={S.cardDesc}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Bottom padding sentinel */}
      <div style={{ height: 32, flexShrink: 0, position: 'relative', zIndex: 5 }} />
    </div>
  );
}

/* ─── Styles ─────────────────────────────────────────────── */
const S: Record<string, React.CSSProperties> = {
  root: {
    position: 'relative',
    width: '100vw',
    height: '100vh',
    overflow: 'hidden',
    background: '#000',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    WebkitFontSmoothing: 'antialiased',
  },

  /* ── Nav ── */
  nav: {
    position: 'relative',
    zIndex: 10,
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '20px 32px',
    flexShrink: 0,
  },
  navLogo: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  navLogoText: {
    fontSize: 16,
    fontWeight: 700,
    color: '#ffffff',
    letterSpacing: '-0.02em',
  },
  navBtn: {
    background: 'transparent',
    border: '1px solid rgba(255,255,255,0.3)',
    color: '#e0e0e0',
    fontSize: 13,
    fontWeight: 500,
    padding: '8px 20px',
    borderRadius: 40,
    cursor: 'pointer',
    fontFamily: 'inherit',
    letterSpacing: '0.01em',
    transition: 'border-color 0.18s, color 0.18s, background 0.18s',
  },

  /* ── Hero ── */
  hero: {
    position: 'relative',
    zIndex: 5,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    flex: '1 0 0',
    justifyContent: 'center',
    padding: '0 32px',
    // Push hero slightly upward so cards feel below center
    marginTop: '-40px',
  },
  heroTitle: {
    fontSize: 'clamp(54px, 8vw, 86px)',
    fontWeight: 800,
    letterSpacing: '-0.04em',
    lineHeight: 1,
    color: '#e53935',
    marginBottom: 30,
    textShadow: '0 0 80px rgba(229,57,53,0.5)',
  },
  heroSub: {
    fontSize: 16,
    lineHeight: 1.8,
    color: 'rgba(220,228,240,0.7)',
    maxWidth: 560,
    marginBottom: 48,
    fontWeight: 400,
  },
  heroCta: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 10,
    padding: '14px 36px',
    background: '#e53935',
    color: '#fff',
    fontSize: 15,
    fontWeight: 700,
    letterSpacing: '0.01em',
    border: 'none',
    borderRadius: 40,
    cursor: 'pointer',
    fontFamily: 'inherit',
    boxShadow: '0 0 40px rgba(229,57,53,0.45)',
    transition: 'background 0.18s, box-shadow 0.18s, transform 0.18s',
  },

  /* ── Cards ── */
  cardsWrapper: {
    position: 'relative',
    zIndex: 5,
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 0,
    width: 'calc(100% - 64px)',
    maxWidth: 960,
    borderRadius: 14,
    overflow: 'hidden',
    border: '1px solid rgba(255,255,255,0.1)',
    background: 'rgba(12,12,15,0.75)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
    flexShrink: 0,
    marginBottom: 0,
  },
  card: {
    padding: '28px 28px 32px',
  },
  cardBorder: {
    borderRight: '1px solid rgba(255,255,255,0.08)',
  },
  cardIcon: {
    width: 42,
    height: 42,
    borderRadius: 10,
    background: 'rgba(229,57,53,0.12)',
    border: '1px solid rgba(229,57,53,0.25)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#e53935',
    marginBottom: 16,
    flexShrink: 0,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: 700,
    color: '#f4f4f5',
    marginBottom: 10,
    letterSpacing: '-0.015em',
  },
  cardDesc: {
    fontSize: 13,
    lineHeight: 1.7,
    color: 'rgba(170,185,210,0.65)',
  },
};
