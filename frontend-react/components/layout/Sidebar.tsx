'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/', label: 'Dashboard', icon: '⬡' },
  { href: '/cases', label: 'Four Cases', icon: '⬡' },
  { href: '/trace', label: 'Reasoning Trace', icon: '⬡' },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-text">✦ Crosscheck</div>
        <div className="sidebar-logo-sub">Cross-document Fact Reasoning</div>
      </div>
      <nav className="sidebar-nav">
        {NAV.map(n => (
          <Link
            key={n.href}
            href={n.href}
            className={`sidebar-nav-item${path === n.href || (n.href !== '/' && path.startsWith(n.href)) ? ' active' : ''}`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {n.href === '/' && <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>}
              {n.href === '/cases' && <><path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></>}
              {n.href === '/trace' && <><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></>}
            </svg>
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="status-dot" />
          <span>API: localhost:8000</span>
        </div>
      </div>
    </aside>
  );
}
