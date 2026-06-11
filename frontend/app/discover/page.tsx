import type { Metadata } from 'next';

import { DiscoverClient } from './discover-client';

export const metadata: Metadata = {
  title: 'Mein Universe',
};

export default function DiscoverPage() {
  return <DiscoverClient />;
}
