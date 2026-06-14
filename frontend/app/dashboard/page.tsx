import type { Metadata } from 'next';

import { DashboardClient } from './dashboard-client';

export const metadata: Metadata = {
  title: 'Dashboard',
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard.</h1>
      <DashboardClient />
    </div>
  );
}
