import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';

import { CompareTable } from '../compare-table';
import type { CompareRow } from '@/lib/compare';

function row(overrides: Partial<CompareRow>): CompareRow {
  return {
    ticker: 'AAPL',
    rankA: 1,
    rankB: 1,
    scoreA: 0.9,
    scoreB: 0.9,
    deltaRank: 0,
    deltaScore: 0,
    ...overrides,
  };
}

describe('<CompareTable />', () => {
  it('renders one row per CompareRow', () => {
    const { getByText } = render(
      <CompareTable rows={[row({ ticker: 'AAPL' }), row({ ticker: 'MSFT' })]} />,
    );

    expect(getByText('AAPL')).toBeInTheDocument();
    expect(getByText('MSFT')).toBeInTheDocument();
  });

  it('shows green up indicator when deltaRank > 0 (B better)', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: 3 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('+3');
    expect(deltaCell?.className).toMatch(/text-green/);
  });

  it('shows red down indicator when deltaRank < 0 (A better)', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: -2 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('-2');
    expect(deltaCell?.className).toMatch(/text-red/);
  });

  it('shows muted dot when deltaRank === 0', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: 0 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('0');
    expect(deltaCell?.className).toMatch(/text-muted/);
  });

  it('formats deltaScore with sign and two decimals', () => {
    const { container } = render(<CompareTable rows={[row({ deltaScore: 0.123 })]} />);

    const cell = container.querySelector('[data-testid="delta-score-cell"]');
    expect(cell?.textContent).toContain('+0.12');
  });
});
