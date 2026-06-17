# UX Repolish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the PRISMA V2 frontend for design consistency, Swiss-precision hierarchy, and correct loading UX — all in branch `feat/ux-repolish`.

**Architecture:** Pure frontend changes in `frontend/`. No backend touches. All changes are either CSS-only tweaks, JSX restructures, or component-level state additions. The nav rewrite is the most structural change; everything else is targeted and surgical.

**Tech Stack:** Next.js 14 App Router, React, Tailwind CSS, CSS Modules, `@radix-ui/react-popover` (already installed), `@tanstack/react-query`

## Global Constraints

- Branch: `feat/ux-repolish` — never commit to main directly
- All files are under `frontend/` — all paths in this plan are relative to `frontend/`
- Do NOT introduce new npm packages — use only what is already in `package.json`
- `@radix-ui/react-popover` is available; `@radix-ui/react-tooltip` and `@radix-ui/react-dropdown-menu` are NOT installed
- Skeleton color: always use `bg-muted` / `border-border` (Tailwind CSS vars) — never hard-code hex
- Nav label rename: `"Start"` → `"Profil"` everywhere it appears as a nav label (NOT in page `<h1>` or other copy)
- Loading screen total duration: **4000ms** (not 2500ms, not 6500ms)
- Spec: `docs/superpowers/specs/2026-06-17-ux-repolish-design.md`

---

## File Map

| File | Change |
|------|--------|
| `app/providers.tsx` | `LOADING_DURATION_MS` 1200→4000; add `fadeOut` state to trigger CSS fade before unmount |
| `components/LoadingScreen.tsx` | Accept `fadeOut?: boolean` prop; apply `opacity-0 transition-opacity duration-400` when true |
| `components/LoadingScreen.module.css` | Replace all `6.5s` → `4s`; add `.overlayFadeOut` rule |
| `app/layout.tsx` | Remove glow-blur div; spectrum bar `h-[2px] opacity-30`; controls `border-l border-border/40` |
| `components/ui/PrismaBar.tsx` | `NavigationProgressBar`: height 3px→2px, glow opacity 0.45→0.25 |
| `app/nav-links.tsx` | Full rewrite: chromatic cluster B, color dividers, `"Start"`→`"Profil"`, Pro overflow Popover |
| `app/discover/loading.tsx` | Replace hard-coded `#161b22`/`#21262d` with `bg-muted`/`border-border` |
| `app/fonds/fonds-client.tsx` | Add `PrismaBar` import; replace bare `<Skeleton>` fondsLoading state with `PrismaBar` + skeleton stack |
| `app/news/news-client.tsx` | Add `PrismaBar` + skeleton rows to `SimpleNewsView` and `ProNewsView` null-daily-news state |
| `app/watchlist/watchlist-client.tsx` | Replace `Loader2` + text with `PrismaBar` for `loadingSignals` |
| `app/portfolio/portfolio-client.tsx` | Add `PrismaBar` for `mutation.isPending` calculation state |

---

## Task 1: Branch + Loading Screen Fix

**Files:**
- Modify: `app/providers.tsx`
- Modify: `components/LoadingScreen.tsx`
- Modify: `components/LoadingScreen.module.css`

**Interfaces:**
- Produces: `LoadingScreen({ fadeOut?: boolean })` — prop triggers CSS fade-out before unmount

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feat/ux-repolish
```

Expected: `Switched to a new branch 'feat/ux-repolish'`

- [ ] **Step 2: Add `.overlayFadeOut` to CSS module**

In `components/LoadingScreen.module.css`, after the `.overlay` block, add:

```css
.overlayFadeOut {
  opacity: 0;
  transition: opacity 400ms ease;
}
```

Also replace every occurrence of `6.5s` with `4s` in the file. There are exactly these instances:
- `.dotGrid { animation: gridFade 6.5s ... }`
- `.colorWash { animation: washSpin 10s ..., washFade 6.5s ... }` — change only `washFade 6.5s` → `washFade 4s`; `washSpin 10s` stays
- `.scene { animation: sceneFade 6.5s ... }`
- `.laserBeam { animation: laserDrop 6.5s ... }`
- `.diamondG { animation: diamondCharge 6.5s ... }`
- `.fTable { animation: facetT 6.5s ... }` and all other facet classes (fCL, fCR, fCCL, fCCR, fP1–fP5)
- `.ir1`–`.ir5` `animation: intRay 6.5s ...`
- `.exitBeam, .exitGlow { animation: exitBeam 6.5s ... }`
- `.prismaName { animation: nameReveal 6.5s ... }`
- `.spectrumLine { animation: specLine 6.5s ... }`
- `.taglineWrap { animation: tagReveal 6.5s ... }`

Run: `grep -c "6.5s" components/LoadingScreen.module.css`
Expected: `0` (all replaced)

- [ ] **Step 3: Update `LoadingScreen.tsx` to accept `fadeOut` prop**

Replace the current export:

```tsx
export function LoadingScreen() {
  return (
    <div className={s.overlay} aria-hidden="true">
```

With:

```tsx
export function LoadingScreen({ fadeOut = false }: { fadeOut?: boolean }) {
  return (
    <div className={`${s.overlay}${fadeOut ? ` ${s.overlayFadeOut}` : ''}`} aria-hidden="true">
```

- [ ] **Step 4: Update `providers.tsx` for 4s duration + CSS fade-out**

Replace the entire `Providers` function body timer logic. Current:

```tsx
const LOADING_DURATION_MS = 1200;
// ...
const [showLoading, setShowLoading] = useState(true);

useEffect(() => {
  const timer = setTimeout(() => setShowLoading(false), LOADING_DURATION_MS);
  return () => clearTimeout(timer);
}, []);
```

Replace with:

```tsx
const LOADING_DURATION_MS = 4000;
const FADE_OUT_MS = 400;
// ...
const [showLoading, setShowLoading] = useState(true);
const [fadeOut, setFadeOut] = useState(false);

useEffect(() => {
  const fadeTimer = setTimeout(() => setFadeOut(true), LOADING_DURATION_MS);
  const hideTimer = setTimeout(() => setShowLoading(false), LOADING_DURATION_MS + FADE_OUT_MS);
  return () => {
    clearTimeout(fadeTimer);
    clearTimeout(hideTimer);
  };
}, []);
```

And pass `fadeOut` to `LoadingScreen`:

```tsx
{showLoading && <LoadingScreen fadeOut={fadeOut} />}
```

- [ ] **Step 5: Verify visually**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000` — the diamond animation should play fully for ~3.5s, then fade out gracefully over 0.4s. Total: ~4s before app is visible. No hard cut.

- [ ] **Step 6: Commit**

```bash
git add components/LoadingScreen.tsx components/LoadingScreen.module.css app/providers.tsx
git commit -m "fix(loading): extend loading screen to 4s with CSS fade-out"
```

---

## Task 2: Spectrum Bar + NavigationProgressBar

**Files:**
- Modify: `app/layout.tsx`
- Modify: `components/ui/PrismaBar.tsx`

**Interfaces:**
- No interface changes — pure visual tweaks

- [ ] **Step 1: Remove glow layer and tone down spectrum bar in `layout.tsx`**

Find this block (after the `</div>` closing the `container` div):

```tsx
{/* PRISMA-Spektrum: zerlegt weisses Licht in 5 quantitative Dimensionen */}
<div className="relative" aria-hidden="true">
  {/* Glow-Bloom darunter */}
  <div
    className="absolute inset-x-0 top-0 h-[8px] blur-[6px] opacity-60"
    style={{ background: SPECTRUM_GRADIENT }}
  />
  {/* Hauptbalken */}
  <div
    className="relative h-[4px] w-full overflow-hidden spectrum-shimmer"
    style={{ background: SPECTRUM_GRADIENT }}
  />
</div>
```

Replace with:

```tsx
{/* PRISMA-Spektrum: 5 quantitative Dimensionen */}
<div
  className="h-[2px] w-full opacity-30"
  style={{ background: SPECTRUM_GRADIENT }}
  aria-hidden="true"
/>
```

- [ ] **Step 2: Add border-separator before header controls in `layout.tsx`**

Find:

```tsx
<div className="ml-auto flex items-center gap-2 pl-4">
```

Replace with:

```tsx
<div className="ml-auto flex items-center gap-2 pl-4 border-l border-border/40">
```

- [ ] **Step 3: Quiet down `NavigationProgressBar` in `PrismaBar.tsx`**

Find the `return` of `NavigationProgressBar` (the inline `style` block):

```tsx
style={{
  position: 'fixed',
  top: 0,
  left: 0,
  zIndex: 9999,
  height: '3px',
  width: `${pct}%`,
  background: SPECTRUM,
  boxShadow: GLOW,
  borderRadius: '0 9999px 9999px 0',
  transition: 'width 200ms ease-out, opacity 380ms ease',
  pointerEvents: 'none',
}}
```

Replace with (height 3px→2px, glow constant updated):

```tsx
style={{
  position: 'fixed',
  top: 0,
  left: 0,
  zIndex: 9999,
  height: '2px',
  width: `${pct}%`,
  background: SPECTRUM,
  boxShadow: '0 0 6px rgba(88, 166, 255, 0.25)',
  borderRadius: '0 9999px 9999px 0',
  transition: 'width 200ms ease-out, opacity 380ms ease',
  pointerEvents: 'none',
}}
```

Also update the `GLOW` constant at the top of the file from:

```tsx
const GLOW = '0 0 8px rgba(88, 166, 255, 0.45)';
```

To:

```tsx
const GLOW = '0 0 6px rgba(88, 166, 255, 0.25)';
```

(This also quiets `PrismaBar` and `RunProgressBar` which use `GLOW`.)

- [ ] **Step 4: Verify**

Navigate between pages in the running dev server. The top progress bar should be a thin 2px pulse, barely noticeable. The static header bar below the nav should be a subtle 2px line at 30% opacity — brand present but not glowing.

- [ ] **Step 5: Commit**

```bash
git add app/layout.tsx components/ui/PrismaBar.tsx
git commit -m "fix(header): subdue spectrum bar; quiet NavigationProgressBar glow"
```

---

## Task 3: Nav Rewrite — Chromatic Cluster B

**Files:**
- Modify: `app/nav-links.tsx`

**Interfaces:**
- Produces: same `NavLinks` export — drop-in replacement, no layout.tsx changes needed
- The `···` overflow uses `@radix-ui/react-popover` (already installed, used elsewhere)

- [ ] **Step 1: Write the full rewrite of `nav-links.tsx`**

Replace the entire file contents with:

```tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Compass, MoreHorizontal } from 'lucide-react';
import * as Popover from '@radix-ui/react-popover';

import { cn } from '@/lib/utils';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { PROFILE_STORAGE_KEY } from '@/app/start/start-client';

const PROFILE_BADGE_LABEL: Record<string, string> = {
  conservative: 'Stabiler Investor',
  moderate:     'Ausgewogener Investor',
  aggressive:   'Chancen-Investor',
};

interface NavLink { href: string; label: string }

interface NavCluster {
  groupLabel: string;
  color: string;
  links: NavLink[];
}

// Links visible in the nav bar (primary)
const CLUSTERS_SIMPLE: NavCluster[] = [
  { groupLabel: 'Entdecken',   color: '#8b5cf6', links: [{ href: '/start',    label: 'Profil' }, { href: '/discover', label: 'Universum' }] },
  { groupLabel: 'Analysieren', color: '#3b82f6', links: [{ href: '/rankings', label: 'Rankings' }, { href: '/stocks', label: 'Aktien' }, { href: '/crypto', label: 'Krypto' }] },
  { groupLabel: 'Entscheiden', color: '#f59e0b', links: [{ href: '/decision', label: 'Signale' }, { href: '/alerts', label: 'Alerts' }, { href: '/news', label: 'News' }] },
  { groupLabel: 'Beobachten',  color: '#10b981', links: [{ href: '/watchlist', label: 'Watchlist' }, { href: '/research', label: 'Research' }] },
];

const CLUSTERS_PRO_PRIMARY: NavCluster[] = [
  { groupLabel: 'Entdecken',   color: '#8b5cf6', links: [{ href: '/start',    label: 'Profil' }, { href: '/discover', label: 'Universum' }] },
  { groupLabel: 'Analysieren', color: '#3b82f6', links: [{ href: '/rankings', label: 'Rankings' }, { href: '/stocks', label: 'Aktien' }, { href: '/research', label: 'Research' }, { href: '/crypto', label: 'Krypto' }] },
  { groupLabel: 'Entscheiden', color: '#f59e0b', links: [{ href: '/decision', label: 'Signale' }, { href: '/alerts', label: 'Alerts' }, { href: '/news', label: 'News' }] },
  { groupLabel: 'Beobachten',  color: '#10b981', links: [{ href: '/watchlist', label: 'Watchlist' }] },
];

// Overflow links only in Pro mode
const OVERFLOW_LINKS: NavLink[] = [
  { href: '/universes', label: 'Universen' },
  { href: '/backtest',  label: 'Backtest'  },
  { href: '/fonds',     label: 'Fonds'     },
  { href: '/steuer',    label: 'Steuer'    },
  { href: '/portfolio', label: 'Portfolio' },
];

function isActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href);
}

function ClusterDivider({ color, label }: { color: string; label: string }) {
  return (
    <div
      className="flex items-center self-stretch shrink-0 mx-1"
      title={label}
      aria-hidden="true"
    >
      <div className="w-px h-4 rounded-full opacity-40" style={{ background: color }} />
    </div>
  );
}

function NavLinkItem({ link, color, pathname }: { link: NavLink; color: string; pathname: string }) {
  const active = isActive(link.href, pathname);
  return (
    <Link
      href={link.href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'text-sm shrink-0 transition-all duration-150 px-0.5',
        active
          ? 'font-semibold border-b border-current'
          : 'text-muted-foreground hover:text-foreground',
      )}
      style={active ? { color } : undefined}
    >
      {link.label}
    </Link>
  );
}

function OverflowMenu({ pathname }: { pathname: string }) {
  const [open, setOpen] = useState(false);
  const hasActive = OVERFLOW_LINKS.some((l) => isActive(l.href, pathname));

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          className={cn(
            'inline-flex items-center justify-center h-5 w-5 rounded text-muted-foreground transition-colors hover:text-foreground hover:bg-muted shrink-0',
            hasActive && 'text-foreground',
          )}
          aria-label="Mehr"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          className="z-50 min-w-[140px] rounded-lg border border-border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95"
          sideOffset={8}
          align="start"
        >
          {OVERFLOW_LINKS.map((link) => {
            const active = isActive(link.href, pathname);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className={cn(
                  'flex items-center px-3 py-1.5 text-sm rounded-md transition-colors',
                  active
                    ? 'font-medium text-foreground bg-accent'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent',
                )}
              >
                {link.label}
              </Link>
            );
          })}
          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function NavLinks() {
  const pathname = usePathname();
  const { mode } = usePrismaMode();
  const [profileType, setProfileType] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (stored) setProfileType(stored);
    const onStorage = (e: StorageEvent) => {
      if (e.key === PROFILE_STORAGE_KEY) setProfileType(e.newValue);
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const isPro = mode === 'pro';
  const clusters = isPro ? CLUSTERS_PRO_PRIMARY : CLUSTERS_SIMPLE;

  return (
    <nav className="flex items-center gap-3 min-w-0" aria-label="Hauptnavigation">
      {clusters.map((cluster, ci) => (
        <div key={cluster.groupLabel} className="flex items-center gap-3">
          {ci > 0 && <ClusterDivider color={cluster.color} label={cluster.groupLabel} />}
          {cluster.links.map((link) => (
            <NavLinkItem key={link.href} link={link} color={cluster.color} pathname={pathname} />
          ))}
        </div>
      ))}

      {isPro && (
        <>
          <ClusterDivider color="#64748b" label="Mehr" />
          <OverflowMenu pathname={pathname} />
        </>
      )}

      {profileType && (
        <span className="ml-2 inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30 whitespace-nowrap shrink-0">
          <Compass className="h-3 w-3 shrink-0" />
          {PROFILE_BADGE_LABEL[profileType] ?? 'Entdecker'}
        </span>
      )}
    </nav>
  );
}
```

- [ ] **Step 2: Verify**

In the running dev server:
- Simple mode: all clusters on one row, no label text visible, color dividers between groups
- Pro mode: same + `···` button at end; clicking it opens Popover with Universen/Backtest/Fonds/Steuer/Portfolio
- Active page: colored text + bottom border in group color
- Navigate to `/universes` in Pro mode — link in overflow should show active state (bg-accent)
- Check on narrow viewport: nav should not wrap (it may scroll horizontally on very small screens — that is acceptable)

- [ ] **Step 3: Run existing nav test**

```bash
cd frontend && npx vitest run app/__tests__/nav-links.test.tsx
```

Expected: tests pass. If any test references `"Start"` as a link label, update the test to expect `"Profil"` instead.

- [ ] **Step 4: Commit**

```bash
git add app/nav-links.tsx app/__tests__/nav-links.test.tsx
git commit -m "feat(nav): chromatic cluster redesign — color dividers, Pro overflow, 'Start'→'Profil'"
```

---

## Task 4: Skeleton Light-Mode + Missing Loading States

**Files:**
- Modify: `app/discover/loading.tsx`
- Modify: `app/fonds/fonds-client.tsx`
- Modify: `app/news/news-client.tsx`
- Modify: `app/watchlist/watchlist-client.tsx`
- Modify: `app/portfolio/portfolio-client.tsx`

**Interfaces:**
- No interface changes — all internal to each component

- [ ] **Step 1: Fix `discover/loading.tsx` hard-coded colors**

Find the grid skeleton cards:

```tsx
<div
  key={i}
  className="h-28 rounded-xl animate-pulse"
  style={{ background: '#161b22', border: '1px solid #21262d' }}
/>
```

Replace with:

```tsx
<div
  key={i}
  className="h-28 rounded-xl animate-pulse bg-muted border border-border"
/>
```

- [ ] **Step 2: Add `PrismaBar` to `fonds-client.tsx` loading state**

Add import at top of file (with other imports):

```tsx
import { PrismaBar } from '@/components/ui/PrismaBar';
```

Find the `fondsLoading` branch (~line 232):

```tsx
} : fondsLoading ? (
  <Skeleton className="h-9 w-64" />
) : (
```

Replace with:

```tsx
} : fondsLoading ? (
  <div className="space-y-2 w-64">
    <PrismaBar />
    <Skeleton className="h-9 w-64" />
  </div>
) : (
```

- [ ] **Step 3: Add `PrismaBar` + skeleton to `news-client.tsx` null-news state**

Add import at top:

```tsx
import { PrismaBar } from '@/components/ui/PrismaBar';
import { Skeleton } from '@/components/ui/skeleton';
```

In `SimpleNewsView`, replace the `dailyNews === null` branch:

```tsx
{dailyNews === null ? (
  <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
    <Newspaper className="h-10 w-10 text-muted-foreground/40 animate-pulse" />
    <p className="text-sm text-muted-foreground">News werden geladen…</p>
  </div>
) : ...
```

With:

```tsx
{dailyNews === null ? (
  <div className="space-y-3">
    <PrismaBar />
    {[1, 2, 3].map((i) => (
      <div key={i} className="rounded-lg border border-border p-4 space-y-2 animate-pulse">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    ))}
  </div>
) : ...
```

In `ProNewsView`, find where the feed is rendered when `dailyNews` is null and no search results exist (~line 380). Find:

```tsx
{feedItems.length === 0 && (
```

Just above that block, add (inside the existing feed `<div className="space-y-4">`):

```tsx
{dailyNews === null && !displayResults && (
  <div className="space-y-3">
    <PrismaBar />
    {[1, 2, 3, 4].map((i) => (
      <div key={i} className="rounded-lg border border-border p-4 space-y-2 animate-pulse">
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-3 w-1/3" />
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 4: Upgrade watchlist loading indicator**

In `app/watchlist/watchlist-client.tsx`, add import:

```tsx
import { PrismaBar } from '@/components/ui/PrismaBar';
```

Find the `loadingSignals` block (~line 499):

```tsx
{loadingSignals && (
  <div className="flex items-center gap-2 text-xs text-[#8b949e]">
    <Loader2 className="h-3.5 w-3.5 animate-spin" />
    Signale werden geladen...
  </div>
)}
```

Replace with:

```tsx
{loadingSignals && (
  <div className="space-y-1">
    <PrismaBar />
    <p className="text-xs text-muted-foreground">Signale werden geladen…</p>
  </div>
)}
```

Remove the `Loader2` import if it's no longer used elsewhere in the file:
```bash
grep -n "Loader2" app/watchlist/watchlist-client.tsx
```
If no other uses: remove from the import line.

- [ ] **Step 5: Add `PrismaBar` to portfolio calculation state**

In `app/portfolio/portfolio-client.tsx`, add import:

```tsx
import { PrismaBar } from '@/components/ui/PrismaBar';
```

Find the `mutation.isPending` button (around line 437):

```tsx
{mutation.isPending ? 'Berechne…' : 'Plan berechnen'}
```

Find the parent section that renders the results area. Add a loading state just below the submit button group:

```tsx
{mutation.isPending && (
  <div className="space-y-1 pt-2">
    <PrismaBar />
    <p className="text-xs text-muted-foreground">Portfolio wird berechnet…</p>
  </div>
)}
```

- [ ] **Step 6: Verify all pages in dev server**

- `/discover` — skeleton cards should use bg-muted (correct in both dark and light mode)
- `/fonds` — on page load, the Fonds selector shows PrismaBar + skeleton while list loads
- `/news` — loading state shows PrismaBar + skeleton cards instead of bare spinner icon
- `/watchlist` — signal loading shows PrismaBar instead of Loader2
- `/portfolio` — calculation in progress shows PrismaBar below the submit button
- Toggle to Light Mode (☀ button in header) — all skeletons must be visible (not invisible on white)

- [ ] **Step 7: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass. Fix any test that asserts on `Loader2` in watchlist or the old news loading text.

- [ ] **Step 8: Commit**

```bash
git add app/discover/loading.tsx app/fonds/fonds-client.tsx app/news/news-client.tsx app/watchlist/watchlist-client.tsx app/portfolio/portfolio-client.tsx
git commit -m "fix(loading): add PrismaBar to missing states; fix light-mode skeleton colors"
```

---

## Task 5: Push Branch + PR

- [ ] **Step 1: Final check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: zero type errors.

```bash
cd frontend && npx vitest run
```

Expected: all tests pass.

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/ux-repolish
```

- [ ] **Step 3: Create PR**

```bash
gh pr create \
  --title "feat(ux): repolish — chromatic nav, loading screen, spectrum bar, loading states" \
  --body "$(cat <<'EOF'
## Summary

- **Nav:** Chromatic Cluster B redesign — color dividers replace text group labels, single-row in both Simple and Pro mode, Pro overflow Popover for secondary pages, 'Start' → 'Profil'
- **Loading Screen:** Extended from 1.2s → 4s to match 4s animation cycle; CSS fade-out transition instead of hard unmount
- **Spectrum Bar:** Removed glow layer; height 4px → 2px; opacity 30%. NavigationProgressBar: 2px, quieter glow
- **Skeletons:** Fixed hard-coded dark hex colors (light-mode invisible) → bg-muted/border-border
- **Missing Loading States:** PrismaBar + skeleton cards added to Fonds, News, Watchlist, Portfolio

## Test plan
- [ ] Loading screen plays full 4s animation then fades out gracefully
- [ ] Spectrum bar is subtle (2px, 30% opacity) — brand present, not focal
- [ ] Nav is single-row on 13" MacBook in both Simple and Pro mode
- [ ] Overflow popover opens/closes correctly in Pro mode
- [ ] Active state shows correct group color
- [ ] Light mode: all skeleton states visible
- [ ] All vitest tests pass
- [ ] No TypeScript errors

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
