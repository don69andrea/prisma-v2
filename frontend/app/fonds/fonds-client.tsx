'use client';

import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Download, Plus, Trash2 } from 'lucide-react';

import {
  listFonds,
  compareFonds,
  type FondsVergleichResponse,
  type PortfolioMetrics,
} from '@/lib/api/fonds';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PrismaBar } from '@/components/ui/PrismaBar';
import { cn } from '@/lib/utils';

function InfoBtn({ text }: { text: string }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold bg-muted text-muted-foreground hover:bg-accent hover:text-foreground transition-colors ml-1"
        aria-label="Mehr Info"
      >
        i
      </button>
      {show && (
        <span className="absolute z-50 left-6 -top-1 w-52 text-xs bg-popover border border-border rounded-md px-2 py-1.5 text-popover-foreground shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}

function pctFmt(v: string | null): string {
  if (v === null) return '—';
  return (parseFloat(v) * 100).toFixed(1) + '%';
}

function ratioFmt(v: string | null): string {
  if (v === null) return '—';
  return parseFloat(v).toFixed(2);
}

function MetricColumn({ label, metrics }: { label: string; metrics: PortfolioMetrics }) {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-3 flex-1">
      <p className="text-sm font-semibold text-center">{label}</p>
      <div className="space-y-2">
        <MetricRow label="Erw. Rendite p.a." value={pctFmt(metrics.expected_return_pa)} positive />
        <MetricRow label="Volatilität p.a." value={pctFmt(metrics.volatility_pa)} />
        <MetricRow
          label={
            <span className="flex items-center gap-0.5">
              Sharpe Ratio
              <InfoBtn text="Rendite im Verhältnis zum Risiko. Über 1 ist gut — du wirst für das eingegangene Risiko gut entschädigt." />
            </span>
          }
          value={ratioFmt(metrics.sharpe_ratio)}
          positive
        />
        <MetricRow label="Max. Drawdown" value={pctFmt(metrics.max_drawdown)} />
      </div>
    </div>
  );
}

function MetricRow({
  label,
  value,
  positive,
}: {
  label: React.ReactNode;
  value: string;
  positive?: boolean;
}) {
  const isGood = positive
    ? parseFloat(String(value)) > 0
    : value !== '—' && parseFloat(String(value)) < 0;

  return (
    <div className="flex justify-between items-center text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('font-medium tabular-nums', isGood ? 'text-emerald-600 dark:text-emerald-400' : '')}>
        {value}
      </span>
    </div>
  );
}

function exportFondsCsv(result: FondsVergleichResponse) {
  const rows = [
    ['Metrik', result.fonds_name, 'Mein Portfolio'],
    ['Erw. Rendite p.a.', pctFmt(result.fonds_metrics.expected_return_pa), pctFmt(result.custom_metrics.expected_return_pa)],
    ['Volatilität p.a.', pctFmt(result.fonds_metrics.volatility_pa), pctFmt(result.custom_metrics.volatility_pa)],
    ['Sharpe Ratio', ratioFmt(result.fonds_metrics.sharpe_ratio), ratioFmt(result.custom_metrics.sharpe_ratio)],
    ['Max. Drawdown', pctFmt(result.fonds_metrics.max_drawdown), pctFmt(result.custom_metrics.max_drawdown)],
  ];
  const csv = rows.map((r) => r.map((v) => `"${v}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `fonds-vergleich-${result.fonds_name.replace(/\s+/g, '-')}-${result.snapshot_date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function VergleichResult({ result }: { result: FondsVergleichResponse }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium">Ergebnis: {result.snapshot_date}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => exportFondsCsv(result)}
          data-testid="fonds-csv-export-btn"
        >
          <Download className="mr-1 h-3.5 w-3.5" />
          CSV
        </Button>
      </div>
      <div className="flex gap-3 flex-col sm:flex-row">
        <MetricColumn label={result.fonds_name} metrics={result.fonds_metrics} />
        <MetricColumn label="Mein Portfolio" metrics={result.custom_metrics} />
      </div>
      <p className="text-xs text-muted-foreground border-t pt-3">{result.disclaimer}</p>
    </div>
  );
}

interface Position {
  ticker: string;
  weight: string;
}

const DEFAULT_FONDS_POSITIONS: Position[] = [
  { ticker: 'NESN', weight: '30' },
  { ticker: 'NOVN', weight: '25' },
  { ticker: 'ROG',  weight: '20' },
  { ticker: 'ABBN', weight: '25' },
];

const LS_FONDS_KEY = 'prisma_fonds_config';

function loadStoredFonds() {
  try {
    const raw = localStorage.getItem(LS_FONDS_KEY);
    if (raw) return JSON.parse(raw) as { selectedFonds: string; positions: Array<{ ticker: string; weight: string }> };
  } catch {}
  return null;
}

export function FondsClient() {
  const [selectedFonds, setSelectedFonds] = useState('');
  const [positions, setPositions] = useState<Position[]>(DEFAULT_FONDS_POSITIONS);
  const [error, setError] = useState('');

  useEffect(() => {
    const s = loadStoredFonds();
    if (!s) return;
    if (s.selectedFonds) setSelectedFonds(s.selectedFonds);
    if (s.positions?.length) setPositions(s.positions);
  }, []);

  const { data: fondsList, isLoading: fondsLoading, isError: fondsError, refetch } = useQuery({
    queryKey: ['fonds'],
    queryFn: listFonds,
  });

  const totalWeight = positions.reduce((sum, p) => sum + (parseFloat(p.weight) || 0), 0);
  const weightError = totalWeight > 100 ? `Gesamtgewichtung: ${totalWeight.toFixed(1)}% — maximal 100% erlaubt` : null;

  const mutation = useMutation({
    mutationFn: compareFonds,
    onSuccess: () => {
      try { localStorage.setItem(LS_FONDS_KEY, JSON.stringify({ selectedFonds, positions })); } catch {}
    },
    onError: () => setError('Vergleich konnte nicht berechnet werden.'),
  });

  function addPosition() {
    setPositions((p) => [...p, { ticker: '', weight: '0' }]);
  }

  function removePosition(i: number) {
    setPositions((p) => p.filter((_, idx) => idx !== i));
  }

  function updatePosition(i: number, field: keyof Position, value: string) {
    setPositions((p) => p.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (!selectedFonds) {
      setError('Bitte einen Fonds auswählen.');
      return;
    }
    const positionsClean = positions
      .filter((p) => p.ticker)
      .map((p) => ({ ticker: p.ticker.toUpperCase(), weight: parseFloat(p.weight) / 100 }));
    if (positionsClean.length === 0) {
      setError('Mindestens eine Position erforderlich.');
      return;
    }
    mutation.mutate({ fonds_name: selectedFonds, positions: positionsClean });
  }

  return (
    <div className="space-y-6">
      {fondsError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400 flex items-center justify-between">
          <span>Fondsliste konnte nicht geladen werden</span>
          <button onClick={() => refetch()} className="text-xs hover:underline">Erneut versuchen</button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="rounded-lg border bg-card p-4 space-y-4">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground flex items-center">
            VIAC-Fonds
            <InfoBtn text="Ein Fonds bündelt viele Aktien in einem einzigen Wertpapier. Ein ETF (Exchange Traded Fund) ist ein börsengehandelter Fonds der einen Index abbildet." />
          </label>
          {fondsError ? (
            <p className="text-xs text-destructive">Fondsliste konnte nicht geladen werden. Bitte Seite neu laden.</p>
          ) : fondsLoading ? (
            <div className="space-y-2 w-64">
              <PrismaBar />
              <Skeleton className="h-9 w-64" />
            </div>
          ) : (
            <select
              className="w-64 rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              value={selectedFonds}
              onChange={(e) => setSelectedFonds(e.target.value)}
            >
              <option value="">— Fonds wählen —</option>
              {fondsList?.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name} ({Math.round(f.equity_ratio * 100)}% Aktien)
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <p className="text-xs text-muted-foreground mb-2">Mein Portfolio (Ticker + Gewicht %)</p>
          <div className="space-y-1.5">
            {positions.map((pos, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  className="w-20 rounded border bg-background px-2 py-1 text-sm uppercase focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="NESN"
                  value={pos.ticker}
                  onChange={(e) => updatePosition(i, 'ticker', e.target.value)}
                />
                <input
                  className="w-20 rounded border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary"
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={pos.weight}
                  onChange={(e) => updatePosition(i, 'weight', e.target.value)}
                />
                <span className="text-xs text-muted-foreground">%</span>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  onClick={() => removePosition(i)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
          <Button type="button" size="sm" variant="outline" className="mt-2" onClick={addPosition}>
            <Plus className="h-3.5 w-3.5 mr-1" /> Position
          </Button>
        </div>

        {weightError && <p className="text-xs text-destructive">{weightError}</p>}
        {error && <p className="text-xs text-destructive">{error}</p>}

        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={mutation.isPending || fondsLoading || !!weightError || totalWeight === 0}>
            {mutation.isPending ? 'Berechne…' : 'Vergleichen'}
          </Button>
          {JSON.stringify(positions) !== JSON.stringify(DEFAULT_FONDS_POSITIONS) && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive border-destructive/40 hover:bg-destructive/5"
              onClick={() => setPositions(DEFAULT_FONDS_POSITIONS)}
              data-testid="fonds-reset-positions-btn"
            >
              Zurücksetzen
            </Button>
          )}
        </div>
      </form>

      {mutation.data && <VergleichResult result={mutation.data} />}
    </div>
  );
}
