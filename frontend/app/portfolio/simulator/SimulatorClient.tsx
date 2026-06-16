'use client';

import { useState, useCallback } from 'react';
import { Loader2, Sparkles, TrendingUp } from 'lucide-react';

import { runMonteCarlo, type MonteCarloResponse, type HoldingWeightInput } from '@/lib/api/montecarlo';
import { MonteCarloFanChart } from '@/components/portfolio/MonteCarloFanChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const DEFAULT_HOLDINGS: HoldingWeightInput[] = [
  { ticker: 'NESN.SW', weight: 0.4 },
  { ticker: 'NOVN.SW', weight: 0.3 },
  { ticker: 'ABBN.SW', weight: 0.3 },
];

function formatCHF(v: number) {
  if (v >= 1_000_000) return `CHF ${(v / 1_000_000).toFixed(2)}M`;
  return `CHF ${v.toLocaleString('de-CH', { maximumFractionDigits: 0 })}`;
}

export function SimulatorClient() {
  const [holdings, setHoldings] = useState<HoldingWeightInput[]>(DEFAULT_HOLDINGS);
  const [contribution, setContribution] = useState(588);
  const [years, setYears] = useState(30);
  const [result, setResult] = useState<MonteCarloResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalWeight = holdings.reduce((s, h) => s + h.weight, 0);

  const handleSimulate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runMonteCarlo({ holdings, monthly_contribution: contribution, years });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler bei der Simulation');
    } finally {
      setLoading(false);
    }
  }, [holdings, contribution, years]);

  const updateWeight = (i: number, w: number) => {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, weight: w } : h)));
  };
  const updateTicker = (i: number, t: string) => {
    setHoldings((prev) => prev.map((h, idx) => (idx === i ? { ...h, ticker: t.toUpperCase() } : h)));
  };

  const contributionLine = result
    ? Array.from({ length: result.months }, (_, i) => contribution * (i + 1))
    : [];

  return (
    <div className="min-h-screen bg-background text-foreground p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-purple-400" />
            3a Retirement Simulator.
          </h1>
          <p className="text-muted-foreground text-sm">
            10&apos;000 Monte-Carlo-Simulationen · Geometric Brownian Motion · Swiss 3a
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT: Input Panel */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="bg-card border-border backdrop-blur-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-foreground">Portfolio</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {holdings.map((h, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <Input
                      value={h.ticker}
                      onChange={(e) => updateTicker(i, e.target.value)}
                      className="w-28 font-mono text-sm bg-muted border-border"
                      placeholder="NESN.SW"
                    />
                    <input
                      type="range"
                      min={0.05}
                      max={0.9}
                      step={0.05}
                      value={h.weight}
                      onChange={(e) => updateWeight(i, parseFloat(e.target.value))}
                      className="flex-1 accent-purple-500"
                    />
                    <span className="w-10 text-right text-sm tabular-nums text-purple-300">
                      {Math.round(h.weight * 100)}%
                    </span>
                  </div>
                ))}
                <div className={cn('text-xs text-right', Math.abs(totalWeight - 1) > 0.01 ? 'text-red-400' : 'text-emerald-400')}>
                  Gesamt: {Math.round(totalWeight * 100)}%
                </div>
              </CardContent>
            </Card>

            <Card className="bg-card border-border backdrop-blur-sm">
              <CardContent className="pt-4 space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Monatliche Einzahlung</span>
                    <span className="font-medium text-purple-300">CHF {contribution}</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={2000}
                    step={50}
                    value={contribution}
                    onChange={(e) => setContribution(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <div className="text-[10px] text-muted-foreground">Swiss 3a Max: CHF 7&apos;056 / Jahr</div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Anlagehorizont</span>
                    <span className="font-medium text-purple-300">{years} Jahre</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={40}
                    step={1}
                    value={years}
                    onChange={(e) => setYears(Number(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground">
                    <span>1J</span><span>10J</span><span>20J</span><span>30J</span><span>40J</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Button
              onClick={handleSimulate}
              disabled={loading || Math.abs(totalWeight - 1) > 0.01}
              className="w-full bg-purple-600 hover:bg-purple-500 text-white font-semibold py-3 relative overflow-hidden group"
              style={{ boxShadow: loading ? '0 0 20px rgba(168,85,247,0.5)' : undefined }}
            >
              {loading ? (
                <><Loader2 className="h-4 w-4 animate-spin mr-2" />Simuliere...</>
              ) : (
                <><Sparkles className="h-4 w-4 mr-2" />Jetzt simulieren</>
              )}
              <div className="absolute inset-0 bg-white/10 scale-x-0 group-hover:scale-x-100 transition-transform origin-left" />
            </Button>

            {error && <p className="text-sm text-red-400 text-center">{error}</p>}
          </div>

          {/* RIGHT: Chart + Stats */}
          <div className="lg:col-span-3 space-y-4">
            {result ? (
              <>
                {/* Stats */}
                <div className="grid grid-cols-2 gap-3">
                  <Card className="bg-card border-emerald-500/20" style={{ boxShadow: '0 0 20px rgba(16,185,129,0.1)' }}>
                    <CardContent className="pt-4 space-y-1">
                      <p className="text-xs text-muted-foreground">Median-Endvermögen</p>
                      <p className="text-2xl font-bold text-emerald-400 tabular-nums">
                        {formatCHF(result.p50[result.p50.length - 1])}
                      </p>
                    </CardContent>
                  </Card>
                  <Card className="bg-card border-purple-500/20" style={{ boxShadow: '0 0 20px rgba(168,85,247,0.1)' }}>
                    <CardContent className="pt-4 space-y-1">
                      <p className="text-xs text-muted-foreground">P95-Endvermögen</p>
                      <p className="text-2xl font-bold text-purple-400 tabular-nums">
                        {formatCHF(result.p95[result.p95.length - 1])}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge className="bg-emerald-950 border-emerald-500/40 text-emerald-300 text-xs">
                    {Math.round(result.prob_positive_return * 100)}% Chance positiver Return
                  </Badge>
                  <Badge className="bg-purple-950 border-purple-500/40 text-purple-300 text-xs">
                    {Math.round(result.prob_500k * 100)}% Chance CHF 500k+
                  </Badge>
                  <Badge className="bg-muted border-border text-muted-foreground text-xs">
                    Einzahlungen total: {formatCHF(result.contribution_total)}
                  </Badge>
                </div>

                {/* Fan Chart */}
                <Card className="bg-card border-border">
                  <CardContent className="pt-4">
                    <MonteCarloFanChart
                      p5={result.p5}
                      p50={result.p50}
                      p95={result.p95}
                      contributionLine={contributionLine}
                      years={years}
                    />
                  </CardContent>
                </Card>

                {/* Text Interpretation */}
                {result.interpretation && (
                  <div className="rounded-xl border border-purple-500/20 bg-purple-950/20 p-4 space-y-2">
                    <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Was bedeutet das?
                    </h3>
                    {result.interpretation.split('. ').filter(Boolean).map((sentence, i) => (
                      <p key={i} className="text-sm text-muted-foreground leading-relaxed">
                        {sentence.endsWith('.') ? sentence : sentence + '.'}
                      </p>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <Card className="bg-card border-border border-dashed h-64 flex items-center justify-center">
                <div className="text-center text-muted-foreground">
                  <TrendingUp className="h-10 w-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">Simulation starten →</p>
                </div>
              </Card>
            )}
          </div>
        </div>

        <p className="text-[10px] text-muted-foreground text-center">
          Simulationsergebnisse basieren auf historischen Daten und ML-Prognosen. Keine Anlageberatung. PRISMA V2.
        </p>
      </div>
    </div>
  );
}
