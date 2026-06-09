export const ROUTES = {
  dashboard: '/',
  universes: '/universes',
  rankings: '/rankings',
  backtest: '/backtest',
  decision: '/decision',
  stocks: '/stocks',
  news: '/news',
  steuer: '/steuer',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
