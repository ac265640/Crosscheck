'use client';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === '/landing';

  if (isLanding) {
    // Landing page renders full-screen, no sidebar/shell
    return <>{children}</>;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <div className="page-body">{children}</div>
      </main>
    </div>
  );
}
