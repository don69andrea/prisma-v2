import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { LoadingState, LoadingStateMulti } from '../LoadingState';

describe('LoadingState', () => {
  it('zeigt Stock-Meldung mit Ticker', () => {
    render(<LoadingState type="stock" ticker="NESN.SW" />);
    expect(screen.getByText('PRISMA analysiert NESN.SW…')).toBeInTheDocument();
  });

  it('zeigt Default-Meldung', () => {
    render(<LoadingState />);
    expect(screen.getByText('PRISMA lädt…')).toBeInTheDocument();
  });

  it('kein "Loading..." Text vorhanden', () => {
    render(<LoadingState type="signal" />);
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });

  it('zeigt Erklär-Meldung', () => {
    render(<LoadingState type="explain" />);
    expect(screen.getByText('PRISMA erklärt…')).toBeInTheDocument();
  });
});

describe('LoadingStateMulti', () => {
  it('zeigt mehrere Meldungen für stock', () => {
    render(<LoadingStateMulti type="stock" ticker="ROG.SW" />);
    expect(screen.getByText('PRISMA analysiert ROG.SW…')).toBeInTheDocument();
    expect(screen.getByText('Quant-Scores werden berechnet…')).toBeInTheDocument();
    expect(screen.getByText('ML-Modell läuft…')).toBeInTheDocument();
  });
});
