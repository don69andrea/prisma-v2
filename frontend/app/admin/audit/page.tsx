'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAuditTrail, type AuditRecord } from '@/lib/api/audit';
import { apiFetch } from '@/lib/api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface CostSummary {
  last_calls: Array<{
    created_at: string;
    model: string;
    feature: string;
    cost_usd: number;
  }>;
}

const SIGNAL_COLORS: Record<string, string> = {
  BUY: '#10b981',
  HOLD: '#f59e0b',
  SELL: '#ef4444',
};

const SIGNAL_BADGE: Record<string, string> = {
  BUY: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  HOLD: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  SELL: 'bg-destructive/10 text-destructive border-destructive/20',
};

export default function AdminAuditPage() {
  const [ticker, setTicker] = useState('');
  const [activeTicker, setActiveTicker] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: auditData, isLoading: auditLoading, isError } = useQuery({
    queryKey: ['audit-trail', activeTicker],
    queryFn: () => getAuditTrail(activeTicker),
    enabled: activeTicker.length > 0,
  });

  const { data: costsData } = useQuery<CostSummary>({
    queryKey: ['admin-costs-audit'],
    queryFn: () => apiFetch<CostSummary>('/api/v1/admin/costs?last=100'),
  });

  const records: AuditRecord[] = auditData?.records ?? [];

  const chartData = records
    .slice()
    .reverse()
    .map((r) => ({
      date: new Date(r.snapshot_date).toLocaleDateString('de-CH', { month: 'short', day: 'numeric' }),
      score: r.weighted_score,
      signal: r.signal,
    }));

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Audit Trail</h1>

      {/* Decision Audit */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-4">
        <h2 className="text-sm font-medium">Decision Audit Trail</h2>

        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Ticker (z.B. NESN oder AAPL)"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && setActiveTicker(ticker)}
            className="text-sm px-3 py-2 rounded border border-border bg-background font-mono flex-1"
          />
          <button
            onClick={() => setActiveTicker(ticker)}
            disabled={!ticker}
            className="text-sm px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            Suchen
          </button>
        </div>

        {auditLoading && <p className="text-sm text-muted-foreground">Lädt…</p>}
        {isError && <p className="text-sm text-destructive">Ticker nicht gefunden oder Fehler.</p>}

        {records.length > 0 && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded border border-border p-3">
                <p className="text-xs text-muted-foreground">Letztes Signal</p>
                <span className={`inline-block mt-1 text-xs px-2 py-0.5 rounded-full border ${SIGNAL_BADGE[records[0].signal]}`}>
                  {records[0].signal}
                </span>
              </div>
              <div className="rounded border border-border p-3">
                <p className="text-xs text-muted-foreground">Letzter Score</p>
                <p className="text-lg font-bold mt-0.5">{records[0].weighted_score.toFixed(1)}</p>
              </div>
              <div className="rounded border border-border p-3">
                <p className="text-xs text-muted-foreground">Einträge</p>
                <p className="text-lg font-bold mt-0.5">{auditData?.total ?? records.length}</p>
              </div>
            </div>

            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} domain={[0, 100]} width={30} />
                <Tooltip formatter={(v: number) => [v.toFixed(1), 'Score']} />
                <Bar dataKey="score" radius={[3, 3, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={SIGNAL_COLORS[entry.signal] ?? '#6366f1'} />
                  ))}
                </Bar>
                <Legend
                  payload={Object.entries(SIGNAL_COLORS).map(([value, color]) => ({
                    value,
                    color,
                    type: 'square' as const,
                  }))}
                />
              </BarChart>
            </ResponsiveContainer>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="pb-2 pr-3 font-medium">Datum</th>
                    <th className="pb-2 pr-3 font-medium">Signal</th>
                    <th className="pb-2 pr-3 font-medium">Score</th>
                    <th className="pb-2 pr-3 font-medium">Quant</th>
                    <th className="pb-2 pr-3 font-medium">ML</th>
                    <th className="pb-2 pr-3 font-medium">Makro</th>
                    <th className="pb-2 pr-3 font-medium">3a</th>
                    <th className="pb-2 font-medium">Erklärung</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <>
                      <tr
                        key={r.id}
                        className="border-b border-border/50 cursor-pointer hover:bg-muted/30"
                        onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                      >
                        <td className="py-2 pr-3 text-muted-foreground text-xs">
                          {new Date(r.snapshot_date).toLocaleDateString('de-CH')}
                        </td>
                        <td className="py-2 pr-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${SIGNAL_BADGE[r.signal]}`}>
                            {r.signal}
                          </span>
                        </td>
                        <td className="py-2 pr-3 font-mono font-medium">{r.weighted_score.toFixed(1)}</td>
                        <td className="py-2 pr-3 text-xs text-muted-foreground">{r.quant_score.toFixed(1)}</td>
                        <td className="py-2 pr-3 text-xs text-muted-foreground">{r.ml_score.toFixed(1)}</td>
                        <td className="py-2 pr-3 text-xs text-muted-foreground">{r.macro_score.toFixed(1)}</td>
                        <td className="py-2 pr-3 text-xs">{r.is_3a_eligible ? '✓' : '—'}</td>
                        <td className="py-2 text-xs text-muted-foreground truncate max-w-[200px]">
                          {r.explanation_de.slice(0, 80)}…
                        </td>
                      </tr>
                      {expandedId === r.id && (
                        <tr key={`${r.id}-expanded`} className="border-b border-border/50">
                          <td colSpan={8} className="py-3 px-0">
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              {r.explanation_de}
                            </p>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* LLM Call Log */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-medium">LLM-Call-Log (letzte 100)</h2>
        {!costsData?.last_calls?.length ? (
          <p className="text-sm text-muted-foreground">Keine Calls erfasst.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Zeitpunkt</th>
                  <th className="pb-2 pr-4 font-medium">Modell</th>
                  <th className="pb-2 pr-4 font-medium">Feature</th>
                  <th className="pb-2 font-medium text-right">Kosten</th>
                </tr>
              </thead>
              <tbody>
                {costsData.last_calls.map((call, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-4 text-xs text-muted-foreground">
                      {new Date(call.created_at).toLocaleString('de-CH')}
                    </td>
                    <td className="py-2 pr-4 text-xs">{call.model}</td>
                    <td className="py-2 pr-4 text-xs">{call.feature}</td>
                    <td className="py-2 text-right font-mono text-xs">${call.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
