import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { TopTenBars } from '../TopTenBars';
import type { RankingItem } from '@/lib/api/runs';

// next/navigation mock — Recharts-Klick navigiert via router.push
const pushMock = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Recharts braucht Dimensionen in jsdom — ResponsiveContainer cloned mit Fixed-Size
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

function makeItem(ticker: string, rank: number, avg: number, sweetSpot = false): RankingItem {
  return {
    stock_id: null,
    ticker,
    total_rank: rank,
    weighted_avg: avg,
    is_sweet_spot: sweetSpot,
    per_model_ranks: {},
  };
}

const items: RankingItem[] = [
  makeItem('AAPL', 1, 1.8, true),
  makeItem('MSFT', 2, 2.2, true),
  makeItem('NVDA', 3, 2.5, false),
];

// Recharts rendert pro Ticker einen hidden measurement-Span — wir querien nur die SVG-<text>-Ticks
function getTickByText(container: HTMLElement, ticker: string): SVGTextElement {
  const texts = container.querySelectorAll<SVGTextElement>('text');
  const match = Array.from(texts).find((t) => t.textContent === ticker);
  if (!match) throw new Error(`No <text> tick found for ${ticker}`);
  return match;
}

describe('TopTenBars', () => {
  beforeEach(() => {
    pushMock.mockClear();
  });

  it('rendert für jedes Item einen Tick mit Ticker', () => {
    const { container } = render(<TopTenBars items={items} runId="run-1" />);
    expect(getTickByText(container, 'AAPL')).toBeInTheDocument();
    expect(getTickByText(container, 'MSFT')).toBeInTheDocument();
    expect(getTickByText(container, 'NVDA')).toBeInTheDocument();
  });

  it('Sweet-Spot-Bars haben Amber-Fill, andere Primary-Fill', () => {
    const { container } = render(<TopTenBars items={items} runId="run-1" />);
    // Recharts rendert in jsdom <Bar> als <g class="recharts-bar-rectangle"> mit innerem <path>;
    // <Cell> Fill landet auf dem path-Element.
    const paths = container.querySelectorAll('.recharts-bar-rectangle path');
    const rects = container.querySelectorAll('.recharts-bar-rectangle rect');
    const elements = paths.length > 0 ? paths : rects;
    const fills = Array.from(elements).map((c) => c.getAttribute('fill'));
    // 3 Bars — AAPL und MSFT sind sweet-spot (Amber), NVDA nicht
    const amberCount = fills.filter((f) => f === '#f59e0b').length;
    expect(amberCount).toBe(2);
  });

  it('Klick auf Y-Tick-Label navigiert zur Factsheet', () => {
    const { container } = render(<TopTenBars items={items} runId="run-1" />);
    const aaplLabel = getTickByText(container, 'AAPL');
    fireEvent.click(aaplLabel);
    expect(pushMock).toHaveBeenCalledWith('/rankings/run-1/stock/AAPL');
  });

  it('Enter-Taste auf Y-Tick navigiert', () => {
    const { container } = render(<TopTenBars items={items} runId="run-1" />);
    const aaplLabel = getTickByText(container, 'AAPL');
    fireEvent.keyDown(aaplLabel, { key: 'Enter' });
    expect(pushMock).toHaveBeenCalledWith('/rankings/run-1/stock/AAPL');
  });
});
