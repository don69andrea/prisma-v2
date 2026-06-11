import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AuditTrail } from '../AuditTrail';

// freeze timers so useEffect animation fires synchronously
beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

const DEFAULT_PROPS = {
  quantScore: 80,
  mlScore: 70,
  macroScore: 60,
  signal: 'BUY' as const,
};

describe('AuditTrail', () => {
  it('rendert alle drei Dimensionen', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    expect(screen.getByText('Quant-Score')).toBeInTheDocument();
    expect(screen.getByText('ML-Prediction')).toBeInTheDocument();
    expect(screen.getByText('Makro-Kontext')).toBeInTheDocument();
  });

  it('zeigt data-testid="audit-trail"', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    expect(screen.getByTestId('audit-trail')).toBeInTheDocument();
  });

  it('zeigt das Signal im Gesamt-Score', () => {
    render(<AuditTrail {...DEFAULT_PROPS} signal="BUY" />);
    expect(screen.getByText(/BUY/)).toBeInTheDocument();
    expect(screen.getByText(/≥ 65/)).toBeInTheDocument();
  });

  it('zeigt HOLD-Schwelle 40–64', () => {
    render(<AuditTrail {...DEFAULT_PROPS} signal="HOLD" />);
    expect(screen.getByText(/40–64/)).toBeInTheDocument();
  });

  it('zeigt WATCH-Schwelle < 40', () => {
    render(<AuditTrail {...DEFAULT_PROPS} signal="WATCH" />);
    expect(screen.getByText(/< 40/)).toBeInTheDocument();
  });

  it('berechnet Gesamt-Score korrekt: 80×0.45 + 70×0.35 + 60×0.20 = 72.5', () => {
    render(<AuditTrail quantScore={80} mlScore={70} macroScore={60} signal="BUY" />);
    expect(screen.getByText(/72\.5/)).toBeInTheDocument();
  });

  it('zeigt snapshotDate wenn übergeben', () => {
    render(<AuditTrail {...DEFAULT_PROPS} snapshotDate="2026-06-11T00:00:00" />);
    const meta = screen.getByTestId('audit-metadata');
    // date span should exist and contain "06" (Juni) in some locale format
    expect(meta.querySelectorAll('span')).toHaveLength(2);
    expect(meta.textContent).toMatch(/06/);
  });

  it('zeigt kein Datum-Span wenn snapshotDate fehlt', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    const meta = screen.getByTestId('audit-metadata');
    expect(meta.querySelectorAll('span')).toHaveLength(1);
  });

  it('alle Progressbars haben aria-valuenow gesetzt', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    const bars = screen.getAllByRole('progressbar');
    expect(bars).toHaveLength(3);
    expect(bars[0]).toHaveAttribute('aria-valuenow', '80');
    expect(bars[1]).toHaveAttribute('aria-valuenow', '70');
    expect(bars[2]).toHaveAttribute('aria-valuenow', '60');
  });

  it('akzeptiert optionale className', () => {
    const { container } = render(
      <AuditTrail {...DEFAULT_PROPS} className="custom-class" />,
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('zeigt Modell-Info in Metadata', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    expect(screen.getByText(/Modell v1/)).toBeInTheDocument();
    expect(screen.getByText(/0\.45.*0\.35.*0\.20/)).toBeInTheDocument();
  });

  it('zeigt Beitrags-Werte (×0.45, ×0.35, ×0.20)', () => {
    render(<AuditTrail {...DEFAULT_PROPS} />);
    expect(screen.getByText('×0.45')).toBeInTheDocument();
    expect(screen.getByText('×0.35')).toBeInTheDocument();
    expect(screen.getByText('×0.20')).toBeInTheDocument();
  });
});
