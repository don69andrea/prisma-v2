import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { UniverseList } from '../universe-list';
import type { UniverseRead } from '@/lib/api/universes';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/components/universes/StartRankingDialog', () => ({
  StartRankingDialog: ({ universe }: { universe: { name: string } | null }) =>
    universe ? <div data-testid="dialog">{universe.name}</div> : null,
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

  it('renders a "Ranking starten" button for each universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    const buttons = screen.getAllByRole('button', { name: /Ranking starten/i });
    expect(buttons).toHaveLength(2);
  });

  it('klick auf Button öffnet Dialog mit richtigem Universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.queryByTestId('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Ranking starten/i })[0]);
    expect(screen.getByTestId('dialog')).toHaveTextContent('SMI');
  });
});
