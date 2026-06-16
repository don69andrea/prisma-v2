# Audit-Findings — News, Alerts, Chat, Reports (2026-06-16)

## Getestete Funktionen
- POST /api/v1/news/ingest: OK (mit Hinweis — kein freier Text/URL-Input möglich)
- POST /api/v1/news/retrieve: UX-ISSUE (Ticker-Filter funktionslos, niedrige Relevanz)
- POST /api/v1/alerts (Happy Path): OK
- POST /api/v1/alerts (SSRF-Regressionstest): OK — kein Bug, Schutz greift
- POST /api/v1/chat (Happy Path, Edge Cases leer/lang): teilweise BUG
- GET /api/v1/runs/{run_id}/export: OK, aber Doku-Missverständnis (ist CSV, kein PDF)
- GET /api/v1/stocks/{ticker}/report.pdf: BUG (HTTP 500 statt 503)
- GET/POST /api/v1/decisions/{ticker}/audit: OK
- GET /api/v1/admin/costs: BUG (Chat-Feature fehlt im Cost-Tracking)

## Befunde

### F-COMM-1 — SSRF-Schutz bei Webhook-Alerts funktioniert (Regressionstest bestanden)
- **Bereich:** Security
- **Schweregrad:** Nice-to-have (Verifikation, kein Fund)
- **Ort:** backend/interfaces/rest/schemas/alert.py (`AlertCreateRequest.validate_webhook_target`)
- **Beschreibung:** Der in der Aufgabe vorgegebene Original-Payload (`condition`/`PRICE_ABOVE`) passt nicht mehr zum aktuellen Schema (`trigger_type`: `SIGNAL_CHANGE`|`PRICE_CHANGE`) und schlägt bereits mit 422 "Field required" fehl — das ist ein False-Positive-Pass. Mit korrekt angepasstem, aktuellem Schema wurde der SSRF-Schutz gezielt erneut getestet: `http://169.254.169.254/...` (422, fehlt https://), `https://169.254.169.254/...` (422, blockierte IP), `https://127.0.0.1/...` (422), `https://10.0.0.5/...` (422). Alle Varianten korrekt blockiert.
- **Reproduktion:** s. oben, 4 curl-Varianten gegen POST /api/v1/alerts.
- **Vorschlag:** Restrisiko: Schutz prüft nur IP-Literale per Regex, kein DNS-Resolve-Check (DNS-Rebinding auf Hostnamen, die zur Request-Zeit auf private IPs zeigen, wäre nicht erkannt). Für echte Tiefenverteidigung zusätzlich beim tatsächlichen HTTP-Call (nicht nur Schema-Validierung) die aufgelöste IP prüfen.

### F-COMM-2 — Chat-Tool `get_factsheet` schlägt mit `.SW`-Suffix fehl, obwohl Tool-Beschreibung dieses Format vorschlägt
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** backend/application/services/chat_service.py:97-99 (`_get_factsheet`) und :202 (Tool-Schema-Beschreibung "z.B. NESN.SW oder AAPL")
- **Beschreibung:** Chat-Anfrage "Was ist die aktuelle Einschätzung für Nestlé (NESN)?" führt dazu, dass Claude (korrekt der Tool-Beschreibung folgend) `get_factsheet(ticker="NESN.SW")` aufruft. `SwissMarketService.get_swiss_stock()` macht aber nur `ticker.upper()` ohne Suffix-Stripping, DB enthält nur `"NESN"` → "Keine Daten für NESN.SW gefunden." Der Chat-Stream endet danach direkt mit `done`, ohne erklärenden Text an den Nutzer. Der separate REST-Endpoint `/api/v1/stocks/{ticker}/factsheet` normalisiert das Suffix dagegen korrekt (getestet: beide Formen liefern 200).
- **Reproduktion:** POST /api/v1/chat mit `{"message":"Was ist die aktuelle Einschätzung für Nestlé (NESN)?"}` → SSE: tool_call get_factsheet(NESN.SW) → tool_result "Keine Daten..." → done, keine Nutzerantwort.
- **Vorschlag:** Ticker-Suffix (`.SW`, `.US` etc.) in `_get_factsheet`/`SwissMarketService.get_swiss_stock()` strippen, analog zur Normalisierung im REST-Stocks-Router. Alternativ Tool-Beschreibung auf reines Kürzel ohne Suffix ändern.

### F-COMM-3 — Chat-Endpoint trackt keine LLM-Kosten im Admin-Cost-Dashboard
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** backend/application/services/chat_service.py (kein CostTracker-Aufruf); backend/interfaces/rest/routers/admin.py
- **Beschreibung:** `GET /api/v1/admin/costs` zeigt Features wie `narrative_engine`, `news_rag_ingestion`, `profile_classification_turn1`, aber kein `chat`-Feature, obwohl ein echter Claude-Sonnet-Call über POST /api/v1/chat durchgeführt wurde. Bei einem System mit hartem Budget-Cap (BUDGET_CAP_USD=20.00) ist es ein Risiko, wenn ein potenziell mehrstufiges Tool-Use-Feature wie Chat nicht in die Kostenkontrolle einfliesst.
- **Reproduktion:** Chat-Call durchführen, danach GET /api/v1/admin/costs prüfen — `by_feature` enthält keinen Chat-Eintrag.
- **Vorschlag:** CostTracker.track_call(...) im ChatService nach jedem Claude-API-Call ergänzen (Feature-Tag z.B. "chat").

### F-COMM-4 — PDF-Report-Endpoint liefert HTTP 500 statt erwarteter 503 bei fehlendem WeasyPrint
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have
- **Ort:** backend/interfaces/rest/routers/reports.py:27-40 (`get_report`), backend/application/services/report_service.py:144-151 (`_render_pdf`)
- **Beschreibung:** WeasyPrint ist im venv nicht installiert (`ModuleNotFoundError`) bzw. die native Lib `libgobject-2.0-0` fehlt (`OSError` beim dlopen). Der Endpoint fängt nur `ImportError` ab und mapped diesen auf 503; der tatsächlich auftretende `OSError` (fehlende System-Lib via cffi) fällt in den generischen `except Exception`-Branch → HTTP 500 "PDF-Generierung fehlgeschlagen." statt des dokumentierten/erwarteten 503. Hinweis: Laut Aufgabenstellung ist 503 bei fehlendem WeasyPrint explizit als bekanntes/akzeptiertes Verhalten vermerkt — hier tritt aber der Fehler in einer Form auf, die nicht von diesem Fix abgedeckt ist.
- **Reproduktion:** GET /api/v1/stocks/NESN/report.pdf → HTTP 500 `{"detail":"PDF-Generierung fehlgeschlagen."}`.
- **Vorschlag:** `except (ImportError, OSError)` in `get_report()`, damit fehlende native Abhängigkeiten ebenfalls als 503 statt 500 signalisiert werden (Client kann dann zuverlässig zwischen "temporär nicht verfügbar" und "echter Server-Bug" unterscheiden).

### F-COMM-5 — News-Retrieve: Ticker-Filter liefert durchgehend 0 Treffer, NER-Tagging scheint nicht zu greifen
- **Bereich:** Funktional / UX
- **Schweregrad:** Wichtig
- **Ort:** backend/application/services/news_ingestion_service.py (`TickerNer.extract`), POST /api/v1/news/retrieve mit `ticker`-Parameter
- **Beschreibung:** Nach Ingestion von 101 NZZ/SRF-Artikeln haben alle zurückgegebenen Such-Treffer ein leeres `tickers: []`-Feld. Eine gezielte Suche mit `{"query":"Nestlé","ticker":"NESN"}` liefert 0 Treffer, obwohl Artikel zum Thema Finanzen/Börse vorhanden sind. Der ticker-gefilterte Modus ist damit für RSS-Ingestion praktisch nutzlos.
- **Reproduktion:** POST /api/v1/news/ingest, danach POST /api/v1/news/retrieve mit `ticker` gesetzt → total:0.
- **Vorschlag:** TickerNer-Erkennung auf NZZ/SRF-Artikeltexten prüfen/kalibrieren (evtl. zu strikte Matching-Regeln oder fehlende Aliasliste für Schweizer Firmennamen).

### F-COMM-6 — News-Retrieve: niedrige Relevanz der Top-Treffer bei thematischer Suche
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** POST /api/v1/news/retrieve, backend/application/services/news_retrieval_service.py
- **Beschreibung:** Suche `{"query":"Nestlé Aktie Quartalszahlen","k":5}` liefert Top-Treffer mit Similarity 0.32–0.45 zu Themen wie "DSM-Firmenich Börsengang", "Pensionskassen-Qualität", "Newsquiz der Woche" — keiner der 5 Treffer behandelt tatsächlich Nestlé-Quartalszahlen. Erwartbar, da der RSS-Corpus (NZZ Finanzen + SRF allgemein) zum Ingest-Zeitpunkt evtl. keinen passenden Artikel enthielt, aber die UI/API liefert keinen Hinweis auf "geringe Konfidenz" an den Nutzer.
- **Reproduktion:** s. oben.
- **Vorschlag:** Similarity-Schwellwert einführen (z.B. Hinweis "geringe Relevanz" ab < 0.5) statt immer k Treffer ungefiltert zurückzugeben.

### F-COMM-7 — News-Ingest hat keinen Endpoint-Parameter für freien Testtext/URL; synchron mit ~33s Laufzeit
- **Bereich:** Funktional / Performance
- **Schweregrad:** Nice-to-have
- **Ort:** backend/interfaces/rest/routers/news.py (`ingest_news`), backend/interfaces/rest/schemas/news.py
- **Beschreibung:** POST /api/v1/news/ingest nimmt keinen Request-Body — es triggert ausschliesslich die fest konfigurierten RSS-Feeds (NZZ + SRF), kein Ad-hoc-Text oder URL wie in der Aufgabenstellung angenommen. Der Call blockierte synchron 33 Sekunden (101 Artikel inkl. Embedding-Calls), ohne Fortschrittsanzeige/Async-Job-Pattern.
- **Reproduktion:** POST /api/v1/news/ingest ohne Body → 200 nach 33s, `{"ingested":101,"skipped_duplicate":3,"errors":0}`.
- **Vorschlag:** Für manuelles Debugging/Testing einen optionalen Single-Artikel-Ingest-Endpoint anbieten; für Produktion ggf. Background-Task/Job-Queue statt synchronem Request, um Timeouts bei wachsendem Feed-Volumen zu vermeiden.

### F-COMM-8 — Endpoint /api/v1/runs/{run_id}/export liefert CSV, nicht PDF (Doku-Erwartung in Aufgabenstellung falsch)
- **Bereich:** Funktional (kein Code-Bug, Klarstellung)
- **Schweregrad:** Nice-to-have
- **Ort:** backend/interfaces/rest/routers/runs.py:92-134 (`export_rankings_csv`)
- **Beschreibung:** Der Endpoint ist by Design ein CSV-Export der Rankings (`format` Query-Param mit `pattern="^csv$"`), kein PDF/Audit-Report. Der echte PDF-Export liegt unter `GET /api/v1/stocks/{ticker}/report.pdf` (separater Service, siehe F-COMM-4). Kein Bug, aber Verwechslungspotenzial zwischen "Run-Export" und "PDF-Report".
- **Reproduktion:** GET /api/v1/runs/{run_id}/export → HTTP 200, `file`-Check ergibt "CSV text".
- **Vorschlag:** Keine Code-Änderung nötig; Doku/Naming zwischen Run-Export (CSV) und Ticker-Report (PDF) klarer trennen, evtl. Endpoint-Pfad `/export?format=csv` explizit kommunizieren.

### F-COMM-9 — Decision-Audit-Trail vollständig und nachvollziehbar (Verifikation)
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have (positiver Fund)
- **Ort:** backend/interfaces/rest/routers/decision_audit.py, backend/application/services/decision_audit_service.py
- **Beschreibung:** GET /api/v1/decisions/NESN/audit lieferte zunächst `total:0` (kein Run erzeugt automatisch einen Audit-Record). Nach manuellem POST /api/v1/decisions/NESN/audit wurde ein vollständiger Record erzeugt mit nachvollziehbarer Erklärung: Signal HOLD, weighted_score 53.0, Quant-Score 50 (45%), ML-Signal NEUTRAL→50 (35%), Makro-Score 65/SNB-Leitzins (20%), 3a-eligible. Die Gewichtungs-Logik ist transparent in `explanation_de` nachvollziehbar.
- **Reproduktion:** POST dann GET /api/v1/decisions/NESN/audit.
- **Vorschlag:** Erwägen, ob Audit-Records automatisch bei Run-Abschluss für alle Ticker im Universe erzeugt werden sollten, statt nur on-demand per POST — sonst bleibt der Trail für die meisten Ticker leer.
