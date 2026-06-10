import type { Metadata } from 'next';
import { SimulatorClient } from './SimulatorClient';

export const metadata: Metadata = {
  title: 'PRISMA — 3a Retirement Simulator',
};

export default function SimulatorPage() {
  return <SimulatorClient />;
}
