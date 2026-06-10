export const ROUTES = {
  dashboard: '/',
  universes: '/universes',
  rankings: '/rankings',
  backtest: '/backtest',
  decision: '/decision',
  alerts: '/alerts',
  portfolio: '/portfolio',
  simulator: '/portfolio/simulator',
  fonds: '/fonds',
  stocks: '/stocks',
  news: '/news',
  steuer: '/steuer',
  research: '/research',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
