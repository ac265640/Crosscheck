'use client';

import { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface PixelSnowProps {
  /** How many snow particles to spawn */
  count?: number;
  /** Pixel size in world units */
  pixelSize?: number;
  /** Fall speed multiplier */
  speed?: number;
  /** Particle colour (hex) */
  color?: string;
  /** Canvas opacity (0-1) */
  opacity?: number;
}

export default function PixelSnow({
  count = 600,
  pixelSize = 0.012,
  speed = 0.0004,
  color = '#ffffff',
  opacity = 0.55,
}: PixelSnowProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    /* ── Renderer ─────────────────────────────────────────── */
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    /* ── Scene / Camera ───────────────────────────────────── */
    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
    camera.position.z = 10;

    /* ── Particle geometry ────────────────────────────────── */
    const positions = new Float32Array(count * 3);
    const phases   = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      positions[i * 3]     = (Math.random() - 0.5) * 2;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 2;
      positions[i * 3 + 2] = 0;
      phases[i] = Math.random() * Math.PI * 2;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    /* ── Square sprite texture (pixelated look) ───────────── */
    const canvas2d = document.createElement('canvas');
    canvas2d.width = 4;
    canvas2d.height = 4;
    const ctx2d = canvas2d.getContext('2d')!;
    ctx2d.fillStyle = '#ffffff';
    ctx2d.fillRect(0, 0, 4, 4);
    const tex = new THREE.CanvasTexture(canvas2d);
    tex.magFilter = THREE.NearestFilter;
    tex.minFilter = THREE.NearestFilter;

    const material = new THREE.PointsMaterial({
      map: tex,
      color: new THREE.Color(color),
      size: pixelSize,
      sizeAttenuation: false,
      transparent: true,
      opacity,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    /* ── Resize handler ───────────────────────────────────── */
    const onResize = () => {
      if (!mount) return;
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener('resize', onResize);

    /* ── Animation loop ───────────────────────────────────── */
    let frame = 0;
    let animId: number;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      frame++;

      const pos = geometry.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < count; i++) {
        pos.array[i * 3 + 1] -= speed * (0.5 + Math.random() * 0.5);
        pos.array[i * 3] += Math.sin(frame * 0.008 + phases[i]) * 0.0003;

        if (pos.array[i * 3 + 1] < -1) {
          pos.array[i * 3 + 1] = 1.05;
          pos.array[i * 3]     = (Math.random() - 0.5) * 2;
        }
      }
      pos.needsUpdate = true;
      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', onResize);
      geometry.dispose();
      material.dispose();
      tex.dispose();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [count, pixelSize, speed, color, opacity]);

  return (
    <div
      ref={mountRef}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
      }}
    />
  );
}
