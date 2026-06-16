import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { StockRead } from '@/lib/api/stocks';

// next/navigation mock — useRouter is not used in StocksListClient but
// Next.js Link needs a router context in jsdom.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/stocks',
  useSearchParams: () => new URLSearchParams(),
}));

import { StocksListClient } from '@/components/stocks-list-client';

// ---- Fixtures ---------------------------------------------------------------

const makeStock = (
  ticker: string,
  name: string,
  sector: string | null,
  country: string | null,
): StockRead => ({
  id: `id-${ticker}`,
  ticker,
  name,
  isin: null,
  sector,
  country,
  currency: 'USD',
  exchange: null,
  market_cap_chf: null,
});

const sampleStocks: StockRead[] = [
  makeStock('AAPL', 'Apple Inc.', 'Technology', 'US'),
  makeStock('NESN', 'Nestlé S.A.', 'Consumer Staples', 'CH'),
  makeStock('NOVN', 'Novartis AG', 'Health Care', 'CH'),
  makeStock('MSFT', 'Microsoft Corp.', 'Technology', 'US'),
];

// ---- Tests ------------------------------------------------------------------

describe('StocksListClient', () => {
  it('rendert eine Zeile pro Aktie', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('NESN')).toBeInTheDocument();
    expect(screen.getByText('NOVN')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('zeigt 3a-Badge nur für CH-Aktien', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const badges = screen.getAllByTestId('badge-3a');
    expect(badges).toHaveLength(2); // NESN + NOVN
  });

  it('Live-Suche filtert nach Ticker (case-insensitive)', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const input = screen.getByRole('textbox', { name: /Suche/i });

    fireEvent.change(input, { target: { value: 'aapl' } });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.queryByText('NESN')).not.toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
  });

  it('Live-Suche filtert nach Name', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const input = screen.getByRole('textbox', { name: /Suche/i });

    fireEvent.change(input, { target: { value: 'nestlé' } });

    expect(screen.getByText('NESN')).toBeInTheDocument();
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
  });

  it('leerer Suchbegriff zeigt alle Aktien', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const input = screen.getByRole('textbox', { name: /Suche/i });

    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.change(input, { target: { value: '' } });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('NESN')).toBeInTheDocument();
    expect(screen.getByText('NOVN')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('"Nur 3a-geeignet"-Checkbox zeigt nur CH-Aktien', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const checkbox = screen.getByRole('checkbox', { name: /3a/i });

    fireEvent.click(checkbox);

    expect(screen.getByText('NESN')).toBeInTheDocument();
    expect(screen.getByText('NOVN')).toBeInTheDocument();
    expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
  });

  it('Sortierung Ticker: erster Klick A→Z, zweiter Klick Z→A, dritter zurück zu Default', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const tickerHeader = screen.getByRole('columnheader', { name: /Ticker/i });

    // Default: keine Sortierung — Reihenfolge wie API zurückgibt (AAPL, NESN, NOVN, MSFT)
    const rowsBefore = screen.getAllByRole('row').slice(1).map((r: HTMLElement) => r.textContent);
    expect(rowsBefore[0]).toContain('AAPL');

    // Erster Klick: A→Z
    fireEvent.click(tickerHeader);
    const rowsAsc = screen.getAllByRole('row').slice(1).map((r: HTMLElement) => r.textContent);
    expect(rowsAsc[0]).toContain('AAPL');
    expect(rowsAsc[rowsAsc.length - 1]).toContain('NOVN');

    // Zweiter Klick: Z→A
    fireEvent.click(tickerHeader);
    const rowsDesc = screen.getAllByRole('row').slice(1).map((r: HTMLElement) => r.textContent);
    expect(rowsDesc[0]).toContain('NOVN');
    expect(rowsDesc[rowsDesc.length - 1]).toContain('AAPL');

    // Dritter Klick: zurück zu Default
    fireEvent.click(tickerHeader);
    const rowsDefault = screen.getAllByRole('row').slice(1).map((r: HTMLElement) => r.textContent);
    expect(rowsDefault[0]).toContain('AAPL');
  });

  it('Sortierung Sektor: A→Z sortiert alphabetisch', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const sectorHeader = screen.getByRole('columnheader', { name: /Sektor/i });

    fireEvent.click(sectorHeader);
    const rows = screen.getAllByRole('row').slice(1).map((r: HTMLElement) => r.textContent ?? '');
    // Consumer Staples < Health Care < Technology
    expect(rows[0]).toContain('Consumer Staples');
    expect(rows[1]).toContain('Health Care');
  });

  it('aria-sort-Attribut zeigt aktive Sortierrichtung', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const tickerHeader = screen.getByRole('columnheader', { name: /Ticker/i });

    expect(tickerHeader).toHaveAttribute('aria-sort', 'none');

    fireEvent.click(tickerHeader);
    expect(tickerHeader).toHaveAttribute('aria-sort', 'ascending');

    fireEvent.click(tickerHeader);
    expect(tickerHeader).toHaveAttribute('aria-sort', 'descending');
  });

  it('Empty-State wenn keine Aktien dem Filter entsprechen', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const input = screen.getByRole('textbox', { name: /Suche/i });

    fireEvent.change(input, { target: { value: 'XXXXXNOTFOUND' } });

    expect(screen.getByText(/Keine Aktien/i)).toBeInTheDocument();
  });

  it('Zeilen-Klick navigiert zu /stocks/[ticker]', () => {
    render(<StocksListClient stocks={sampleStocks} />);
    const links = screen.getAllByRole('link');
    const appleLink = links.find((l: HTMLElement) => l.textContent === 'AAPL');
    expect(appleLink).toBeDefined();
    expect(appleLink!.getAttribute('href')).toBe('/stocks/AAPL');
  });
});
