'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Terminal, Send, RotateCcw, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { streamChat, type ChatHistoryMessage, type SSEEvent } from '@/lib/api/chat';
import { getMacroContext } from '@/lib/api/macro';
import { retrieveSwissFilings, type SwissChunkResult } from '@/lib/api/rag';
import { parseMessageWithTickers } from '@/components/chat/TickerChip';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { Badge } from '@/components/ui/badge';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CYAN = '#00d4ff';

const EXAMPLE_QUERIES = [
  'Soll ich Novartis kaufen?',
  'Welche SMI-Aktie hat das beste BUY-Signal?',
  'Was bedeutet der SNB-Entscheid für mein Portfolio?',
  'Vergleiche Roche und Nestlé',
  'Wie vermeide ich Klumpenrisiko?',
];

const TOOL_LABELS: Record<string, string> = {
  search_stocks: 'Aktiensuche',
  filter_stocks: 'Aktienfilter',
  get_factsheet: 'Factsheet',
  get_macro_context: 'Makro-Kontext',
  compare_stocks: 'Vergleich',
  get_ranking: 'Ranking',
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ToolEntry {
  tool: string;
  startMs: number;
  doneMs?: number;
}

interface SessionMetrics {
  startMs: number;
  endMs?: number;
  charCount: number;
}

// ---------------------------------------------------------------------------
// MacroPanel — live macro data with fallback
// ---------------------------------------------------------------------------

function MacroPanel() {
  const { data, isError } = useQuery({
    queryKey: ['macro-context'],
    queryFn: getMacroContext,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });

  const rate = data ? `${data.leitzins.toFixed(2)}%` : '—';
  const fx = data ? data.chf_eur.toFixed(3) : '—';
  const sentiment = data?.narrative_de ?? null;
  const isLive = !!data && !isError;

  return (
    <div
      className="rounded-md border p-4 space-y-2"
      style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] tracking-widest uppercase text-muted-foreground">Makro-Kontext</p>
        {!isLive && (
          <Badge
            variant="warning"
            className="text-[9px] py-0 px-1.5 normal-case font-mono"
            data-testid="research-macro-demo-badge"
          >
            Beispieldaten
          </Badge>
        )}
      </div>
      <div className="flex items-center justify-between text-muted-foreground">
        <span>SNB</span>
        <span style={{ color: CYAN }}>{rate}</span>
      </div>
      <div className="flex items-center justify-between text-muted-foreground">
        <span>CHF/EUR</span>
        <span style={{ color: CYAN }}>{fx}</span>
      </div>
      {sentiment && (
        <p
          className="text-muted-foreground text-[10px] pt-1 border-t leading-relaxed"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}
        >
          &ldquo;{sentiment}&rdquo;
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AgentPanel — real tool-call log from SSE stream
// ---------------------------------------------------------------------------

function AgentPanel({ toolLog, streaming }: { toolLog: ToolEntry[]; streaming: boolean }) {
  return (
    <div
      className="rounded-md border p-4 space-y-2"
      style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
    >
      <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-3">
        Agent-Aktivität
      </p>
      {toolLog.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">Warte auf Anfrage…</p>
      ) : (
        toolLog.map((t, i) => {
          const duration = t.doneMs ? ((t.doneMs - t.startMs) / 1000).toFixed(1) : null;
          const label = TOOL_LABELS[t.tool] ?? t.tool;
          return (
            <div key={i} className="flex items-center justify-between text-[11px] font-mono">
              <span style={{ color: t.doneMs ? '#7ee787' : CYAN }}>
                {t.doneMs ? '✓' : streaming ? '⟳' : '·'} {label}
              </span>
              {duration ? (
                <span className="text-muted-foreground">{duration}s</span>
              ) : (
                !t.doneMs && streaming && (
                  <span className="text-muted-foreground animate-pulse">…</span>
                )
              )}
            </div>
          );
        })
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricsPanel — antwortzeit, tokens, geschätzte kosten
// ---------------------------------------------------------------------------

function MetricsPanel({
  metrics,
  toolLog,
}: {
  metrics: SessionMetrics | null;
  toolLog: ToolEntry[];
}) {
  return (
    <div
      className="rounded-md border p-4 space-y-2"
      style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
    >
      <p className="text-[10px] tracking-widest uppercase text-muted-foreground mb-3">Metriken</p>
      {!metrics ? (
        <p className="text-[11px] text-muted-foreground">Noch keine Anfrage.</p>
      ) : (
        <div className="space-y-1.5 font-mono text-[11px]">
          {metrics.endMs && (
            <div className="flex justify-between text-muted-foreground">
              <span>Antwortzeit</span>
              <span style={{ color: CYAN }}>
                {((metrics.endMs - metrics.startMs) / 1000).toFixed(1)}s
              </span>
            </div>
          )}
          <div className="flex justify-between text-muted-foreground">
            <span>Tools genutzt</span>
            <span style={{ color: CYAN }}>{toolLog.length}</span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Tokens (est.)</span>
            <span style={{ color: CYAN }}>
              ~{Math.round(metrics.charCount / 3.5).toLocaleString('de-CH')}
            </span>
          </div>
          <div className="flex justify-between text-muted-foreground">
            <span>Kosten (est.)</span>
            <span style={{ color: CYAN }}>
              ~CHF {(Math.round(metrics.charCount / 3.5) * 0.000015).toFixed(4)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RagPanel — collapsible, ready for future document indexing
// ---------------------------------------------------------------------------

function RagPanel() {
  const [open, setOpen] = useState(false);
  const [ragQuery, setRagQuery] = useState('');

  const ragMutation = useMutation({
    mutationFn: () => retrieveSwissFilings({ query: ragQuery, k: 5 }),
  });

  const results: SwissChunkResult[] = ragMutation.isSuccess ? ragMutation.data.results : [];

  return (
    <div
      className="rounded-md border overflow-hidden"
      style={{ borderColor: 'rgba(0,212,255,0.12)', background: 'rgba(0,0,0,0.2)' }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-[10px] tracking-widest uppercase text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>Dokument-Suche (RAG)</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {open && (
        <div
          className="px-4 pb-4 space-y-3 border-t"
          style={{ borderColor: 'rgba(0,212,255,0.08)' }}
        >
          <p className="text-[10px] text-muted-foreground pt-3 leading-relaxed">
            Vektor-Suche in Geschäftsberichten und Filings. Indexiere Berichte via CLI um diese
            Funktion zu aktivieren.
          </p>
          <div className="flex gap-2">
            <input
              value={ragQuery}
              onChange={(e) => setRagQuery(e.target.value)}
              onKeyDown={(e) =>
                e.key === 'Enter' && ragQuery.length >= 3 && ragMutation.mutate()
              }
              placeholder="Suche in Berichten…"
              className="flex-1 bg-transparent text-[11px] border rounded px-2 py-1.5 text-muted-foreground placeholder-slate-700 outline-none focus:border-cyan-500/40"
              style={{ borderColor: 'rgba(0,212,255,0.15)' }}
            />
            <button
              onClick={() => ragMutation.mutate()}
              disabled={ragQuery.length < 3 || ragMutation.isPending}
              className="text-[10px] px-3 py-1.5 rounded border disabled:opacity-30 transition-colors hover:border-cyan-500/40"
              style={{ borderColor: 'rgba(0,212,255,0.2)', color: CYAN }}
            >
              {ragMutation.isPending ? '…' : 'Suchen'}
            </button>
          </div>

          {ragMutation.isSuccess && results.length === 0 && (
            <p className="text-[10px] text-amber-400/70">
              Keine Dokumente gefunden. Indexiere zuerst Berichte via{' '}
              <code className="font-mono">python -m backend.scripts.ingest</code>.
            </p>
          )}

          {results.map((r, i) => (
            <a
              key={i}
              href={r.url ?? '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between gap-2 rounded px-2.5 py-1.5 border transition-colors hover:border-cyan-500/40 group"
              style={{ borderColor: 'rgba(255,255,255,0.07)', color: '#94a3b8' }}
            >
              <span className="truncate text-[10px] group-hover:text-cyan-400 transition-colors">
                {r.ticker} · {r.doc_type} {r.filing_date?.slice(0, 4) ?? ''}
              </span>
              <ExternalLink className="h-3 w-3 shrink-0" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatArea — streaming messages + input
// ---------------------------------------------------------------------------

function ChatArea({
  messages,
  streaming,
  toolHint,
  onSend,
  input,
  setInput,
  onReset,
}: {
  messages: Message[];
  streaming: boolean;
  toolHint: string | null;
  onSend: (text: string) => void;
  input: string;
  setInput: (v: string) => void;
  onReset: () => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, toolHint]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4" style={{ color: CYAN }} />
          <span className="text-xs tracking-widest uppercase text-muted-foreground">
            PRISMA · Research
          </span>
        </div>
        {messages.length > 0 && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Neu
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 pr-1 mb-4" style={{ minHeight: 0 }}>
        {messages.length === 0 ? (
          <div className="space-y-6 pt-2">
            <div>
              <h1
                className="text-4xl font-bold tracking-tight mb-2"
                style={{ fontFamily: "'JetBrains Mono', monospace" }}
              >
                Research<span style={{ color: CYAN }}>.</span>
              </h1>
              <p className="text-sm text-muted-foreground">
                KI-Assistent mit echten PRISMA-Daten. Frag auf Deutsch oder Englisch.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => onSend(q)}
                  className="flex items-center gap-2 text-left text-xs px-3 py-2.5 rounded-lg border transition-all text-muted-foreground hover:text-foreground"
                  style={{
                    borderColor: 'rgba(0,212,255,0.15)',
                    background: 'rgba(0,212,255,0.02)',
                  }}
                >
                  <span style={{ color: CYAN }}>&gt;</span>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => {
            const isLast = i === messages.length - 1;
            const isUser = msg.role === 'user';
            return (
              <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                <div
                  className="max-w-[90%] rounded-xl px-4 py-3 text-sm leading-relaxed"
                  style={
                    isUser
                      ? {
                          background: 'rgba(0,212,255,0.1)',
                          border: '1px solid rgba(0,212,255,0.2)',
                          color: '#e6edf3',
                        }
                      : {
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(255,255,255,0.08)',
                          color: '#c9d1d9',
                        }
                  }
                >
                  {!isUser && isLast && streaming && toolHint && (
                    <p className="text-[10px] italic mb-2 font-mono" style={{ color: CYAN + 'aa' }}>
                      {toolHint}
                    </p>
                  )}
                  <p className="whitespace-pre-wrap">
                    {isUser ? msg.content : parseMessageWithTickers(msg.content)}
                    {!isUser && isLast && streaming && (
                      <span
                        className="inline-block w-1.5 h-4 ml-0.5 align-middle animate-pulse"
                        style={{ background: CYAN }}
                      />
                    )}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Input */}
      <div
        className="rounded-xl border px-4 py-3 flex items-center gap-3 transition-colors focus-within:border-cyan-500/40"
        style={{ borderColor: 'rgba(0,212,255,0.2)', background: 'rgba(0,0,0,0.3)' }}
      >
        <input
          data-testid="research-query-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) =>
            e.key === 'Enter' && !e.shiftKey && !streaming && onSend(input)
          }
          placeholder="Stelle eine Frage zu Aktien, Makro oder Rankings…"
          disabled={streaming}
          className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 outline-none"
        />
        <button
          data-testid="research-search-btn"
          onClick={() => onSend(input)}
          disabled={!input.trim() || streaming}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg disabled:opacity-30 transition-all font-mono"
          style={{
            background: 'rgba(0,212,255,0.12)',
            color: CYAN,
            border: '1px solid rgba(0,212,255,0.25)',
          }}
        >
          <Send className="h-3.5 w-3.5" />
          {streaming ? 'Lädt…' : 'Senden'}
        </button>
      </div>
      <p className="text-[10px] text-muted-foreground mt-2 text-center">
        Keine Anlageberatung — PRISMA-Signale sind modellbasiert.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ResearchClient — main export
// ---------------------------------------------------------------------------

export function ResearchClient() {
  const { mode } = usePrismaMode();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [toolHint, setToolHint] = useState<string | null>(null);
  const [toolLog, setToolLog] = useState<ToolEntry[]>([]);
  const [metrics, setMetrics] = useState<SessionMetrics | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || streaming) return;

      const history: ChatHistoryMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      setMessages((prev) => [
        ...prev,
        { role: 'user', content: text },
        { role: 'assistant', content: '' },
      ]);
      setStreaming(true);
      setInput('');
      setToolHint(null);
      setToolLog([]);

      const startMs = Date.now();
      setMetrics({ startMs, charCount: 0 });

      abortRef.current = streamChat(
        text,
        history,
        (evt: SSEEvent) => {
          if (evt.type === 'token' && evt.content) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + evt.content,
              };
              return updated;
            });
            setMetrics((m) =>
              m ? { ...m, charCount: m.charCount + (evt.content?.length ?? 0) } : m,
            );
            setToolHint(null);
          } else if (evt.type === 'tool_call' && evt.tool) {
            const label = TOOL_LABELS[evt.tool] ?? evt.tool;
            setToolHint(`${label} wird abgefragt…`);
            setToolLog((prev) => [...prev, { tool: evt.tool!, startMs: Date.now() }]);
          } else if (evt.type === 'tool_result' && evt.tool) {
            setToolLog((prev) =>
              prev.map((t) =>
                t.tool === evt.tool && !t.doneMs ? { ...t, doneMs: Date.now() } : t,
              ),
            );
          }
        },
        () => {
          setStreaming(false);
          setToolHint(null);
          setMetrics((m) => (m ? { ...m, endMs: Date.now() } : m));
        },
        (msg) => {
          setStreaming(false);
          setToolHint(null);
          setMetrics((m) => (m ? { ...m, endMs: Date.now() } : m));
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Fehler: ${msg}`,
            };
            return updated;
          });
        },
      );
    },
    [messages, streaming],
  );

  const reset = useCallback(() => {
    abortRef.current?.();
    setMessages([]);
    setInput('');
    setStreaming(false);
    setToolHint(null);
    setToolLog([]);
    setMetrics(null);
  }, []);

  if (mode === 'simple') {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 h-[calc(100vh-120px)] flex flex-col">
        <ChatArea
          messages={messages}
          streaming={streaming}
          toolHint={toolHint}
          onSend={sendMessage}
          input={input}
          setInput={setInput}
          onReset={reset}
        />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen"
      style={{
        background:
          'radial-gradient(ellipse at 50% 0%, rgba(0,212,255,0.05) 0%, transparent 70%), #090d12',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
      }}
    >
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6 h-[calc(100vh-120px)]">
          {/* Left: Chat */}
          <ChatArea
            messages={messages}
            streaming={streaming}
            toolHint={toolHint}
            onSend={sendMessage}
            input={input}
            setInput={setInput}
            onReset={reset}
          />

          {/* Right: Panels */}
          <div className="flex flex-col gap-4 overflow-y-auto text-xs font-mono">
            <MacroPanel />
            <AgentPanel toolLog={toolLog} streaming={streaming} />
            <MetricsPanel metrics={metrics} toolLog={toolLog} />
            <RagPanel />
          </div>
        </div>
      </div>
    </div>
  );
}
