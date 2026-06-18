'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter, usePathname } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

const NAV_LINKS = [
  { href: '/admin', label: 'Übersicht', exact: true },
  { href: '/admin/stocks', label: 'Stocks & Universen' },
  { href: '/admin/runs', label: 'Ranking-Runs' },
  { href: '/admin/memos', label: 'Memos' },
  { href: '/admin/alerts', label: 'Alerts' },
  { href: '/admin/audit', label: 'Audit' },
  { href: '/admin/backtests', label: 'Backtests' },
  { href: '/admin/users', label: 'User-Verwaltung' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && (!user || user.role !== 'admin')) {
      router.replace('/');
    }
  }, [user, loading, router]);

  if (loading || !user || user.role !== 'admin') {
    return null;
  }

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <nav className="flex flex-wrap gap-1">
          {NAV_LINKS.map(({ href, label, exact }) => {
            const isActive = exact ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`text-sm px-3 py-1.5 rounded-md font-medium transition-colors ${
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <span className="text-xs text-muted-foreground hidden md:block">
          {user.email}
        </span>
      </div>
      {children}
    </div>
  );
}
