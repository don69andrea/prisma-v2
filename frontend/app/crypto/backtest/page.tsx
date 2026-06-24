import type { Metadata } from 'next';
import { BacktestClient } from './backtest-client';

export const metadata: Metadata = { title: 'Backtest — PRISMA Krypto' };

export default function BacktestPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Backtest</h1>
        <p className="text-muted-foreground text-sm mt-1">Walk-Forward Out-of-Sample Backtests · netto 0.1% Transaktionskosten</p>
      </div>
      <BacktestClient />
    </div>
  );
}
