'use client';

import { Fragment, Suspense, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import {
  ArrowLeft,
  Bell,
  FileSearch,
  BookOpen,
  TrendingUp,
  Minus,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Bookmark,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { apiFetch } from '@/lib/api/client';
import {
  getFactsheet,
  getLangfristScore,
  getPrices,
  type LangfristScore,
} from '@/lib/api/stocks';
import { getDividends, type DividendData } from '@/lib/api/dividends';
import { getFundamentals } from '@/lib/api/fundamentals';
import { getAuditTrail, type AuditRecord } from '@/lib/api/audit';
import { getMLPrediction, type MLPredictResponse } from '@/lib/api/ml';
import { FundamentalsCard } from '@/components/factsheet/FundamentalsCard';
import { NewsPanel } from '@/components/factsheet/NewsPanel';
import { SteuerPanel } from '@/components/factsheet/SteuerPanel';
import { PriceChart } from '@/components/factsheet/PriceChart';
import { AuditPanel } from '@/components/factsheet/AuditPanel';
import { MLPanel } from '@/components/factsheet/MLPanel';
import { MemoPanel } from '@/components/factsheet/MemoPanel';
import { SwissBadge } from '@/components/ui/swiss-badge';
import { cn } from '@/lib/utils';
import { usePrismaMode } from '@/hooks/usePrismaMode';

// ─── Types ─────────────────────────────────────────────────────────────────

type Signal = 'BUY' | 'HOLD' | 'SELL';

interface SignalValidation {
  ticker: string;
  return_pct: number;
  buy_and_hold_pct: number;
  win_rate_pct: number;
  label: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatPrice(price: number, currency: string): string {
  return `${currency} ${price.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

const SIGNAL_STYLE: Record<Signal, { bg: string; text: string; border: string; Icon: React.ComponentType<{ className?: string }>; rotate?: string }> = {
  BUY:  { bg: 'bg-[#0d2d1a]', text: 'text-[#7ee787]', border: 'border-[#7ee787]/30', Icon: TrendingUp },
  HOLD: { bg: 'bg-[#2d1a0d]', text: 'text-[#ffa657]', border: 'border-[#ffa657]/30', Icon: Minus },
  SELL: { bg: 'bg-[#2d0d0d]', text: 'text-[#f85149]', border: 'border-[#f85149]/30', Icon: TrendingUp, rotate: 'rotate-180' },
};

function HeroSignalBadge({ signal, score }: { signal: Signal; score: number }) {
  const cfg = SIGNAL_STYLE[signal] ?? SIGNAL_STYLE.HOLD;
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-5 py-2 text-lg font-bold tracking-wide',
        cfg.bg, cfg.text, cfg.border,
      )}
    >
      <cfg.Icon className={cn('h-5 w-5', cfg.rotate)} aria-hidden />
      <span>{signal}</span>
      <span className="opacity-70 font-normal text-base">Score {score}/100</span>
    </div>
  );
}

// ─── Zone 2: Warum-Sektion ──────────────────────────────────────────────────

interface ShapFactor {
  label: string;
  value: string;
  note?: string;
  positive: boolean;
}

function WarumSection({ signal, ticker, auditRecord, mlData }: {
  signal: Signal;
  ticker: string;
  auditRecord?: AuditRecord;
  mlData?: MLPredictResponse;
}) {
  const { data: validationData, isLoading: validationLoading } = useQuery({
    queryKey: ['signal-validation', ticker],
    queryFn: async () => {
      try {
        return await apiFetch<SignalValidation>(`/api/v1/backtest/signal-validation/${ticker}`);
      } catch {
        return null;
      }
    },
    retry: false,
    staleTime: 10 * 60 * 1000,
  });

  // Build top factors from SHAP or audit scores
  const factors: ShapFactor[] = [];

  if (mlData?.shap_values && mlData.shap_values.length > 0) {
    const sorted = [...mlData.shap_values].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value)).slice(0, 3);
    for (const sv of sorted) {
      factors.push({
        label: sv.label,
        value: sv.shap_value.toFixed(2),
        positive: sv.shap_value > 0,
      });
    }
  } else if (auditRecord) {
    if (auditRecord.quant_score >= 65) {
      factors.push({ label: 'Quant-Score', value: `${auditRecord.quant_score.toFixed(0)}/100`, positive: true });
    } else {
      factors.push({ label: 'Quant-Score', value: `${auditRecord.quant_score.toFixed(0)}/100`, positive: false, note: 'unter Schwellenwert' });
    }
    if (auditRecord.ml_score >= 65) {
      factors.push({ label: 'KI-Modell', value: `${auditRecord.ml_score.toFixed(0)}/100`, positive: true });
    } else {
      factors.push({ label: 'KI-Modell', value: `${auditRecord.ml_score.toFixed(0)}/100`, positive: false });
    }
    if (auditRecord.macro_score >= 65) {
      factors.push({ label: 'Makro-Umfeld', value: `${auditRecord.macro_score.toFixed(0)}/100`, positive: true });
    } else {
      factors.push({ label: 'Makro-Umfeld', value: `${auditRecord.macro_score.toFixed(0)}/100`, positive: false, note: 'vorsichtig' });
    }
  }

  const hasValidation = validationData && !validationLoading;
  const validationIsNull = !validationLoading && validationData === null;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">
        Warum empfiehlt PRISMA {signal}?
      </h2>

      {factors.length > 0 && (
        <ul className="space-y-2">
          {factors.map((f, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              {f.positive
                ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                : <XCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
              }
              <span>
                <span className="font-medium">{f.label}:</span>{' '}
                <span>{f.value}</span>
                {f.note && <span className="text-muted-foreground"> — {f.note}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}

      {auditRecord && (
        <div className="rounded-md border bg-muted/30 p-3 text-sm space-y-1">
          <p className="font-medium text-muted-foreground text-xs uppercase tracking-wide">Sicherheits-Check</p>
          {auditRecord.explanation_de && (
            <p className="text-muted-foreground text-xs leading-relaxed">{auditRecord.explanation_de}</p>
          )}
        </div>
      )}

      {validationLoading && (
        <div className="rounded-md border p-3 text-sm text-muted-foreground animate-pulse">
          Historische Analyse wird geladen...
        </div>
      )}

      {hasValidation && validationData && (
        <div className="rounded-md border bg-muted/30 p-3 text-sm space-y-1">
          <p className="font-medium text-muted-foreground text-xs uppercase tracking-wide">Signal-Validierung</p>
          <p className="text-sm">
            Wenn du PRISMA&apos;s {signal}-Signalen in den letzten 3 Jahren gefolgt wärst:
          </p>
          <p className="font-medium">
            Rendite {formatPct(validationData.return_pct)} &middot; vs. Buy&Hold {formatPct(validationData.buy_and_hold_pct)} &middot; Gewinn-Trades {validationData.win_rate_pct.toFixed(0)}%
          </p>
          <p className="text-xs text-muted-foreground">{validationData.label}</p>
        </div>
      )}

      {/* validationIsNull: section is simply hidden — no error shown */}
      {validationIsNull && null}
    </div>
  );
}

// ─── Accordion item ─────────────────────────────────────────────────────────

function AccordionItem({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50 transition-colors"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
          {title}
        </span>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-2 border-t">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Steuer Zone 3 panel ─────────────────────────────────────────────────────

function SteuerZone3({ dividendData }: { dividendData?: DividendData | null }) {
  if (!dividendData || dividendData.last_dividend_chf === null) {
    return (
      <p className="text-sm text-muted-foreground">Dividendendaten werden geladen...</p>
    );
  }

  const gross = dividendData.last_dividend_chf;
  const vst = gross * 0.35;
  const netto = gross - vst;

  return (
    <div className="space-y-3 text-sm">
      <p className="font-medium">Was bleibt dir wirklich?</p>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
        <dt className="text-muted-foreground">Dividende</dt>
        <dd className="font-mono text-right">CHF {gross.toFixed(2)} pro Aktie</dd>
        <dt className="text-muted-foreground">Verrechnungssteuer</dt>
        <dd className="font-mono text-right text-red-500">− CHF {vst.toFixed(2)} (35%)</dd>
        <dt className="text-muted-foreground">Netto Dividende</dt>
        <dd className="font-mono text-right font-semibold">CHF {netto.toFixed(2)}</dd>
      </dl>
      <div className="rounded-md bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 p-3 text-xs text-emerald-800 dark:text-emerald-300">
        <span className="font-medium">Rückforderbar: CHF {vst.toFixed(2)}</span>
        <br />
        Als Schweizer Privatanleger kannst du die Verrechnungssteuer vollständig zurückfordern.
      </div>
    </div>
  );
}

// ─── Main content ────────────────────────────────────────────────────────────

function FactsheetContent() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';
  const symbol = ticker.toUpperCase();

  const { mode, isSimple } = usePrismaMode();

  const [watchlistAdded, setWatchlistAdded] = useState(false);
  const [memoOpen, setMemoOpen] = useState(false);
  const [stockId, setStockId] = useState<string | null>(null);
  const [memoError, setMemoError] = useState<string | null>(null);
  const [memoLoading, setMemoLoading] = useState(false);

  const { data: factsheet, error: factsheetError } = useQuery({
    queryKey: ['factsheet', symbol],
    queryFn: () => getFactsheet(symbol),
    retry: 1,
  });

  const { data: auditData } = useQuery({
    queryKey: ['audit', symbol],
    queryFn: () => getAuditTrail(symbol),
    retry: false,
  });

  const { data: mlData } = useQuery({
    queryKey: ['ml-predict', symbol],
    queryFn: () => getMLPrediction(symbol),
    retry: false,
  });

  const { data: dividendData } = useQuery({
    queryKey: ['dividends', symbol],
    queryFn: () => getDividends(symbol),
    retry: 1,
    staleTime: 5 * 60 * 1_000,
  });

  const { data: fundamentalsData } = useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => getFundamentals(symbol),
    retry: 1,
    staleTime: 5 * 60 * 1_000,
  });

  const { data: prices } = useQuery({
    queryKey: ['prices', symbol],
    queryFn: () => getPrices(symbol),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const { data: langfrist } = useQuery({
    queryKey: ['langfrist-score', symbol],
    queryFn: () => getLangfristScore(symbol),
    retry: 1,
  });

  // Resolve stockId from factsheet or by lookup
  const resolvedStockId = factsheet?.stock?.id ?? stockId;

  // Determine signal from audit trail
  const latestAudit: AuditRecord | undefined = auditData?.records?.[0];
  const rawSignal = latestAudit?.signal ?? null;
  // Normalize: only BUY/HOLD/SELL allowed
  const signal: Signal | null = rawSignal === 'BUY' || rawSignal === 'HOLD' || rawSignal === 'SELL'
    ? rawSignal
    : null;
  const score = latestAudit ? Math.round(latestAudit.weighted_score) : null;

  // Prices: last price and daily change
  const priceList = prices?.prices ?? [];
  const lastPrice = priceList.length > 0
    ? priceList[priceList.length - 1].close
    : null;
  const prevPrice = priceList.length > 1
    ? priceList[priceList.length - 2].close
    : null;
  const dailyChangePct = lastPrice && prevPrice
    ? ((lastPrice - prevPrice) / prevPrice) * 100
    : null;

  const currency = factsheet?.stock?.currency ?? 'CHF';
  const stockName = factsheet?.stock?.name ?? symbol;

  // signal_reason: from audit explanation_de (always visible in Zone 1)
  const signalReason = latestAudit?.explanation_de ?? null;

  const handleWatchlist = () => {
    const existing = JSON.parse(localStorage.getItem('prisma-watchlist') ?? '[]') as string[];
    if (!existing.includes(symbol)) {
      localStorage.setItem('prisma-watchlist', JSON.stringify([...existing, symbol]));
    }
    setWatchlistAdded(true);
  };

  const handleMemoLesen = async () => {
    setMemoOpen(true);
    // If we don't have stockId yet, fetch it
    if (!resolvedStockId) {
      try {
        setMemoLoading(true);
        const stock = await apiFetch<{ id: string }>(`/api/v1/stocks/${symbol}`);
        setStockId(stock.id);
      } catch (err) {
        setMemoError(err instanceof Error ? err.message : 'Fehler beim Laden');
      } finally {
        setMemoLoading(false);
      }
    }
  };

  const hasError = factsheetError;

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-12">
      {/* ── Nav ── */}
      <div className="flex items-center justify-between">
        <Link
          href={runId ? `/rankings/${runId}` : '/discover'}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          {runId ? 'Zurück' : 'Mein Universe'}
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href={`/research?ticker=${symbol}`}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            data-testid="research-link"
          >
            <FileSearch className="h-3.5 w-3.5" />
            CH-Filings
          </Link>
        </div>
      </div>

      {hasError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Einige Daten konnten nicht geladen werden. Bitte Seite neu laden.
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════
          ZONE 1 — Above the fold
          ═══════════════════════════════════════════════════════════ */}
      <div className="rounded-xl border bg-card p-5 space-y-4">
        {/* Stock identity + price */}
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-bold" data-testid="factsheet-ticker">
              {stockName}
            </h1>
            <span className="font-mono text-sm text-muted-foreground">{symbol}</span>
            {factsheet?.stock && <SwissBadge exchange={factsheet.stock.exchange} />}
          </div>
          {lastPrice !== null && (
            <div className="flex items-baseline gap-2" data-testid="factsheet-metrics">
              <span className="text-2xl font-semibold tabular-nums">
                {formatPrice(lastPrice, currency)}
              </span>
              {dailyChangePct !== null && (
                <span
                  className={cn(
                    'text-sm font-medium tabular-nums',
                    dailyChangePct >= 0 ? 'text-emerald-500' : 'text-red-500',
                  )}
                >
                  {formatPct(dailyChangePct)} heute
                </span>
              )}
            </div>
          )}
        </div>

        {/* Signal badge */}
        {signal && score !== null && (
          <HeroSignalBadge signal={signal} score={score} />
        )}

        {/* signal_reason — ALWAYS visible, never behind a click */}
        {signalReason && (
          <blockquote className="border-l-4 border-primary/40 pl-3 text-sm text-muted-foreground italic leading-relaxed">
            {signalReason}
          </blockquote>
        )}

        {/* 3 CTA buttons */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleWatchlist}
            data-testid="watchlist-btn"
            className={cn(watchlistAdded && 'text-emerald-600 border-emerald-500')}
          >
            <Bookmark className="h-4 w-4 mr-1.5" />
            {watchlistAdded ? 'Auf Watchlist' : '+ Zur Watchlist'}
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={handleMemoLesen}
            data-testid="request-memo-btn"
            // NEVER disabled — no disabled prop here
          >
            <FileText className="h-4 w-4 mr-1.5" />
            {memoLoading ? 'Wird geladen…' : 'Memo lesen'}
          </Button>

          <Button
            variant="outline"
            size="sm"
            asChild
            data-testid="create-alert-link"
          >
            <Link href={`/alerts?ticker=${symbol}`}>
              <Bell className="h-4 w-4 mr-1.5" />
              Alert setzen
            </Link>
          </Button>
        </div>

        {memoError && (
          <p className="text-xs text-destructive">{memoError}</p>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════
          ZONE 2 — One scroll: Warum empfiehlt PRISMA X?
          ═══════════════════════════════════════════════════════════ */}
      {signal && (
        <div className="rounded-xl border bg-card p-5">
          <WarumSection
            signal={signal}
            ticker={symbol}
            auditRecord={latestAudit}
            mlData={mlData ?? undefined}
          />
        </div>
      )}

      {/* Price chart between zones */}
      {prices && (
        <PriceChart ticker={symbol} prices={prices.prices} />
      )}

      {/* ═══════════════════════════════════════════════════════════
          ZONE 3 — Expandable sections
          ═══════════════════════════════════════════════════════════ */}
      <div className="space-y-2">
        {/* Memo inline (opened when "Memo lesen" is clicked) */}
        {memoOpen && (resolvedStockId ? (
          <AccordionItem title="KI-Analyse (Memo)" icon={FileText} defaultOpen>
            <MemoPanel stockId={resolvedStockId} runId={runId} />
          </AccordionItem>
        ) : (
          <div className="rounded-lg border p-4 text-sm text-muted-foreground">
            Memo wird geladen...
          </div>
        ))}

        {/* Vollständige Analyse — both modes */}
        <AccordionItem title="Vollständige Analyse" icon={BookOpen}>
          <div className="space-y-4">
            {langfrist && (
              <LangfristCard score={langfrist} />
            )}
            {fundamentalsData && (
              <FundamentalsCard data={fundamentalsData} />
            )}
          </div>
        </AccordionItem>

        {/* News — both modes */}
        <AccordionItem title="News" icon={undefined}>
          <NewsPanel ticker={symbol} />
        </AccordionItem>

        {/* Steuer — both modes */}
        <AccordionItem title="Steuer" icon={undefined}>
          <SteuerZone3 dividendData={dividendData} />
        </AccordionItem>

        {/* Pro-only sections */}
        {!isSimple && (
          <>
            <AccordionItem title="SHAP-Analyse" icon={undefined}>
              <MLPanel ticker={symbol} />
            </AccordionItem>

            <AccordionItem title="Audit-Trail" icon={undefined}>
              <AuditPanel ticker={symbol} />
            </AccordionItem>

            <AccordionItem title="Fundamentals (Detail)" icon={undefined}>
              {fundamentalsData ? (
                <FundamentalsCard data={fundamentalsData} />
              ) : (
                <p className="text-sm text-muted-foreground">Keine Fundamentaldaten verfügbar.</p>
              )}
            </AccordionItem>

            <AccordionItem title="Steuer (Erweitert)" icon={undefined}>
              <SteuerPanel ticker={symbol} />
            </AccordionItem>
          </>
        )}
      </div>

      {/* Mode indicator */}
      <p className="text-center text-xs text-muted-foreground">
        Modus: {mode === 'simple' ? 'Einfach' : 'Pro'} — über Einstellungen ändern
      </p>
    </div>
  );
}

// ─── Langfrist card (kept local) ─────────────────────────────────────────────

function scoreColor(value: number): string {
  if (value >= 7.5) return 'text-emerald-600 dark:text-emerald-400';
  if (value >= 5.0) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function LangfristCard({ score }: { score: LangfristScore }) {
  const componentLabels: Record<string, string> = {
    dividende: 'Dividende',
    bilanz: 'Bilanz',
    stabilitaet: 'Stabilität',
    marktkapita: 'Marktgrösse',
  };
  return (
    <Card data-testid="langfrist-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">VIAC Langfrist-Score</CardTitle>
          <span className={`text-2xl font-bold tabular-nums ${scoreColor(score.value)}`}>
            {score.value.toFixed(1)}<span className="text-sm font-normal text-muted-foreground">/10</span>
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {Object.entries(score.components).map(([key, val]) => (
            <Fragment key={key}>
              <dt className="text-muted-foreground">{componentLabels[key] ?? key}</dt>
              <dd className={`font-medium ${scoreColor(val)}`}>{val.toFixed(1)}</dd>
            </Fragment>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">{score.disclaimer}</p>
      </CardContent>
    </Card>
  );
}

// ─── Skeleton ───────────────────────────────────────────────────────────────

function FactsheetSkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="h-5 w-32 rounded bg-muted animate-pulse" />
      <div className="h-48 rounded-xl bg-muted animate-pulse" />
      <div className="h-36 rounded-xl bg-muted animate-pulse" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    </div>
  );
}

// ─── Page export ─────────────────────────────────────────────────────────────

export default function StockFactsheetPage() {
  return (
    <Suspense fallback={<FactsheetSkeleton />}>
      <FactsheetContent />
    </Suspense>
  );
}
