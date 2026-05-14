import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { UniverseList } from '../universe-list';
import type { UniverseRead } from '@/lib/api/universes';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const sampleUniverses: UniverseRead[] = [
  {
    id: '11111111-0000-0000-0000-000000000001',
    name: 'SMI',
    region: 'CH',
    tickers: ['NESN', 'NOVN', 'ROG'],
  },
  {
    id: '11111111-0000-0000-0000-000000000002',
    name: 'S&P 500',
    region: 'US',
    tickers: ['AAPL', 'MSFT'],
  },
];

describe('UniverseList', () => {
  it('shows universe names in the table', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('SMI')).toBeInTheDocument();
    expect(screen.getByText('S&P 500')).toBeInTheDocument();
  });

  it('shows region for each universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('CH')).toBeInTheDocument();
    expect(screen.getByText('US')).toBeInTheDocument();
  });

  it('shows ticker count correctly', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows empty-state message when list is empty', () => {
    render(<UniverseList universes={[]} />);
    expect(screen.getByText(/Noch keine Universen angelegt/)).toBeInTheDocument();
  });
});
