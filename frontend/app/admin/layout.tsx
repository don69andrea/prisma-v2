'use client';

import { useAuth } from '@/hooks/useAuth';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Link from 'next/link';

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
      <nav className="flex gap-4 border-b border-border pb-4">
        <Link href="/admin" className="text-sm font-medium hover:text-primary">
          Übersicht
        </Link>
        <Link href="/admin/users" className="text-sm font-medium hover:text-primary">
          User-Verwaltung
        </Link>
      </nav>
      {children}
    </div>
  );
}
