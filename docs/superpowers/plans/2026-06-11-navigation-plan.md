# Plan: Navigation Restructure — 5 Bereiche (R2.4-4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Navigation in `frontend/app/nav-links.tsx` auf 5 neue semantische Gruppen
umstrukturieren gemäss Spec `docs/specs/2026-06-11-navigation-restructure.md`.

**Spec-Referenz:** `docs/specs/2026-06-11-navigation-restructure.md`
**Branch:** `feature/helin-navigation`
**Person:** Helin
**Datum:** 2026-06-11

---

## File Map

| Datei | Aktion |
|-------|--------|
| `frontend/app/nav-links.tsx` | **Modify** — NAV_GROUPS neu strukturieren |
| `frontend/app/__tests__/nav-links.test.tsx` | **Modify** — Tests anpassen auf neue Labels |
| `frontend/app/layout.tsx` | **Modify** (optional) — flex-wrap für mobile Nav |
| `docs/AI-USAGE.md` | **Modify** — Eintrag nach Abschluss anfügen |

---

## Vorbedingungen prüfen

Vor Beginn der Implementation:

```bash
cd /Users/helinkoyuncu/prisma-v2/frontend
# Sicherstellen dass Tests heute grün sind
npm run test -- --run 2>&1 | tail -20
```

Erwartetes Ergebnis: alle Tests grün, insbesondere `nav-links.test.tsx`.

---

## Task 1: `nav-links.tsx` — NAV_GROUPS ersetzen

**File:** `frontend/app/nav-links.tsx`
**Commit:** `feat(nav): restructure navigation into 5 semantic areas R2.4-4`

### Was ersetzen

Die bestehende `NAV_GROUPS`-Konstante (Zeilen 9–48) durch folgende neue Struktur
ersetzen:

```typescript
const NAV_GROUPS = [
  {
    label: 'ENTDECKEN',
    links: [
      { href: ROUTES.start,      label: 'Einstieg' },
      { href: ROUTES.universes,  label: 'Universen' },
    ],
  },
  {
    label: 'ANALYSIEREN',
    links: [
      { href: ROUTES.rankings,   label: 'Rankings' },
      { href: ROUTES.stocks,     label: 'Aktien' },
      { href: ROUTES.research,   label: 'Research' },
    ],
  },
  {
    label: 'VERGLEICHEN',
    links: [
      { href: ROUTES.backtest,   label: 'Backtest' },
      { href: ROUTES.fonds,      label: 'Fonds' },
    ],
  },
  {
    label: 'ENTSCHEIDEN',
    links: [
      { href: ROUTES.decision,   label: 'Signale' },
      { href: ROUTES.alerts,     label: 'Alerts' },
      { href: ROUTES.news,       label: 'News' },
    ],
  },
  {
    label: 'PORTFOLIO',
    links: [
      { href: ROUTES.portfolio,  label: 'Portfolio' },
      { href: ROUTES.simulator,  label: '3a Sim' },
      { href: ROUTES.steuer,     label: 'Steuer' },
    ],
  },
] as const;
```

**Änderungen gegenüber heute:**
- `VERSTEHEN` → umbenannt zu `ANALYSIEREN`
- `Rankings` zieht von ENTDECKEN → ANALYSIEREN
- `Aktien` + `Research` bleiben in ANALYSIEREN (waren VERSTEHEN)
- `News` zieht von VERSTEHEN → ENTSCHEIDEN

### Mobile flex-wrap — `<nav>`-Tag anpassen

In derselben Datei die `<nav>`-Klasse um `flex-wrap` ergänzen:

```tsx
// Vorher:
className="flex items-start gap-6 overflow-x-auto scrollbar-none pb-0.5"

// Nachher:
className="flex flex-wrap items-start gap-x-6 gap-y-2 pb-0.5"
```

Begründung: `flex-wrap` erlaubt Umbruch auf < 640 px ohne `overflow-x-auto`.
`gap-x-6` erhält horizontalen Abstand, `gap-y-2` gibt vertikalen Abstand zwischen
umgebrochenen Zeilen.

### Gruppen-Label-Grösse

```tsx
// Vorher:
className="text-[9px] font-semibold tracking-[0.12em] text-[#8b949e] uppercase px-1"

// Nachher:
className="text-[10px] font-semibold tracking-[0.12em] text-[#8b949e] uppercase px-1"
```

Begründung: `10px` statt `9px` für bessere Mobile-Lesbarkeit (Spec §Mobile-First).

- [ ] Datei editiert
- [ ] `tsc --noEmit` läuft fehlerfrei durch

---

## Task 2: Tests aktualisieren

**File:** `frontend/app/__tests__/nav-links.test.tsx`
**Commit:** `test(nav): update NavLinks tests for restructured 5-area navigation`

### Vollständiger neuer Test-Inhalt

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
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

import { usePathname } from 'next/navigation';
import { NavLinks } from '../nav-links';

describe('NavLinks', () => {
  it('TC-01: zeigt alle 5 Gruppenbezeichnungen', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByText('ENTDECKEN')).toBeInTheDocument();
    expect(screen.getByText('ANALYSIEREN')).toBeInTheDocument();
    expect(screen.getByText('VERGLEICHEN')).toBeInTheDocument();
    expect(screen.getByText('ENTSCHEIDEN')).toBeInTheDocument();
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
  });

  it('TC-02: hebt den aktiven Link hervor und setzt aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    const active = screen.getByRole('link', { name: 'Rankings' });
    expect(active).toHaveAttribute('aria-current', 'page');
    expect(active.className).toContain('text-foreground');
  });

  it('TC-03: matched verschachtelte Pfade — /rankings/abc aktiviert Rankings', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings/some-run-id');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Rankings' })).toHaveAttribute('aria-current', 'page');
  });

  it('TC-04: alle 14 Links sind im DOM vorhanden', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    const expectedLinks = [
      'Einstieg', 'Universen',
      'Rankings', 'Aktien', 'Research',
      'Backtest', 'Fonds',
      'Signale', 'Alerts', 'News',
      'Portfolio', '3a Sim', 'Steuer',
    ];
    for (const label of expectedLinks) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('TC-05: inaktiver Link trägt kein aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Aktien' })).not.toHaveAttribute('aria-current');
  });

  it('TC-06: News-Link ist vorhanden (in ENTSCHEIDEN-Gruppe)', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'News' })).toBeInTheDocument();
  });

  it('TC-07: Signale- und Alerts-Link sind vorhanden', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Signale' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Alerts' })).toBeInTheDocument();
  });

  it('TC-08: /start aktiviert Einstieg-Link', () => {
    vi.mocked(usePathname).mockReturnValue('/start');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Einstieg' })).toHaveAttribute('aria-current', 'page');
  });
});
```

- [ ] Datei editiert
- [ ] `npm run test -- --run` alle Tests grün

---

## Task 3: Verifikation

```bash
cd /Users/helinkoyuncu/prisma-v2/frontend

# TypeScript-Check
npx tsc --noEmit

# Unit-Tests
npm run test -- --run

# Lint-Check (optional, kein CI-Blocker für Spec+Plan-PR)
npx eslint app/nav-links.tsx app/__tests__/nav-links.test.tsx --max-warnings 0
```

Erwartetes Ergebnis: kein Fehler.

- [ ] `tsc --noEmit` grün
- [ ] Alle Vitest-Tests grün

---

## Task 4: Commit & Push

```bash
cd /Users/helinkoyuncu/prisma-v2

# Spec + Plan committen (dieser PR — nur Docs)
git add docs/specs/2026-06-11-navigation-restructure.md
git add docs/superpowers/plans/2026-06-11-navigation-plan.md
git commit -m "docs(spec): add navigation restructure spec and plan R2.4-4

Spec definiert 5 semantische Bereiche (ENTDECKEN, ANALYSIEREN, VERGLEICHEN,
ENTSCHEIDEN, PORTFOLIO) mit Mobile-first Responsive-Anforderungen, Test-Cases
und Nicht-Zielen. Plan enthält verbatim Code-Snippets und Bash-Befehle.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

# Implementation-Commits (nach Freigabe durch User)
git add frontend/app/nav-links.tsx
git commit -m "feat(nav): restructure navigation into 5 semantic areas R2.4-4

ENTDECKEN: Einstieg, Universen
ANALYSIEREN: Rankings, Aktien, Research (ehem. VERSTEHEN + Rankings)
VERGLEICHEN: Backtest, Fonds
ENTSCHEIDEN: Signale, Alerts, News (News von VERSTEHEN hierher)
PORTFOLIO: Portfolio, 3a Sim, Steuer

Adds flex-wrap for mobile, 10px group label for readability.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git add frontend/app/__tests__/nav-links.test.tsx
git commit -m "test(nav): update NavLinks tests for restructured 5-area navigation

8 Test-Cases gemäss Spec TC-01 bis TC-08. Neu: TC-06 (News in ENTSCHEIDEN),
TC-07 (Signale + Alerts), TC-08 (/start aktiviert Einstieg).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push -u origin feature/helin-navigation
```

---

## Task 5: Draft-PR öffnen

```bash
gh pr create \
  --title "feat(nav): restructure navigation into 5 semantic areas (R2.4-4)" \
  --body "$(cat <<'EOF'
## Summary

- Restructures PRISMA navigation from 5 existing groups into 5 semantically clearer areas aligned with the PRISMA spectrum gradient colors
- Moves `Rankings` from ENTDECKEN → ANALYSIEREN (new name for VERSTEHEN)
- Moves `News` from VERSTEHEN → ENTSCHEIDEN (better semantic fit)
- Adds `flex-wrap` to `<nav>` for mobile-first layout (no horizontal scrolling on 375 px)
- Updates 8 Vitest unit tests to match new group labels and link assignments

**Groups:**
| # | Label | Links |
|---|-------|-------|
| 1 | ENTDECKEN | Einstieg, Universen |
| 2 | ANALYSIEREN | Rankings, Aktien, Research |
| 3 | VERGLEICHEN | Backtest, Fonds |
| 4 | ENTSCHEIDEN | Signale, Alerts, News |
| 5 | PORTFOLIO | Portfolio, 3a Sim, Steuer |

**Spec:** `docs/specs/2026-06-11-navigation-restructure.md`

## Test plan

- [ ] `npm run test -- --run` in `frontend/` — all green
- [ ] `npx tsc --noEmit` — no errors
- [ ] Manual: all 14 links reachable in browser
- [ ] Manual: no horizontal scroll on 375 px viewport (iPhone SE)
- [ ] Manual: PRISMA spectrum gradient line still visible across full width

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" \
  --draft \
  --base develop
```

- [ ] PR URL notieren

---

## Task 6: AI-USAGE.md Eintrag

Folgenden Eintrag **oben** in den Eintrags-Bereich von `docs/AI-USAGE.md` einfügen
(nach dem Format-Block, vor dem ältesten Eintrag):

```markdown
## 2026-06-11 · Navigation Restructure Spec + Plan (R2.4-4)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: Spec `docs/specs/2026-06-11-navigation-restructure.md` + Plan
  `docs/superpowers/plans/2026-06-11-navigation-plan.md` für Navigation-Restrukturierung
  in 5 semantische Bereiche (ENTDECKEN, ANALYSIEREN, VERGLEICHEN, ENTSCHEIDEN, PORTFOLIO).
  Kein Implementierungscode — nur Spec + Plan gemäss AGENTS.md §2.1/2.2.
- **Was gut lief**: Bestehende `nav-links.tsx` und `routes.ts` gelesen, bevor die Spec
  geschrieben wurde (Reality-Check-Pattern P2). Alle 14 Links inventarisiert und in neue
  Gruppen verteilt ohne eine Route zu verlieren.
- **Was nicht klappte**: Noch keine — Implementierung steht aus.
- **Nachbearbeitung nötig bei**: Implementation nach User-Freigabe der Spec.
- **Autor**: Helin Koyuncu (mit Claude Code)
```

Commit:

```bash
git add docs/AI-USAGE.md
git commit -m "docs(ai-usage): add R2.4-4 navigation spec+plan entry

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

## Checkliste gesamt

- [ ] Task 1: `nav-links.tsx` geändert
- [ ] Task 2: Tests aktualisiert und grün
- [ ] Task 3: `tsc --noEmit` und `npm run test` grün
- [ ] Task 4: Commits und Push
- [ ] Task 5: Draft-PR geöffnet
- [ ] Task 6: AI-USAGE.md Eintrag
