'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Skeleton } from '@/components/ui/skeleton';
import { ExplainabilityPanel } from '@/components/crypto/ExplainabilityPanel';
import { CandlestickChart } from '@/components/crypto/CandlestickChart';
import { HitlDialog } from '@/components/crypto/HitlDialog';
import { CryptoSignalBadge } from '@/components/crypto/CryptoSignalBadge';
import { getSignal, getAgentSignal } from '@/lib/api/crypto-signals';
import { getAgentAudit } from '@/lib/api/agent-audit';
import { getOHLCV } from '@/lib/api/ohlcv';

type Tab = 'overview' | 'chart';

interface Props { coin: string; }

export function CoinDetailClient({ coin }: Props) {
  const [tab, setTab] = useState<Tab>('overview');
  const [hitlSeen, setHitlSeen] = useState(false);
  const [hitlOpen, setHitlOpen] = useState(false);

  const { data: signal } = useQuery({
    queryKey: ['signal', coin],
    queryFn: () => getSignal(`${coin}-USD`),
    staleTime: 5 * 60_000,
  });

  const { data: agentSignal } = useQuery({
    queryKey: ['agent-signal', coin],
    queryFn: () => getAgentSignal(coin),
    staleTime: 5 * 60_000,
    retry: false,
  });

  // Show HITL dialog on first load when confidence is low
  if (agentSignal && agentSignal.confidence < 0.65 && !hitlSeen) {
    setHitlSeen(true);
    setHitlOpen(true);
  }

  const { data: audit } = useQuery({
    queryKey: ['agent-audit', coin],
    queryFn: () => getAgentAudit(coin),
    staleTime: 5 * 60_000,
  });

  const { data: ohlcv } = useQuery({
    queryKey: ['ohlcv', coin, 120],
    queryFn: () => getOHLCV(coin, 120),
    staleTime: 15 * 60_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link href="/crypto" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft size={18} />
        </Link>
        <h1 className="text-xl font-bold">{coin}</h1>
        {signal && <CryptoSignalBadge action={signal.action} confidence={signal.confidence} />}
      </div>

      <div className="flex border-b">
        {(['overview', 'chart'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}>
            {t === 'overview' ? 'Übersicht & Erklärung' : 'Chart & Indikatoren'}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="space-y-4">
          {signal ? (
            <ExplainabilityPanel signal={signal} audit={audit ?? null} />
          ) : <Skeleton className="h-48 w-full" />}
          <p className="text-xs text-muted-foreground italic">
            Entscheidungsunterstützung, kein Anlagerat. SELL = Exposure 0 (kein Shorting).
            Konfidenz &lt; 65% löst menschlichen Bestätigungs-Checkpoint aus.
          </p>
        </div>
      )}

      {tab === 'chart' && (
        <div>
          {ohlcv ? (
            <CandlestickChart bars={ohlcv.bars} coin={coin} />
          ) : <Skeleton className="h-80 w-full" />}
        </div>
      )}

      {agentSignal && (
        <HitlDialog
          signal={agentSignal}
          open={hitlOpen}
          onProceed={() => setHitlOpen(false)}
          onAbort={() => { setHitlOpen(false); window.history.back(); }}
        />
      )}
    </div>
  );
}
