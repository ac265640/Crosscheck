import type { Metadata } from 'next';
import './globals.css';
import Sidebar from '@/components/layout/Sidebar';

export const metadata: Metadata = {
  title: 'Crosscheck — Cross-document Fact Reasoning',
  description: 'Ingest PDFs, extract verifiable facts, and reason about cross-document corroborations and contradictions.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-layout">
          <Sidebar />
          <main className="main-content">
            <div className="page-body">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
