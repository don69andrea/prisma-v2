'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Terminal, Send, ChevronRight, ExternalLink, Download, Check } from 'lucide-react';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import {
  retrieveSecFilings,
  retrieveSwissFilings,
  type SecChunkResult,
  type SwissChunkResult,
} from '@/lib/api/rag';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LS_RESEARCH_KEY = 'prisma_research_last_search';
const CYAN = '#00d4ff';

const EXAMPLE_QUERIES = [
  'Wie sieht Novartis fundamental aus?',
  'Welche SMI-Aktie hat die beste Dividende?',
  'Was bedeutet der SNB-Entscheid für mich?',
  'Vergleiche Roche und Novartis',
  'Zeige mir Aktien mit niedrigem KGV',
];

const AGENT_STEPS = [
  { agent: 'MacroAgent', action: 'lädt Marktdaten...' },
  { agent: 'FilingRAG', action: 'durchsucht Berichte...' },
  { agent: 'QuantAgent', action: 'berechnet Signale...' },
];

const MOCK_SOURCES = [
  { label: 'Novartis GB 2025', url: '#' },
  { label: 'SNB Q1 2026', url: '#' },
];

const MOCK_MACRO = {
  rate: '1.0%',
  fx: '0.938',
  sentiment: 'Leicht risiko-positiv',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function loadStoredResearch() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(LS_RESEARCH_KEY);
    if (raw) return JSON.parse(raw) as { query: string; ticker: string };
  } catch {}
  return null;
}

function exportResearchCsv(results: (SwissChunkResult | SecChunkResult)[], filename: string) {
  const rows = [
    ['Ticker', 'Typ', 'Datum', 'Ähnlichkeit%', 'Quelle', 'Inhalt'],
    ...results.map((r) => {
      const swiss = r as SwissChunkResult;
      const sec = r as SecChunkResult;
      return [
        swiss.ticker ?? sec.ticker ?? '',
        r.doc_type ?? '',
        swiss.filing_date ?? '',
        Math.round(r.similarity * 100).toString(),
        swiss.source ?? '',
        (r.content ?? '').slice(0, 200),
      ];
    }),
  ];
  const csv = rows
    .map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// TypewriterText
// ---------------------------------------------------------------------------

function TypewriterText({ text, speed = 20 }: { text: string; speed?: number }) {
  const [displayed, setDisplayed] = useState('');

  useEffect(() => {
    setDisplayed('');
    let i = 0;
    const interval = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      <span className="animate-pulse">▊</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// AgentLog (Pro Mode)
// ---------------------------------------------------------------------------

type AgentLogEntry =
  | { type: 'step'; agent: string; action: string; done: boolean; duration?: number }
  | { type: 'ready' };

function useAgentLog(active: boolean) {
  const [log, setLog] = useState<AgentLogEntry[]>([]);
  const startRef = useRef<number[]>([]);

  useEffect(() => {
    if (!active) {
      setLog([]);
      startRef.current = [];
      return;
    }

    setLog([]);
    startRef.current = [];

    const delays = [0, 500, 1300];
    const durations = [800, 1200, 400];

    const timers: ReturnType<typeof setTimeout>[] = [];

    AGENT_STEPS.forEach((step, i) => {
      const t1 = setTimeout(() => {
        startRef.current[i] = Date.now();
        setLog((prev) => [
          ...prev,
          { type: 'step', agent: step.agent, action: step.action, done: false },
        ]);
      }, delays[i]);

      const t2 = setTimeout(() => {
        const elapsed = startRef.current[i]
          ? ((Date.now() - startRef.current[i]) / 1000).toFixed(1)
          : durations[i] / 1000;
        setLog((prev) =>
          prev.map((entry, idx) =>
            idx === i && entry.type === 'step'
              ? { ...entry, done: true, duration: parseFloat(String(elapsed)) }
              : entry,
          ),
        );
      }, delays[i] + durations[i]);

      timers.push(t1, t2);
    });

    const readyDelay = delays[AGENT_STEPS.length - 1] + durations[AGENT_STEPS.length - 1] + 100;
    const t3 = setTimeout(() => {
      setLog((prev) => [...prev, { type: 'ready' }]);
    }, readyDelay);
    timers.push(t3);

    return () => timers.forEach(clearTimeout);
  }, [active]);

  return log;
}

// ---------------------------------------------------------------------------
// ResultSummary — builds a one-liner from RAG results
// ---------------------------------------------------------------------------

function buildSummary(
  swissResults: SwissChunkResult[] | null,
  secResults: SecChunkResult[] | null,
  query: string,
): string {
  const allResults = [...(swissResults ?? []), ...(secResults ?? [])];
  if (allResults.length === 0) {
    return `Keine Ergebnisse für «${query}» gefunden. Versuche eine andere Formulierung oder einen spezifischeren Ticker.`;
  }

  const topSwiss = swissResults?.[0];
  const topSec = secResults?.[0];
  const top = topSwiss ?? topSec;

  const ticker = top
    ? (top as SwissChunkResult).ticker ?? (top as SecChunkResult).ticker
    : null;

  const score = top ? Math.round(top.similarity * 100) : null;
  const snippet = top ? top.content.slice(0, 180).replace(/\s+/g, ' ').trim() : '';

  const tickerStr = ticker ? `[${ticker}] ` : '';
  const scoreStr = score !== null ? ` · Relevanz ${score}%` : '';

  return (
    `${tickerStr}${snippet}…${scoreStr} — ` +
    `${allResults.length} Dokument${allResults.length !== 1 ? 'e' : ''} analysiert. ` +
    `Quellen: ${[topSwiss ? 'SIX Jahresberichte' : null, topSec ? 'SEC Filings' : null]
      .filter(Boolean)
      .join(' & ')}.`
  );
}

// ---------------------------------------------------------------------------
// SimpleModeView
// ---------------------------------------------------------------------------

function SimpleModeView({
  query,
  setQuery,
  onSubmit,
  isPending,
  summary,
}: {
  query: string;
  setQuery: (q: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isPending: boolean;
  summary: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-col gap-8 max-w-2xl mx-auto">
      {/* Hero */}
      <div className="space-y-3">
        <p
          className="text-xs font-mono tracking-widest uppercase"
          style={{ color: CYAN }}
        >
          Research ist dein PRISMA-Assistent. Stelle Fragen auf Deutsch oder Englisch.
        </p>
        <p className="text-sm text-zinc-400 leading-relaxed">
          Frag PRISMA. Basierend auf Schweizer Geschäftsberichten,
          Makrodaten und deinem Universum.
        </p>
      </div>

      {/* Example chips */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => {
              setQuery(q);
              inputRef.current?.focus();
            }}
            className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-mono transition-colors hover:border-[#00d4ff] hover:text-[#00d4ff]"
            style={{ borderColor: 'rgba(0,212,255,0.25)', color: '#94a3b8' }}
          >
            <ChevronRight className="h-3 w-3" />
            {q}
          </button>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Frag PRISMA..."
          className="flex-1 rounded-md border px-4 py-2.5 text-sm font-mono bg-transparent outline-none focus:ring-1 transition-colors"
          style={{
            borderColor: query ? CYAN : 'rgba(255,255,255,0.12)',
            color: '#e2e8f0',
            caretColor: CYAN,
          }}
          data-testid="research-query-input"
        />
        <button
          type="submit"
          disabled={isPending || !query.trim()}
          className="inline-flex items-center gap-2 rounded-md px-4 py-2.5 text-sm font-mono font-medium disabled:opacity-40 transition-all"
          style={{ background: CYAN, color: '#090d12' }}
          data-testid="research-search-btn"
        >
          {isPending ? (
            <span className="animate-pulse">...</span>
          ) : (
            <>
              <Send className="h-4 w-4" />
              Senden
            </>
          )}
        </button>
      </form>

      {/* Response */}
      {summary !== null && (
        <div
          className="rounded-md border p-5 font-mono text-sm leading-relaxed"
          style={{ borderColor: 'rgba(0,212,255,0.2)', background: 'rgba(0,212,255,0.03)' }}
        >
          <span className="text-xs font-mono mb-3 block" style={{ color: CYAN }}>
            PRISMA
          </span>
          <TypewriterText text={summary} speed={18} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProModeView
// ---------------------------------------------------------------------------

function ProModeView({
  query,
  setQuery,
  onSubmit,
  isPending,
  swissResults,
  secResults,
  agentLog,
  summary,
}: {
  query: string;
  setQuery: (q: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isPending: boolean;
  swissResults: SwissChunkResult[] | null;
  secResults: SecChunkResult[] | null;
  agentLog: AgentLogEntry[];
  summary: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentLog]);

  const allSources: { label: string; url: string }[] = [
    ...(swissResults ?? []).slice(0, 4).map((r) => ({
      label: `${r.ticker} · ${r.doc_type} ${r.filing_date?.slice(0, 4) ?? ''}`,
      url: r.url ?? '#',
    })),
    ...(secResults ?? []).slice(0, 2).map((r) => ({
      label: `${r.ticker} · ${r.doc_type}`,
      url: '#',
    })),
  ];

  const completedSteps = agentLog.filter(
    (e): e is Extract<AgentLogEntry, { type: 'step' }> =>
      e.type === 'step' && e.done,
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      {/* ---- Left: Terminal chat ---- */}
      <div className="flex flex-col gap-4">
        {/* Agent log + response area */}
        <div
          className="rounded-md border min-h-[280px] p-5 font-mono text-sm flex flex-col gap-2 overflow-y-auto"
          style={{
            borderColor: 'rgba(0,212,255,0.15)',
            background: 'rgba(0,0,0,0.35)',
          }}
        >
          {agentLog.length === 0 && summary === null && (
            <span className="text-zinc-600 flex items-center gap-1">
              <span style={{ color: CYAN }}>{'>'}</span>{' '}
              <span className="animate-pulse">_</span>
            </span>
          )}

          {agentLog.map((entry, i) => {
            if (entry.type === 'ready') {
              return (
                <span key={i} className="text-zinc-400">
                  <span style={{ color: CYAN }}>{'>'}</span> Antwort bereit.
                </span>
              );
            }
            return (
              <span
                key={i}
                className={cn(
                  'flex items-center gap-2',
                  entry.done ? 'text-zinc-400' : 'text-zinc-500',
                )}
              >
                <span style={{ color: CYAN }}>{'>'}</span>
                <span className="w-28 shrink-0" style={{ color: entry.done ? '#94a3b8' : CYAN }}>
                  {entry.agent}
                </span>
                <span>{entry.done ? `✓ ${entry.duration}s` : entry.action}</span>
              </span>
            );
          })}

          {summary !== null && (
            <div className="mt-3 pt-3 border-t" style={{ borderColor: 'rgba(0,212,255,0.12)' }}>
              <span className="text-xs mb-1 block" style={{ color: CYAN }}>
                PRISMA
              </span>
              <TypewriterText text={summary} speed={18} />
            </div>
          )}

          <div ref={logEndRef} />
        </div>

        {/* Example chips */}
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUERIES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => {
                setQuery(q);
                inputRef.current?.focus();
              }}
              className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-mono transition-colors hover:border-[#00d4ff] hover:text-[#00d4ff]"
              style={{ borderColor: 'rgba(0,212,255,0.2)', color: '#64748b' }}
            >
              <ChevronRight className="h-3 w-3" />
              {q}
            </button>
          ))}
        </div>

        {/* Input row */}
        <form onSubmit={onSubmit} className="flex gap-2">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Frag PRISMA..."
            className="flex-1 rounded-md border px-4 py-2.5 text-sm font-mono bg-transparent outline-none focus:ring-1 transition-colors"
            style={{
              borderColor: query ? CYAN : 'rgba(255,255,255,0.1)',
              color: '#e2e8f0',
              caretColor: CYAN,
            }}
            data-testid="research-query-input"
          />
          <button
            type="submit"
            disabled={isPending || !query.trim()}
            className="inline-flex items-center gap-1.5 rounded-md px-4 py-2.5 text-sm font-mono font-medium disabled:opacity-40 transition-all"
            style={{ background: CYAN, color: '#090d12' }}
            data-testid="research-search-btn"
          >
            {isPending ? (
              <span className="animate-pulse">...</span>
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>

      {/* ---- Right: panels ---- */}
      <div className="flex flex-col gap-4 text-xs font-mono">
        {/* Sources */}
        <div
          className="rounded-md border p-4 space-y-2"
          style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
        >
          <p className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3">Quellen</p>
          {(allSources.length > 0 ? allSources : MOCK_SOURCES).map((s) => (
            <a
              key={s.label}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between gap-2 rounded px-2.5 py-1.5 border transition-colors hover:border-[#00d4ff] group"
              style={{ borderColor: 'rgba(255,255,255,0.07)', color: '#94a3b8' }}
            >
              <span className="truncate group-hover:text-[#00d4ff] transition-colors">
                {s.label}
              </span>
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          ))}
          {allSources.length > 0 && (
            <button
              onClick={() =>
                exportResearchCsv(
                  [...(swissResults ?? []), ...(secResults ?? [])],
                  `research-${new Date().toISOString().slice(0, 10)}.csv`,
                )
              }
              className="inline-flex items-center gap-1.5 mt-1 rounded px-2 py-1 border text-[10px] hover:text-[#00d4ff] hover:border-[#00d4ff] transition-colors w-full justify-center"
              style={{ borderColor: 'rgba(255,255,255,0.07)', color: '#64748b' }}
              data-testid="research-csv-export-btn"
            >
              <Download className="h-3 w-3" />
              CSV Export
            </button>
          )}
        </div>

        {/* Agent activity */}
        <div
          className="rounded-md border p-4 space-y-2"
          style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
        >
          <p className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3">
            Agent-Aktivitat
          </p>
          {AGENT_STEPS.map((step, i) => {
            const completed = completedSteps.find((e) => e.agent === step.agent);
            const running =
              agentLog.find(
                (e): e is Extract<AgentLogEntry, { type: 'step' }> =>
                  e.type === 'step' && e.agent === step.agent && !e.done,
              ) !== undefined;
            return (
              <div key={step.agent} className="flex items-center justify-between">
                <span style={{ color: completed ? '#94a3b8' : running ? CYAN : '#475569' }}>
                  {step.agent}
                </span>
                <span style={{ color: completed ? '#22c55e' : running ? CYAN : '#334155' }}>
                  {completed ? (
                    <span className="flex items-center gap-1">
                      <Check className="h-3 w-3" />
                      {completed.duration}s
                    </span>
                  ) : running ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    '—'
                  )}
                </span>
              </div>
            );
          })}
        </div>

        {/* Macro context */}
        <div
          className="rounded-md border p-4 space-y-2"
          style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
        >
          <p className="text-[10px] tracking-widest uppercase text-zinc-500 mb-3">Makro-Kontext</p>
          <div className="flex items-center justify-between text-zinc-400">
            <span>SNB</span>
            <span style={{ color: CYAN }}>{MOCK_MACRO.rate}</span>
          </div>
          <div className="flex items-center justify-between text-zinc-400">
            <span>CHF/EUR</span>
            <span style={{ color: CYAN }}>{MOCK_MACRO.fx}</span>
          </div>
          <p className="text-zinc-500 pt-1 border-t" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
            &ldquo;{MOCK_MACRO.sentiment}&rdquo;
          </p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ResearchClient (main export)
// ---------------------------------------------------------------------------

export function ResearchClient() {
  const searchParams = useSearchParams();
  const { mode, toggle } = usePrismaMode();

  const [query, setQuery] = useState(
    () => searchParams.get('q') ?? loadStoredResearch()?.query ?? '',
  );
  const [ticker] = useState(
    () => searchParams.get('ticker')?.toUpperCase() ?? loadStoredResearch()?.ticker ?? '',
  );
  const [swissLang] = useState<'' | 'de' | 'en' | 'fr'>(() => {
    const lang = searchParams.get('lang');
    return lang === 'de' || lang === 'en' || lang === 'fr' ? lang : '';
  });

  const [swissResults, setSwissResults] = useState<SwissChunkResult[] | null>(null);
  const [secResults, setSecResults] = useState<SecChunkResult[] | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [agentActive, setAgentActive] = useState(false);

  const agentLog = useAgentLog(agentActive);

  const swissMutation = useMutation({
    mutationFn: () =>
      retrieveSwissFilings({
        query,
        k: 10,
        ticker: ticker.trim() || undefined,
        language: swissLang || undefined,
      }),
    onSuccess: (data) => {
      setSwissResults(data.results);
      try {
        localStorage.setItem(LS_RESEARCH_KEY, JSON.stringify({ query, ticker }));
      } catch {}
    },
  });

  const secMutation = useMutation({
    mutationFn: () =>
      retrieveSecFilings({ query, k: 10, ticker: ticker.trim() || undefined }),
    onSuccess: (data) => {
      setSecResults(data.results);
      try {
        localStorage.setItem(LS_RESEARCH_KEY, JSON.stringify({ query, ticker }));
      } catch {}
    },
  });

  // Derive summary whenever both mutations settle
  useEffect(() => {
    const swissDone = !swissMutation.isPending && swissMutation.isSuccess;
    const secDone = !secMutation.isPending && secMutation.isSuccess;
    if (swissDone || secDone) {
      setSummary(buildSummary(swissResults, secResults, query));
      setAgentActive(false);
    }
  }, [
    swissMutation.isPending,
    swissMutation.isSuccess,
    secMutation.isPending,
    secMutation.isSuccess,
    swissResults,
    secResults,
    query,
  ]);

  const isPending = swissMutation.isPending || secMutation.isPending;

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!query.trim()) return;
      setSummary(null);
      setSwissResults(null);
      setSecResults(null);
      setAgentActive(true);
      swissMutation.mutate();
      secMutation.mutate();
    },
    [query, swissMutation, secMutation],
  );

  return (
    <div
      className="min-h-screen"
      style={{
        background:
          'radial-gradient(ellipse at 50% 0%, rgba(0,212,255,0.05) 0%, transparent 70%), #090d12',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      }}
    >
      {/* Top bar */}
      <div className="max-w-5xl mx-auto px-6 pt-10 pb-6">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Terminal className="h-5 w-5" style={{ color: CYAN }} />
            <span className="text-xs tracking-widest uppercase text-zinc-500 font-mono">
              PRISMA · Research
            </span>
          </div>
          {/* Mode toggle */}
          <button
            type="button"
            onClick={toggle}
            className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-mono transition-colors hover:border-[#00d4ff]"
            style={{
              borderColor: mode === 'pro' ? CYAN : 'rgba(255,255,255,0.12)',
              color: mode === 'pro' ? CYAN : '#64748b',
            }}
          >
            {mode === 'pro' ? 'Pro Mode' : 'Simple Mode'}
          </button>
        </div>

        <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Research.</h1>

        {mode === 'simple' ? (
          <SimpleModeView
            query={query}
            setQuery={setQuery}
            onSubmit={handleSubmit}
            isPending={isPending}
            summary={summary}
          />
        ) : (
          <ProModeView
            query={query}
            setQuery={setQuery}
            onSubmit={handleSubmit}
            isPending={isPending}
            swissResults={swissResults}
            secResults={secResults}
            agentLog={agentLog}
            summary={summary}
          />
        )}
      </div>
    </div>
  );
}
