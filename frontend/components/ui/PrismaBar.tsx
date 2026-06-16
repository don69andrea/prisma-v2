'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { usePathname } from 'next/navigation';

const SPECTRUM = 'linear-gradient(to right, #8b5cf6, #3b82f6, #10b981, #f59e0b, #ef4444)';
const GLOW = '0 0 8px rgba(88, 166, 255, 0.45)';

/** Indeterminate inline progress bar with PRISMA spectrum gradient.
 *  Drop in anywhere a section is loading — needs no props. */
export function PrismaBar({ className = '' }: { className?: string }) {
  return (
    <div
      role="progressbar"
      aria-label="Lädt…"
      aria-valuemin={0}
      aria-valuemax={100}
      className={`relative h-[3px] w-full overflow-hidden rounded-full bg-muted/40 ${className}`}
    >
      <div
        className="absolute inset-y-0 w-[35%] rounded-full"
        style={{ background: SPECTRUM, boxShadow: GLOW, animation: 'prismaIndeterminate 2s ease-in-out infinite' }}
      />
    </div>
  );
}

interface RunProgressBarProps {
  /** Expected duration in ms — bar fills 0→88% over this time, then holds. */
  estimatedMs?: number;
  /** Set true when the job finishes to snap the bar to 100%. */
  done?: boolean;
  /** Optional status line shown below the bar. */
  label?: string;
}

/** Deterministic-looking progress bar for long-running backend jobs (rankings, rebalancing, …).
 *  Fills logarithmically toward 88%, then completes when `done` flips to true. */
export function RunProgressBar({ estimatedMs = 45_000, done = false, label }: RunProgressBarProps) {
  const [pct, setPct] = useState(0);
  const startRef = useRef(Date.now());
  const itvRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (done) {
      clearInterval(itvRef.current);
      setPct(100);
      return;
    }
    startRef.current = Date.now();
    itvRef.current = setInterval(() => {
      const elapsed = Date.now() - startRef.current;
      // Logarithmic ease: fast at first, slows toward 88%
      const p = 88 * (1 - Math.exp(-3 * elapsed / estimatedMs));
      setPct(Math.min(p, 87));
    }, 400);
    return () => clearInterval(itvRef.current);
  }, [done, estimatedMs]);

  return (
    <div className="space-y-2" role="status">
      <div className="relative h-[4px] w-full overflow-hidden rounded-full bg-muted/40">
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            background: SPECTRUM,
            boxShadow: GLOW,
            borderRadius: '9999px',
            transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      </div>
      {label && <p className="text-xs text-muted-foreground">{label}</p>}
    </div>
  );
}

/** Fixed top-of-page bar that activates on every Next.js client-side route transition.
 *  Add once to the root layout — it manages itself. */
export function NavigationProgressBar() {
  const pathname = usePathname();
  const [pct, setPct] = useState(0);
  const [visible, setVisible] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval>>();
  const prevPath = useRef(pathname);
  const completing = useRef(false);

  const start = useCallback(() => {
    if (completing.current) return;
    clearInterval(timer.current);
    setVisible(true);
    setPct(8);
    timer.current = setInterval(() => {
      setPct((p) => {
        if (p >= 84) { clearInterval(timer.current); return 84; }
        return p + Math.random() * 10 * (1 - p / 100);
      });
    }, 200);
  }, []);

  const complete = useCallback(() => {
    completing.current = true;
    clearInterval(timer.current);
    setPct(100);
    setTimeout(() => {
      setVisible(false);
      setPct(0);
      completing.current = false;
    }, 380);
  }, []);

  // Detect navigation end (pathname changed → page loaded)
  useEffect(() => {
    if (prevPath.current !== pathname) {
      prevPath.current = pathname;
      complete();
    }
  }, [pathname, complete]);

  // Intercept history.pushState to detect navigation start
  useEffect(() => {
    const orig = window.history.pushState.bind(window.history);
    window.history.pushState = (...args: Parameters<typeof window.history.pushState>) => {
      orig(...args);
      start();
    };
    return () => { window.history.pushState = orig; };
  }, [start]);

  if (!visible) return null;

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 9999,
        height: '3px',
        width: `${pct}%`,
        background: SPECTRUM,
        boxShadow: GLOW,
        borderRadius: '0 9999px 9999px 0',
        transition: 'width 200ms ease-out, opacity 380ms ease',
        pointerEvents: 'none',
      }}
    />
  );
}
