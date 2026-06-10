'use client';

import { useState } from 'react';
import { Receipt, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

import { getSteuerEinschaetzung, type SteuerEinschaetzungResponse } from '@/lib/api/steuer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface SteuerPanelProps {
  ticker: string;
}

function SteuerResult({ data }: { data: SteuerEinschaetzungResponse }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="space-y-3" data-testid="steuer-result">
      {data.steuerarten.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Steuerarten</p>
          <ul className="space-y-0.5">
            {data.steuerarten.map((s, i) => (
              <li key={i} className="text-sm flex items-start gap-1.5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.pflichten.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Pflichten</p>
          <ul className="space-y-0.5">
            {data.pflichten.map((p, i) => (
              <li key={i} className="text-sm flex items-start gap-1.5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      {expanded && data.hinweise.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1">Hinweise</p>
          <ul className="space-y-0.5">
            {data.hinweise.map((h, i) => (
              <li key={i} className="text-xs text-muted-foreground flex items-start gap-1.5">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/50" />
                {h}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button
        variant="ghost"
        size="sm"
        className="w-full text-xs"
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? (
          <><ChevronUp className="mr-1 h-3 w-3" />Weniger</>
        ) : (
          <><ChevronDown className="mr-1 h-3 w-3" />Hinweise anzeigen</>
        )}
      </Button>

      <p className="text-[10px] text-muted-foreground border-t pt-2 leading-relaxed">
        {data.disclaimer}
      </p>
    </div>
  );
}

export function SteuerPanel({ ticker }: SteuerPanelProps) {
  const [result, setResult] = useState<SteuerEinschaetzungResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRequest = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSteuerEinschaetzung({
        ticker,
        anlegerprofil: 'privatperson',
        halteperiode_jahre: 10,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Steuer-Fehler');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card data-testid="steuer-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Receipt className="h-4 w-4" />
          Steuer-Einschätzung
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!result && (
          <Button
            variant="outline"
            onClick={handleRequest}
            disabled={loading}
            data-testid="request-steuer-btn"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Wird analysiert…
              </>
            ) : (
              <>
                <Receipt className="mr-2 h-4 w-4" />
                Steuer-Einschätzung anfordern
              </>
            )}
          </Button>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {result && <SteuerResult data={result} />}
      </CardContent>
    </Card>
  );
}
