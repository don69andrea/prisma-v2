'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Compass } from 'lucide-react';

import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/routes';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { PROFILE_STORAGE_KEY } from '@/app/start/start-client';

const PROFILE_BADGE_LABEL: Record<string, string> = {
  conservative: 'Stabiler Investor',
  moderate:     'Ausgewogener Investor',
  aggressive:   'Chancen-Investor',
};

interface NavGroup {
  label: string;
  color: string;
  links: { href: string; label: string }[];
}

const NAV_GROUPS_SIMPLE: NavGroup[] = [
  {
    label: 'ENTDECKEN',
    color: '#8b5cf6',
    links: [
      { href: '/start',    label: 'Start' },
      { href: '/discover', label: 'Mein Universum' },
    ],
  },
  {
    label: 'ANALYSIEREN',
    color: '#3b82f6',
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
    ],
  },
  {
    label: 'ENTSCHEIDEN',
    color: '#f59e0b',
    links: [
      { href: '/decision', label: 'Signale' },
      { href: '/alerts',   label: 'Alerts' },
      { href: '/news',     label: 'News' },
    ],
  },
  {
    label: 'KRYPTO',
    color: '#f97316',
    links: [
      { href: '/crypto', label: 'Krypto-Signale' },
    ],
  },
  {
    label: 'WATCHLIST',
    color: '#10b981',
    links: [
      { href: '/watchlist', label: 'Watchlist' },
    ],
  },
  {
    label: 'RESEARCH',
    color: '#06b6d4',
    links: [
      { href: '/research', label: 'Research' },
    ],
  },
];

const NAV_GROUPS_PRO: NavGroup[] = [
  {
    label: 'ENTDECKEN',
    color: '#8b5cf6',
    links: [
      { href: '/start',    label: 'Start' },
      { href: '/discover', label: 'Mein Universum' },
    ],
  },
  {
    label: 'ANALYSIEREN',
    color: '#3b82f6',
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
      { href: '/research', label: 'Research' },
    ],
  },
  {
    label: 'ENTSCHEIDEN',
    color: '#f59e0b',
    links: [
      { href: '/decision', label: 'Signale' },
      { href: '/alerts',   label: 'Alerts' },
      { href: '/news',     label: 'News' },
    ],
  },
  {
    label: 'KRYPTO',
    color: '#f97316',
    links: [
      { href: '/crypto', label: 'Krypto-Signale' },
    ],
  },
  {
    label: 'WATCHLIST',
    color: '#10b981',
    links: [
      { href: '/watchlist', label: 'Watchlist' },
    ],
  },
  {
    label: 'MEHR',
    color: '#64748b',
    links: [
      { href: '/universes', label: 'Universen' },
      { href: '/backtest',  label: 'Backtest' },
      { href: '/steuer',    label: 'Steuer' },
    ],
  },
];

function isActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href);
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

  const groups = mode === 'pro' ? NAV_GROUPS_PRO : NAV_GROUPS_SIMPLE;

  return (
    <nav
      className="flex flex-wrap items-start gap-6 pb-0.5"
      aria-label="Hauptnavigation"
    >
      {groups.map((group) => (
        <div key={group.label} className="flex flex-col gap-1 shrink-0">
          <span className="flex items-center gap-1 text-[9px] font-semibold tracking-[0.15em] text-[#8b949e] uppercase px-1">
            <span className="inline-block w-[3px] h-[3px] rounded-full bg-current opacity-40" aria-hidden="true" />
            {group.label}
          </span>
          <div className="flex items-center gap-3">
            {group.links.map((link) => {
              const active = isActive(link.href, pathname);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'text-sm shrink-0 transition-all duration-200 px-1',
                    active
                      ? 'font-medium border-b'
                      : 'text-muted-foreground hover:text-foreground hover:scale-[1.04]',
                  )}
                  style={
                    active
                      ? { color: group.color, borderBottomColor: group.color }
                      : undefined
                  }
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}

      {profileType && (
        <div className="flex flex-col gap-1 shrink-0 ml-2">
          <span className="text-[9px] font-semibold tracking-[0.15em] text-[#8b949e] uppercase px-1 opacity-0 select-none">
            &nbsp;
          </span>
          <span className="ml-1 inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 whitespace-nowrap">
            <Compass className="h-3 w-3 shrink-0" />
            {PROFILE_BADGE_LABEL[profileType] ?? 'Entdecker'}
          </span>
        </div>
      )}
    </nav>
  );
}
