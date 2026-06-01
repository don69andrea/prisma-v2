# Spec: Backtest — Run-Auswahl per Dropdown

**Datum:** 2026-06-01
**Status:** Accepted
**Rolle:** Frontend & Demo

## Problem

Das Backtest-Formular (`/backtest`) verlangt die **Run-ID als rohes UUID-Textfeld**. Ein Nutzer hat im UI keinen bequemen Weg, an die UUID zu kommen — sie steckt nur in der Rankings-Detail-URL. Schlechte UX, fehleranfällig (Tippfehler).

## Ziel

Das UUID-Textfeld durch ein **Dropdown** ersetzen, das die letzten Runs auflistet (Datum · Universum), Wert = Run-UUID. Niemand muss mehr eine UUID anfassen.

## Scope

**In Scope**
- `<select>` (natives Element, analog `RankingsForm`-Universe-Select) statt `<Input>` für die Run-Auswahl.
- Befüllung über bestehende `listRuns(50, 0)`-API via `useQuery` (kein Backend-Change).
- Nur **completed** Runs werden als Optionen angeboten (Backtest braucht ein fertiges Ranking).
- Option-Label: `de-CH`-formatiertes Datum · `universe_name`.
- Zustände: Loading („Lädt Runs…"), Empty („Keine abgeschlossenen Runs"), Default-Platzhalter („— Run wählen —").
- **Deep-Link-Kompatibilität:** `?run_id=<uuid>` füllt weiter den State; ist die UUID nicht in der Liste, wird sie als zusätzliche Fallback-Option gerendert (E2E `05-backtest` bleibt grün).

**Out of Scope**
- Backend-Änderungen, Pagination des Dropdowns, Filter nach Universum.

## Tests

- `app/backtest/__tests__/backtest-form.test.tsx` (Vitest):
  - nur completed Runs als Optionen (pending/failed werden gefiltert)
  - Start-Button disabled bis ein Run gewählt ist
  - Empty-State wenn keine completed Runs
- Bestehender E2E `05-backtest.spec.ts` bleibt unverändert grün (Deep-Link-Pfad).

## Akzeptanzkriterien

1. `/backtest` zeigt ein Run-Dropdown statt UUID-Textfeld.
2. Nur completed Runs wählbar; Auswahl aktiviert den Start-Button.
3. Deep-Link `?run_id=` funktioniert weiterhin.
4. CI-Mirror grün (lint + tsc + vitest + e2e).
