# Audit-Findings — Backtest, Crypto, Universes (2026-06-16)

## Getestete Funktionen

- `POST /api/v1/backtests` (SMI-20 vs. ^SSMI, mode=full): OK (funktional) | BUG (Zeitraum wird stillschweigend gekappt)
- Backtest-Series-Typen (`prisma`/`universe`/`benchmark` als `number[]`): OK — alle Werte echte `float`, keine NaN/Infinity, Vorgänger-Bug verifiziert gefixt
- `frontend/app/backtest/page.tsx` Ergebnis-Metadaten-Anzeige: UX-ISSUE (zeigt angefordertes statt tatsächliches Datumsfenster)
- `/crypto` Simple Mode (Fear&Greed-Gauge, Top-3 BUY-Karten): OK
- `/crypto` Pro Mode (volle Signal-Tabelle, Score-Breakdown): UX-ISSUE (Preis-Rundung bei Low-Price-Coins)
- `CRYPTO_FEATURE_ENABLED` Flag (`backend/config.py:61`): BUG — totes Konfigurationsfeld, nirgends im Code gelesen
- `POST /api/v1/universes` manueller Pfad (gültige + erfundene Ticker): OK (kein Crash), aber keine Ticker-Existenzprüfung
- `POST /api/v1/universes` Duplicate-Name Edge Case: BUG — rohe 500 statt 409/422 mit verständlicher Meldung
- `POST /api/v1/universes/{id}/sync` mit erfundenem Ticker: OK (kein Crash, kontrollierte Fehlerantwort), aber Sync markiert auch valide SMI-Ticker als fehlgeschlagen
- `/universes/wizard` (1x LLM-Call): OK — sinnvolle Tickerauswahl und Reasoning, kleinere Ungenauigkeit bei Region
- `/universes/new`: OK — klares Formular, sinnvoller Folge-Dialog "Ranking starten?"
- Frontend-Dev-Stack Crypto/Universe-Seiten ohne `NEXT_PUBLIC_API_KEY`: UX-ISSUE (lokales Setup-Problem, sauberer Error-State aber unvollständig)

## Befunde

### F-BTCR-1 — Backtest ignoriert angeforderten Zeitraum stillschweigend (504-Tage-Fenster)
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/application/services/backtest_service.py:87-98`; `backend/domain/ports/market_data_provider.py:11`; Frontend-Anzeige `frontend/app/backtest/page.tsx:501`
- **Beschreibung:** `MarketDataProvider.get_prices()` liefert laut Vertrag immer genau die letzten 504 Handelstage (~2 Jahre) bis heute, unabhängig von den im Request übergebenen `start_date`/`end_date`. Der Service filtert diese 504 Tage erst nachträglich auf das angeforderte Fenster (Zeile 92-98). Ein Request mit `start_date=2023-01-01` liefert dadurch tatsächlich nur Daten ab ca. 2024-07-11 (385 statt ~750 erwarteter Handelstage) — der Anfang des gewünschten Zeitraums fehlt komplett, ohne Fehler oder Warnung. Das Frontend zeigt zudem in der Ergebnis-Kopfzeile weiterhin das ursprünglich eingegebene Datumsfenster an (`{startDate} – {endDate}`), nicht das tatsächlich verwendete — der Nutzer bemerkt die Verkürzung nicht.
- **Reproduktion:** `POST /api/v1/backtests` mit `model_run_id` eines SMI-20-Runs, `start_date=2023-01-01`, `end_date=2025-12-31`. Antwort: `series.dates[0] = "2024-07-11"` statt `"2023-01-01"`, `series.dates` enthält 385 statt ~755 Einträge.
- **Vorschlag:** Entweder (a) API-Antwort soll das tatsächlich abgedeckte Zeitfenster explizit zurückgeben und das Frontend soll dieses statt der Eingabewerte anzeigen, oder (b) bei zu lang gewähltem Zeitraum einen 422/Warning zurückgeben ("nur die letzten 504 Handelstage verfügbar"). Mittelfristig: `get_prices` sollte echte Datums-Parameter unterstützen.

### F-BTCR-2 — `CRYPTO_FEATURE_ENABLED` ist ein totes Feature-Flag
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/config.py:60-61`; `backend/interfaces/rest/routers/crypto.py` (alle 4 Endpoints); `.env.example:58`
- **Beschreibung:** Das Setting `crypto_feature_enabled: bool = True` ist im `Settings`-Modell definiert und in `.env.example` dokumentiert, wird aber an keiner Stelle im Code gelesen (`grep` über das gesamte Repo findet nur die Definition selbst). Die Crypto-Router (`/signals`, `/signals/{ticker}`, `/fear-greed`, `/market`) prüfen das Flag nicht. Setzt ein Betreiber `CRYPTO_FEATURE_ENABLED=false`, bleibt das Crypto-Modul vollständig aktiv — Frontend zeigt die Seite unverändert an. Die UI selbst (`crypto-client.tsx`) hat kein Degradations-Verhalten für ein deaktiviertes Feature vorgesehen (kein Feature-Flag-Check, keine "Feature deaktiviert"-Anzeige).
- **Reproduktion:** Code-Review — `grep -rn "crypto_feature_enabled"` liefert nur den einen Treffer in `config.py`.
- **Vorschlag:** Entweder das Flag tatsächlich verdrahten (Dependency-Guard im Router, der bei `crypto_feature_enabled=False` 404/503 liefert, plus Frontend-Fallback-UI), oder das totes Flag aus `Settings` und `.env.example` entfernen, um Verwechslung zu vermeiden.

### F-BTCR-3 — Universe-Anlage mit existierendem Namen liefert rohe 500-Fehlermeldung
- **Bereich:** Funktional / UX
- **Schweregrad:** Kritisch
- **Ort:** `backend/infrastructure/persistence/repositories/universe_repository.py:26-44` (`save()`); `backend/application/services/universe_service.py:51-64` (`create_universe`); UNIQUE-Index `ix_universes_name` in `backend/infrastructure/persistence/models/universe.py:20`
- **Beschreibung:** `universes.name` hat einen UNIQUE-Index. `SQLAUniverseRepository.save()` nutzt `INSERT ... ON CONFLICT (id) DO UPDATE`, der Conflict-Handler greift aber nur auf die `id`-Spalte. Bei `create_universe()` wird immer eine neue UUID generiert, sodass ein Namens-Konflikt nie über den ON-CONFLICT-Pfad behandelt wird — die `UniqueViolationError`/`IntegrityError` propagiert ungefangen bis zum globalen Handler, der ein generisches `{"detail":"Interner Serverfehler."}` mit HTTP 500 zurückgibt. Andere Repositories im selben Code (`embedding_repository.py`, `news_repository.py`) fangen `IntegrityError` explizit ab — `universe_repository.py`/`universe_service.py` tun das nicht. Im Frontend (`frontend/app/universes/new/page.tsx:103-112`) wird `mutation.error.message` direkt angezeigt, also erscheint "Interner Serverfehler." statt einer verständlichen Meldung wie "Ein Universe mit diesem Namen existiert bereits."
- **Reproduktion:** `POST /api/v1/universes` mit `{"name": "SMI-20", "region": "CH", "tickers": ["NESN"]}` → HTTP 500, `{"detail":"Interner Serverfehler."}`. Im Browser via `/universes/new`-Formular mit Name "SMI-20" identisch reproduzierbar — sichtbarer Fehlertext im UI: "Interner Serverfehler."
- **Vorschlag:** `IntegrityError`/`UniqueViolationError` im Service oder Repository explizit abfangen und als `DuplicateUniverseName`-Exception werfen, im Router auf HTTP 409 mit Klartextmeldung mappen (analog zum Pattern in `news_repository.py`). Frontend zeigt dann direkt die verständliche Meldung.

### F-BTCR-4 — Universe-Erstellung validiert Ticker nicht (keine Existenzprüfung)
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have
- **Ort:** `backend/interfaces/rest/schemas/universe.py:27-33` (`tickers_not_empty`); `backend/application/services/universe_service.py:51-64`
- **Beschreibung:** Beim Anlegen eines Universe wird nur geprüft, dass die Ticker-Liste nicht leer ist (Whitespace-Trim). Ein komplett erfundener Ticker wie `ZZZFAKE99` wird klaglos akzeptiert und gespeichert (HTTP 201). Das Problem zeigt sich erst beim nachgelagerten `sync`, der den Ticker als `failed` markiert (kein Crash, aber später Diagnoseaufwand statt sofortigem Feedback beim Anlegen).
- **Reproduktion:** `POST /api/v1/universes` mit `{"name": "Audit-Test-Universe", "region": "CH", "tickers": ["NESN", "ZZZFAKE99"]}` → 201 Created, beide Ticker werden gespeichert.
- **Vorschlag:** Optional: synchrone oder asynchrone Ticker-Validierung beim Anlegen (z.B. gegen Stock-Katalog), mit Warnung statt Hard-Block, um UX nicht zu verschlechtern.

### F-BTCR-5 — Universe-Sync markiert auch valide SMI-Ticker durchgehend als "failed"
- **Bereich:** Funktional
- **Schweregrad:** Wichtig
- **Ort:** `backend/application/services/universe_service.py:66-96` (`sync_universe`)
- **Beschreibung:** `POST /api/v1/universes/{id}/sync` für das produktiv geseedete SMI-20-Universe liefert `synced_count: 0` und listet alle 20 realen, gültigen SMI-Ticker (NESN, NOVN, ROG, ...) als `failed_tickers`. Das deutet darauf hin, dass `FundamentalsProvider` und/oder `MarketDataProvider` im aktuellen Audit-Stack für reale Ticker keine verwertbaren Daten liefern (z.B. weil dort kein Stub, sondern der echte yfinance-Adapter mit Rate-Limits/Netzwerkproblemen hängt, oder weil Stub- und Live-Provider inkonsistent gemischt sind). Auch wenn der Endpoint nicht crasht (Exceptions werden in Zeile 73-82 abgefangen und zu einem leeren Ergebnis degradiert), ist das Verhalten für ein bereits funktionierendes Kern-Universe hochgradig unerwartet und sollte funktional weiter untersucht werden.
- **Reproduktion:** `POST /api/v1/universes/3a2d87d2-7dbe-4a07-86c3-0feac3988819/sync` → `{"synced_count":0,"failed_tickers":["NESN","NOVN",...alle 20...]}`.
- **Vorschlag:** Root-Cause-Analyse, ob `FundamentalsProvider`/`MarketDataProvider` im Audit-Stack korrekt konfiguriert sind; ggf. striktere Unterscheidung zwischen "Daten-Provider down" (klare Fehlermeldung) und "Ticker ungültig" (aktuell beides identisch als `failed_tickers` dargestellt).

### F-BTCR-6 — Crypto Pro-Tabelle rundet Niedrigpreis-Coins auf "CHF 0"
- **Bereich:** UX
- **Schweregrad:** Wichtig
- **Ort:** `frontend/components/crypto/CryptoProRow.tsx:9-12,55`
- **Beschreibung:** Die Preis-Spalte formatiert mit `fmt(signal.price_chf, 0)`, also fix null Dezimalstellen für alle 10 Kryptowährungen. Für Coins mit Preis < CHF 1 (z.B. Cardano/ADA, real ca. CHF 0.30–0.50) erscheint in der Pro-Tabelle "CHF 0" — der tatsächliche Preis ist nicht erkennbar bzw. wirkt wie ein Datenfehler. XRP (~CHF 1.x) wird ebenfalls grob auf "CHF 1" gerundet.
- **Reproduktion:** `/crypto` im Pro-Mode öffnen, Zeile "ADA / Cardano" in der Tabelle ansehen → Preis-Spalte zeigt "CHF 0".
- **Vorschlag:** Dynamische Dezimalstellen abhängig von der Preisgrösse (z.B. 2 Dezimalstellen unter CHF 10, 0 darüber), analog zu üblichen Krypto-Preis-Formatierungen.

### F-BTCR-7 — Fear&Greed-Gauge zeigt bei Query-Error dauerhaft Skeleton statt Fehlermeldung
- **Bereich:** UX
- **Schweregrad:** Nice-to-have
- **Ort:** `frontend/app/crypto/crypto-client.tsx:23-27,44-49`
- **Beschreibung:** Die Signal-Liste hat einen expliziten Error-State (`signalsError` → "Signale konnten nicht geladen werden."), die Fear&Greed-Query dagegen nicht: Bei einem fehlgeschlagenen `getFearGreed`-Call bleibt `fgLoading` aus Sicht der UI dauerhaft "lädt" (Skeleton wird angezeigt, da nur `fgLoading || !fearGreed` geprüft wird, kein eigener `fgError`-Zweig). Nutzer sehen einen ewig ladenden Platzhalter statt eines Fehlerhinweises.
- **Reproduktion:** Mit ungültigem/fehlendem API-Key `/crypto` öffnen (401 auf `/api/v1/crypto/fear-greed`) → Gauge-Bereich zeigt dauerhaft `Skeleton` statt Fehlertext.
- **Vorschlag:** `error: fgError` aus dem `useQuery`-Hook destrukturieren und analog zur Signalliste eine Fehlermeldung im Gauge-Slot anzeigen.

### F-BTCR-8 — Lokaler Frontend-Dev-Stack ohne `NEXT_PUBLIC_API_KEY` konfiguriert
- **Bereich:** UX / Infrastruktur
- **Schweregrad:** Nice-to-have
- **Ort:** `frontend/.env.local` (fehlt im Audit-Stack); `frontend/lib/api/client.ts:1-6`
- **Beschreibung:** Der laufende Frontend-Dev-Server (Port 3090) hat keine `.env.local` mit `NEXT_PUBLIC_API_KEY` — nur `.env.local.example` als Vorlage existiert. Dadurch schlagen alle authentifizierten Endpoints (inkl. Crypto, Backtest-Run-Liste) im Browser mit 401 fehl; das Fehlerhandling fängt das zwar ab (keine rohen Crashes), aber praktisch jede Seite, die Live-Daten braucht, zeigt nur Fehlertexte. Dies ist primär ein Setup-Problem dieses Audit-Stacks, kein Produktbug — wird hier dokumentiert, weil es das Live-Testen aller Seiten ohne Workaround verunmöglicht.
- **Reproduktion:** `/crypto` im Browser ohne API-Key-Header öffnen → Console-Warnung "[prisma] NEXT_PUBLIC_API_KEY is not set", alle Daten-Endpoints liefern 401.
- **Vorschlag:** `.env.local` für den Audit-/Demo-Stack mit gültigem `NEXT_PUBLIC_API_KEY` versehen, damit folgende Audit-Runden ohne Playwright-Workaround (Header-Injektion per `addInitScript`) browser-seitig testen können.
