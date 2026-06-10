# Spec: Rankings CSV-Export (#65)

**Datum:** 2026-06-10  
**Issue:** #65  
**Status:** draft

## Ziel

Ranking-Resultate als CSV-Datei exportieren, damit Quant-Analysten die Daten in Excel/Python weiterverarbeiten können. Das Frontend hat bereits einen client-seitigen Export (Blob-Download). Zusätzlich wird ein Backend-Endpunkt bereitgestellt, der serverseitig CSV generiert.

## Backend

### Endpoint

```
GET /api/v1/runs/{run_id}/export?format=csv
```

- `run_id`: UUID des Ranking-Runs
- `format=csv` (einziger unterstützter Wert; default: `csv`)
- Response Content-Type: `text/csv; charset=utf-8`
- Response Header: `Content-Disposition: attachment; filename="prisma-ranking-{run_id[:8]}.csv"`

### CSV-Spalten

```
rank,ticker,name,sector,weighted_avg,is_sweet_spot,quality_classic,diversification,trend_momentum,value_alpha_potential,alpha
```

- `rank` = `total_rank`
- `ticker`, `name`, `sector` werden aus StockService angereichert (best-effort: fehlt ein Stock → name/sector leer)
- `weighted_avg` auf 4 Dezimalstellen
- `is_sweet_spot` = `true`/`false`
- Modell-Ranks: Integer oder leer wenn `null`
- Sortierung: `total_rank ASC` (null ans Ende)

### Fehlerfall

- Run nicht gefunden → `404 { "detail": "RankingRun ... not found" }`

### Implementierung

- Neues `export_rankings_csv()` in `backend/interfaces/rest/routers/runs.py`
- Nutzt `StreamingResponse` mit `media_type="text/csv"`
- Kein neues Service-Layer nötig: Router kombiniert `get_rankings()` + `stock_service.get_by_ticker()`

## Tests

- `GET /api/v1/runs/{valid_run_id}/export?format=csv` → 200, `text/csv`
- Response-Body enthält CSV-Header-Zeile
- Response-Body enthält Ticker-Zeile
- `Content-Disposition`-Header gesetzt
- Unbekannte `run_id` → 404

## Out of Scope

- Frontend-Änderungen (client-seitiger Export in `rankings-table.tsx` bereits vorhanden)
- Andere Formate (Excel, JSON)
- Datenbankpersistenz des Exports
