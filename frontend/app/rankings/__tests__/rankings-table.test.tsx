import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

import { RankingsTable } from '../[runId]/rankings-table';
import type { RankingItem } from '@/lib/api/runs';

function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const sampleItems: RankingItem[] = [
  {
    stock_id: null,
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
    stock_id: null,
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
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Badge nur wenn is_sweet_spot=true', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    // Sweet-Spot wird als klickbares Info-Icon mit aria-label "Sweet-Spot-Begründung für …" dargestellt
    const badges = screen.queryAllByRole('button', { name: /Sweet-Spot-Begründung für/ });
    expect(badges).toHaveLength(1);
    expect(badges[0]).toHaveAccessibleName('Sweet-Spot-Begründung für AAPL');
  });

  it('zeigt em-dash für null-Werte', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const dashes = screen.queryAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('rendert Modell-Spalten in fixer Reihenfolge', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
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
    renderWithQuery(<RankingsTable items={[]} runId="test-run-id" />);
    expect(screen.getByText(/Keine Ergebnisse/)).toBeInTheDocument();
  });

  // --- Sortierung ---

  it('klick auf #-Header wechselt aria-sort: none → ascending → descending', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
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
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const avgHeader = screen.getByRole('columnheader', { name: /Avg/ });

    // Initially inactive (sorted by total_rank)
    expect(avgHeader).toHaveAttribute('aria-sort', 'none');

    fireEvent.click(avgHeader);
    expect(avgHeader).toHaveAttribute('aria-sort', 'ascending');
  });

  // --- Filter ---

  it('filter nach AAPL verbirgt MSFT-Zeile', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const input = screen.getByRole('textbox', { name: /Ticker suchen/i });

    fireEvent.change(input, { target: { value: 'AAPL' } });

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument();
  });

  it('leerer Filter zeigt alle Zeilen', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
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

    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    fireEvent.click(screen.getByRole('button', { name: /CSV exportieren/i }));

    expect(mockAnchor.download).toBe('rankings.csv');
    expect(mockClick).toHaveBeenCalledOnce();
    expect(mockRevoke).toHaveBeenCalledWith(mockUrl);

    vi.restoreAllMocks();
    Reflect.deleteProperty(global.URL, 'createObjectURL');
    Reflect.deleteProperty(global.URL, 'revokeObjectURL');
  });

  it('rendert Info-Icon im Quality-Header', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeInTheDocument();
  });

  it('Klick auf Header-Info-Icon sortiert nicht', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    // Initial: sortiert nach total_rank asc → AAPL=1, MSFT=2
    const rowsBefore = screen.getAllByRole('row').slice(1).map((r) => r.textContent);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    const rowsAfter = screen.getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rowsAfter).toEqual(rowsBefore);
  });

  it('rendert Info-Icon im Sweet-Spot-Header mit generischer Definition', () => {
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const trigger = screen.getByRole('button', { name: 'Sweet-Spot-Definition' });
    fireEvent.click(trigger);
    expect(screen.getByText(/Top-25 ?% in mindestens 3 von 5/)).toBeInTheDocument();
  });

  it('Klick auf Sweet-Spot-Badge zeigt ticker-spezifische Modell-Liste', () => {
    const sweetSpotSample: RankingItem[] = Array.from({ length: 20 }, (_, i) => ({
      stock_id: null,
      ticker: `T${i + 1}`,
      total_rank: i + 1,
      weighted_avg: i + 1,
      is_sweet_spot: i === 0, // nur T1 ist sweet spot
      per_model_ranks: {
        quality_classic: i + 1,
        alpha: i + 1,
        trend_momentum: i + 1,
        value_alpha_potential: i + 1,
        diversification: i + 1,
      },
    }));
    renderWithQuery(<RankingsTable items={sweetSpotSample} runId="test-run-id" />);
    const badge = screen.getByRole('button', { name: 'Sweet-Spot-Begründung für T1' });
    fireEvent.click(badge);
    // Schwelle: ceil(20*0.25)=5 → T1 (rank=1 überall) erfüllt in allen 5
    // Mit <strong>{ticker}</strong> sind T1 und der Rest separate Text-Nodes,
    // daher per textContent über das Eltern-Element matchen.
    const matches = screen.getAllByText((_, el) =>
      el?.textContent?.startsWith('T1 ist Top-25') ?? false,
    );
    expect(matches.length).toBeGreaterThan(0);
    const content = matches[0].textContent ?? '';
    expect(content).toMatch(/T1 ist Top-25 ?% in/);
    expect(content).toMatch(/5\/5/);
  });

  // --- Memo-Sheet-Integration ---

  it('opens memo sheet on row click when stock_id present', () => {
    const itemsWithId: RankingItem[] = [
      {
        ...sampleItems[0],
        stock_id: '11111111-1111-1111-1111-111111111111',
      },
    ];
    renderWithQuery(<RankingsTable items={itemsWithId} runId="test-run-id" />);
    // Click anywhere on the row's last column (avoiding Links + InfoPopover buttons)
    const row = screen.getByText('AAPL').closest('tr');
    expect(row).not.toBeNull();
    fireEvent.click(row!);
    // Sheet now renders ticker again in its header (SheetTitle) — total 2 occurrences
    expect(screen.getAllByText('AAPL').length).toBeGreaterThanOrEqual(2);
  });

  it('ticker link still navigates (stopPropagation on Link)', () => {
    const itemsWithId: RankingItem[] = [
      {
        ...sampleItems[0],
        stock_id: '11111111-1111-1111-1111-111111111111',
      },
    ];
    renderWithQuery(<RankingsTable items={itemsWithId} runId="test-run-id" />);
    // Two links per row (rank and ticker) — find the ticker one
    const links = screen.getAllByRole('link');
    const tickerLink = links.find((l) => l.textContent === 'AAPL');
    expect(tickerLink).toBeDefined();
    expect(tickerLink!.getAttribute('href')).toContain('/rankings/test-run-id/stock/AAPL');
  });

  it('row without stock_id (legacy) does not open sheet', () => {
    // sampleItems has stock_id: null for all
    renderWithQuery(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const row = screen.getByText('AAPL').closest('tr');
    fireEvent.click(row!);
    // Sheet did NOT open — AAPL appears only in the table row, not in a sheet header
    expect(screen.getAllByText('AAPL').length).toBe(1);
  });
});
