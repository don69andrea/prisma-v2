'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/routes';

const NAV_GROUPS = [
  {
    label: 'ENTDECKEN',
    links: [
      { href: ROUTES.start,     label: 'Einstieg' },
      { href: ROUTES.universes, label: 'Universen' },
      { href: ROUTES.rankings,  label: 'Rankings' },
    ],
  },
  {
    label: 'VERSTEHEN',
    links: [
      { href: ROUTES.stocks,    label: 'Aktien' },
      { href: ROUTES.news,      label: 'News' },
      { href: ROUTES.research,  label: 'Research' },
    ],
  },
  {
    label: 'VERGLEICHEN',
    links: [
      { href: ROUTES.backtest,  label: 'Backtest' },
      { href: ROUTES.fonds,     label: 'Fonds' },
    ],
  },
  {
    label: 'ENTSCHEIDEN',
    links: [
      { href: ROUTES.decision,  label: 'Signale' },
      { href: ROUTES.alerts,    label: 'Alerts' },
    ],
  },
  {
    label: 'PORTFOLIO',
    links: [
      { href: ROUTES.portfolio, label: 'Portfolio' },
      { href: ROUTES.simulator, label: '3a Sim' },
      { href: ROUTES.steuer,    label: 'Steuer' },
    ],
  },
] as const;

function isActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href);
}

export function NavLinks() {
  const pathname = usePathname();

  return (
    <nav
      className="flex items-start gap-6 overflow-x-auto scrollbar-none pb-0.5"
      aria-label="Hauptnavigation"
    >
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="flex flex-col gap-1 shrink-0">
          <span className="text-[9px] font-semibold tracking-[0.12em] text-[#8b949e] uppercase px-1">
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
                    'text-sm shrink-0 transition-colors hover:text-foreground px-1',
                    active
                      ? 'text-foreground font-medium border-b border-[#58a6ff]'
                      : 'text-muted-foreground',
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
