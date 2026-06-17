'use client';

interface CryptoAgentPanelProps {
  ticker: string;
  detectedPatterns?: string[];
  cachedAnalysis?: string | null;
}

export function CryptoAgentPanel({ ticker, detectedPatterns, cachedAnalysis }: CryptoAgentPanelProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border/50 bg-card p-4">
        <h3 className="text-sm font-semibold mb-2 text-muted-foreground">
          KI-Analyse für {ticker}
        </h3>
        {cachedAnalysis ? (
          <p className="text-sm leading-relaxed">{cachedAnalysis}</p>
        ) : (
          <p className="text-sm text-muted-foreground italic">Keine Analyse verfügbar.</p>
        )}
      </div>
      {detectedPatterns && detectedPatterns.length > 0 && (
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Erkannte Muster</h3>
          <div className="flex flex-wrap gap-2">
            {detectedPatterns.map((pattern) => (
              <span
                key={pattern}
                className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20"
              >
                {pattern}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
