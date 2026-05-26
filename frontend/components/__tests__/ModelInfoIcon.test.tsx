import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ModelInfoIcon } from '../ModelInfoIcon';

describe('ModelInfoIcon', () => {
  it('aria-label nutzt MODEL_INFO.label', () => {
    render(<ModelInfoIcon modelKey="quality_classic" />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeInTheDocument();
  });

  it('Klick zeigt Modell-Beschreibung aus MODEL_INFO', () => {
    render(<ModelInfoIcon modelKey="quality_classic" />);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(screen.getByText(/8 klassische Kennzahlen/)).toBeInTheDocument();
  });

  it('funktioniert für alle 5 Modell-Keys', () => {
    const cases: Array<[Parameters<typeof ModelInfoIcon>[0]['modelKey'], string]> = [
      ['quality_classic', 'Quality'],
      ['alpha', 'Alpha'],
      ['trend_momentum', 'Trend'],
      ['value_alpha_potential', 'Value'],
      ['diversification', 'Diversification'],
    ];
    for (const [key, label] of cases) {
      const { unmount } = render(<ModelInfoIcon modelKey={key} />);
      expect(screen.getByRole('button', { name: `Info zu ${label}` })).toBeInTheDocument();
      unmount();
    }
  });
});
