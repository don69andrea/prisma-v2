'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';

const FLAG_KEY = 'prisma_just_logged_in';
const DISPLAY_MS = 4000;
const FADE_MS = 500;

function deriveName(email: string, firstName?: string): string {
  if (firstName) {
    return firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase();
  }
  const raw = email.split('@')[0].split(/[._-]/)[0];
  return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
}

export function WelcomePopup() {
  const { user } = useAuth();
  const [visible, setVisible] = useState(false);
  const [fading, setFading] = useState(false);
  const [name, setName] = useState('');
  const timerFade = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerHide = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!user) return;
    if (typeof window === 'undefined') return;
    const flag = sessionStorage.getItem(FLAG_KEY);
    if (!flag) return;
    sessionStorage.removeItem(FLAG_KEY);
    setName(deriveName(user.email, (user as { first_name?: string }).first_name));
    setVisible(true);
    timerFade.current = setTimeout(() => setFading(true), DISPLAY_MS);
    timerHide.current = setTimeout(() => setVisible(false), DISPLAY_MS + FADE_MS);
    return () => {
      if (timerFade.current) clearTimeout(timerFade.current);
      if (timerHide.current) clearTimeout(timerHide.current);
    };
  }, [user]);

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.82)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        transition: `opacity ${FADE_MS}ms ease`,
        opacity: fading ? 0 : 1,
      }}
    >
      {/* Card */}
      <div
        className="relative w-[400px] max-w-[90vw] overflow-hidden rounded-2xl animate-welcome-in"
        style={{
          background: 'linear-gradient(135deg, hsl(220 45% 8% / 0.97) 0%, hsl(222 60% 5% / 0.97) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.35)',
          boxShadow: '0 0 0 1px rgba(99,102,241,0.1), 0 0 60px rgba(99,102,241,0.25), 0 20px 60px rgba(0,0,0,0.6)',
        }}
      >
        {/* Scanning line */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute top-0 bottom-0 w-[60%] animate-scan-h"
            style={{
              background: 'linear-gradient(90deg, transparent 0%, rgba(99,102,241,0.18) 40%, rgba(139,92,246,0.28) 50%, rgba(99,102,241,0.18) 60%, transparent 100%)',
            }}
          />
        </div>

        {/* Grid texture */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(rgba(99,102,241,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.06) 1px, transparent 1px)',
            backgroundSize: '28px 28px',
          }}
        />

        {/* Corner glows */}
        <div className="absolute -top-8 -right-8 w-28 h-28 rounded-full pointer-events-none" style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.25) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-8 -left-8 w-28 h-28 rounded-full pointer-events-none" style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)' }} />

        {/* Content */}
        <div className="relative px-10 py-10 flex flex-col items-center gap-5 text-center">
          {/* Logo */}
          <div
            className="flex items-center justify-center w-14 h-14 rounded-xl"
            style={{
              background: 'linear-gradient(135deg, rgba(99,102,241,0.2) 0%, rgba(59,130,246,0.1) 100%)',
              border: '1px solid rgba(99,102,241,0.4)',
              boxShadow: '0 0 20px rgba(99,102,241,0.2)',
            }}
          >
            <span className="font-black text-2xl" style={{ color: 'hsl(210 40% 98%)', letterSpacing: '-0.05em' }}>P</span>
          </div>

          {/* Text block */}
          <div className="space-y-2">
            <p
              className="text-[10px] font-mono uppercase tracking-[0.35em]"
              style={{ color: 'rgba(148,163,184,0.5)' }}
            >
              PRISMA · Swiss Stock Intelligence
            </p>
            <h2
              className="text-3xl font-black tracking-tight"
              style={{
                color: 'hsl(210 40% 98%)',
                textShadow: '0 0 30px rgba(99,102,241,0.4)',
              }}
            >
              WILLKOMMEN
            </h2>
            <p
              className="text-xl font-light tracking-widest"
              style={{
                background: 'linear-gradient(90deg, #818cf8, #60a5fa, #818cf8)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              {name}
            </p>
          </div>

          {/* Pulsing dots */}
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full animate-blink-dot"
                  style={{
                    backgroundColor: '#818cf8',
                    animationDelay: `${i * 0.22}s`,
                  }}
                />
              ))}
            </div>
            <span
              className="text-[10px] font-mono uppercase tracking-[0.25em]"
              style={{ color: 'rgba(148,163,184,0.45)' }}
            >
              System wird geladen
            </span>
          </div>

          {/* Progress bar */}
          <div className="w-full mt-1">
            <div
              className="h-[2px] rounded-full overflow-hidden"
              style={{ background: 'rgba(99,102,241,0.15)' }}
            >
              <div
                className="h-full rounded-full animate-progress-shrink"
                style={{
                  background: 'linear-gradient(90deg, #6366f1, #60a5fa, #818cf8)',
                  boxShadow: '0 0 8px rgba(99,102,241,0.8)',
                }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
