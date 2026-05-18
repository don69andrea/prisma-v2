import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface Props {
  perModelRanks: Record<string, number | null>;
}

const MODELS: Array<{ key: string; label: string }> = [
  { key: 'quality_classic', label: 'Quality Classic' },
  { key: 'alpha', label: 'Alpha' },
  { key: 'trend_momentum', label: 'Trend Momentum' },
  { key: 'value_alpha_potential', label: 'Value Alpha Potential' },
  { key: 'diversification', label: 'Diversification' },
];

const TOTAL_STOCKS = 20; // MVP: assume universe of 20 stocks

function getQuartile(rank: number): 1 | 2 | 3 | 4 {
  const q = Math.ceil((rank / TOTAL_STOCKS) * 4);
  return Math.min(Math.max(q, 1), 4) as 1 | 2 | 3 | 4;
}

const QUARTILE_CLASSES: Record<1 | 2 | 3 | 4, string> = {
  1: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  2: 'bg-lime-100 text-lime-800 border-lime-200',
  3: 'bg-orange-100 text-orange-800 border-orange-200',
  4: 'bg-red-100 text-red-800 border-red-200',
};

const QUARTILE_LABELS: Record<1 | 2 | 3 | 4, string> = {
  1: 'Q1',
  2: 'Q2',
  3: 'Q3',
  4: 'Q4',
};

export function ModelRankCards({ perModelRanks }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {MODELS.map(({ key, label }) => {
        const rank = perModelRanks[key] ?? null;
        const quartile = rank !== null ? getQuartile(rank) : null;

        return (
          <Card key={key}>
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground leading-tight">
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="flex items-end justify-between gap-2">
                <span className="text-3xl font-bold tabular-nums">
                  {rank !== null ? rank : '—'}
                </span>
                {quartile !== null && (
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${QUARTILE_CLASSES[quartile]}`}
                  >
                    {QUARTILE_LABELS[quartile]}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
