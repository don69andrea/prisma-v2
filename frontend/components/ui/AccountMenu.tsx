'use client';

import { useState } from 'react';
import Link from 'next/link';
import * as Popover from '@radix-ui/react-popover';
import { useAuth } from '@/hooks/useAuth';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api/client';

function InlineApiStatus() {
  const { isSuccess } = useQuery({
    queryKey: ['api-status'],
    queryFn: () => apiFetch('/health/ready'),
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 20_000,
  });
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
      <span className={`h-1.5 w-1.5 rounded-full ${isSuccess ? 'bg-emerald-400 shadow-[0_0_4px_#34d399]' : 'bg-red-400'}`} />
      API {isSuccess ? 'online' : 'offline'}
    </span>
  );
}

function InlineModeToggle() {
  const { mode, toggle } = usePrismaMode();
  const isPro = mode === 'pro';
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground select-none">
      <span className={isPro ? 'text-muted-foreground' : 'text-foreground font-medium'}>Simple</span>
      <button
        onClick={toggle}
        aria-label={isPro ? 'Zu Simple Mode wechseln' : 'Zu Pro Mode wechseln'}
        className="relative inline-flex h-5 w-9 items-center rounded-full border border-border bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        role="switch"
        aria-checked={isPro}
      >
        <span
          className={`inline-block h-3.5 w-3.5 rounded-full bg-blue-500 shadow transition-transform duration-200 ${
            isPro ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </button>
      <span className={isPro ? 'text-foreground font-medium' : 'text-muted-foreground'}>Pro</span>
    </div>
  );
}

export function AccountMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  const firstName = user.email.split('@')[0].split(/[._-]/)[0];
  const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1);
  const initials = displayName.charAt(0);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur transition-colors hover:border-border/80 hover:text-foreground"
          style={{ minWidth: '120px' }}
          aria-label="Account-Menü öffnen"
        >
          <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary/20 text-primary text-[9px] font-bold leading-none shrink-0">
            {initials}
          </span>
          <span className="truncate flex-1">{displayName}</span>
          {user.role === 'admin' && (
            <span className="rounded-sm bg-violet-500/15 px-0.5 text-[9px] text-violet-400 shrink-0">
              admin
            </span>
          )}
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className="z-50 w-52 rounded-lg border border-border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95"
          sideOffset={8}
          align="end"
        >
          <div className="px-3 py-2 border-b border-border mb-1">
            <p className="text-xs font-medium text-foreground truncate">{user.email}</p>
            <p className="text-[10px] text-muted-foreground capitalize">{user.role}</p>
          </div>

          {/* Mode + API status inline under username */}
          <div className="px-3 py-2 border-b border-border mb-1 space-y-2">
            <InlineModeToggle />
            <InlineApiStatus />
          </div>

          {user.role === 'admin' && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className="flex items-center px-3 py-1.5 text-sm rounded-md text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
            >
              Admin-Panel
            </Link>
          )}

          <Link
            href="/start"
            onClick={() => setOpen(false)}
            className="flex items-center px-3 py-1.5 text-sm rounded-md text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
          >
            Einstellungen
          </Link>

          <div className="my-1 border-t border-border" />

          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center px-3 py-1.5 text-sm rounded-md text-muted-foreground transition-colors hover:text-destructive hover:bg-destructive/10"
          >
            Abmelden
          </button>

          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
