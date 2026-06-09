'use client';

import { useState } from 'react';
import { PieChart, Loader2 } from 'lucide-react';

import { allocatePortfolio, type PortfolioAllocation } from '@/lib/api/portfolio';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface PortfolioAllocationPanelProps {
  runId: string;
}

function pctFmt(weight: number): string {
  return (weight * 100).toFixed(1) + '%';
}

function AllocationResult({ allocation }: { allocation: PortfolioAllocation }) {
  return (
    <div className="space-y-4" data-testid="portfolio-allocation-result">
      <div className="rounded-md border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Ticker</th>
              <th className="px-3 py-2 text-right font-medium">Gewicht</th>
              <th className="px-3 py-2 text-right font-medium hidden sm:table-cell">Quant-Score</th>
              <th className="px-3 py-2 text-center font-medium hidden sm:table-cell">3a</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {allocation.positions.map((pos) => (
              <tr key={pos.ticker} className="hover:bg-muted/30 transition-colors">
                <td className="px-3 py-2 font-mono font-medium">{pos.ticker}</td>
                <td className="px-3 py-2 text-right tabular-nums font-semibold">
                  {pctFmt(pos.weight)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground hidden sm:table-cell">
                  {pos.quant_score.toFixed(3)}
                </td>
                <td className="px-3 py-2 text-center hidden sm:table-cell">
                  {pos.is_3a_eligible && (
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0">3a</Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg bg-muted/30 border p-3 text-sm text-muted-foreground leading-relaxed">
        {allocation.overall_rationale_de}
      </div>

      <p className="text-[10px] text-muted-foreground">
        Methode: {allocation.method} · {allocation.total_positions} Positionen ·
        Keine Anlageberatung.
      </p>
    </div>
  );
}

export function PortfolioAllocationPanel({ runId }: PortfolioAllocationPanelProps) {
  const [allocation, setAllocation] = useState<PortfolioAllocation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await allocatePortfolio({ run_id: runId, top_n: 10 });
      setAllocation(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Portfolio-Fehler');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card data-testid="portfolio-allocation-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <PieChart className="h-4 w-4" />
          Portfolio vorschlagen
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!allocation && (
          <Button
            variant="outline"
            onClick={handleGenerate}
            disabled={loading}
            data-testid="generate-portfolio-btn"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Wird berechnet…
              </>
            ) : (
              <>
                <PieChart className="mr-2 h-4 w-4" />
                Top-10 Portfolio generieren
              </>
            )}
          </Button>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {allocation && <AllocationResult allocation={allocation} />}
      </CardContent>
    </Card>
  );
}
