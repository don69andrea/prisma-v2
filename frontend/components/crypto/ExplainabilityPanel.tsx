'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { SignalVector } from '@/lib/api/crypto-signals';
import type { AgentAuditResponse } from '@/lib/api/agent-audit';

interface Props {
  signal: SignalVector;
  audit: AgentAuditResponse | null;
}

interface LayerRowProps {
  label: string;
  value: string;
  detail?: string;
}

function LayerRow({ label, value, detail }: LayerRowProps) {
  return (
    <div className="flex justify-between py-2 border-b last:border-0">
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      <div className="text-right">
        <span className="text-sm font-semibold">{value}</span>
        {detail && <p className="text-xs text-muted-foreground mt-0.5 max-w-xs">{detail}</p>}
      </div>
    </div>
  );
}

export function ExplainabilityPanel({ signal, audit }: Props) {
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const ss = signal.sub_scores;

  const layer1 = `Momentum-Rank: ${ss.momentum_rank?.toFixed(0) ?? '—'}/10 · On-Chain: ${
    ss.onchain_score !== undefined ? (ss.onchain_score > 0.5 ? 'Stark' : 'Neutral') : '—'
  }`;

  const indicators = [
    ss.ma_signal !== undefined && `MA ${ss.ma_signal > 0 ? '✓' : '✗'}`,
    ss.macd_signal !== undefined && `MACD ${ss.macd_signal > 0 ? '✓' : '✗'}`,
    ss.rsi_signal !== undefined && `RSI ${ss.rsi_signal > 0 ? '✓' : '✗'}`,
  ].filter(Boolean).join(' · ');
  const layer2 = `Konsens ${signal.consensus} (${indicators})`;

  const layer3 = `Vol-Prognose: ${ss.vol_pred !== undefined ? (ss.vol_pred * 100).toFixed(0) + '%' : '—'} → Größe ${signal.size_factor.toFixed(2)}×`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Erklärung</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <LayerRow label="Schicht 1 — WAS" value={signal.action} detail={layer1} />
        <LayerRow label="Schicht 2 — WANN" value={signal.consensus} detail={layer2} />
        <LayerRow label="Schicht 3 — WIEVIEL" value={`${signal.size_factor.toFixed(2)}×`} detail={layer3} />

        {audit && (
          <div className="mt-3">
            <button
              onClick={() => setReasoningOpen(!reasoningOpen)}
              className="flex items-center gap-1 text-sm text-primary hover:underline"
            >
              {reasoningOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Agent-Reasoning-Kette
            </button>
            {reasoningOpen && (
              <div className="mt-2 space-y-2 text-xs text-muted-foreground bg-muted/30 rounded p-3">
                {audit.agent_run.technical && (
                  <div><strong>Technical ({audit.agent_run.technical.stance}):</strong> {audit.agent_run.technical.reasoning}</div>
                )}
                {audit.agent_run.onchain && (
                  <div><strong>On-Chain ({audit.agent_run.onchain.valuation}):</strong> {audit.agent_run.onchain.reasoning}</div>
                )}
                {audit.agent_run.macro && (
                  <div><strong>Makro ({audit.agent_run.macro.regime}):</strong> {audit.agent_run.macro.reasoning}</div>
                )}
                {audit.agent_run.bull && (
                  <div><strong>Bull-These:</strong> {audit.agent_run.bull.thesis}</div>
                )}
                {audit.agent_run.bear && (
                  <div><strong>Bear-These:</strong> {audit.agent_run.bear.thesis}</div>
                )}
                {audit.agent_run.risk && (
                  <div><strong>Risk ({audit.agent_run.risk.approve ? 'Freigegeben' : 'Veto'}):</strong> {audit.agent_run.risk.reasoning}</div>
                )}
              </div>
            )}
          </div>
        )}

        <p className="mt-3 text-[11px] text-muted-foreground italic">
          Entscheidungsunterstützung, kein Anlagerat. Konfidenz-Quelle: deterministische Signal-Engine (Schichten 1–3).
        </p>
      </CardContent>
    </Card>
  );
}
