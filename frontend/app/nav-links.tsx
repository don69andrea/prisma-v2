'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Compass, MoreHorizontal } from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';

import { cn } from '@/lib/utils';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { PROFILE_STORAGE_KEY } from '@/app/start/start-client';

const PROFILE_BADGE_LABEL: Record<string, string> = {
  conservative: 'Stabiler Investor',
  moderate:     'Ausgewogener Investor',
  aggressive:   'Chancen-Investor',
};

interface NavLink { href: string; label: string }

interface NavCluster {
  groupLabel: string;
  color: string;
  links: NavLink[];
}

// Links visible in the nav bar (primary)
const CLUSTERS_SIMPLE: NavCluster[] = [
  { groupLabel: 'Entdecken',   color: '#8b5cf6', links: [{ href: '/start',    label: 'Profil' }, { href: '/discover', label: 'Universum' }] },
  { groupLabel: 'Analysieren', color: '#3b82f6', links: [{ href: '/rankings', label: 'Rankings' }, { href: '/stocks', label: 'Aktien' }, { href: '/crypto', label: 'Krypto' }] },
  { groupLabel: 'Entscheiden', color: '#f59e0b', links: [{ href: '/decision', label: 'Signale' }, { href: '/alerts', label: 'Alerts' }, { href: '/news', label: 'News' }] },
  { groupLabel: 'Beobachten',  color: '#10b981', links: [{ href: '/watchlist', label: 'Watchlist' }, { href: '/research', label: 'Research' }] },
];

const CLUSTERS_PRO_PRIMARY: NavCluster[] = [
  { groupLabel: 'Entdecken',   color: '#8b5cf6', links: [{ href: '/start',    label: 'Profil' }, { href: '/discover', label: 'Universum' }] },
  { groupLabel: 'Analysieren', color: '#3b82f6', links: [{ href: '/rankings', label: 'Rankings' }, { href: '/stocks', label: 'Aktien' }, { href: '/research', label: 'Research' }, { href: '/crypto', label: 'Krypto' }] },
  { groupLabel: 'Entscheiden', color: '#f59e0b', links: [{ href: '/decision', label: 'Signale' }, { href: '/alerts', label: 'Alerts' }, { href: '/news', label: 'News' }] },
  { groupLabel: 'Beobachten',  color: '#10b981', links: [{ href: '/watchlist', label: 'Watchlist' }] },
];

// Overflow links only in Pro mode
const OVERFLOW_LINKS: NavLink[] = [
  { href: '/universes', label: 'Universen' },
  { href: '/backtest',  label: 'Backtest'  },
  { href: '/fonds',     label: 'Fonds'     },
  { href: '/steuer',    label: 'Steuer'    },
  { href: '/portfolio', label: 'Portfolio' },
];

function isActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href);
}

function ClusterDivider({ color, label }: { color: string; label: string }) {
  return (
    <div
      className="flex items-center self-stretch shrink-0 mx-1"
      title={label}
      aria-hidden="true"
    >
      <div className="w-px h-4 rounded-full opacity-40" style={{ background: color }} />
    </div>
  );
}

function NavLinkItem({ link, color, pathname }: { link: NavLink; color: string; pathname: string }) {
  const active = isActive(link.href, pathname);
  return (
    <Link
      href={link.href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'text-sm shrink-0 transition-all duration-150 px-0.5',
        active
          ? 'font-semibold border-b border-current'
          : 'text-muted-foreground hover:text-foreground',
      )}
      style={active ? { color } : undefined}
    >
      {link.label}
    </Link>
  );
}

function OverflowMenu({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);
  const hasActive = OVERFLOW_LINKS.some((l) => isActive(l.href, pathname));

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          className={cn(
            'inline-flex items-center justify-center h-5 w-5 rounded text-muted-foreground transition-colors hover:text-foreground hover:bg-muted shrink-0',
            hasActive && 'text-foreground',
          )}
          aria-label="Mehr"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="z-50 min-w-[140px] rounded-lg border border-border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95"
          sideOffset={8}
          align="start"
        >
          {OVERFLOW_LINKS.map((link) => {
            const active = isActive(link.href, pathname);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={cn(
                  'flex items-center px-3 py-1.5 text-sm rounded-md transition-colors',
                  active
                    ? 'font-medium text-foreground bg-accent'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent',
                )}
              >
                {link.label}
              </Link>
            );
          })}
          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function NavLinks() {
  const pathname = usePathname();
  const { mode } = usePrismaMode();
  const [profileType, setProfileType] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (stored) setProfileType(stored);
    const onStorage = (e: StorageEvent) => {
      if (e.key === PROFILE_STORAGE_KEY) setProfileType(e.newValue);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const isPro = mode === 'pro';
  const clusters = isPro ? CLUSTERS_PRO_PRIMARY : CLUSTERS_SIMPLE;

  return (
    <nav className="flex items-center gap-3 min-w-0" aria-label="Hauptnavigation">
      {clusters.map((cluster, ci) => (
        <div key={cluster.groupLabel} className="flex items-center gap-3">
          {ci > 0 && <ClusterDivider color={cluster.color} label={cluster.groupLabel} />}
          {cluster.links.map((link) => (
            <NavLinkItem key={link.href} link={link} color={cluster.color} pathname={pathname} />
          ))}
        </div>
      ))}

      {isPro && (
        <>
          <ClusterDivider color="#64748b" label="Mehr" />
          <OverflowMenu pathname={pathname} />
        </>
      )}

      {profileType && (
        <span className="ml-2 inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 whitespace-nowrap shrink-0">
          <Compass className="h-3 w-3 shrink-0" />
          {PROFILE_BADGE_LABEL[profileType] ?? 'Entdecker'}
        </span>
      )}
    </nav>
  );
}
