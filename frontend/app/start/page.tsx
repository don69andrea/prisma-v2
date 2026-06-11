import type { Metadata } from 'next';

import { StartClient } from './start-client';

export const metadata: Metadata = {
  title: 'Starten',
};

export default function StartPage() {
  return <StartClient />;
}
