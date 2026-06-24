'use client';

import { useState } from 'react';
import {
  Dialog, DialogContent, DialogHeader,
  DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { TradeSignal } from '@/lib/api/crypto-signals';
import { confirmHitl } from '@/lib/api/agent-audit';

interface Props {
  signal: TradeSignal;
  open: boolean;
  onProceed: () => void;
  onAbort: () => void;
}

export function HitlDialog({ signal, open, onProceed, onAbort }: Props) {
  const [loading, setLoading] = useState(false);

  const handleDecision = async (decision: 'proceed' | 'abort') => {
    setLoading(true);
    try {
      // Log decision to backend (append-only audit log, kein Handelsauftrag)
      await confirmHitl(signal.coin, {
        audit_trail_id: signal.audit_trail_id,
        decision,
      });
    } catch {
      // Non-blocking: logging failure should not block user decision
    } finally {
      setLoading(false);
    }
    if (decision === 'proceed') onProceed();
    else onAbort();
  };

  const confidencePct = Math.round(signal.confidence * 100);

  return (
    <Dialog open={open}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            ⚠ Geringe Konfidenz — Menschliche Bestätigung erforderlich
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <p>
            Das System hat für <strong>{signal.coin}</strong> ein{' '}
            <strong
              className={
                signal.action === 'BUY'
                  ? 'text-emerald-600'
                  : signal.action === 'SELL'
                  ? 'text-red-600'
                  : ''
              }
            >
              {signal.action}
            </strong>
            -Signal generiert, aber die Konfidenz ist mit{' '}
            <strong>{confidencePct}%</strong> unter dem Schwellenwert (65%).
          </p>
          {/* Iron Rule: SELL = Exposure 0, kein Shorting */}
          {signal.action === 'SELL' && (
            <p className="text-xs text-muted-foreground bg-muted/30 rounded p-2">
              SELL bedeutet: Exposure auf 0 reduzieren (kein Leerverkauf / kein Shorting).
            </p>
          )}
          <p className="text-muted-foreground">
            Dies ist eine Entscheidungsunterstützung, kein automatischer Handelsauftrag.
            Deine Bestätigung wird protokolliert —{' '}
            <strong>kein Handel wird ausgelöst</strong>.
          </p>
          <div className="bg-muted/30 rounded p-2 text-xs">
            <strong>Signal-Begründung:</strong>{' '}
            {signal.rationale_by_layer?.['risk'] ??
              signal.rationale_by_layer?.['technical'] ??
              'Keine Begründung verfügbar'}
          </div>
        </div>
        <DialogFooter className="flex gap-2 sm:justify-start">
          <Button
            variant="default"
            disabled={loading}
            onClick={() => handleDecision('proceed')}
          >
            Verstanden, fortfahren
          </Button>
          <Button
            variant="outline"
            disabled={loading}
            onClick={() => handleDecision('abort')}
          >
            Abbrechen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
