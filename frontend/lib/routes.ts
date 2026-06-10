export const ROUTES = {
  dashboard: '/',
  stocks: '/stocks',
  universes: '/universes',
  rankings: '/rankings',
  backtest: '/backtest',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
