import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

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
    expect(screen.getByText('Quality')).toBeDefined();
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Trend')).toBeDefined();
    expect(screen.getByText('Value')).toBeDefined();
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

  it('jede Card hat ein Info-Icon mit aria-label', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Alpha' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Trend' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Value' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Diversification' })).toBeDefined();
  });

  it('Klick auf Quality-Info zeigt 8-Kennzahlen-Tooltip', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(screen.getByText(/8 klassische Kennzahlen/)).toBeDefined();
  });
});
