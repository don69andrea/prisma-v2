import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { SignalBadge } from '../SignalBadge';

describe('SignalBadge', () => {
  it('zeigt BUY mit Konfidenz', () => {
    render(<SignalBadge signal="BUY" confidence={0.74} />);
    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('74%')).toBeInTheDocument();
  });

  it('zeigt WATCH als BEOBACHTEN ohne Konfidenz', () => {
    render(<SignalBadge signal="WATCH" />);
    expect(screen.getByText('BEOBACHTEN')).toBeInTheDocument();
  });

  it('zeigt HOLD korrekt', () => {
    render(<SignalBadge signal="HOLD" />);
    expect(screen.getByText('HOLD')).toBeInTheDocument();
  });

  it('zeigt SELL korrekt', () => {
    render(<SignalBadge signal="SELL" />);
    expect(screen.getByText('SELL')).toBeInTheDocument();
  });

  it('kein Konfidenz-Text wenn nicht übergeben', () => {
    render(<SignalBadge signal="BUY" />);
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});
