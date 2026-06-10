# Spec: Aktien-Liste mit Suche, Filter & Sortierung

**Datum:** 2026-06-10
**Status:** Accepted
**Issues:** #61, #69
**Rolle:** Frontend

## Problem

Die Route `/stocks` hat aktuell nur eine Detailseite (`/stocks/[ticker]`), aber keine Index-Seite. Nutzer können Aktien nur direkt ansteuern, wenn sie den Ticker bereits kennen. Es gibt keine Möglichkeit, das Universum zu browsen, zu filtern oder zu sortieren.

## Ziel

Eine `/stocks`-Listenseite mit:
- Durchsuchbarer, sortierbarer Tabelle aller Aktien
- Live-Suche (Debounce 300 ms) nach Ticker und Name
- 3a-Badge für Swiss-Aktien mit Market-Cap ≥ 100M CHF
- Filter-Checkbox "Nur 3a-geeignet"
- Klickbare Spaltenköpfe (Ticker A→Z, Market-Cap, Sektor A→Z)
- Navigation-Link "Aktien" in der Top-Nav

## Scope

**In Scope**
- `app/stocks/page.tsx` — neue Server/Client-Seite mit `StocksListClient`-Komponente.
- `components/stocks-list-client.tsx` — Client-Komponente: Tabelle, Suche, Filter, Sortierung.
- `ROUTES.stocks` und Nav-Link "Aktien" in `nav-links.tsx`.
- Daten via bestehendem `listStocks()` aus `lib/api/stocks.ts` (kein Backend-Change).
- 3a-Eignung: `exchange === 'XSWX'` (Swiss Exchange) — market_cap-Feld fehlt im aktuellen `StockRead`; 3a-Badge wird vorerst nur auf Basis von `country === 'CH'` angezeigt (exakte Market-Cap-Prüfung folgt wenn Backend-Field vorhanden).
- Sortierung: `ticker` (A→Z / Z→A), `sector` (A→Z), default keine Sortierung.
- Spalten: Ticker, Name, Sektor, Land, Währung, 3a-Badge.
- Lucide-Icons für aktive Sortier-Spalte (`ArrowUp`, `ArrowDown`, `ArrowUpDown`).

**Out of Scope**
- Pagination (limit=200 reicht für aktuelles Universum).
- Market-Cap-Spalte (Feld fehlt im Backend-Response).
- Exchange-Filter per Dropdown (folgt in separatem Issue).
- Backend-Änderungen.

## Betroffene Schichten

| Schicht | Datei |
|---|---|
| Frontend Route | `frontend/app/stocks/page.tsx` |
| Frontend Component | `frontend/components/stocks-list-client.tsx` |
| Frontend Nav | `frontend/app/nav-links.tsx`, `frontend/lib/routes.ts` |
| Tests | `frontend/app/stocks/__tests__/stocks-list.test.tsx` |

## Tests (Vitest)

- Rendert Tabelle mit Stock-Daten
- Live-Suche filtert nach Ticker (case-insensitive)
- Live-Suche filtert nach Name
- "Nur 3a-geeignet"-Checkbox versteckt Nicht-CH-Aktien
- Sortierung nach Ticker: Klick auf Header sortiert A→Z, zweiter Klick Z→A, dritter Klick zurück auf Default
- Sortierung nach Sektor: A→Z
- Leerer Suchbegriff zeigt alle Aktien

## Akzeptanzkriterien

1. `/stocks` zeigt eine Tabelle mit allen Aktien aus `GET /api/v1/stocks`.
2. Nav-Link "Aktien" erscheint in der Top-Navigation und ist bei aktivem Pfad hervorgehoben.
3. Live-Suche filtert by Ticker und Name (debounced).
4. "Nur 3a-geeignet"-Checkbox filtert auf CH-Aktien.
5. Klickbare Spaltenköpfe (Ticker, Sektor) mit Pfeil-Icon; aktive Spalte hervorgehoben.
6. Zeilen-Klick navigiert zu `/stocks/[ticker]`.
7. CI: lint + tsc + vitest grün.
