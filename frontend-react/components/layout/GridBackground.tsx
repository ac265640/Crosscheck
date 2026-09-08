'use client';

import '@/gridscan.css';
import dynamic from 'next/dynamic';

const GridScan = dynamic(
  () => import('@/gridscan').then(m => m.GridScan ?? m.default),
  { ssr: false }
);

export default function GridBackground() {
  return (
    <div
      style={{
        position: 'fixed',
        left: 'var(--sidebar-width, 16rem)',
        top: 0,
        bottom: 0,
        right: 0,
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.6,
      }}
    >
      <GridScan
        sensitivity={0.55}
        lineThickness={0.5}
        linesColor="#000000"
        gridScale={0.1}
        scanColor="#000000"
        scanOpacity={0.15}
        enablePost={false}
        bloomIntensity={0}
        chromaticAberration={0}
        noiseIntensity={0.02}
        enableParallax={false}
      />
    </div>
  );
}
