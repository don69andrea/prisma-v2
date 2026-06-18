export const ROUTES = {
  login: '/login',
  dashboard: '/',
  discover: '/discover',
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
  watchlist: '/watchlist',
  steuer: '/steuer',
  research: '/research',
  admin: '/admin',
  adminUsers: '/admin/users',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
