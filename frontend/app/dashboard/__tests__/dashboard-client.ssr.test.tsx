import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

// renderToStaticMarkup never commits, so useEffect never runs — this mirrors
// exactly what Next.js produces for the initial server HTML. If a value used
// in this output differs from what the same component renders in the browser
// (where localStorage is already populated), hydration fails with React
// errors #418/#423/#425 — the same trio fixed for other files in 933e007.

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
vi.mock('@/hooks/usePrismaMode', () => ({
  usePrismaMode: () => ({ mode: 'simple', isSimple: true, isPro: false, toggle: vi.fn() }),
}));
vi.mock('@/components/GuidedTour', () => ({
  GuidedTourButton: () => null,
}));
vi.mock('@/app/start/start-client', () => ({
  DISCOVER_STORAGE_KEY: 'prisma_discover_cache',
}));

import { DashboardClient } from '../dashboard-client';
import * as universesApi from '@/lib/api/universes';
import { DISCOVER_STORAGE_KEY } from '@/app/start/start-client';

function wrap(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

// Node 22+'s native global `localStorage` shadows jsdom's implementation and
// throws without a `--localstorage-file`, so stub a minimal in-memory one.
function createMemoryStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
}

describe('DashboardClient SSR output', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal('localStorage', createMemoryStorage());
  });

  it('does not include cached discover-ticker count in the render-only (pre-hydration) pass', () => {
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({ items: [], total: 0 });
    localStorage.setItem(
      DISCOVER_STORAGE_KEY,
      JSON.stringify({ stocks: Array.from({ length: 7 }, (_, i) => ({ ticker: `T${i}` })) }),
    );

    const html = renderToStaticMarkup(wrap(<DashboardClient />));

    // A real Next.js server render never sees localStorage (no window), so it
    // must produce this same "no universe yet" output regardless of what's
    // cached in the browser. If this fails, the component's first render
    // depends on localStorage and will mismatch real SSR output.
    expect(html).not.toContain('Aktien in deinem Universum');
  });
});
