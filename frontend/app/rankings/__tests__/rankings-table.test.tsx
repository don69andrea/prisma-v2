import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { RankingsTable } from '../[runId]/rankings-table';
import type { RankingItem } from '@/lib/api/runs';

const sampleItems: RankingItem[] = [
  {
    ticker: 'AAPL',
    total_rank: 1,
    weighted_avg: 2.1,
    is_sweet_spot: true,
    per_model_ranks: {
      quality_classic: 1,
      diversification: 3,
      trend_momentum: 2,
      value_alpha_potential: 2,
      alpha: 1,
    },
  },
  {
    ticker: 'MSFT',
    total_rank: 2,
    weighted_avg: 2.4,
    is_sweet_spot: false,
    per_model_ranks: {
      quality_classic: 2,
      diversification: null,
      trend_momentum: 4,
      value_alpha_potential: 1,
      alpha: 3,
    },
  },
];

describe('RankingsTable', () => {
  it('rendert eine Zeile pro Item', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Badge nur wenn is_sweet_spot=true', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const badges = screen.queryAllByText('★');
    expect(badges).toHaveLength(1);
  });

  it('zeigt em-dash für null-Werte', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const dashes = screen.queryAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('rendert Modell-Spalten in fixer Reihenfolge', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const headers = screen
      .getAllByRole('columnheader')
      .map((h) => h.textContent?.replace(/\s/g, '') ?? '');
    // SVG icons add no text, so textContent still matches label text
    expect(headers).toEqual([
      '#',
      'Ticker',
      'Avg',
      'Sweet-Spot',
      'Quality',
      'Diversification',
      'Trend',
      'Value',
      'Alpha',
    ]);
  });

  it('zeigt Empty-State wenn items leer', () => {
    render(<RankingsTable items={[]} runId="test-run-id" />);
    expect(screen.getByText(/Keine Ergebnisse/)).toBeInTheDocument();
  });

  // --- Sortierung ---

  it('klick auf #-Header wechselt aria-sort: none → ascending → descending', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const rankHeader = screen.getByRole('columnheader', { name: /#/ });

    // Default: sorted by total_rank ascending (active)
    expect(rankHeader).toHaveAttribute('aria-sort', 'ascending');

    // Second click → descending
    fireEvent.click(rankHeader);
    expect(rankHeader).toHaveAttribute('aria-sort', 'descending');

    // Third click → ascending again
    fireEvent.click(rankHeader);
    expect(rankHeader).toHaveAttribute('aria-sort', 'ascending');
  });

  it('klick auf Avg-Header sortiert nach weighted_avg', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const avgHeader = screen.getByRole('columnheader', { name: /Avg/ });

    // Initially inactive (sorted by total_rank)
    expect(avgHeader).toHaveAttribute('aria-sort', 'none');

    fireEvent.click(avgHeader);
    expect(avgHeader).toHaveAttribute('aria-sort', 'ascending');
  });

  // --- Filter ---

  it('filter nach AAPL verbirgt MSFT-Zeile', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const input = screen.getByRole('textbox', { name: /Ticker suchen/i });

    fireEvent.change(input, { target: { value: 'AAPL' } });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
  });

  it('leerer Filter zeigt alle Zeilen', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const input = screen.getByRole('textbox', { name: /Ticker suchen/i });

    fireEvent.change(input, { target: { value: 'AAPL' } });
    fireEvent.change(input, { target: { value: '' } });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  // --- CSV-Export ---

  it('CSV-Export-Button setzt download-Attribut auf rankings.csv', () => {
    const mockUrl = 'blob:mock-url';
    const mockRevoke = vi.fn();

    // jsdom does not implement URL.createObjectURL — assign directly
    global.URL.createObjectURL = vi.fn().mockReturnValue(mockUrl);
    global.URL.revokeObjectURL = mockRevoke;

    // Use a real anchor so appendChild/removeChild work in jsdom
    const mockAnchor = document.createElement('a');
    const mockClick = vi.spyOn(mockAnchor, 'click').mockImplementation(() => {});
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') return mockAnchor;
      return originalCreateElement(tag as keyof HTMLElementTagNameMap);
    });

    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    fireEvent.click(screen.getByRole('button', { name: /CSV exportieren/i }));

    expect(mockAnchor.download).toBe('rankings.csv');
    expect(mockClick).toHaveBeenCalledOnce();
    expect(mockRevoke).toHaveBeenCalledWith(mockUrl);

    vi.restoreAllMocks();
    Reflect.deleteProperty(global.URL, 'createObjectURL');
    Reflect.deleteProperty(global.URL, 'revokeObjectURL');
  });
});
