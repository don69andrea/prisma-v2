'use client';

import { Sparkles, Loader2 } from 'lucide-react';
import { useCryptoAgentAnalysis } from '@/hooks/useCryptoAgentAnalysis';

interface CryptoAgentPanelProps {
  ticker: string;
  detectedPatterns?: string[];
  cachedAnalysis?: string | null;
}

function patternBadgeClass(pattern: string): string {
  const upper = pattern.toUpperCase();
  if (upper.includes('BULLISH') || upper.includes('GOLDEN') || upper.includes('OVERSOLD') || upper === 'MORNING_STAR') {
    return 'bg-green-500/15 text-green-400';
  }
  if (upper.includes('BEARISH') || upper.includes('DEATH') || upper.includes('OVERBOUGHT') || upper === 'EVENING_STAR') {
    return 'bg-red-500/15 text-red-400';
  }
  return 'bg-yellow-500/15 text-yellow-400';
}

export function CryptoAgentPanel({ ticker, detectedPatterns = [], cachedAnalysis }: CryptoAgentPanelProps) {
  const { analysis, loading, error, analyze } = useCryptoAgentAnalysis();
  const displayText = analysis || cachedAnalysis;

  return (
    <div className="rounded-lg border border-border/40 bg-muted/20 p-3 space-y-2" data-testid="crypto-agent-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-medium">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          <span>KI-Chartanalyse</span>
          {cachedAnalysis && !analysis && (
            <span className="text-[10px] text-muted-foreground">(letzter Snapshot)</span>
          )}
        </div>
        <button
          onClick={() => analyze(ticker)}
          disabled={loading}
          data-testid="crypto-agent-analyze-button"
          className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
          {loading ? 'Analysiere…' : 'Neu analysieren'}
        </button>
      </div>

      {detectedPatterns.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {detectedPatterns.slice(0, 6).map((p) => (
            <span key={p} className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${patternBadgeClass(p)}`}>
              {p.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}

      <div className="min-h-[32px] text-xs text-muted-foreground" data-testid="crypto-agent-text">
        {loading && !analysis && <span className="italic">Analysiere {ticker}…</span>}
        {displayText && (
          <p className="leading-relaxed">
            {displayText}
            {loading && <span className="ml-0.5 animate-pulse">▌</span>}
          </p>
        )}
        {error && <span className="text-destructive">Fehler: {error}</span>}
        {!displayText && !loading && !error && (
          <span className="italic text-muted-foreground/60">«Neu analysieren» für eine KI-Einschätzung.</span>
        )}
      </div>

      <p className="text-[10px] text-muted-foreground/50">
        KI-generiert. Keine Anlageberatung. Vergangenheitsdaten garantieren keine zukünftige Wertentwicklung.
      </p>
    </div>
  );
}
