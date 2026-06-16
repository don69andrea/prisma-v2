'use client';

import { useQuery } from '@tanstack/react-query';
import { getCryptoSignals, getFearGreed } from '@/lib/api/crypto';
import { FearGreedGauge } from '@/components/crypto/FearGreedGauge';
import { CryptoSignalCard } from '@/components/crypto/CryptoSignalCard';
import { CryptoProRow } from '@/components/crypto/CryptoProRow';
import { ScoreBreakdown } from '@/components/crypto/ScoreBreakdown';
import { Skeleton } from '@/components/ui/skeleton';
import { usePrismaMode } from '@/hooks/usePrismaMode';

const DISCLAIMER = `⚠️ Kryptowährungen sind hochvolatile Spekulations-Assets. Kein 3a-Instrument. Kein gesetzliches Zahlungsmittel in der Schweiz. Kapitalgewinne für Privatanleger steuerfrei (CH) — Vermögen ist steuerpflichtig (ESTV-Jahreswert). PRISMA-Signale sind keine Anlageberatung. Nur für freies Vermögen geeignet.`;

export function CryptoClient() {
  const { mode } = usePrismaMode();

  const { data: signals, isLoading: signalsLoading, error: signalsError } = useQuery({
    queryKey: ['crypto-signals'],
    queryFn: getCryptoSignals,
    staleTime: 10 * 60 * 1000,
  });

  const { data: fearGreed, isLoading: fgLoading } = useQuery({
    queryKey: ['fear-greed'],
    queryFn: getFearGreed,
    staleTime: 60 * 60 * 1000,
  });

  const buySignals = signals?.filter((s) =>
    s.signal === 'STRONG_BUY' || s.signal === 'BUY'
  ).slice(0, 3) ?? [];

  return (
    <div className="space-y-6">
      {/* Fear & Greed */}
      <div className="rounded-lg border border-border/50 bg-card p-4 flex flex-col sm:flex-row items-center gap-4">
        <div>
          <div className="text-sm font-medium">Crypto Fear &amp; Greed Index</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Contrarian-Indikator: Extreme Angst = Einstiegsgelegenheit
          </div>
        </div>
        <div className="ml-auto">
          {fgLoading || !fearGreed ? (
            <Skeleton className="w-40 h-24" />
          ) : (
            <FearGreedGauge value={fearGreed.value} label={fearGreed.label} />
          )}
        </div>
      </div>

      {/* Simple Mode: Top-3 BUY-Signale */}
      {mode === 'simple' && (
        <div className="space-y-3" data-testid="simple-section">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Beste Einstiegschancen
          </h2>
          {signalsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}
            </div>
          ) : signalsError ? (
            <p className="text-sm text-red-400" data-testid="signals-error">Signale konnten nicht geladen werden.</p>
          ) : buySignals.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="no-buy-signals">Keine BUY-Signale aktuell.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {buySignals.map((s) => <CryptoSignalCard key={s.ticker} signal={s} />)}
            </div>
          )}
        </div>
      )}

      {/* Pro Mode: Vollständige Tabelle */}
      {mode === 'pro' && (
        <div className="space-y-3" data-testid="pro-section">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Alle Signale (Pro)
          </h2>
          {signalsLoading ? (
            <Skeleton className="h-64" />
          ) : signalsError ? (
            <p className="text-sm text-red-400" data-testid="signals-error">Signale konnten nicht geladen werden.</p>
          ) : (
            <div className="rounded-lg border border-border/50 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium">Asset</th>
                    <th className="text-left py-2 px-3 font-medium">Signal</th>
                    <th className="text-left py-2 px-3 font-medium">Score</th>
                    <th className="text-right py-2 px-3 font-medium">Preis</th>
                    <th className="text-right py-2 px-3 font-medium">24h</th>
                    <th className="text-right py-2 px-3 font-medium">7d</th>
                    <th className="text-right py-2 px-3 font-medium">RSI</th>
                    <th className="text-right py-2 px-3 font-medium">Vola</th>
                    <th className="text-right py-2 px-3 font-medium">SMI-Korr</th>
                  </tr>
                </thead>
                <tbody>
                  {signals?.map((s) => <CryptoProRow key={s.ticker} signal={s} />)}
                </tbody>
              </table>
            </div>
          )}

          {/* Score-Breakdown Accordion für Pro */}
          {signals && signals.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Score-Aufschlüsselung
              </h3>
              {signals.slice(0, 5).map((s) => (
                <div key={s.ticker} className="flex flex-col gap-1">
                  <span className="text-xs font-medium">{s.name} ({s.ticker})</span>
                  <ScoreBreakdown signal={s} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Disclaimer — immer sichtbar */}
      <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/80 leading-relaxed" data-testid="crypto-disclaimer">
        {DISCLAIMER}
      </div>
    </div>
  );
}
