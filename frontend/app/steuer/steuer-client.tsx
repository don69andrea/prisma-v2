'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Check, Copy } from 'lucide-react';

import {
  getSteuerEinschaetzung,
  type Anlegerprofil,
  type SteuerEinschaetzungResponse,
} from '@/lib/api/steuer';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const LS_STEUER_KEY = 'prisma_steuer_config';

function loadStoredSteuer() {
  try {
    const raw = localStorage.getItem(LS_STEUER_KEY);
    if (raw) return JSON.parse(raw) as { ticker: string; profil: Anlegerprofil; halteperiode: number };
  } catch {}
  return null;
}

const PROFIL_OPTIONS: { value: Anlegerprofil; label: string }[] = [
  { value: 'privatperson',  label: 'Privatperson' },
  { value: 'vorsorge_3a',   label: 'Säule 3a' },
  { value: 'vorsorge_2a',   label: 'Pensionskasse (2. Säule)' },
  { value: 'institution',   label: 'Institution' },
];

function ResultSection({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-muted-foreground mt-0.5">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function buildClipboardText(data: SteuerEinschaetzungResponse): string {
  const lines: string[] = [
    `Steuer-Einschätzung: ${data.ticker} | ${data.anlegerprofil} | ${data.halteperiode_jahre} Jahre`,
    '',
  ];
  if (data.steuerarten.length > 0) {
    lines.push('Steuerarten:', ...data.steuerarten.map((s) => `• ${s}`), '');
  }
  if (data.pflichten.length > 0) {
    lines.push('Pflichten:', ...data.pflichten.map((s) => `• ${s}`), '');
  }
  if (data.hinweise.length > 0) {
    lines.push('Hinweise:', ...data.hinweise.map((s) => `• ${s}`), '');
  }
  lines.push(`Modell: ${data.model_version}`);
  return lines.join('\n');
}

function SteuerResult({ data }: { data: SteuerEinschaetzungResponse }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(buildClipboardText(data)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">
            {data.ticker} · {data.anlegerprofil} · {data.halteperiode_jahre} Jahre
          </CardTitle>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            data-testid="steuer-copy-btn"
            aria-label="Ergebnis kopieren"
          >
            {copied
              ? <><Check className="h-3 w-3 text-emerald-500" /> Kopiert</>
              : <><Copy className="h-3 w-3" /> Kopieren</>
            }
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <ResultSection title="Steuerarten" items={data.steuerarten} />
        <ResultSection title="Pflichten" items={data.pflichten} />
        <ResultSection title="Hinweise" items={data.hinweise} />
        {data.quellen.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Quellen
            </p>
            <ul className="space-y-0.5">
              {data.quellen.map((q, i) => (
                <li key={i} className="text-xs text-muted-foreground">{q}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3 flex gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-800 dark:text-amber-300">{data.disclaimer}</p>
        </div>
        <p className="text-[10px] text-muted-foreground">
          Modell: {data.model_version} ·{' '}
          {new Date(data.generated_at).toLocaleString('de-CH')}
        </p>
      </CardContent>
    </Card>
  );
}

export function SteuerClient() {
  const [ticker, setTicker] = useState(() => loadStoredSteuer()?.ticker ?? 'NESN');
  const [profil, setProfil] = useState<Anlegerprofil>(() => loadStoredSteuer()?.profil ?? 'vorsorge_3a');
  const [halteperiode, setHalteperiode] = useState(() => loadStoredSteuer()?.halteperiode ?? 30);
  const [result, setResult] = useState<SteuerEinschaetzungResponse | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      getSteuerEinschaetzung({ ticker, anlegerprofil: profil, halteperiode_jahre: halteperiode }),
    onSuccess: (data) => {
      localStorage.setItem(LS_STEUER_KEY, JSON.stringify({ ticker, profil, halteperiode }));
      setResult(data);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate();
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Steuer-Einschätzung</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium">Ticker</label>
              <Input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="z.B. NESN"
                data-testid="steuer-ticker-input"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Anlegerprofil</label>
              <select
                value={profil}
                onChange={(e) => setProfil(e.target.value as Anlegerprofil)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                data-testid="steuer-profil-select"
              >
                {PROFIL_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Halteperiode (Jahre)</label>
              <Input
                type="number"
                value={halteperiode}
                onChange={(e) => setHalteperiode(Number(e.target.value))}
                min={1}
                max={50}
                data-testid="steuer-halteperiode-input"
              />
            </div>
            <div className="sm:col-span-3">
              <Button
                type="submit"
                disabled={mutation.isPending || !ticker.trim()}
                className="w-full sm:w-auto"
                data-testid="steuer-submit-btn"
              >
                {mutation.isPending ? 'Wird analysiert…' : 'Steuer-Einschätzung anfordern'}
              </Button>
            </div>
          </form>
          {mutation.isError && (
            <p className="mt-3 text-sm text-destructive">
              Anfrage fehlgeschlagen. Bitte erneut versuchen.
            </p>
          )}
        </CardContent>
      </Card>

      {result && <SteuerResult data={result} />}
    </div>
  );
}
