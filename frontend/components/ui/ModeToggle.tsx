'use client';

import { usePrismaMode } from '@/hooks/usePrismaMode';

export function ModeToggle() {
  const { mode, toggle } = usePrismaMode();
  const isPro = mode === 'pro';

  return (
    <div className="flex items-center gap-1.5 text-xs text-slate-400 select-none">
      <span className={isPro ? 'text-slate-500' : 'text-slate-200 font-medium'}>Simple</span>
      <button
        onClick={toggle}
        aria-label={isPro ? 'Zu Simple Mode wechseln' : 'Zu Pro Mode wechseln'}
        className="relative inline-flex h-5 w-9 items-center rounded-full border border-slate-600 bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        role="switch"
        aria-checked={isPro}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-blue-400 shadow transition-transform duration-200 ${
            isPro ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </button>
      <span className={isPro ? 'text-slate-200 font-medium' : 'text-slate-500'}>Pro</span>
    </div>
  );
}
