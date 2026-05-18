import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ModelRankCards } from '../ModelRankCards';

const perModelRanks: Record<string, number | null> = {
  quality_classic: 1,
  alpha: 18,
  trend_momentum: 5,
  value_alpha_potential: null,
  diversification: 10,
};

describe('ModelRankCards', () => {
  it('renders all 5 model cards', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('Quality Classic')).toBeDefined();
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Trend Momentum')).toBeDefined();
    expect(screen.getByText('Value Alpha Potential')).toBeDefined();
    expect(screen.getByText('Diversification')).toBeDefined();
  });

  it('shows rank number when available', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('1')).toBeDefined();
    expect(screen.getByText('18')).toBeDefined();
  });

  it('shows dash for null rank', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('—')).toBeDefined();
  });
});
