import type { Metadata } from 'next';

import { DashboardClient } from './dashboard/dashboard-client';

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'PRISMA — Quantitative Stock Intelligence Platform',
};

export default function HomePage() {
  return <DashboardClient />;
}
