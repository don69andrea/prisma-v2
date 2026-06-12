import type { Metadata } from 'next';

import { DashboardClient } from './dashboard/dashboard-client';

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'PRISMA — Quantitative Stock Intelligence Platform',
};

export default function HomePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
      <DashboardClient />
    </div>
  );
}
