import { describe, it, expect } from 'vitest';
import { is3aEligible, sortStocks } from '../stocks-list-client';
import type { StockRead } from '@/lib/api/stocks';

function makeStock(overrides: Partial<StockRead> = {}): StockRead {
  return {
    id: 'a-uuid',
    ticker: 'TEST',
    name: 'Test AG',
    isin: null,
    country: 'CH',
    currency: 'CHF',
    exchange: 'XSWX',
    sector: 'Financials',
    market_cap_chf: '500000000',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// is3aEligible
// ---------------------------------------------------------------------------

describe('is3aEligible', () => {
  it('returns true for XSWX stock with market cap >= 100M CHF', () => {
    expect(is3aEligible(makeStock({ market_cap_chf: '100000000' }))).toBe(true);
    expect(is3aEligible(makeStock({ market_cap_chf: '5000000000' }))).toBe(true);
  });

  it('returns false for XSWX stock below 100M CHF threshold', () => {
    expect(is3aEligible(makeStock({ market_cap_chf: '99999999' }))).toBe(false);
  });

  it('returns false for non-XSWX exchange', () => {
    expect(is3aEligible(makeStock({ exchange: 'XNYS', market_cap_chf: '5000000000' }))).toBe(false);
  });

  it('returns false when market_cap_chf is null', () => {
    expect(is3aEligible(makeStock({ market_cap_chf: null }))).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// sortStocks
// ---------------------------------------------------------------------------

describe('sortStocks', () => {
  const stocks: StockRead[] = [
    makeStock({ ticker: 'NOVN', name: 'Novartis', sector: 'Healthcare',   market_cap_chf: '200000000' }),
    makeStock({ ticker: 'NESN', name: 'Nestle',   sector: 'Consumer',     market_cap_chf: '300000000' }),
    makeStock({ ticker: 'ABBN', name: 'ABB',      sector: 'Industrials',  market_cap_chf: '100000000' }),
  ];

  it('returns original order when sortKey is null', () => {
    const result = sortStocks(stocks, null, 'asc');
    expect(result.map((s) => s.ticker)).toEqual(['NOVN', 'NESN', 'ABBN']);
  });

  it('sorts by ticker ascending', () => {
    const result = sortStocks(stocks, 'ticker', 'asc');
    expect(result.map((s) => s.ticker)).toEqual(['ABBN', 'NESN', 'NOVN']);
  });

  it('sorts by ticker descending', () => {
    const result = sortStocks(stocks, 'ticker', 'desc');
    expect(result.map((s) => s.ticker)).toEqual(['NOVN', 'NESN', 'ABBN']);
  });

  it('sorts by market_cap ascending', () => {
    const result = sortStocks(stocks, 'market_cap', 'asc');
    expect(result.map((s) => s.ticker)).toEqual(['ABBN', 'NOVN', 'NESN']);
  });

  it('sorts by market_cap descending', () => {
    const result = sortStocks(stocks, 'market_cap', 'desc');
    expect(result.map((s) => s.ticker)).toEqual(['NESN', 'NOVN', 'ABBN']);
  });

  it('sorts by sector ascending', () => {
    const result = sortStocks(stocks, 'sector', 'asc');
    expect(result.map((s) => s.sector)).toEqual(['Consumer', 'Healthcare', 'Industrials']);
  });

  it('does not mutate the original array', () => {
    const original = [...stocks];
    sortStocks(stocks, 'ticker', 'asc');
    expect(stocks).toEqual(original);
  });
});
