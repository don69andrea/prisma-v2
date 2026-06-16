'use client';

import { useState, useEffect } from 'react';

export type PrismaMode = 'simple' | 'pro';

const LS_KEY = 'prisma-mode';
const EVENT = 'prisma-mode-change';

export function usePrismaMode() {
  const [mode, setMode] = useState<PrismaMode>('simple');

  useEffect(() => {
    const stored = localStorage.getItem(LS_KEY) as PrismaMode | null;
    if (stored === 'simple' || stored === 'pro') setMode(stored);

    const handleChange = (e: Event) => {
      const next = (e as CustomEvent<PrismaMode>).detail;
      if (next === 'simple' || next === 'pro') setMode(next);
    };
    window.addEventListener(EVENT, handleChange);
    return () => window.removeEventListener(EVENT, handleChange);
  }, []);

  const toggle = () => {
    const next: PrismaMode = mode === 'simple' ? 'pro' : 'simple';
    localStorage.setItem(LS_KEY, next);
    setMode(next);
    window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
  };

  return { mode, toggle, isSimple: mode === 'simple', isPro: mode === 'pro' };
}
