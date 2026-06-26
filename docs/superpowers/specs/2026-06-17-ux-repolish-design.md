# PRISMA UX Repolish — Design Spec
**Date:** 2026-06-17  
**Branch:** `feat/ux-repolish`  
**Approach:** Swiss precision for spacing/typography/grid discipline; PRISMA spectrum fully dominant; no SBB red.

---

## Audit Findings

| # | Area | Issue | Severity |
|---|------|--------|----------|
| 1 | Loading Screen | `LOADING_DURATION_MS = 1200ms` but animation is 6.5s — screen unmounts before content plays | Critical |
| 2 | Header Spectrum Bar | Double spectrum bars: static 4px + 8px blur glow (always on) + dynamic `NavigationProgressBar`. The static glow is the "too prominent orange bar" | High |
| 3 | Navigation | Pro mode: 5 groups × 13 links wraps to 2 rows on 13" MacBook. Group labels take vertical space | High |
| 4 | Skeleton Light-Mode | Hard-coded `#161b22`, `#21262d` (GitHub dark) in loading skeletons — breaks in light mode | Medium |
| 5 | Missing Loading States | `fonds`, `news`, `watchlist`, `portfolio` pages have no `PrismaBar` or structured skeletons | Medium |
| 6 | Header Controls | `ModeToggle` and `ThemeToggle` sit next to `ApiStatusBadge` with no visual separation | Low |
| 7 | Label "Start" | `/start` page labelled "Start" — generic, unfit for an investor profile config page | Low |

---

## Design Decisions

### 1. Navigation — Chromatic Cluster (Approach B)

**Goal:** Single-row nav on 13" MacBook in Pro mode. Remove text group labels. Preserve information architecture visually via color.

**Implementation:**
- Group labels (`ENTDECKEN`, `ANALYSIEREN`, etc.) are removed from the rendered DOM
- Between each cluster: a `1px` vertical separator in the group's accent color (`h-4`, `opacity-50`)
- Links remain flat `text-sm`, same sizing as today
- Active state: `font-semibold` + 1px colored bottom border (unchanged)
- Pro-mode overflow: `Universes`, `Backtest`, `Steuer` move into a `···` dropdown (Radix `DropdownMenu`)
- Hover on separator shows tooltip (Radix `Tooltip`) with the group name (e.g. "Analysieren")
- `"Start"` renamed to `"Profil"` across label definition and any page titles that reference it

**Nav layout (Pro mode):**
```
PRISMA ◆  Profil · Universum  ╎  Rankings · Aktien · Research · Krypto  ╎  Signale · Alerts · News  ╎  Watchlist  ╎  ···  │  [Simple|Pro]  [☀]
```

**Nav layout (Simple mode):**
```
PRISMA ◆  Profil · Universum  ╎  Rankings · Aktien · Krypto  ╎  Signale · Alerts · News  ╎  Watchlist · Research  │  [Simple|Pro]  [☀]
```

**Files changed:** `app/nav-links.tsx`

---

### 2. Loading Screen — 4s Cycle with CSS Fade-Out

**Goal:** Animation plays fully, then fades out smoothly instead of hard-cutting.

**Implementation:**
- All `LoadingScreen.module.css` keyframes rescaled from 6.5s → 4s (ratio: 4/6.5 ≈ 0.615)
  - Hold window: 3.2s → 3.5s ends, fade: 3.5s → 4s (was 5.7s → 6.5s)
- `LOADING_DURATION_MS` in `providers.tsx`: `1200` → `4000`
- `LoadingScreen` overlay gets `transition: opacity 400ms ease` in CSS
- `Providers` passes a `fadeOut` prop; when timer fires, sets `opacity: 0` before unmounting (300ms delay after opacity transition)

**Files changed:** `components/LoadingScreen.module.css`, `components/LoadingScreen.tsx`, `app/providers.tsx`

---

### 3. Static Spectrum Bar — Subdued Accent

**Goal:** Brand marker stays, but no longer competes with content.

**Current:**
```tsx
<div className="absolute inset-x-0 top-0 h-[8px] blur-[6px] opacity-60" style={{ background: SPECTRUM_GRADIENT }} />
<div className="relative h-[4px] w-full overflow-hidden spectrum-shimmer" style={{ background: SPECTRUM_GRADIENT }} />
```

**Target:**
- Remove glow layer entirely (the blur div)
- Main bar: `h-[2px]`, add `opacity-30` class
- Remove `spectrum-shimmer` class (shimmer animation on a static bar is excessive)

**Files changed:** `app/layout.tsx`

---

### 4. NavigationProgressBar — Quieter

**Goal:** Progress indicator stays functional but doesn't compete with the static bar.

**Changes:**
- Height: `3px → 2px`
- `boxShadow`: `0 0 8px rgba(88,166,255,0.45)` → `0 0 6px rgba(88,166,255,0.25)`

**Files changed:** `components/ui/PrismaBar.tsx`

---

### 5. Skeleton Light-Mode Fixes

All `loading.tsx` and client files using hard-coded dark hex values get replaced:

| Hard-coded value | Replacement |
|-----------------|-------------|
| `background: '#161b22'` | `className="bg-muted"` |
| `border: '1px solid #21262d'` | `className="border border-border"` |

Affected files: `app/discover/loading.tsx`, `app/rankings/loading.tsx`, `app/rankings/[runId]/loading.tsx`, any others found via grep.

---

### 6. Missing Loading States

Each missing page gets a consistent pattern:

```tsx
// Top of client component, during fetch:
if (isLoading) return (
  <div className="space-y-4">
    <PrismaBar />
    <Skeleton className="h-6 w-48" />
    <Skeleton className="h-32 w-full rounded-xl" />
    {/* repeat as needed for content shape */}
  </div>
);
```

Pages: `app/fonds/fonds-client.tsx`, `app/news/news-client.tsx`, `app/watchlist/watchlist-client.tsx`, `app/portfolio/portfolio-client.tsx`

---

### 7. Header Controls Separation

Add a subtle left-border divider before the controls group:

```tsx
<div className="ml-auto flex items-center gap-2 pl-4 border-l border-border/40">
  <ModeToggle />
  <ApiStatusBadge />
  <ThemeToggle />
</div>
```

**Files changed:** `app/layout.tsx`

---

## Visual Hierarchy (Swiss Precision Principles Applied)

- **Level 1 — Brand:** PRISMA wordmark + logo (unchanged)
- **Level 2 — Navigation:** Flat chromatic cluster, no label overhead
- **Level 3 — Brand accent:** 2px spectrum bar at 30% opacity (ambient, not focal)
- **Level 4 — Content:** Page h1, cards, data tables
- **Level 5 — Status:** ApiStatusBadge, ModeToggle, ThemeToggle (separated right)

---

## Non-Goals

- No color system changes (spectrum stays as-is)
- No SBB red introduced
- No dark/light mode visual overhaul beyond skeleton fixes
- No font changes
- No backend changes
