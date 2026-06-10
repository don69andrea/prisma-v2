# Spec: 3a-Eignung Panel auf Factsheet (#63)

**Datum:** 2026-06-10  
**Issue:** #63  
**Status:** draft

## Ziel

Auf dem Stock-Factsheet (`/stocks/[ticker]` und Rankings-Factsheet) wird ein Panel angezeigt, das erklärt, ob eine Aktie für die Säule 3a (gebundene Vorsorge, BVV2) geeignet ist und — falls nicht — warum.

## Backend

### Endpoint

```
GET /api/v1/stocks/{ticker}/3a-eligibility
```

### Response-Schema (`EligibilityRead`)

```json
{
  "ticker": "NESN",
  "eligible": true,
  "reasons": [],
  "disclaimer": "Regelbasiert – keine Anlageberatung."
}
```

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `ticker` | string | Ticker-Symbol (uppercase) |
| `eligible` | bool | Erfüllt BVV2-Kriterien |
| `reasons` | list[str] | Ablehnungsgründe (leer wenn eligible) |
| `disclaimer` | string | Pflicht-Hinweis |

### Stub-Regelwerk

| Bedingung | eligible | Grund |
|-----------|----------|-------|
| `country == 'CH'` | `true` | — |
| `country != 'CH'` | `false` | `"Nicht an anerkannter Börse kotiert (SIX/BX Swiss)"` |

- Ticker nicht in DB → 404

### Router

Erweiterung von `backend/interfaces/rest/routers/stocks.py`.

## Tests

- 200 für NESN (CH) → eligible=true
- 200 für AAPL (US) → eligible=false
- AAPL reasons enthält Börsen-Grund
- Response hat disclaimer
- 404 für unbekannten Ticker

## Frontend

### API-Funktion

`frontend/lib/api/eligibility.ts` → `getEligibility(ticker): Promise<EligibilityRead>`

### Komponente

`frontend/components/EligibilityPanel.tsx`

- Grüner Badge "3a-geeignet" wenn eligible, roter Badge "Nicht 3a-geeignet" wenn nicht
- Bei nicht-eligible: Ablehnungsgründe als Liste
- Disclaimer als Fusszeile
- Skeleton während Loading

### Integration

- `frontend/app/stocks/[ticker]/page.tsx` — via `useQuery(getEligibility)`

## Out of Scope

- Echte BVV2-Datenbank / FINMA-Whitelist
- Integration in Rankings-Factsheet (`factsheet-view.tsx`) — separates Issue
- Mehrsprachigkeit
