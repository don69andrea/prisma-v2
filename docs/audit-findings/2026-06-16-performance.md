# Audit-Findings — Performance (2026-06-16)

## Setup
Eigene isolierte Infrastruktur (nicht der gemeinsame Audit-Stack auf 8090/3090/5433):
- Postgres (pgvector/pgvector:pg16) in eigenem Docker-Container `prisma-db-perf`, Port 5434, eigenes Volume `prisma-perf-pgdata`
- Backend nativ via uvicorn, Port 8092, gegen obige DB (alembic upgrade head + seed_smi_universe.py + seed_tech_catalog.py)
- Last-Tool: Locust 2.44.3, Profil gegen `/api/v1/stocks`, `/api/v1/universes`, `/api/v1/stocks/NESN/factsheet` (alle drei reine DB-Reads, kein LLM-/VoyageAI-Call)
- Beide Komponenten nach Test wieder vollständig entfernt (Backend-Prozess gekillt, Container + Volume gelöscht)

## Last-Test-Ergebnisse
| Concurrent Users | p50 | p95 | p99 | Error-Rate |
|---|---|---|---|---|
| 5   | 4 ms   | 40 ms  | 210 ms  | 63.6% |
| 20  | 4 ms   | 16 ms  | 27 ms   | 66.3% |
| 50  | 3 ms   | 14 ms  | 19 ms   | 66.0% |
| 100 | 3 ms   | 13 ms  | 20 ms   | 65.7% |
| 200 | 2 ms   | 13 ms  | 93 ms   | 67.1% |

Hinweis: Die reinen Latenzwerte sind durchgehend niedrig (p95 nie über 40ms) — die hohe Error-Rate ist **kein** Performance-Problem im engeren Sinn, sondern ein Fehlkonfigurationsfund (siehe F-PERF-1). Die "echten" 2xx-Antworten (insb. `/api/v1/universes`, das nicht vom Bug betroffen ist) bleiben auch bei 200 Usern schnell und fehlerfrei (0% Error-Rate, p95 ~17ms).

## Breaking Point
Kein klassischer Last-induzierter Breaking Point gefunden — die DB/App-Latenz bleibt bis 200 gleichzeitigen Usern unauffällig niedrig (Tabelle `stocks` hat nur 33 Zeilen, `EXPLAIN ANALYZE` zeigt 0.167ms Execution Time, Index auf `ticker` vorhanden). Stattdessen tritt bereits **ab 5 parallelen Usern** eine strukturelle Fehlerquote von >60% auf 429 Too Many Requests zurückzuführen auf eine Fehlkonfiguration des Rate-Limiters (F-PERF-1) — dies ist faktisch der "Breaking Point" aus Nutzersicht, weil ein Großteil der echten Produktiv-Last (jede Stock-Liste/Factsheet-Abfrage) künstlich limitiert wird, lange bevor die Infrastruktur selbst an Grenzen käme.

## Befunde

### F-PERF-1 — Rate-Limiter blockiert LLM-freie Stocks-Endpoints fälschlich mit
- **Bereich:** Performance / Verfügbarkeit
- **Schweregrad:** Kritisch
- **Ort:** `backend/interfaces/rest/rate_limiter.py:32` (`_LLM_PREFIXES`-Tupel, Eintrag `"/api/v1/stocks"`); betrifft alle Routen aus `backend/interfaces/rest/routers/stocks.py` (reine GET-Endpoints: Liste, Factsheet, etc. — keiner davon löst einen Claude/VoyageAI-Call aus)
- **Beschreibung:** Der `LLMRateLimiterMiddleware` matched Pfade per `str.startswith()` gegen ein Prefix-Tupel, das eigentlich nur LLM-auslösende Endpoints (Chat, Discovery, Memo-Generierung etc.) schützen soll. Der Prefix `"/api/v1/stocks"` ist jedoch zu breit gefasst und erfasst **alle** Stocks-Endpoints inkl. der reinen Lese-Routen `GET /api/v1/stocks` (Liste) und `GET /api/v1/stocks/{ticker}/factsheet`, die keinen LLM-Call machen. Das Limit von 10 Requests/IP/60s ist für ein einzelnes teures LLM-Memo sinnvoll, killt aber jede normale Nutzung der Stocks-Liste (z.B. beim Tabellen-Scrollen/Sortieren im Frontend) nach wenigen Klicks.
- **Reproduktion:** Lasttest mit 5 gleichzeitigen Usern gegen `/api/v1/stocks` und `/api/v1/stocks/NESN/factsheet` (kein Discovery/Chat/Memo beteiligt) ergibt bereits ab dem 11. Request pro Client innerhalb 60s durchgehend `429 Too Many Requests` — Error-Rate >60% schon bei niedrigster Teststufe, verschlechtert sich nicht weiter bei höherer Last (Sättigungseffekt des Limiters, nicht der DB).
- **Vorschlag:** `_LLM_PREFIXES` auf die tatsächlich LLM/Embedding-auslösenden Pfade einschränken (z.B. `/api/v1/discovery`, `/api/v1/chat`, `/memos/generate`, `/memos/batch`, `/api/v1/macro/score`, `/api/v1/portfolio/monte-carlo`, `/api/v1/steuer`, `/api/v1/decisions/explain`, `/api/v1/news/ingest`). `/api/v1/stocks` und `/api/v1/runs` so verfeinern, dass nur die tatsächlich teuren Sub-Routen (z.B. POST-Aktionen, die Memos/Discovery anstoßen) erfasst werden, nicht die GET-Liste/Factsheet/Health-Pfade. Ggf. zusätzlich ein separates, deutlich großzügigeres Limit für reine Lese-Endpoints einführen, falls DoS-Schutz dort gewünscht ist.

### F-PERF-2 — Mehrere Frontend-Routen mit überdurchschnittlich großem First-Load-JS
- **Bereich:** Performance (Frontend)
- **Schweregrad:** Nice-to-have
- **Ort:** `frontend/app/stocks/[ticker]` (258 kB), `frontend/app/rankings/[runId]/stock/[ticker]` (256 kB), `frontend/app/rankings/[runId]` (253 kB), `frontend/app/backtest` (237 kB)
- **Beschreibung:** Median-First-Load-JS über alle 26 Routen liegt bei ca. 125-150 kB (Shared-Chunk 87.6 kB + Route-spezifisch). Die vier genannten Routen liegen 60-75% darüber. Das sind durchweg Detail-/Charting-Seiten — plausibel durch Chart-Bibliotheken (z.B. recharts/visx) bedingt, aber nicht codesplittet/lazy geladen.
- **Reproduktion:** `cd frontend && npm run build` — Tabelle "Route (app) / First Load JS" in der Build-Ausgabe.
- **Vorschlag:** Prüfen, ob Chart-Komponenten auf diesen Routen per `next/dynamic` mit `ssr: false` nachgeladen werden können, um den initialen Bundle für Erstaufruf zu verkleinern. Kein dringender Fix, da absolute Werte (<260 kB) noch im akzeptablen Bereich liegen.

## Negativ-Befunde (geprüft, kein Problem gefunden)
- **DB-Performance:** `EXPLAIN ANALYZE` für die reale `list()`-Query aus `backend/infrastructure/persistence/repositories/stock_repository.py:53-58` (`SELECT * FROM stocks ORDER BY ticker LIMIT 50 OFFSET 0`) zeigt Execution Time 0.167ms bei 33 Zeilen, Sort nutzt vorhandenen Unique-Index `ix_stocks_ticker`. Keine Optimierung nötig bei aktueller Datenmenge.
- **Blockierende Sync-Calls im Event-Loop:** `grep -rn "yf\.\|requests\.get\|requests\.post" backend/application backend/infrastructure` ergab 15 Treffer. Alle async-Pfad-relevanten Stellen sind korrekt mit `asyncio.to_thread` abgesichert: `yfinance_swiss.py` (`_sync_info`/`_sync_history`/`_sync_dividends` werden nur via `to_thread` aufgerufen), `yfinance_crypto.py:_download` (`to_thread`-Wrapper), `macro_service.py:_fetch_chf_eur` (`to_thread`-Wrapper), `monte_carlo_service.py:_fetch_ticker_params` (`to_thread`-Wrapper), `ml_feature_service.py:build_features` ruft `_current_chf_eur` via `to_thread` auf. Die einzigen *unwrapped* `yf.download`/`yf.Ticker(...).info`-Aufrufe liegen in `ml_feature_service.py` (`build_dataset`, `_stub_fundamentals`, `_current_chf_eur`-Body) und `crypto_scoring_service.py` — `build_dataset` ist aber eine reine `def` (nicht `async def`) und wird ausschließlich von `scripts/train_return_predictor.py` (Offline-CLI, kein Request-Handler, kein Event-Loop-Konflikt) aufgerufen. **Kein neuer Fund** seit letztem Audit — keine zusätzlichen ungeschützten Stellen im Crypto-Modul oder anderswo identifiziert.
