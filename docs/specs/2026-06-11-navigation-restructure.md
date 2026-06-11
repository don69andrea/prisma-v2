# Spec: Navigation Restructure — 5 Bereiche (R2.4-4)

**Status:** Draft — ready for review
**Datum:** 2026-06-11
**Task-ID:** R2.4-4
**Autor:** Helin Koyuncu (mit Claude Code Sonnet 4.6)
**Branch:** `feature/helin-navigation`
**Bezieht sich auf:** `docs/specs/2026-04-21-prisma-capstone-design.md` §11 (Frontend), `CLAUDE.md` §R2.4-4

---

## Ziel

Die aktuelle horizontale Top-Navigation in `frontend/app/nav-links.tsx` verteilt 14 Links
über 5 Gruppen (ENTDECKEN, VERSTEHEN, VERGLEICHEN, ENTSCHEIDEN, PORTFOLIO), die auf
einem einzigen `<header>`-Streifen nebeneinander erscheinen. Auf mittleren Bildschirmen
läuft die Nav über — die Gruppenbezeichnungen sind ab ~768 px abgeschnitten, und auf
Mobile (< 640 px) ist das horizontale Scrolling unergonomisch.

**Ziel dieser Spec:** Die Navigation in 5 semantisch klare Bereiche umstrukturieren,
die auf allen Viewports (Mobile-first) stabil und ohne horizontales Overflow-Scrollen
bedienbar sind, und dabei das bestehende PRISMA-Spektrum-Design (5-Farb-Gradient-Linie)
zu stärken.

Die 5 neuen Bereiche bilden die Nutzungsreise ab:

| Nr. | Bereich-Label | Route(s) | Icon-Farbe (PRISMA-Spektrum) |
|-----|---------------|----------|-------------------------------|
| 1 | **ENTDECKEN** | `/start`, `/universes` | Violett `#8b5cf6` |
| 2 | **ANALYSIEREN** | `/rankings`, `/stocks`, `/research` | Blau `#3b82f6` |
| 3 | **VERGLEICHEN** | `/backtest`, `/fonds` | Grün `#10b981` |
| 4 | **ENTSCHEIDEN** | `/decision`, `/alerts`, `/news` | Amber `#f59e0b` |
| 5 | **PORTFOLIO** | `/portfolio`, `/portfolio/simulator`, `/steuer` | Rot `#ef4444` |

Jeder Bereich entspricht einer Farbe des PRISMA-Spektrum-Gradients, der bereits im
`<header>` als 3 px hohe Linie existiert.

---

## Betroffene Komponenten

| Datei | Änderungstyp | Beschreibung |
|-------|--------------|--------------|
| `frontend/app/nav-links.tsx` | **Modify** | `NAV_GROUPS` von 5 auf 5 neu strukturierte Gruppen; neue Gruppenstruktur und Link-Zuweisung |
| `frontend/app/layout.tsx` | **Modify** | Header-Container auf `flex-wrap` + `gap-y-1` anpassen für mobile Zeilenumbrüche |
| `frontend/app/__tests__/nav-links.test.tsx` | **Modify** | Bestehende Tests auf neue Gruppen-Labels aktualisieren; neue Test-Cases für mobile Darstellung |
| `frontend/lib/routes.ts` | **Keine Änderung** | Alle Routen bleiben unverändert |

> **Nicht-Änderung:** Die Routen in `frontend/lib/routes.ts` bleiben vollständig identisch.
> Es werden keine neuen Seiten, Backend-Endpunkte oder API-Verträge berührt.

---

## Neue Struktur (5 Bereiche im Detail)

### Bereich 1: ENTDECKEN
**Semantik:** Einstiegspunkt und Universum-Selektion — der Nutzer entdeckt, was PRISMA kann.

| Link-Label | Route | Bestehend? |
|------------|-------|------------|
| Einstieg | `/start` | Ja (war in ENTDECKEN) |
| Universen | `/universes` | Ja (war in ENTDECKEN) |

**Entfernt aus diesem Bereich:** `Rankings` → zieht um nach ANALYSIEREN.

---

### Bereich 2: ANALYSIEREN
**Semantik:** Quantitative Analyse — Rankings, Einzelaktien, Research-Memos.

| Link-Label | Route | Bestehend? |
|------------|-------|------------|
| Rankings | `/rankings` | Ja (war in ENTDECKEN) |
| Aktien | `/stocks` | Ja (war in VERSTEHEN) |
| Research | `/research` | Ja (war in VERSTEHEN) |

**Entfernt aus VERSTEHEN:** `News` → zieht um nach ENTSCHEIDEN (thematisch besser dort).
**Umbenennung:** Gruppe heisst neu ANALYSIEREN statt VERSTEHEN.

---

### Bereich 3: VERGLEICHEN
**Semantik:** Backtesting und Fonds-Benchmarking — identisch zum bisherigen Bereich.

| Link-Label | Route | Bestehend? |
|------------|-------|------------|
| Backtest | `/backtest` | Ja (war in VERGLEICHEN) |
| Fonds | `/fonds` | Ja (war in VERGLEICHEN) |

**Keine Änderung der Links** — nur Farb-Zuordnung (Grün) wird explizit.

---

### Bereich 4: ENTSCHEIDEN
**Semantik:** Aktions-Signale, Alerts und aktuelle News als Entscheidungsgrundlage.

| Link-Label | Route | Bestehend? |
|------------|-------|------------|
| Signale | `/decision` | Ja (war in ENTSCHEIDEN) |
| Alerts | `/alerts` | Ja (war in ENTSCHEIDEN) |
| News | `/news` | Neu in diesem Bereich (war in VERSTEHEN) |

**Neuzugang:** `News` passt semantisch besser zu Entscheidungs-Input als zu Analyse.

---

### Bereich 5: PORTFOLIO
**Semantik:** Portfolio-Management, Simulator und Steuer — identisch zum bisherigen Bereich.

| Link-Label | Route | Bestehend? |
|------------|-------|------------|
| Portfolio | `/portfolio` | Ja |
| 3a Sim | `/portfolio/simulator` | Ja |
| Steuer | `/steuer` | Ja |

**Keine Änderung der Links.**

---

## Mobile-First Responsive Design

### Problem heute
Die aktuelle `nav`-Klasse `flex items-start gap-6 overflow-x-auto scrollbar-none`
erzeugt horizontales Scrollen auf kleinen Viewports. Die Gruppenbezeichnungen
`text-[9px]` sind bei 320–375 px kaum lesbar.

### Anforderungen

| Viewport | Verhalten |
|----------|-----------|
| **Mobile** (< 640 px) | Nav bricht auf 2–3 Zeilen um; kein horizontales Scrollen; alle 5 Gruppen bleiben sichtbar |
| **Tablet** (640–1024 px) | Nav bleibt in einer Zeile; Gruppen sind kompakt, aber vollständig lesbar |
| **Desktop** (> 1024 px) | Identisch zu heute — alle 5 Gruppen horizontal |

### Umsetzung (in der Spec definiert, Details im Plan)

- `<nav>` erhält zusätzlich `flex-wrap` um Zeilenumbrüche zu erlauben
- `shrink-0` auf Gruppen-`<div>` bleibt, verhindert zu schmale Gruppen
- `<header>`-Container: `flex-col gap-2 py-2 sm:flex-row sm:items-center sm:gap-0 sm:py-0`
  bleibt unverändert (bereits vorhanden in `layout.tsx`)
- Gruppen-Label-Schriftgrösse: `text-[9px]` → `text-[10px]` für bessere Lesbarkeit
  auf Mobile
- Kein Einführen von Hamburger-Menu / Drawer — Scope dieser Spec

---

## Test-Cases

### Unit-Tests (Vitest — `frontend/app/__tests__/nav-links.test.tsx`)

| TC-ID | Beschreibung | Erwartetes Ergebnis |
|-------|--------------|---------------------|
| TC-01 | Rendert alle 5 Gruppen-Labels | `ENTDECKEN`, `ANALYSIEREN`, `VERGLEICHEN`, `ENTSCHEIDEN`, `PORTFOLIO` sichtbar |
| TC-02 | Aktiver Link `/rankings` hebt Rankings hervor | `aria-current="page"` + `text-foreground` auf Rankings-Link |
| TC-03 | Verschachtelte Pfade — `/rankings/abc` aktiviert Rankings | `aria-current="page"` bei `startsWith('/rankings')` |
| TC-04 | Alle 14 Links sind im DOM vorhanden | Je Link-Label ein `<a>`-Element |
| TC-05 | Inaktiver Link trägt kein `aria-current` | Kein Attribut auf nicht-aktivem Link |
| TC-06 | News-Link ist in ENTSCHEIDEN-Gruppe | `screen.getByText('ENTSCHEIDEN')` enthält `getByRole('link', {name: 'News'})` |
| TC-07 | Rankings ist in ANALYSIEREN-Gruppe | `screen.getByText('ANALYSIEREN')` enthält Rankings-Link |
| TC-08 | Root-Pfad `/` aktiviert keinen Link ausser Dashboard | Kein Link hat `aria-current` auf `/` wenn kein Link auf `/` zeigt |

### Manuelle Akzeptanz-Tests

| TC-ID | Beschreibung | Viewport |
|-------|--------------|----------|
| MT-01 | Alle 5 Gruppen sichtbar ohne horizontales Scrollen | 375 px (iPhone SE) |
| MT-02 | PRISMA-Spektrum-Linie bleibt vollständig sichtbar | Alle Viewports |
| MT-03 | Klick auf jeden der 14 Links führt zur richtigen Route | Desktop |
| MT-04 | Aktiver Zustand korrekt bei direktem URL-Aufruf | Desktop + Mobile |

---

## Nicht-Ziele

- **Kein Hamburger-Menu / Drawer-Navigation** — zu aufwändig für R2.4-Scope
- **Kein Icon-Set pro Gruppe** — Text-Labels reichen für Capstone-Demo
- **Keine Änderung der Backend-Routes oder API-Endpunkte**
- **Keine Änderung der Seiteninhalt-Komponenten** — nur Nav-Struktur
- **Kein Einführen neuer npm-Packages** — bestehende Tailwind-Klassen reichen
- **Kein Entfernen bestehender Routen** — alle 14 Links bleiben erhalten
- **Kein A/B-Test oder Feature-Flag** — direkter Austausch
- **Kein Dark-Mode-Toggle** — bereits über PRISMA Dark-Theme gelöst
- **Kein Sub-Navigation / Dropdown** — alle Links bleiben flat auf oberster Ebene

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| `frontend/lib/routes.ts` — alle ROUTES müssen existieren | Bereits vollständig vorhanden |
| `frontend/app/layout.tsx` — Header-Wrapper | Vorhanden, minimale Anpassung nötig |
| Tailwind CSS, shadcn/ui, lucide-react | Installiert |
| R2.4-1 Discovery Engine (Andrea) | Keine Blockierung — Nav-Struktur unabhängig |

---

## Akzeptanz-Kriterien (Definition of Done)

- [ ] `nav-links.tsx` enthält genau 5 `NAV_GROUPS` mit den in dieser Spec definierten Labels
- [ ] Alle 14 Links sind weiterhin erreichbar und zeigen auf dieselben Routen
- [ ] `npm run test` im `frontend/`-Verzeichnis ist grün (Vitest)
- [ ] Keine TypeScript-Fehler (`tsc --noEmit`)
- [ ] Kein horizontales Scrolling auf 375 px Viewport (manuell oder Playwright)
- [ ] PR ist gegen `develop` geöffnet und hat mindestens 1 Approval
