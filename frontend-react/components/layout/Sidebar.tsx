'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/', label: 'Documents' },
  { href: '/cases', label: 'Four Cases' },
  { href: '/trace', label: 'Reasoning Trace' },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Link href="/landing" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <div style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            background: '#e53935',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 12px rgba(229,57,53,0.35)',
            flexShrink: 0,
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <div>
            <div className="sidebar-logo-text">Crosscheck</div>
            <div className="sidebar-logo-sub">Fact Verification Engine</div>
          </div>
        </Link>
      </div>
      <nav className="sidebar-nav">
        {NAV.map(n => {
          const isActive = path === n.href || (n.href !== '/' && path.startsWith(n.href));
          return (
            <Link
              key={n.href}
              href={n.href}
              className={`sidebar-nav-item${isActive ? ' active' : ''}`}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {n.href === '/' && (
                <>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </>
              )}
              {n.href === '/cases' && (
                <>
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </>
              )}
              {n.href === '/trace' && (
                <>
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </>
              )}
              </svg>
              <span>{n.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span className="status-dot" />
            <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>System Active</span>
          </div>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>v1.0.0</span>
        </div>
        <Link
          href="/landing"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 11,
            color: 'var(--text-muted)',
            padding: '4px 0',
            transition: 'color 0.15s ease',
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Back to Landing
        </Link>
      </div>
    </aside>
  );
}
