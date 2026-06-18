'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { generateMemo, getMemo, type Memo } from '@/lib/api/memos';
import { listStocks } from '@/lib/api/stocks';
import { listRuns } from '@/lib/api/runs';

const CONFIDENCE_COLORS: Record<string, string> = {
  high: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  medium: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  low: 'bg-destructive/10 text-destructive border-destructive/20',
};

function MemoCard({ memo }: { memo: Memo }) {
  return (
    <div className="rounded-lg border border-border bg-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm font-medium leading-snug">{memo.one_liner}</p>
        <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${CONFIDENCE_COLORS[memo.confidence]}`}>
          {memo.confidence}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{memo.ranking_interpretation}</p>
      {memo.sweet_spot && (
        <p className="text-xs text-emerald-500 font-medium">Sweet Spot: {memo.sweet_spot_explanation}</p>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Stärken</p>
          <ul className="space-y-0.5">
            {memo.key_strengths.map((s, i) => (
              <li key={i} className="text-xs flex gap-1">
                <span className="text-emerald-500">+</span> {s}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Risiken</p>
          <ul className="space-y-0.5">
            {memo.key_risks.map((r, i) => (
              <li key={i} className="text-xs flex gap-1">
                <span className="text-destructive">−</span> {r}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {memo.contradictions.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Widersprüche</p>
          {memo.contradictions.map((c, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              {c.model_a} vs. {c.model_b}: {c.description}
            </p>
          ))}
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        Erstellt: {new Date(memo.created_at).toLocaleString('de-CH')} · {memo.model_version}
      </p>
    </div>
  );
}

export default function AdminMemosPage() {
  const [ticker, setTicker] = useState('');
  const [runId, setRunId] = useState('');
  const [language, setLanguage] = useState<'de' | 'en'>('de');
  const [fetchedMemo, setFetchedMemo] = useState<Memo | null | undefined>(undefined);

  const { data: stocksData } = useQuery({
    queryKey: ['admin-stocks'],
    queryFn: () => listStocks(200),
  });

  const { data: runs } = useQuery({
    queryKey: ['admin-runs'],
    queryFn: () => listRuns(50),
  });

  const completedRuns = runs?.filter((r) => r.status === 'completed') ?? [];

  const resolveStockId = (t: string): string | null => {
    const stock = stocksData?.items.find(
      (s) => s.ticker.toLowerCase() === t.toLowerCase(),
    );
    return stock?.id ?? null;
  };

  const generateMutation = useMutation({
    mutationFn: () => {
      const stockId = resolveStockId(ticker);
      if (!stockId) throw new Error('Ticker nicht gefunden');
      return generateMemo(stockId, runId || null, language);
    },
  });

  const fetchMemo = async () => {
    const stockId = resolveStockId(ticker);
    if (!stockId || !runId) return;
    const memo = await getMemo(stockId, runId);
    setFetchedMemo(memo);
  };

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Research Memos</h1>

      {/* Controls */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Ticker</label>
            <input
              type="text"
              placeholder="z.B. NESN.SW"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background font-mono"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Ranking-Run (optional)</label>
            <select
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            >
              <option value="">Ohne Run-Bezug</option>
              {completedRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.universe_name} · {new Date(r.created_at).toLocaleDateString('de-CH')}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Sprache</label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as 'de' | 'en')}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            >
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending || !ticker}
            className="text-sm px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {generateMutation.isPending ? 'Generiere…' : 'Memo generieren'}
          </button>
          <button
            onClick={fetchMemo}
            disabled={!ticker || !runId}
            className="text-sm px-4 py-2 rounded border border-border hover:bg-muted disabled:opacity-50"
          >
            Existierendes Memo abrufen
          </button>
        </div>

        {generateMutation.isError && (
          <p className="text-xs text-destructive">
            {generateMutation.error instanceof Error
              ? generateMutation.error.message
              : 'Fehler beim Generieren.'}
          </p>
        )}
      </div>

      {/* Generated Memo */}
      {generateMutation.isSuccess && generateMutation.data && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">Generiertes Memo</h2>
          <MemoCard memo={generateMutation.data} />
        </div>
      )}

      {/* Fetched Memo */}
      {fetchedMemo !== undefined && (
        <div className="space-y-2">
          <h2 className="text-sm font-medium">Gespeichertes Memo</h2>
          {fetchedMemo === null ? (
            <p className="text-sm text-muted-foreground">Kein Memo für diesen Ticker + Run vorhanden.</p>
          ) : (
            <MemoCard memo={fetchedMemo} />
          )}
        </div>
      )}
    </div>
  );
}
