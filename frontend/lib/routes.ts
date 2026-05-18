export const ROUTES = {
  dashboard: '/',
  universes: '/universes',
  rankings: '/rankings',
  backtest: '/backtest',
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
