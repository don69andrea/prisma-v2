'use client';

import { useState, useEffect } from 'react';

export type PrismaMode = 'simple' | 'pro';

export function usePrismaMode() {
  const [mode, setMode] = useState<PrismaMode>('simple');

  useEffect(() => {
    const stored = localStorage.getItem('prisma-mode') as PrismaMode | null;
    if (stored === 'simple' || stored === 'pro') setMode(stored);
  }, []);

  const toggle = () => {
    const next: PrismaMode = mode === 'simple' ? 'pro' : 'simple';
    localStorage.setItem('prisma-mode', next);
    setMode(next);
  };

  return { mode, toggle, isSimple: mode === 'simple', isPro: mode === 'pro' };
}
