import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StatsCards } from '../StatsCards';
import type { RunResponse } from '@/lib/api/runs';

const completedRun: RunResponse = {
  id: 'run-1111-2222-3333',
  status: 'completed',
  universe_id: 'uni-1',
  created_at: '2026-05-28T10:00:00Z',
};

const basicProps = {
  latestRun: completedRun,
  universeCount: 3,
  stockCount: 42,
  topPick: { ticker: 'NVDA', isSweetSpot: true, runId: 'run-1111-2222-3333' },
};

describe('StatsCards', () => {
  it('renders all four cards', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText(/Letzter Run/i)).toBeDefined();
    expect(screen.getByText(/Universen/i)).toBeDefined();
    expect(screen.getByText(/Stocks/i)).toBeDefined();
    expect(screen.getByText(/Top-Pick/i)).toBeDefined();
  });

  it('renders counts correctly', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
  });

  it('renders top-pick ticker', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText('NVDA')).toBeDefined();
  });

  it('shows sweet-spot indicator when isSweetSpot=true', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByLabelText(/Sweet-Spot/i)).toBeDefined();
  });

  it('hides sweet-spot indicator when isSweetSpot=false', () => {
    render(
      <StatsCards
        {...basicProps}
        topPick={{ ticker: 'JPM', isSweetSpot: false, runId: 'run-1111-2222-3333' }}
      />,
    );
    expect(screen.queryByLabelText(/Sweet-Spot/i)).toBeNull();
  });

  it('shows em-dash for top-pick when null', () => {
    render(<StatsCards {...basicProps} topPick={null} />);
    expect(screen.queryByText('NVDA')).toBeNull();
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('shows em-dash for latest run when null', () => {
    render(<StatsCards {...basicProps} latestRun={null} />);
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('top-pick links to factsheet page', () => {
    render(<StatsCards {...basicProps} />);
    const link = screen.getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toBe('/rankings/run-1111-2222-3333/stock/NVDA');
  });

  it('latest-run shows status badge', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText(/Abgeschlossen|completed/i)).toBeDefined();
  });
});
