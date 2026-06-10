# Spec: Fundamentaldaten-Widget auf Factsheet (#68)

**Datum:** 2026-06-10
**Status:** Accepted
**Rolle:** Backend + Frontend

## Problem

Das Stock-Factsheet unter `/stocks/[ticker]` zeigt aktuell nur Ticker und einen Memo-Button. Für die Bewertung eines Titels fehlen Kennzahlen wie KGV, KBV und Dividendenrendite.

## Ziel

Ein `FundamentalsCard`-Widget auf dem Factsheet, das KGV (P/E), KBV (P/B), FCF-Rendite, Operating Margin und Dividendenrendite aus dem vorhandenen `StubFundamentalsProvider` anzeigt.

## Scope

**In Scope**
- `GET /api/v1/stocks/{ticker}/fundamentals` — neuer Endpoint in `stocks.py`
- `FundamentalsRead`-Schema in `backend/interfaces/rest/schemas/stock.py`
- `frontend/lib/api/fundamentals.ts` — API-Client-Funktion
- `frontend/components/FundamentalsCard.tsx` — Display-Komponente
- Integration in `frontend/app/stocks/[ticker]/page.tsx`
- Disclaimer: "Stub-Daten — kein Anlageberatung"

**Out of Scope**
- Live-Daten via yfinance / FMP (folgt in separatem Issue)
- `eps_chf` (nicht im StubProvider vorhanden)
- Andere Factsheet-Seite unter `/rankings/[runId]/stock/[ticker]`

## Betroffene Schichten

| Schicht | Datei |
|---|---|
| Backend Endpoint | `backend/interfaces/rest/routers/stocks.py` |
| Backend Schema | `backend/interfaces/rest/schemas/stock.py` |
| Frontend API | `frontend/lib/api/fundamentals.ts` |
| Frontend Component | `frontend/components/FundamentalsCard.tsx` |
| Frontend Page | `frontend/app/stocks/[ticker]/page.tsx` |
| Backend Tests | `tests/integration/test_stocks_fundamentals.py` |

## Response-Schema

```json
{
  "ticker": "AAPL",
  "pe_ratio": 28.0,
  "pb_ratio": 45.0,
  "fcf_yield": 0.038,
  "operating_margin": 0.302,
  "dividend_yield": 0.005,
  "disclaimer": "Stub-Daten für Demo-Zwecke. Kein Anlageberatung."
}
```

Unbekannte Ticker: alle numerischen Felder `null`, Disclaimer bleibt.

## Tests

**Backend (pytest, Integration):**
- `GET /api/v1/stocks/AAPL/fundamentals` → 200 mit pe_ratio=28.0
- `GET /api/v1/stocks/UNKNOWN/fundamentals` → 200 mit allen Feldern `null`
- `GET /api/v1/stocks/XXXNOTFOUND/fundamentals` wenn Ticker nicht in DB → 404

**Frontend (Vitest):**
- Rendert pe_ratio, pb_ratio als formatierte Zahlen
- Rendert Disclaimer-Text
- Zeigt `—` für null-Felder

## Akzeptanzkriterien

1. Endpoint antwortet mit 200 und korrekten Stub-Daten für bekannte Ticker.
2. Endpoint antwortet mit 404 wenn Ticker nicht in der Stock-DB.
3. `FundamentalsCard` zeigt alle Kennzahlen + Disclaimer auf dem Factsheet.
4. CI grün (ruff, mypy, pytest, vitest).
