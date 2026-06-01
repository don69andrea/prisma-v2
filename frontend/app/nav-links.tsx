'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/routes';

const navLinks = [
  { href: ROUTES.dashboard, label: 'Dashboard' },
  { href: ROUTES.universes, label: 'Universen' },
  { href: ROUTES.rankings,  label: 'Rankings' },
  { href: ROUTES.backtest,  label: 'Backtest' },
] as const;

export function NavLinks() {
  const pathname = usePathname();

  return (
    <nav className="flex items-center gap-4 text-sm sm:gap-6">
      {navLinks.map((link) => {
        const isActive =
          link.href === ROUTES.dashboard
            ? pathname === ROUTES.dashboard
            : pathname.startsWith(link.href);

        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'transition-colors hover:text-foreground',
              isActive ? 'text-foreground font-medium' : 'text-muted-foreground',
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
