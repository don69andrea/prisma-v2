import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TopTenLeaderboard } from '../TopTenLeaderboard';
import type { RankingItem } from '@/lib/api/runs';

// Recharts ResponsiveContainer mock (mirroring TopTenBars test)
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) => (
      <div style={{ width: 600, height: 300 }}>
        {React.cloneElement(children, { width: 600, height: 300 })}
      </div>
    ),
  };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function makeItem(ticker: string, rank: number): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: rank,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('TopTenLeaderboard', () => {
  it('rendert null bei leerer items-Liste', () => {
    const { container } = render(<TopTenLeaderboard items={[]} runId="run-1" />);
    expect(container.firstChild).toBeNull();
  });

  it('Section-Header zeigt "Top 10" bei ≥10 Items', () => {
    const items = Array.from({ length: 12 }, (_, i) => makeItem(`T${i}`, i + 1));
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    expect(screen.getByRole('heading', { name: /Top 10/ })).toBeInTheDocument();
  });

  it('Section-Header zeigt "Top 5" bei 5 Items', () => {
    const items = Array.from({ length: 5 }, (_, i) => makeItem(`T${i}`, i + 1));
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    expect(screen.getByRole('heading', { name: /Top 5/ })).toBeInTheDocument();
  });

  it('rendert maximal 10 Karten auch bei mehr Items', () => {
    const items = Array.from({ length: 15 }, (_, i) => makeItem(`T${i}`, i + 1));
    const { container } = render(<TopTenLeaderboard items={items} runId="run-1" />);
    // Karten sind <a href> Links (TopTenBars Ticks haben role="link" aber kein href) → genau 10
    expect(container.querySelectorAll('a[href]')).toHaveLength(10);
  });

  it('sortiert nach total_rank (FIRST mit rank=1 ist erste Karte)', () => {
    const items = [makeItem('LAST', 99), makeItem('FIRST', 1), makeItem('MID', 50)];
    const { container } = render(<TopTenLeaderboard items={items} runId="run-1" />);
    const cards = container.querySelectorAll<HTMLAnchorElement>('a[href]');
    expect(cards[0]).toHaveTextContent('FIRST');
    expect(cards[1]).toHaveTextContent('MID');
    expect(cards[2]).toHaveTextContent('LAST');
  });
});
