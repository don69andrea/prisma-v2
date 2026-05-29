import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CompareBanner } from '../compare-banner';
import type { RunResponse } from '@/lib/api/runs';

function makeRun(id: string, name: string, universeId?: string): RunResponse {
  return {
    id,
    status: 'completed',
    universe_id: universeId ?? `u-${id}`,
    universe_name: name,
    created_at: '2026-05-29T12:00:00Z',
  };
}

describe('<CompareBanner />', () => {
  it('shows both run headers', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5', 'u-shared')}
        runB={makeRun('b', 'Demo-US-5', 'u-shared')}
        stats={{ commonCount: 5, onlyACount: 0, onlyBCount: 0 }}
      />,
    );

    expect(screen.getByText(/Run A/i)).toBeInTheDocument();
    expect(screen.getByText(/Run B/i)).toBeInTheDocument();
    expect(screen.getAllByText('Demo-US-5')).toHaveLength(2);
  });

  it('shows only commonCount for same-universe comparison', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5', 'u-shared')}
        runB={makeRun('b', 'Demo-US-5', 'u-shared')}
        stats={{ commonCount: 5, onlyACount: 0, onlyBCount: 0 }}
      />,
    );

    expect(screen.getByText(/5 gemeinsame Stocks/i)).toBeInTheDocument();
    expect(screen.queryByText(/nur in Run A/i)).not.toBeInTheDocument();
  });

  it('shows all three counts for cross-universe comparison', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5')}
        runB={makeRun('b', 'Tech-Big-12')}
        stats={{ commonCount: 3, onlyACount: 2, onlyBCount: 9 }}
      />,
    );

    expect(screen.getByText(/3 gemeinsam/i)).toBeInTheDocument();
    expect(screen.getByText(/2 nur in Run A/i)).toBeInTheDocument();
    expect(screen.getByText(/9 nur in Run B/i)).toBeInTheDocument();
  });

  it('shows warning when commonCount is 0', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'X')}
        runB={makeRun('b', 'Y')}
        stats={{ commonCount: 0, onlyACount: 5, onlyBCount: 7 }}
      />,
    );

    expect(screen.getByText(/keine gemeinsamen Stocks/i)).toBeInTheDocument();
  });
});
