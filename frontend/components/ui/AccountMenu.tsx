'use client';

import { useState } from 'react';
import Link from 'next/link';
import * as Popover from '@radix-ui/react-popover';
import { useAuth } from '@/hooks/useAuth';

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
          aria-label="Account-Menü öffnen"
        >
          <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-primary/20 text-primary text-[9px] font-bold leading-none">
            {initials}
          </span>
          <span className="max-w-[80px] truncate">{displayName}</span>
          {user.role === 'admin' && (
            <span className="rounded-sm bg-violet-500/15 px-0.5 text-[9px] text-violet-400">
              admin
            </span>
          )}
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className="z-50 min-w-[160px] rounded-lg border border-border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95"
          sideOffset={8}
          align="end"
        >
          <div className="px-3 py-2 border-b border-border mb-1">
            <p className="text-xs font-medium text-foreground truncate">{user.email}</p>
            <p className="text-[10px] text-muted-foreground">{user.role}</p>
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
