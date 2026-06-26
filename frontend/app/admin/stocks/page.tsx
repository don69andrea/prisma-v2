'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listStocks } from '@/lib/api/stocks';
import {
  listUniverses,
  createUniverse,
  syncUniverseData,
  type UniverseRead,
} from '@/lib/api/universes';

export default function AdminStocksPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [newUniverse, setNewUniverse] = useState({ name: '', region: 'CH', tickers: '' });

  const { data: stocksData, isLoading: stocksLoading } = useQuery({
    queryKey: ['admin-stocks'],
    queryFn: () => listStocks(200),
  });

  const { data: universesData, isLoading: universesLoading } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
  });

  const syncMutation = useMutation({
    mutationFn: (id: string) => syncUniverseData(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['universes'] }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: newUniverse.name,
        region: newUniverse.region,
        tickers: newUniverse.tickers.split(',').map((t) => t.trim()).filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['universes'] });
      setNewUniverse({ name: '', region: 'CH', tickers: '' });
    },
  });

  const stocks = stocksData?.items ?? [];
  const filtered = search
    ? stocks.filter(
        (s) =>
          s.ticker.toLowerCase().includes(search.toLowerCase()) ||
          s.name.toLowerCase().includes(search.toLowerCase()),
      )
    : stocks;

  const universes: UniverseRead[] = universesData?.items ?? [];

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Stocks & Universen</h1>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Stocks</p>
          <p className="text-2xl font-bold mt-1">{stocks.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Universen</p>
          <p className="text-2xl font-bold mt-1">{universes.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Gefiltert</p>
          <p className="text-2xl font-bold mt-1">{filtered.length}</p>
        </div>
      </div>

      {/* Stock List */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Aktien-Datenbank</h2>
          <input
            type="text"
            placeholder="Suche Ticker / Name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm px-3 py-1.5 rounded border border-border bg-background w-56"
          />
        </div>
        {stocksLoading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Ticker</th>
                  <th className="pb-2 pr-4 font-medium">Name</th>
                  <th className="pb-2 pr-4 font-medium">Sektor</th>
                  <th className="pb-2 pr-4 font-medium">Land</th>
                  <th className="pb-2 font-medium">Währung</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 100).map((s) => (
                  <tr key={s.id} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-4 font-mono font-medium">{s.ticker}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{s.name}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{s.sector ?? '—'}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{s.country ?? '—'}</td>
                    <td className="py-2 text-muted-foreground">{s.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length > 100 && (
              <p className="text-xs text-muted-foreground mt-2">
                Zeige 100 von {filtered.length} Ergebnissen
              </p>
            )}
          </div>
        )}
      </div>

      {/* Universe Management */}
      <div className="space-y-4">
        <h2 className="text-sm font-medium">Universe-Verwaltung</h2>

        {universesLoading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="space-y-3">
            {universes.map((u) => (
              <div key={u.id} className="rounded-lg border border-border bg-card p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{u.name}</p>
                    <p className="text-xs text-muted-foreground">{u.region} · {u.tickers.length} Ticker</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setExpanded(expanded === u.id ? null : u.id)}
                      className="text-xs px-3 py-1 rounded border border-border hover:bg-muted"
                    >
                      {expanded === u.id ? 'Schliessen' : 'Ticker anzeigen'}
                    </button>
                    <button
                      onClick={() => syncMutation.mutate(u.id.toString())}
                      disabled={syncMutation.isPending}
                      className="text-xs px-3 py-1 rounded border border-border hover:bg-muted disabled:opacity-50"
                    >
                      {syncMutation.isPending ? 'Sync…' : 'yFinance Sync'}
                    </button>
                  </div>
                </div>
                {expanded === u.id && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {u.tickers.map((t) => (
                      <span
                        key={t}
                        className="text-xs px-2 py-0.5 rounded-full bg-muted font-mono"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                {syncMutation.isSuccess && (
                  <p className="text-xs text-emerald-500 mt-2">
                    Sync abgeschlossen · {syncMutation.data?.synced_count} Ticker aktualisiert
                    {syncMutation.data?.failed_tickers.length
                      ? ` · Fehlgeschlagen: ${syncMutation.data.failed_tickers.join(', ')}`
                      : ''}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Create New Universe */}
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h3 className="text-sm font-medium">Neues Universum anlegen</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              type="text"
              placeholder="Name (z.B. SMI)"
              value={newUniverse.name}
              onChange={(e) => setNewUniverse((p) => ({ ...p, name: e.target.value }))}
              className="text-sm px-3 py-2 rounded border border-border bg-background"
            />
            <input
              type="text"
              placeholder="Region (z.B. CH)"
              value={newUniverse.region}
              onChange={(e) => setNewUniverse((p) => ({ ...p, region: e.target.value }))}
              className="text-sm px-3 py-2 rounded border border-border bg-background"
            />
            <input
              type="text"
              placeholder="Ticker, kommagetrennt: NESN.SW, NOVN.SW"
              value={newUniverse.tickers}
              onChange={(e) => setNewUniverse((p) => ({ ...p, tickers: e.target.value }))}
              className="text-sm px-3 py-2 rounded border border-border bg-background"
            />
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !newUniverse.name || !newUniverse.tickers}
            className="text-sm px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Erstelle…' : 'Universum erstellen'}
          </button>
          {createMutation.isSuccess && (
            <p className="text-xs text-emerald-500">Universum erstellt.</p>
          )}
          {createMutation.isError && (
            <p className="text-xs text-destructive">Fehler beim Erstellen.</p>
          )}
        </div>
      </div>
    </div>
  );
}
