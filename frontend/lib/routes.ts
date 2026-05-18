export const ROUTES = {
  dashboard: '/dashboard',
  universes: '/universes',
  rankings: '/rankings',
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
