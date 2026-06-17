'use client';

import { useState } from 'react';
import { BarChart2 } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { CryptoHistoryChart } from './CryptoHistoryChart';
import { CryptoAgentPanel } from './CryptoAgentPanel';
import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';

interface CryptoChartSheetProps {
  ticker: string;
  signal: CryptoSignal;
}

export function CryptoChartSheet({ ticker, signal }: CryptoChartSheetProps) {
  const [open, setOpen] = useState(false);
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid={`chart-sheet-trigger-${ticker}`}
        className="flex items-center gap-1 rounded-md border border-border/50 px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors"
      >
        <BarChart2 className="h-3 w-3" />
        Chart
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="sm:max-w-2xl overflow-y-auto">
          <SheetHeader className="mb-4">
            <SheetTitle className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-lg">{ticker}</span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full border"
                style={{ color, borderColor: `${color}50`, backgroundColor: `${color}20` }}
              >
                {label}
              </span>
              <span className="text-sm text-muted-foreground font-normal">
                {signal.name}
              </span>
            </SheetTitle>
          </SheetHeader>

          <Tabs defaultValue="chart">
            <TabsList className="mb-4 w-full">
              <TabsTrigger value="chart" className="flex-1">
                📊 Chart
              </TabsTrigger>
              <TabsTrigger value="analysis" className="flex-1">
                ✦ KI-Analyse
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chart" forceMount className="data-[state=inactive]:hidden">
              <CryptoHistoryChart ticker={ticker} />
            </TabsContent>

            <TabsContent value="analysis" forceMount className="data-[state=inactive]:hidden">
              <CryptoAgentPanel
                ticker={ticker}
                detectedPatterns={signal.detected_patterns}
                cachedAnalysis={signal.agent_analysis}
              />
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
    </>
  );
}
