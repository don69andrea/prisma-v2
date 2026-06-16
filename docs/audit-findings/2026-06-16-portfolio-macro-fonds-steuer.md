# Audit-Findings — Portfolio, Macro, Fonds, Steuer (2026-06-16)

## Getestete Funktionen
- POST /api/v1/portfolio/allocate (Happy Path, run_id-basiert): OK (funktional), aber UX-ISSUE bei Score-Skala
- POST /api/v1/portfolio/allocate (Stress, 50+ Positions-JSON wie in Aufgabenstellung gefordert): BUG (Endpoint-Design-Diskrepanz)
- POST /api/v1/portfolio/rebalance (Happy Path + Stress, 53 Positionen inkl. erfundene Ticker): BUG (keine Ticker-Validierung)
- POST /api/v1/portfolio/monte-carlo: BUG + PERF-ISSUE (kritisch — falsche Kursdaten + Crash + Latenz)
- GET /api/v1/macro/context: OK
- GET /api/v1/macro/score/{ticker}: BUG (Score immer konstant, sektor-blind)
- GET /api/v1/fonds: OK
- POST /api/v1/fonds/vergleich (ungültiger Fonds): OK (saubere 404)
- GET /api/v1/stocks/{ticker}/3a-eligibility: OK (für CH-Ticker), UX-ISSUE (US-Ticker → 404 statt "nicht eligible")
- POST /api/v1/steuer/einschaetzung (CH vs. US-Ticker): BUG (identischer Output, fachlich falsch für US-Aktien)
- UX Zahlenformatierung (CHF/%, de-CH): OK mit kleinen Inkonsistenzen

## Befunde

### F-PORT-1 — Monte-Carlo liefert falsche Kursdaten für Schweizer Ticker (Ticker-Verwechslung) und crasht
- **Bereich:** Funktional (kritisch, Datenintegrität)
- **Schweregrad:** Kritisch
- **Ort:** `backend/application/services/monte_carlo_service.py:150-169` (`_fetch_ticker_params`), Endpoint `POST /api/v1/portfolio/monte-carlo`
- **Beschreibung:** `_fetch_ticker_params()` ruft `yf.download(ticker, ...)` mit dem rohen PRISMA-Ticker auf (z.B. "ROG", "CFR") statt den existierenden `YFinanceSwissAdapter` (mit korrektem `.SW`-Suffix-Mapping, inkl. Override `ROG→RO.SW`) zu verwenden. Dadurch matched Yahoo Finance auf falsche, völlig andere Unternehmen: "ROG" → Rogers Corporation (NYQ, US-Elektronikhersteller) statt Roche Holding AG; "CFR" → Cullen/Frost Bankers Inc. (US-Bank) statt Compagnie Financière Richemont. Beide Fehltreffer enthalten zusätzlich 1 NaN-Wert in der Close-Spalte, was downstream zu `ValueError: cannot convert float NaN to integer` (HTTP 422) führt, nachdem `mean of empty slice` Warnings auftreten. Der `except Exception`-Fallback in `_fetch_ticker_params` greift nicht, weil die Exception erst später (in `_run_gbm` bzw. beim Cholesky/Statistik-Schritt) auftritt.
- **Reproduktion:**
  ```
  curl -X POST .../api/v1/portfolio/monte-carlo -d '{"holdings":[{"ticker":"ROG","weight":1.0}],"monthly_contribution":500,"years":10,"initial_value":1000,"n_simulations":500}'
  → HTTP 422 {"detail":"cannot convert float NaN to integer"}
  ```
  Python-Verifikation: `yf.Ticker('ROG').info['longName']` → "Rogers Corporation", Exchange "NYQ" (nicht Roche/SIX).
- **Vorschlag:** `_fetch_ticker_params` muss `YFinanceSwissAdapter._to_yf_symbol(ticker)` (bzw. äquivalentes Suffix-Mapping) nutzen statt rohe PRISMA-Ticker an yfinance zu übergeben. Zusätzlich: NaN-Validierung nach Datenabruf mit klarer 422-Fehlermeldung statt generischem Python-Exception-Text.

### F-PORT-2 — Monte-Carlo: Antwortzeit / Fehlerpfad-Latenz als Performance-Hotspot bestätigt
- **Bereich:** Performance
- **Schweregrad:** Wichtig
- **Ort:** `backend/application/services/monte_carlo_service.py:106-129` (`_fetch_return_params`, sequenzielles Fetching), `backend/interfaces/rest/routers/portfolio.py:107-141`
- **Beschreibung:** Gemessene Antwortzeiten: 5 Holdings inkl. fehlerhaftem Ticker → **13.06s** bis zum (Fehler-)Response; 4 valide Holdings (NESN, NOVN, UBSG, ZURN), n_simulations=500, 10 Jahre → **6.06s**; 1 Holding, n_simulations=500-1000 → ~1.3-1.8s. Die Zeit skaliert linear mit der Anzahl Holdings, da `_fetch_ticker_params` pro Ticker sequenziell (nicht parallel via `asyncio.gather`) aufgerufen wird und jeder Call einen synchronen `yf.download`-Network-Roundtrip via `asyncio.to_thread` macht. Bei realistischen Requests mit dem Default `n_simulations=10000` und mehreren Holdings ist mit deutlich höherer Latenz zu rechnen (GBM-Simulation selbst läuft in `asyncio.to_thread`, ist aber nicht das einzige Nadelöhr — der Daten-Fetch dominiert bei wenigen Simulationen bereits).
- **Reproduktion:** `time curl -X POST .../monte-carlo` mit den oben genannten Payloads (Dateien lagen in `/tmp/mc_perf.json`, `/tmp/mc_4t.json`).
- **Vorschlag:** Ticker-Datenabruf parallelisieren (`asyncio.gather` statt sequenzielle `for`-Schleife in `_fetch_return_params`); historische Kursdaten cachen (z.B. Redis/In-Memory mit TTL), da sich `period="1y"`-Daten pro Ticker nicht pro Request ändern.

### F-PORT-3 — /portfolio/allocate akzeptiert kein Positions-/Stückzahlen-JSON (API-Design-Diskrepanz zur erwarteten Nutzung)
- **Bereich:** Funktional / UX
- **Schweregrad:** Wichtig
- **Ort:** `backend/interfaces/rest/schemas/portfolio.py:11-18` (`PortfolioAllocateRequest`), `backend/interfaces/rest/routers/portfolio.py:61-98`
- **Beschreibung:** `POST /api/v1/portfolio/allocate` erwartet ausschliesslich `run_id` (UUID eines abgeschlossenen Ranking-Runs), `top_n`, `eligible_only`, `method` — keine direkte Eingabe von Ticker+Stückzahl/Gewicht. Ein Versuch, ein eigenes Portfolio mit 60 Positionen (Ticker+Stückzahl) zu senden, schlägt mit HTTP 422 "Field required: run_id" fehl. Das Frontend (`frontend/components/rankings/PortfolioAllocationPanel.tsx`) nutzt den Endpoint korrekt nur im Ranking-Kontext; der eigentliche "eigenes Portfolio eingeben"-Flow im Frontend läuft über `/portfolio/rebalance` (`frontend/app/portfolio/portfolio-client.tsx`), das Gewichte (nicht Stückzahlen) als `current_weights`/`target_weights`-Dicts erwartet. Für Endnutzer, die ein Portfolio mit Stückzahlen (statt Gewichten) eingeben wollen, fehlt durchgängig die Umrechnung (Stückzahl × Kurs → Gewicht).
- **Reproduktion:** `curl -X POST .../portfolio/allocate -d '{"positions":[...60 Einträge mit ticker+quantity...]}'` → HTTP 422 `"Field required","loc":["body","run_id"]`.
- **Vorschlag:** Dokumentation/Frontend klarer trennen: "/allocate" als "KI-Empfehlung aus Ranking" vs. "/rebalance" als "Mein Portfolio verwalten" benennen. Optional: Stückzahl-Eingabe im Rebalance-Formular ergänzen (mit Live-Kurs-Lookup zur Gewichtsberechnung), da Privatanleger eher Stückzahlen als Prozentgewichte kennen.

### F-PORT-4 — /portfolio/rebalance validiert Ticker nicht gegen bekanntes Universum
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/interfaces/rest/routers/rebalancing.py:30-43`, `backend/application/services/rebalancing_service.py`
- **Beschreibung:** Ein Rebalancing-Request mit 53 Positionen, davon 20 frei erfundene Ticker ("FAKE0"–"FAKE19"), wurde mit HTTP 200 akzeptiert und vollständig verarbeitet — inkl. BUY/SELL/HOLD-Aktion, CHF-Beträgen und `is_3a_eligible: true` (Default-Fallback statt echter Prüfung) für jeden erfundenen Ticker. Es gibt keine Validierung gegen das `SwissStockRepository` oder ein bekanntes Aktien-Universum.
- **Reproduktion:** `curl -X POST .../portfolio/rebalance -d '{"current_weights":{"FAKE0":0.05,...},"target_weights":{...}}'` → HTTP 200, `steps` enthält `FAKE0`..`FAKE19` mit vollständigen Plan-Daten.
- **Vorschlag:** Ticker vor Verarbeitung gegen `SwissStockRepository`/bekanntes Universum validieren; bei unbekannten Tickern HTTP 422 mit Liste der ungültigen Ticker zurückgeben statt sie unkommentiert in den Plan zu übernehmen.

### F-PORT-5 — Quant-Score-Skala inkonsistent dargestellt ("X/100" bei 0-10-Werten)
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** `backend/application/agents/portfolio_agent.py:354` (`f"Durchschnittlicher Quant-Score: {avg_score:.0f}/100."`), Response-Beispiel: `quant_score: 5.5` wird zu "Quant-Score 6" gerundet, `overall_rationale_de` sagt aber "Durchschnittlicher Quant-Score: 4/100"
- **Beschreibung:** Im Happy-Path-Test (SMI-20 Run, top_n=5) lagen alle `quant_score`-Werte zwischen 2.25 und 5.5 (offensichtlich 0-10-Skala), aber der generierte Text hängt hart codiert "/100" an. Das suggeriert fälschlich eine 0-100-Skala und macht die Aussage "Durchschnittlicher Quant-Score: 4/100" irreführend (klingt nach sehr schlechter Bewertung, ist aber relativ zur tatsächlichen Skala plausibel).
- **Reproduktion:** `POST /api/v1/portfolio/allocate` mit SMI-20-Run, `top_n=5` → Response-Feld `overall_rationale_de`.
- **Vorschlag:** Skala konsistent halten — entweder `quant_score` durchgängig auf 0-100 normalisieren, oder den Text auf "/10" korrigieren bzw. Skala dynamisch aus dem tatsächlichen Wertebereich ableiten.

### F-MACRO-1 — Makro-Score ist ticker-unabhängig (immer identischer Wert)
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/interfaces/rest/routers/macro.py:70-78` (`agent.get_macro_score(ticker=ticker)` — `sector`-Parameter wird nie übergeben), `backend/application/agents/macro_agent.py:80-115` (erwartet optionalen `sector`-Hint für Export-Sektor-Bonus)
- **Beschreibung:** `GET /api/v1/macro/score/{ticker}` liefert für alle getesteten Ticker (NESN, ROG, UBSG, AAPL, TSLA, SGKN, SREN, GIVN) exakt denselben Score von **80.0**, obwohl die Endpoint-Beschreibung "basierend auf SNB-Leitzins, CHF/EUR-Kurs und Exportprofil" verspricht. Ursache: Der Router übergibt nie ein `sector`-Argument an `get_macro_score()`, wodurch der im Agent vorgesehene Export-Sektor-Bonus (`_EXPORT_SECTORS`-Check) nie greifen kann — der Score bleibt für jeden Ticker auf dem Baseline-Pfad.
- **Reproduktion:** `curl .../api/v1/macro/score/NESN` und `.../macro/score/AAPL` → identischer `score: 80.0` trotz unterschiedlicher Branche/Land.
- **Vorschlag:** Sektor-Information (aus `SwissStockRepository`/Stock-Metadaten) im Router nachschlagen und an `get_macro_score(ticker=ticker, sector=sector)` übergeben, damit die Sektor-Differenzierung tatsächlich wirkt.

### F-STEUER-1 — Steuer-Einschätzung liefert identischen (falschen) Output für US- und CH-Aktien
- **Bereich:** Funktional
- **Schweregrad:** Kritisch
- **Ort:** `backend/application/agents/steuer_agent.py` (Fallback-Pfad, `model_version: "fallback"`), Endpoint `POST /api/v1/steuer/einschaetzung`
- **Beschreibung:** 3a-Eligibility-Check zeigt: NESN/ROG/UBSG sind im `SwissStockRepository` und als 3a-eligible markiert; TSLA/AAPL/NVDA sind dort gar nicht vorhanden (404 "Swiss Stock nicht gefunden" statt einer fachlichen "nicht eligible"-Aussage). Trotzdem liefert `/steuer/einschaetzung` für TSLA exakt denselben Output wie für NESN: "Verrechnungssteuer (35%)" und "VST-Rückerstattung via Formular 103 (bei Schweizer Aktien)" — fachlich falsch, da US-Dividenden der US-Quellensteuer (nicht CH-Verrechnungssteuer) unterliegen und andere Rückerstattungsformulare (DA-1-Anhang, US-W8BEN) gelten. Zudem `model_version: "fallback"` zeigt, dass die LLM-/RAG-Analyse gar nicht lief, sondern ein generischer Ticker-unabhängiger Template-Text ausgegeben wurde.
- **Reproduktion:**
  ```
  curl -X POST .../api/v1/steuer/einschaetzung -d '{"ticker":"NESN","anlegerprofil":"vorsorge_3a","halteperiode_jahre":5}'
  curl -X POST .../api/v1/steuer/einschaetzung -d '{"ticker":"TSLA","anlegerprofil":"vorsorge_3a","halteperiode_jahre":5}'
  → beide liefern identische steuerarten/pflichten/quellen (nur Ticker-String im Text ersetzt), beide model_version "fallback".
  ```
- **Vorschlag:** Fallback-Pfad muss zumindest CH- vs. Nicht-CH-Aktien unterscheiden (z.B. via 3a-Eligibility-Lookup oder Länder-Flag) und unterschiedliche Steuerarten-Templates ausgeben. Zusätzlich: Root Cause klären, warum der LLM-Pfad nicht greift (Kosten/Verfügbarkeit/Fehler) — falls bewusst deaktiviert, sollte das UI den Fallback-Hinweis prominenter zeigen statt nur in `hinweise[]` zu verstecken.

### F-STEUER-2 — 3a-Eligibility für nicht-CH-Ticker liefert 404 statt fachlicher "nicht eligible"-Antwort
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** `backend/interfaces/rest/routers/eligibility.py`, Endpoint `GET /api/v1/stocks/{ticker}/3a-eligibility`
- **Beschreibung:** Für US-Ticker (TSLA, AAPL, NVDA) liefert der Endpoint HTTP 404 "Swiss Stock 'X' nicht gefunden" statt einer fachlich korrekten Antwort wie `{"eligible": false, "reason": "Nicht an SIX/XSWX kotiert"}`. Aus Nutzersicht ist der Unterschied zwischen "technisch nicht im System" und "fachlich nicht 3a-fähig" nicht klar erkennbar — ein 404 könnte fälschlich als Tippfehler/Systemfehler interpretiert werden statt als klare regulatorische Aussage.
- **Reproduktion:** `curl .../api/v1/stocks/TSLA/3a-eligibility` → HTTP 404 `{"detail":"Swiss Stock 'TSLA' nicht gefunden"}`.
- **Vorschlag:** Für bekannte Nicht-CH-Ticker (sofern im System vorhanden, z.B. Tech-Big-12) eine fachliche 200-Antwort mit `eligible: false` und klarem Grund liefern statt 404; 404 nur für komplett unbekannte Ticker.

## UX-Bewertung Zahlenformatierung
- CHF-Beträge nutzen durchgängig `toLocaleString('de-CH', {minimumFractionDigits:2, maximumFractionDigits:2})` (Apostroph als Tausendertrennzeichen, Punkt als Dezimaltrennzeichen) — das ist tatsächlich das korrekte de-CH-Format und konsistent in `portfolio-client.tsx`.
- Prozentwerte nutzen überall simples `(v*100).toFixed(1) + '%'` ohne `toLocaleString` — bei de-CH ergibt das dieselbe Punkt-Notation wie `toLocaleString`, daher visuell konsistent, aber implementatorisch uneinheitlich (zwei verschiedene Formatierungs-Strategien für CHF vs. %) — Wartungsrisiko bei zukünftiger Lokalisierung.
- `PortfolioAllocationPanel.tsx` (nutzt `/allocate`) zeigt keine CHF-Beträge (nur Gewichte/Score) — stilistisch nicht direkt vergleichbar mit `/rebalance`-UI, aber kein Fehler.
- Negative/Verlust-Werte: Es gibt im Portfolio-/Fonds-Bereich kein explizites "Gewinn/Verlust"-Konzept (keine P&L-Anzeige); SELL-Aktionen sind rot, BUY grün, HOLD grau — klar erkennbar. In `fonds-client.tsx` (`MetricRow`) wird nur bei "positive"-Metriken (Rendite, Sharpe) Grün hervorgehoben, negative Werte (z.B. negative Rendite) bleiben ohne Rot-Hervorhebung — Inkonsistenz zur Portfolio-Seite, wo SELL/Kosten explizit rot/amber markiert sind.

Pfad der Findings-Datei: `/Users/andreapetretta/prisma-v2/.claude/worktrees/usability-performance-audit-2026-06-16/docs/audit-findings/2026-06-16-portfolio-macro-fonds-steuer.md`
