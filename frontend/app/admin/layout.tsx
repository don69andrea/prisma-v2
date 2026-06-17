'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

const NAV_LINKS = [
  { href: '/admin', label: 'Übersicht' },
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
      <nav className="flex flex-wrap gap-4 border-b border-border pb-4">
        {NAV_LINKS.map(({ href, label }) => (
          <Link key={href} href={href} className="text-sm font-medium hover:text-primary transition-colors">
            {label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
