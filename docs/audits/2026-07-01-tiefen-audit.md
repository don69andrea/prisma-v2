# PRISMA V2 — Tiefen-Audit

**Repo:** `don69andrea/prisma-v2` · **Branch:** `main` (HEAD `ee6a76c`) · **Datum:** 2026-07-01
**Umfang:** 80.206 Zeilen Python (652 Dateien, Clean Architecture) + 275 JS/TS-Dateien (Next.js)
**Methodik:** Manuelle Kern-Sicherheitsanalyse (Auth, Config, DI, App-Entry) + 5 parallele Subsystem-Audits
(REST-Interfaces, Application-Layer, Infrastructure/Domain, Frontend, DevOps/Migrations). Jeder Befund am
tatsächlichen Code verifiziert — kein Raten.

---

## 0. Executive Summary

Das Projekt ist architektonisch sauber aufgebaut (Hexagonal/Clean Architecture, gute Test-Abdeckung der
Endpoints, korrektes JWT-Algorithmus-Pinning, HMAC-konstantzeitige Key-Vergleiche, non-root Docker-Images,
saubere Alembic-Revision-Chain mit genau einem Head). **Aber:** Es gibt mehrere Befunde, die das
*Kernversprechen* der Plattform — vertrauenswürdige Anlage-Signale — und die Sicherheit/Kostenkontrolle
fundamental untergraben.

### Die 4 Themen, die wirklich wehtun

| Thema | Kern-Problem | Schlimmster Befund |
|---|---|---|
| **A. Fake-/Falsch-Daten** | Signale & Backtests basieren auf Zufallszahlen bzw. falscher Mathematik | C-01, C-02, C-04 |
| **B. Access Control** | Mandanten-Isolation fehlt; Admin-Key im Browser; IDOR | C-03, C-05, H-01 |
| **C. Kostenkontrolle** | Budget-Cap an mehreren Stellen umgehbar | C-04(Chat), H-08, H-09 |
| **D. Deployment-Risiken** | Destruktive Auto-Migrationen; Boot-Crash der Worker | C-06, H-12 |

### Schweregrad-Übersicht (konsolidiert, dedupliziert)

**Welle 1** (REST, Application, Infra/Domain, Frontend, DevOps):
- 🔴 Critical: 7 · 🟠 High: 14 · 🟡 Medium: 19 · ⚪ Low: 15

**Welle 2** (Nachtrag — bisher ungeprüfte Bereiche: Scripts/Boot, ML-Training, LLM-Agenten, prisma_v3_seed, MCP, Test-Qualität — siehe `# NACHTRAG — WELLE 2`):
- 🔴 Critical: 4 · 🟠 High: 11 · 🟡 Medium: 14 · ⚪ Low: 7

**Welle 3** (Tiefen-Deep-Dives: jede Alembic-Migration zeilenweise, CH-Steuer/Rebalancing/Fonds/Portfolio-Fachlogik, Domain-Scorer/Quant-Mathematik, restliche Services — siehe `# NACHTRAG — WELLE 3`):
- 🔴 Critical: 5 · 🟠 High: 10 · 🟡 Medium: 22 · ⚪ Low: 18

**GESAMT (dedupliziert über 3 Wellen): 🔴 16 Critical · 🟠 35 High · 🟡 55 Medium · ⚪ 40 Low — ~146 Befunde.**

> **Ehrliche Grenze:** Auch nach 3 Wellen und 13 Agenten ist „jeder einzelne Bug" bei ~80k LOC nicht mathematisch
> garantiert. Erreicht ist aber: **jedes Subsystem wurde mindestens einmal tief auditiert**, die kritischen
> Bereiche (Signale, Modelle, Auth, Steuer, Migrationen, Kostenkontrolle) mehrfach. Weiteres Graben förderte zuletzt
> überwiegend Medium/Low — die strukturellen und kritischen Probleme sind erfasst.

---

# TEIL 1 — BEFUNDE

> Konvention: `Pfad:Zeile` relativ zu Repo-Root. IDs sind stabil (C/H/M/L = Schweregrad).

---

## 🔴 CRITICAL

### C-01 — Anlage-Signale & Backtests laufen auf Zufallszahlen statt Marktdaten
**Ort:** `backend/interfaces/rest/routers/signals.py:100-110` (`_make_stub_prices`), genutzt in `:141, :176, :282, :541`; Agent-Pfad in `backend/interfaces/rest/dependencies.py:585-589`
**Problem:** `_make_stub_prices` erzeugt einen deterministischen Random-Walk (`seed = hash(coin)`). Sämtliche Endpoints
`GET /api/v1/signals`, `/signals/{coin}`, `/backtest/{coin}`, `/signals/meta-label/{coin}` und `/agent-signal/{coin}`
berechnen BUY/HOLD/SELL-Entscheidungen und Backtest-Renditen aus diesem Rauschen. Im DI-Pfad des `SignalDirector`
wird zusätzlich ein fixer `rng.normal(..., seed=42)`-Frame als „BTC"-Preise eingespeist.
**Failure-Szenario:** Nutzer ruft `/api/v1/signals/BTC-USD` auf → erhält eine voll formatierte Kauf-/Verkaufsempfehlung,
die mit echten Bitcoin-Kursen **nichts** zu tun hat. Der Docstring behauptet wörtlich „In Produktion werden echte
Preise … geladen" — das passiert nirgends. Auf einer Finanzplattform ist das das gravierendste mögliche Problem.
**Schwere:** Critical (Produkt-Integrität).

### C-02 — Falsche FX-Richtung: alle USD-Krypto-Preise ~22 % zu hoch in CHF
**Ort:** `backend/infrastructure/adapters/yfinance_crypto.py:88-92` und `:165-171`
**Problem:** USD-Preise werden mit `CHFUSD=X` (≈ 1.10 USD pro CHF) **multipliziert**, statt dividiert. Beweis der
eigenen Inkonsistenz: der Hardcoded-Fallback in `:168` ist `0.90` (CHF pro USD = korrekte Richtung), der Live-Kurs ist
dessen Inverse.
**Failure-Szenario:** Alle USD-Pairs (SOL, XRP, ADA …) erscheinen ~22 % zu teuer und fließen verfälscht in den
CryptoScorer (Trend/Bollinger/Volatilität) ein.
**Schwere:** Critical (falsche Marktpreise).

### C-03 — Admin-API-Key wird ins öffentliche Frontend-Bundle kompiliert
**Ort:** `render.yaml:86-88` + `Dockerfile.frontend:31-32` (`NEXT_PUBLIC_API_KEY`)
**Problem:** `NEXT_PUBLIC_API_KEY` ist als „muss identisch mit Backend-`API_KEY` sein" dokumentiert und wird durch das
`NEXT_PUBLIC_`-Präfix in das an den Browser ausgelieferte JS-Bundle eingebacken.
**Failure-Szenario:** Jeder Besucher liest den Admin-`X-API-Key` aus dem JS-Bundle und kann geschützte
`/admin`-Endpoints aufrufen. (Zusatz: Die Variable wird im Frontend ansonsten nur vom irreführenden
`MissingApiKeyBanner` verwendet — siehe M-15.)
**Schwere:** Critical (Auth-Bypass).

### C-04 — Budget-Cap im Streaming-Chat komplett umgangen
**Ort:** `backend/application/services/chat_service.py:359-371, :391`
**Problem:** `stream()` ruft `self._llm.raw_client.messages.stream(...)` direkt auf und nutzt den `CostTracker` nur für
ein nachträgliches `record()`. Es gibt **keinen** `check_cap()`-Aufruf vor dem Call. Der Cap greift nur über den
`LLMClient`-Wrapper.
**Failure-Szenario:** Monatsbudget zu 100 % ausgeschöpft → jeder Chat-Request (zwei Sonnet-Calls inkl.
Tool-Continuation) läuft trotzdem. Unbegrenzte reale Anthropic-Kosten.
**Schwere:** Critical (Kostenkontrolle).

### C-05 — Alerts-IDOR: jeder Nutzer liest/löscht die Alerts aller Nutzer
**Ort:** `backend/interfaces/rest/routers/alerts.py:53, :72, :85`; Entity `…/persistence/models/alert.py` (kein `user_id`)
**Problem:** Router ist nur *authentifiziert*, nie *autorisiert*. `Alert` hat keine Owner-Spalte. `list_alerts()` gibt
**alle** Alerts aller Nutzer zurück (inkl. Webhook-URLs & E-Mail-Ziele); `delete_alert(uuid)` löscht jeden beliebigen
Alert; `create_alert` setzt ein beliebiges `target`.
**Failure-Szenario:** Viewer-Token → `GET /api/v1/alerts` dumpt alle Benachrichtigungsziele aller Mandanten;
`DELETE /api/v1/alerts/{fremde_uuid}` löscht fremde Alerts.
**Schwere:** Critical (IDOR / fehlende Mandanten-Isolation).

### C-06 — Migration 0029 TRUNCATEt 8 Nutzerdaten-Tabellen bei jedem Deploy, irreversibel
**Ort:** `backend/alembic/versions/0029_auth_users.py:31-34`
**Problem:** `upgrade()` führt `TRUNCATE TABLE {alerts, backtest_results, decision_audit_log, research_memos,
ranking_runs, llm_call_log, memo_batch_jobs, investor_profiles} CASCADE` aus — und wird über `backend-start.sh`
(`alembic upgrade head`) automatisch beim Container-Start angewandt.
**Failure-Szenario:** Auf jeder Prod-DB, die beim ersten Lauf von 0029 bereits Daten hielt, wurden Audit-Logs, Memos
und Ranking-Historie ohne Backup gelöscht; `downgrade()` kann nichts wiederherstellen. Wichtig: `llm_call_log` ist
die Single-Source-of-Truth des Monatsbudgets → Truncate verfälscht auch die Kostenmessung.
**Schwere:** Critical (Datenverlust).

### C-07 — JWT-Token im `localStorage` + nicht-HttpOnly-Cookie (XSS-Token-Diebstahl)
**Ort:** `frontend/hooks/useAuth.tsx:24-35`, `frontend/lib/api/client.ts:4-7`
**Problem:** Der Session-JWT wird gleichzeitig in `localStorage` und in einem per `document.cookie` gesetzten
(JS-lesbaren) Cookie abgelegt.
**Failure-Szenario:** Jede XSS-Lücke oder ein kompromittiertes npm-Paket liest `localStorage.getItem('prisma_token')`
und exfiltriert das 8h/72h-Session-Token → Vollzugriff auf das Finanzkonto.
**Schwere:** Critical (Token-Exfiltration).

---

## 🟠 HIGH

### H-01 — SSRF-Filter bei Webhook-Alerts trivial umgehbar
**Ort:** `backend/interfaces/rest/schemas/alert.py:27-36, :51-73`
**Problem:** `_is_private_host` matcht nur **bare IPv4-Literale**. Ein DNS-Name, der auf `169.254.169.254`
(Cloud-Metadata) oder `127.0.0.1` auflöst, jedes IPv6 (`[::1]`), sowie dezimal/oktal-kodierte IPs passieren. Der
Alert-Worker POSTet später an `target`. Kombiniert mit C-05 kann jeder authentifizierte Nutzer Server-seitige
Requests an interne/Metadata-Endpoints auslösen.
**Fix-Richtung:** Hostname auflösen, **alle** aufgelösten IPs gegen Blocklisten prüfen, IPv6 behandeln.
**Schwere:** High (SSRF).

### H-02 — `list_decisions` ignoriert das angefragte Universe
**Ort:** `backend/interfaces/rest/routers/decisions.py:275-280`
**Problem:** Sobald ein Tages-Snapshot existiert (`len(snapshots) >= 80 %` der Universe-Größe), wird
`stock_signal_repo.get_today_all()` (alle heutigen Signale, ohne Universe-Filter) zurückgegeben. `universe.tickers`
wird nie angewendet.
**Failure-Szenario:** Zwei Universes → beide `universe_id` liefern denselben globalen Ticker-Set.
**Schwere:** High (falsche Daten pro Universe).

### H-03 — Überlappende Forward-Returns werden auf-multipliziert → grotesk überhöhte „PRISMA-Performance"
**Ort:** `backend/application/services/signal_validation_service.py:59-75`
**Problem:** `returns_20d = pct_change(20).shift(-20)` (20-Tage-Forward-Returns) werden an *jedem* BUY-Tag gesampelt und
dann via `(1+forward_returns).prod()-1` kompoundiert.
**Failure-Szenario:** 100 aufeinanderfolgende BUY-Tage → 100 zu ~95 % überlappende 20-Tage-Returns multipliziert →
ausgewiesene Rendite z. B. +600 % statt real ~+20 %. Wird dem Nutzer als „hat historisch funktioniert" gegen ein
simples Buy&Hold gezeigt (Äpfel/Birnen + massiv inflationiert).
**Schwere:** High (irreführende Performance-Zahlen).

### H-04 — Login ohne Rate-Limiting/Lockout → Passwort-Brute-Force
**Ort:** `backend/interfaces/rest/routers/auth.py:29`; `…/rate_limiter.py:28-41` (Login nicht in `_LLM_PREFIXES`)
**Problem:** Kein Versuchszähler, kein IP/Account-Throttling auf `/api/v1/auth/login`.
**Failure-Szenario:** Unbegrenztes Durchprobieren von Passwörtern.
**Schwere:** High.

### H-05 — Rate-Limiter keyed auf Proxy-IP + unbegrenztes Wachstum
**Ort:** `backend/interfaces/rest/rate_limiter.py:73, :57`
**Problem:** `request.client.host` ist hinter Render die Proxy-IP → alle Nutzer teilen einen Bucket (Limit entweder
kollektiv oder wirkungslos), `X-Forwarded-For` wird ignoriert. Zusätzlich wächst `self._calls` (dict je `IP:path`)
unbegrenzt — die Buckets werden geleert, die Keys nie entfernt (Memory-Leak).
**Schwere:** High (Schutz wirkungslos + Leak).

### H-06 — Live-Sharpe/Calmar/Vol-MAE annualisieren Horizon-Returns als Tagesrenditen
**Ort:** `backend/application/jobs/signal_evaluation_job.py:83, :89, :98`
**Problem:** `realized_fwd_return` läuft über `horizon` Tage, aber Annualisierung nutzt fix `sqrt(252)`/`*252`. Der
`horizon` wird ignoriert; zusätzlich hängt der Drawdown von der nicht garantiert zeit-sortierten `list_resolved`-Reihenfolge ab.
**Failure-Szenario:** `horizon=90` → Vol um √90 ≈ 9.5× überschätzt → `vol_mae > 0.45` → `DriftMonitor` dauerhafte
False-Positives; Sharpe ebenfalls falsch.
**Schwere:** High (falsche Drift-/Risikometriken).

### H-07 — Admin-Schutz ist rein clientseitig (Middleware prüft nur Token-Präsenz)
**Ort:** `frontend/middleware.ts:8-23`, `frontend/app/admin/layout.tsx:24-32`
**Problem:** Middleware lässt jeden mit *irgendeinem* nicht-leeren `prisma_token`-Cookie durch; die Rollenprüfung
passiert ausschließlich clientseitig (`useEffect` + `return null`).
**Failure-Szenario:** Ein Viewer (oder beliebiger Cookie-Wert) kann Admin-Routen-JS laden; Schutz hängt voll am
Backend. Wenn ein Admin-Endpoint backendseitig nicht streng prüft (siehe C-03), ist er offen.
**Schwere:** High (Defense-in-Depth fehlt).

### H-08 — Cost-Cap-Check reserviert kein Budget (TOCTOU über Prozesse)
**Ort:** `backend/infrastructure/persistence/repositories/cost_log_repository.py:129-142`
**Problem:** `check_cap_atomic` hält den `pg_try_advisory_xact_lock` nur während des SELECT; `record()` läuft in einer
separaten Transaktion *nach* dem LLM-Call. Zwischen Check und Record wird nichts reserviert.
**Failure-Szenario:** N parallele Calls bestehen alle den Check und überschreiten gemeinsam den Cap.
**Schwere:** High (Kostenkontrolle).

### H-09 — Budget-Kostenschätzung unterzählt strukturierte Message-Inhalte
**Ort:** `backend/infrastructure/llm/client.py:191` (`_estimate_messages_cost`)
**Problem:** `sum(len(m.get("content", "")) …)` — `content` kann eine **Liste** von Blocks sein; `len(list)` liefert
die Blockanzahl (z. B. 2) statt der Zeichen.
**Failure-Szenario:** Multimodale/strukturierte Messages → Kostenschätzung massiv zu niedrig → Cap-Check besteht,
obwohl überschritten würde. Widerspricht der dokumentierten pessimistischen Absicht.
**Schwere:** High.

### H-10 — GDPR-Löschung entfernt den Budget-/Audit-Cost-Log
**Ort:** `backend/infrastructure/persistence/repositories/user_repository.py:66, :78` (`delete_user_data`)
**Problem:** Löscht `LLMCallLogORM`-Zeilen per `user_id`. Dieser Log ist die Single-Source-of-Truth der
Monats-Spend-Aggregation und ein append-only Audit-Trail.
**Failure-Szenario:** Nach Nutzerlöschung sinkt der gemessene Monatsverbrauch → Budget-Cap leckt; Audit inkonsistent.
**Fix-Richtung:** `user_id` anonymisieren/nullen statt löschen.
**Schwere:** High.

### H-11 — JWT-Worker-Validator hat keinen CI-Bypass → Scheduled Workflows crashen beim Boot
**Ort:** `backend/config.py:164-168` + `.github/workflows/v4-operations-worker.yml:16`, `historical-seed.yml:41`
**Problem:** Beide Workflows setzen `ENVIRONMENT: production`, aber kein `JWT_SECRET`. `_jwt_secret_required_in_production`
hat — anders als `_api_key_required_in_production` (das via `os.getenv("CI")` ausweicht) — **keinen** CI-Bypass.
**Failure-Szenario:** Jeder geplante Lauf instanziiert `Settings()` und stirbt mit `ValueError: JWT_SECRET …` bevor
irgendetwas läuft. Die V4-Learning-Loop und der Historical-Seed laufen still nie.
**Schwere:** High (operativ — Features tot).

### H-12 — Destruktive Embedding-Migrationen löschen alle RAG-Daten ohne Backup
**Ort:** `backend/alembic/versions/0022_*.py:21,35`, `0023_*.py:22,31,45,52`
**Problem:** `DELETE FROM swiss_rag_chunks / news_chunks / embedding_chunks` laufen bedingungslos in up- **und**
downgrade.
**Failure-Szenario:** Upgrade einer Prod-DB zerstört alle Embeddings; Neuerzeugung nur über kostenpflichtige
Voyage-API-Calls.
**Schwere:** High (Datenverlust + Kosten).

### H-13 — `/api/v1/runs` (MCP-Tool) in Produktion standardmäßig ohne Auth
**Ort:** `backend/config.py:43-46` + `render.yaml:54-55`
**Problem:** `tool_api_key` default `""` = „Enforcement deaktiviert"; `TOOL_API_KEY` ist `sync: false` (manuell) und es
gibt **keinen** Production-Validator, der ihn erzwingt (anders als `api_key`/`jwt_secret`).
**Failure-Szenario:** Operator vergisst `TOOL_API_KEY` → der Endpoint, der teure LLM-Ranking-Läufe auslöst, ist offen →
unbegrenzte Anthropic-Kosten.
**Schwere:** High.

### H-14 — Produktions-Image mit komplett ungepinnten Abhängigkeiten gebaut
**Ort:** `Dockerfile.backend:13,20` + `pyproject.toml:10-41`
**Problem:** Image baut aus `pyproject.toml` mit `pip install .` und nur `>=`-Ranges; `uv.lock` wird zwar im
`render.yaml` buildFilter referenziert, aber im Dockerfile nie konsumiert.
**Failure-Szenario:** Zwei Builds desselben Commits ziehen unterschiedliche transitive Versionen (z. B. ein
zurückgezogenes/kompromittiertes `anthropic`/`xgboost`) → nicht reproduzierbar + Supply-Chain-Risiko.
**Schwere:** High.

---

## 🟡 MEDIUM

### M-01 — `_make_stub_prices`-Verwandte Stubs auch im Agentic-DI (Synthetik + Stub-Exposure)
**Ort:** `backend/interfaces/rest/dependencies.py:585-589, :601-624`
**Problem:** Neben dem Fake-Preisframe (siehe C-01) liefert `_StubExposureStore.get_exposure` immer `0.0`, und der
`InvestmentDirector` wird mit `stock_service=None, steuer_agent=None` gebaut. Stubs/None landen im Produktions-Pfad.
**Schwere:** Medium (toter/halb verdrahteter Produktionspfad).

### M-02 — Discovery-Endpoints öffentlich + überschreibbare Profile + LLM-Kosten-Abuse
**Ort:** `backend/interfaces/rest/routers/discovery.py:182, :321, :347`
**Problem:** `/discovery/answer` triggert Claude-Calls **ohne Auth** (nur schwaches IP-Rate-Limit); `POST /api/v1/profile`
überschreibt das Profil für jede client-gelieferte `session_id`.
**Schwere:** Medium (Kosten-Abuse + Profil-Overwrite).

### M-03 — `explain_decision` verschluckt `BudgetCapExceeded` in einen 503
**Ort:** `backend/interfaces/rest/routers/decisions.py:203-232`
**Problem:** Breites `except Exception` fängt das Domain-`BudgetCapExceeded`, das überall sonst über den globalen
Handler zu **402** wird. Budget-Erschöpfung erscheint als transienter Ausfall → inkonsistentes Fehlermodell.
**Schwere:** Medium.

### M-04 — `analyze_stream`: Fire-and-Forget-Task auf geteiltem Singleton-Director
**Ort:** `backend/interfaces/rest/routers/analyze.py:30` + `dependencies.py:798-837`
**Problem:** `asyncio.create_task(director.run_with_events(...))` wird weder gespeichert noch awaited (GC-Risiko,
verschluckte Exceptions, kein Cancel bei Client-Disconnect). `get_investment_director()` ist ein **prozessweiter
Singleton** → geteilter Checkpoint/Run-State, Races zwischen Nutzern.
**Schwere:** Medium.

### M-05 — `submit_checkpoint` löst beliebige Checkpoints auf (IDOR)
**Ort:** `backend/interfaces/rest/routers/analyze.py:61-68`
**Problem:** Auflösung von `checkpoint_id` am geteilten Singleton ohne Owner-Check → ein Nutzer beantwortet den
HITL-Checkpoint eines anderen.
**Schwere:** Medium.

### M-06 — Crypto-Feature-Flag via Dashboard-Router umgehbar
**Ort:** `backend/interfaces/rest/routers/crypto_dashboard.py:40` vs. `crypto.py:31-33`
**Problem:** Beide mounten auf `/api/v1/crypto`, aber dem Dashboard-Router fehlt `Depends(require_crypto_enabled)`. Bei
`CRYPTO_FEATURE_ENABLED=false` bleiben `/{coin}/ohlcv`, `/{coin}/agent-audit`, `/{coin}/confirm` erreichbar.
**Schwere:** Medium.

### M-07 — Equity-Kurve inkonsistent: DD-Brake nutzt andere Returns als die Reports
**Ort:** `backend/application/backtest/portfolio_walkforward.py:200-204` vs. `:209-213`
**Problem:** Interne `portfolio_equity` (treibt den Drawdown-Brake) lagged einen Tag extra (`weight_df.loc[t_prev] *
daily_returns[t]`), während die berichteten Metriken aus dem gleich-getakteten `(weight_df * ret_df).sum()` stammen.
**Schwere:** Medium (nicht reproduzierbarer Backtest).

### M-08 — `run_walkforward` ist kein Walk-Forward — `min_train`/`step` sind tote Parameter
**Ort:** `backend/application/backtest/walkforward.py:134-239`
**Problem:** Header verspricht Expanding-Window mit `min_train`-Trainingsfenster, aber `min_train`/`step` werden nie
verwendet; Metriken inkl. „Trainings"-Phase (erste 252 Tage) → optimistisch verzerrt.
**Schwere:** Medium.

### M-09 — `DriftMonitor` ohne Deduplizierung → Flag-/Alert-Spam
**Ort:** `backend/application/jobs/drift_monitor.py:94-146`
**Problem:** Jeder Lauf insertet pro Metrik unter Schwelle ein neues `DriftFlag` und alarmiert; `list_active()` wird nie
geprüft. Persistent driftender Coin → tägliche Flags + Alerts, keine Idempotenz.
**Schwere:** Medium.

### M-10 — `log_signals`/Krypto-/Stock-Upsert ohne Idempotenz → Duplikate bei Re-Run
**Ort:** `backend/application/jobs/paper_trading_log.py:74-93`; `…/persistence/repositories/crypto_signal_repository.py:21-48`; `…/stock_signal_repository.py:18-48`
**Problem:** „Append/Upsert" per SELECT-then-INSERT ohne Unique-Constraint auf `(coin/ticker, date)`. Zwei parallele
Läufe finden beide nichts → doppelte Tageszeilen; später doppelt mit Outcomes gefüllt → Hit-Rate/Sharpe doppelt
gezählt.
**Schwere:** Medium (Race + Datenduplikate).

### M-11 — On-Chain-Health: hoher MVRV-Z erhöht den Health-Score (finanziell invers)
**Ort:** `backend/application/signals/factors.py:81-95`
**Problem:** `mvrv_score = (z_last+3)/6` → hoher MVRV-Z (historisch Überbewertung/Top, bearish) ergibt hohen
Health-Score (bullish). Inverse Interpretation.
**Schwere:** Medium.

### M-12 — RetrainingJob: leere Modelle aktivierbar + nicht-atomarer Champion-Wechsel
**Ort:** `backend/application/jobs/retraining_job.py:92-126`; `…/persistence/repositories/model_registry_repository.py:46-60`
**Problem:** Bei komplett fehlgeschlagenen Fits ist `model_infos` leer → `avg_oos_r2=0.0`; ein leeres Modell kann beim
ersten Lauf Champion werden. Insert(`is_champion=True`) + separates `set_champion()` ohne Transaktion/Lock und ohne
partiellen Unique-Index → 0 oder 2 Champions möglich.
**Schwere:** Medium.

### M-13 — yfinance `dividendYield`-Konvention widerspricht Scorer-Erwartung
**Ort:** `backend/infrastructure/adapters/yfinance_swiss.py:114` → `domain/services/swiss_quant_scorer.py:108-115`, `langfrist_score_calculator.py:57-68`
**Problem:** `get_fundamentals` legt `dividendYield` roh ab; Scorer behandeln es als Dezimalbruch (`dy > 0.03`). Aktuelle
yfinance-Versionen liefern Prozent (z. B. `2.5`). Eigener Widerspruch: `get_dividends` (`:204-207`) multipliziert
denselben Wert ×100.
**Failure-Szenario:** Bei Prozent-Semantik scoren praktisch alle Titel `2.5 > 0.03` → Income-Score immer 100.
**Schwere:** Medium.

### M-14 — CoinGecko-Cache wird bei dauerhaftem API-Fehler nie invalidiert
**Ort:** `backend/infrastructure/adapters/coingecko_adapter.py:63-65`
**Problem:** Bei jedem Fehler wird `self._market_cache` ohne Altersprüfung zurückgegeben → stale Preise stundenlang als
aktuell ohne Staleness-Signal.
**Schwere:** Medium.

### M-15 — Irreführender/toter „Missing API Key"-Banner
**Ort:** `frontend/components/ui/MissingApiKeyBanner.tsx:7-20`
**Problem:** Zeigt roten Fehler, wenn `NEXT_PUBLIC_API_KEY` fehlt — aber diese Variable wird sonst nirgends genutzt
(Auth läuft über `prisma_token`). In Produktion ohne diese (nutzlose) Var sehen alle Nutzer „alle API-Aufrufe schlagen
mit 401 fehl", obwohl alles funktioniert. (Hängt mit C-03 zusammen.)
**Schwere:** Medium (Falschmeldung).

### M-16 — Retry ignoriert HTTP-Statusfehler (429/5xx) bei News-Adaptern
**Ort:** `backend/infrastructure/adapters/cryptopanic_adapter.py:71`, `rss_news_adapter.py:50`
**Problem:** Retry-Schleife fängt nur `TimeoutException`/`NetworkError`; `raise_for_status()`→`HTTPStatusError`
(429/503) schlägt sofort durch — genau die Fälle, die Backoff bräuchten.
**Schwere:** Medium.

### M-17 — `health_ready` leakt interne Fehlerdetails an unauthentifizierte Clients
**Ort:** `backend/interfaces/rest/routers/health.py:42`
**Problem:** `HTTPException(503, detail=f"Database nicht erreichbar: {exc}")` echot die rohe DB-Exception (Host/Treiber).
**Schwere:** Medium (Info-Leak).

### M-18 — Geldbeträge als `float` in Domain-Value-Objects
**Ort:** `backend/domain/value_objects/portfolio_allocation.py:18-22`, `rebalancing_plan.py:18-33`
**Problem:** `weight`, `estimated_value_chf`, `transaction_cost_chf`, `total_portfolio_value_chf` sind `float` →
Rundungsfehler (Gewichtssumme ≠ 1.0). Inkonsistent zu `SwissFundamentals.market_cap_chf`, das `Decimal` nutzt.
**Schwere:** Medium.

### M-19 — Fehlende Stream/Fetch-Cleanups im Frontend (Memory Leaks, hängende UI)
**Ort:** `frontend/hooks/useAnalysisStream.ts:40-72` (kein `EventSource.close()`; `JSON.parse` ohne try/catch in `:51`),
`frontend/hooks/useCryptoAgentAnalysis.ts:18-53` (kein `AbortController`), `frontend/components/chat/ChatDrawer.tsx:30-52`
(kein Abort bei Unmount)
**Problem:** Mehrere SSE/Fetch-Streams ohne Unmount-Cleanup → offene Verbindungen, `setState` auf unmounteten
Components, ein malformed SSE-Frame kann den Analyse-Stream dauerhaft auf `running` hängen lassen. Hält außerdem den
Cold-Start-Banner „kleben" (`frontend/lib/api/cold-start-store.ts:44-60`).
**Schwere:** Medium (Robustheit).

---

## ⚪ LOW

- **L-01** — `validate_signal_weights_sum` (`backend/config.py:111-114`) ist toter No-Op-Validator; echte Prüfung liegt in `_validate_signal_weights` (`:140-148`). *(auch von DevOps-Audit bestätigt)*
- **L-02** — `_api_key_required_in_production` (`config.py:157`) wird durch ambientes `CI=true` deaktiviert → kompromittierter Container mit `CI=true` bootet in Prod mit leeren Secrets. Eigenes Flag (`SKIP_SECRET_VALIDATION`) statt `CI`.
- **L-03** — Login-User-Enumeration via Timing (`auth_service.py:55-61`): unbekannte E-Mail kehrt vor dem bcrypt-Vergleich zurück → messbarer Latenzunterschied.
- **L-04** — RSI=100 statt 50 bei flachen Preisen (`signals/indicators.py:68`): `ema_up==0 and ema_dn==0` → sollte neutral 50.
- **L-05** — Calmar=0 bei Drawdown 0 (`backtest/walkforward.py:62-68`) benachteiligt drawdown-freie Strategien in `beats_exposure_matched`.
- **L-06** — Konsens degradiert still von 2-aus-3 zu 1-aus-2 bei fehlender Signalspalte (`signals/consensus.py:56-70`).
- **L-07** — Daten-Gaps werden nie berechnet, obwohl gemeldet (`pipeline/etl.py:95,122`): `gaps=[]` bleibt leer.
- **L-08** — `CostTracker.check_cap` verschluckt echte DB-Fehler und degradiert still auf prozess-lokalen Check (`services/cost_tracker.py:76-90`).
- **L-09** — Sweet-Spot-Universumsgröße zählt unranked Ticker mit (`services/ranking_aggregator.py:50-67`) → Top-25%-Schwelle zu locker.
- **L-10** — `BullResearchAgent` Doku sagt Sonnet, Code nutzt Haiku (`agents/bull_research_agent.py:32,46-47`).
- **L-11** — Casing-Mismatch Audit-Trail: Insert speichert `coin` roh, Lookup filtert `coin.upper()` (`agent_audit_trail_repository.py:50-57` vs. `:68-71`; gleiches Risiko in `hitl_confirmation_repository`).
- **L-12** — `CryptoSignal` trotz `frozen=True` mutierbar & unhashbar (dict/list-Felder) (`domain/value_objects/crypto_signal.py:18,34`).
- **L-13** — `get_latest_all` lädt komplette Signal-Historie in den Speicher (`crypto_signal_repository.py:59-68`) → OOM-Risiko auf 512-MB-Free-Tier. `DISTINCT ON (ticker)` nutzen.
- **L-14** — ECB-FX nimmt nur jüngsten Index; `None` an Feiertagen → unnötiger Hardcoded-Fallback trotz 4 gültiger älterer Werte (`ecb_fx_adapter.py:62-65`).
- **L-15** — Diverse Konsistenz-/Aufräum-Themen: `apiFetch` castet 204→`undefined as T` (`client.ts:63-66`); inkonsistentes CSV-Escaping (`rankings-table.tsx:63` vs. `portfolio-client.tsx:77`); Max-Drawdown grün gefärbt (`fonds-client.tsx:66,81-83`); doppelte Komponenten (`EligibilityPanel`, `FundamentalsCard`, `stocks-list-client`); `Number(e.target.value)`-NaN (`steuer-client.tsx:211`); `/api` als Public-Path-Präfix in `middleware.ts:4,15`; FMP `_f` behandelt echte `0` als Missing (`fmp_fundamentals_adapter.py:107`); `DividendEntry.date: str` statt `date` (`dividend_data.py:9-13`); CI ohne Security-Scans; zwei widersprüchliche `dev`-Dependency-Definitionen (`pyproject.toml:43-56` vs. `:146-151`); Hardcoded `prisma:prisma` in `docker-compose.yml`; `.env.example` mit non-leeren Platzhalter-Secrets; CD auto-deployt auf jedes grüne CI inkl. destruktiver Auto-Migration.

---

## ✅ Geprüft & in Ordnung (keine Befunde)

- JWT-Handling solide: fixes `algorithms=["HS256"]` (keine Alg-Confusion), `exp` gesetzt, `is_active` pro Request
  geprüft, leeres `jwt_secret` in *Production* blockiert. HMAC-konstantzeitige Key-Vergleiche.
- Alembic-Chain: genau **ein** Head (`0049` merged sauber `0036`+`0048`), keine Orphans; `signal_outcomes` (0034) ≠
  `crypto_signal_outcomes` (0044) — keine Kollision.
- Docker-Images laufen **non-root** (`USER prisma`/`USER nextjs`).
- Vektor-Interpolation in `find_nearest` ist **keine** SQL-Injection (Float-validiert, `%.8f`, Finite-Check).
- ISIN-Luhn-Validator korrekt (ISO 6166). Monte-Carlo (GBM/Cholesky), `meta_label`-Embargo, PIT-Eligibility korrekt.
- Ticker-Path-Parameter regex-validiert; globaler Exception-Handler verhindert Stacktrace-Leaks app-weit.

---

# TEIL 2 — DIE BESTEN LÖSUNGSWEGE

Priorisiert nach *Wirkung × Dringlichkeit*. Reihenfolge = empfohlene Bearbeitungsreihenfolge.

---

## Sprint 0 — Sofort (Produkt-Integrität & akute Sicherheit)

### Lösung A — Echte Marktdaten statt Random-Walk (behebt C-01, M-01)
**Beste Lösung:** Den `signal_service.evaluate`-Pfad an die bereits vorhandene Infrastruktur anschließen statt an
`_make_stub_prices`.
1. Im Signals-Router echte Preise aus dem `SQLACryptoSignalRepository` / `YFinanceCryptoAdapter` laden (existieren
   bereits, inkl. `crypto_onchain_history`). `_make_stub_prices` nur noch als explizit markierter Test-Fixture
   (`tests/`) behalten, **nicht** im Router importierbar.
2. `get_signal_director` analog umbauen: realen Preis-Frame injizieren; `_StubExposureStore` durch ein echtes
   Exposure-Repository ersetzen; `InvestmentDirector(stock_service=…, steuer_agent=…)` vollständig verdrahten.
3. **Schutzgeländer:** Wenn echte Daten fehlen → `503` + Response-Feld `data_source: "unavailable"` zurückgeben,
   **niemals** synthetische Zahlen als Empfehlung ausliefern. Optional `?demo=true` mit klar gelabeltem
   `data_source: "synthetic"`.
4. Test: Integrationstest, der sicherstellt, dass kein Produktions-Endpoint `_make_stub_prices` aufruft (z. B. Grep-
   Guard im CI).

### Lösung B — FX-Richtung korrigieren (behebt C-02)
Ticker auf `USDCHF=X` umstellen **oder** `df[col] = df[col] / chfusd_rate`. Danach einen Property-Test ergänzen:
„1 USD muss < 1 CHF ergeben" (Sanity-Assertion `0.7 < rate < 1.1`), damit eine künftige Inversion sofort auffliegt.
Den Hardcoded-Fallback (`0.90`) und den Live-Pfad auf **dieselbe** Richtung normalisieren.

### Lösung C — Admin-Key aus dem Browser entfernen (behebt C-03, H-07, M-15)
1. `NEXT_PUBLIC_API_KEY` komplett streichen. Admin-Aufrufe laufen ausschließlich über das JWT (`require_admin_role`
   existiert bereits) — kein statischer Shared-Key im Client.
2. `MissingApiKeyBanner` entfernen.
3. Admin-Routen serverseitig absichern: in der Next.js-Middleware **nicht** nur Token-Präsenz prüfen, sondern den JWT
   verifizieren und die Rolle aus dem Claim lesen (oder einen `/auth/me`-Check im Server-Layout). Der Client-Guard
   bleibt nur kosmetisch.

### Lösung D — Mandanten-Isolation für Alerts (behebt C-05, H-01)
1. Migration: `alerts.user_id` (FK, NOT NULL) hinzufügen; alle Queries/Deletes auf `current_user.id` scopen; bei
   Fremdzugriff `404`.
2. SSRF: `target`-Host auflösen, **alle** resolved IPs gegen private/Link-Local/Metadata-Ranges prüfen (IPv4 **und**
   IPv6), dezimal/oktal-Encoding normalisieren. Am besten Egress-Allowlist + dedizierte Bibliothek statt
   selbstgebautem Regex.

### Lösung E — Destruktive Migration entschärfen (behebt C-06, H-12)
1. `0029`-TRUNCATE und die Embedding-`DELETE`-Migrationen **aus dem Container-Start-Pfad entkoppeln**:
   `backend-start.sh` nicht mehr blind `alembic upgrade head`. Stattdessen: Schema-Migrationen automatisch,
   *daten-löschende* Migrationen nur über einen manuellen, geloggten Job mit vorherigem `pg_dump`-Backup.
2. Bereits angewandte destruktive Migrationen als „one-way" dokumentieren; künftig Datenmigration **in-place**
   (Re-Embed) statt `DELETE`.
3. CD: Environment-Protection mit manueller Freigabe für Prod; `force_deploy` (CI-Bypass) entfernen oder eng
   absichern.

### Lösung F — Token-Speicherung härten (behebt C-07)
Token serverseitig als `HttpOnly; Secure; SameSite=Strict`-Cookie setzen (Login-Response über einen Next.js
Route-Handler/Backend), `localStorage`-Speicherung entfernen. Der `Authorization`-Header entfällt dann; CSRF über
`SameSite=Strict` + ggf. Double-Submit-Token absichern.

---

## Sprint 1 — Kostenkontrolle wasserdicht (behebt C-04, H-08, H-09, H-10, H-13, L-08)

**Beste Lösung — ein einziger erzwungener Cap-Pfad:**
1. **Reservierungs-Muster** statt Check-then-Act: Vor jedem LLM-Call ein „pending"-Kostenrecord mit geschätztem Betrag
   in derselben Transaktion wie der Cap-Check einfügen (Advisory-Lock über Check **und** Insert halten). Nach dem Call
   den Record mit Ist-Kosten finalisieren. Das schließt das TOCTOU-Fenster (H-08).
2. **Streaming-Chat** zwingend über denselben Pfad leiten: `check_cap()` vor beiden `messages.stream`-Calls (C-04).
   Kein direkter `raw_client`-Zugriff, der den Wrapper umgeht — am besten `raw_client` privat kapseln.
3. **Schätzung korrigieren** (H-09): bei Listen-`content` die `text`-Felder der Blocks summieren (wie bei `system`).
4. **Cost-Log unantastbar** (H-10): bei GDPR-Löschung `user_id` anonymisieren statt Zeilen zu löschen.
5. **`tool_api_key` erzwingen** (H-13): Production-Model-Validator ergänzen, der bei leerem `tool_api_key` den Boot
   abbricht — analog zu `api_key`/`jwt_secret`.
6. `CostTracker.check_cap` (L-08): nur den erwarteten „Stub-fehlt"-Fall fangen, echte DB-Fehler propagieren/alarmieren.

---

## Sprint 2 — Quantitative Korrektheit (behebt H-03, H-06, M-07..M-12, M-16, L-04..L-09)

Diese Befunde betreffen die *Glaubwürdigkeit der Zahlen*. Empfehlung: eine eigene „Quant-Correctness"-Testsuite mit
synthetischen Ground-Truth-Serien.
- **H-03 Forward-Returns:** nicht-überlappendes Sampling (jeder n-te Tag) **oder** mittlere Forward-Return statt
  Produkt; gegen exposure-/zeit-gematchte Baseline vergleichen.
- **H-06 Annualisierung:** mit `sqrt(252/horizon)` bzw. `252/horizon` skalieren; Records nach Datum sortieren.
- **M-07/M-08 Backtest:** eine einzige Lag-Konvention für Equity & Report; echtes Train/Test-Split implementieren
  oder die irreführenden Parameter/Doku entfernen.
- **M-09 DriftMonitor / M-10 Idempotenz:** vor Insert gegen aktive Flags bzw. existierende `(coin, date)`-Einträge
  prüfen; DB-Unique-Constraints + `on_conflict_do_update` für Krypto-/Stock-Tagessignale.
- **M-11 MVRV:** Komponente invertieren (hoher Z → niedriger Health-Score) oder explizit validieren.
- **M-12 ModelRegistry:** leeres `model_infos` als Skip; Insert+`set_champion` atomar in einer Transaktion; partieller
  Unique-Index `WHERE is_champion`.
- **M-16:** 429/5xx in die Retry-Bedingung der News-Adapter aufnehmen (mit Backoff).
- **L-04..L-09:** Einzelfixes (RSI-Neutral-Fall, Calmar-Sonderfall, Konsens-Mindestspalten, ETL-Gaps implementieren
  oder Anspruch entfernen, Sweet-Spot nur geranked zählen).

---

## Sprint 3 — Härtung & Robustheit (behebt H-04, H-05, H-11, H-14, M-02..M-06, M-13..M-19, Low-Rest)

- **H-04/H-05 Rate-Limiting:** `X-Forwarded-For` (erste vertrauenswürdige Hop-IP) als Key; periodische Bereinigung
  leerer Buckets (oder Redis/slowapi). Eigenes striktes Login-Throttling + Account-Lockout-Backoff.
- **H-11:** denselben `and not os.getenv("CI")`-Bypass im JWT-Validator ergänzen **oder** `JWT_SECRET` in beide
  Worker-Workflows eintragen.
- **H-14:** Produktions-Image aus `uv.lock` bzw. `pip install --require-hashes` bauen (reproduzierbar).
- **M-02:** Discovery-Endpoints hinter ein leichtgewichtiges Session-Token/Captcha stellen; `session_id` write-once.
- **M-03:** `BudgetCapExceeded` vor dem generischen `except` re-raisen (konsistentes 402).
- **M-04/M-05:** Task-Referenz + Done-Callback fürs Error-Logging; per-Request/Session-State statt Prozess-Singleton;
  Checkpoint-Ownership prüfen.
- **M-06:** `require_crypto_enabled` auch am Dashboard-Router.
- **M-13:** `dividendYield`-Konvention an genau einer Stelle festnageln und konsistent normalisieren.
- **M-14:** Cache-Maximalalter auch im Fehlerpfad prüfen / Staleness-Flag zurückgeben.
- **M-17:** DB-Exception loggen, generischen 503-Body senden.
- **M-18:** `Decimal` für alle CHF-Beträge/Gewichte.
- **M-19:** Einheitliches `useEffect`-Cleanup-Pattern für alle SSE/Fetch-Streams (`AbortController` + `close()`),
  `JSON.parse` in try/catch, jedes `trackRequestStart` garantiert ein `done()`.

---

## Sprint 4 — Aufräumen / Tech-Debt (Low)

Toter Code & Inkonsistenzen entfernen: No-Op-Validator (L-01), `require_admin_api_key` (ungenutzt), doppelte
Frontend-Komponenten, `CI`-basierter Secret-Bypass → eigenes Flag (L-02), `.env.example`-Platzhalter leeren,
Coverage-`omit`-Liste verkleinern, CI-Security-Scans (pip-audit/npm-audit/Bandit/Secret-Scan) als Pflicht-Gate,
`dev`-Dependencies konsolidieren, Datum-Value-Objects als `date` typisieren.

---

## Empfohlene Sofort-Reihenfolge (TL;DR)

1. **C-01 + C-02** — Echte Daten/FX, sonst sind alle Signale wertlos.
2. **C-03 + C-05 + H-01** — Admin-Key raus, Alerts-Owner + SSRF.
3. **C-06 + H-12** — Destruktive Auto-Migrationen entkoppeln (bevor der nächste Deploy Daten löscht).
4. **C-04 + H-08/H-09/H-13** — Budget-Cap-Lecks schließen.
5. **C-07 + H-11** — Token-Cookie härten; Worker-Boot-Crash fixen.
6. Danach Sprint 2 (Quant-Korrektheit) und Sprint 3/4.

---
---

# NACHTRAG — WELLE 2 (bisher ungeprüfte Bereiche)

Nach Rückfrage „Sind das wirklich alle Befunde?" wurden die im ersten Durchlauf **nicht** auditierten Bereiche
nachgezogen: `scripts/` (top-level, 6.244 LOC) + `backend/scripts/`, die ML-Trainings-Pipeline, die committeten
`models/`-Binärdateien, die 15 LLM-Agenten, `prisma_v3_seed/`, das MCP-Interface und — als Meta-Ebene — die
**Qualität der Test-Suite selbst**. IDs mit Präfix `W2-`.

## 🔴 CRITICAL (Welle 2)

### W2-C-01 — ML-Modelle werden via `joblib`/`pickle` aus dem Git-Repo geladen → RCE-Fläche
**Ort:** `backend/application/services/ml_prediction_service.py:17-19,66`, `quantile_prediction_service.py:35,76`; Artefakte in `models/*.joblib` (13 Dateien, eingecheckt)
**Problem:** `joblib.load()` == `pickle.load()` → führt beim Deserialisieren **beliebigen Code** aus. Die produktiv geladenen Modelle liegen als Binär-Blobs im Git und sind in Reviews nicht prüfbar.
**Failure-Szenario:** Wer einen PR/Branch/das Trainings-Artefakt manipulieren kann, erreicht Code-Execution im Backend beim ersten Predict-Call.
**Fix:** Modelle aus Git nehmen → signiertes Object-Storage mit SHA256-Pinning; Integritätsprüfung vor `joblib.load`.

### W2-C-02 — Kein Quality-Gate: nachweislich schlechtes Modell wird Champion
**Ort:** `scripts/train_quantile_model.py:226` (`active_quantile` unbedingt gesetzt); `scripts/train_return_predictor.py:603-635` (kein Mindest-Gate); Beleg: `models/registry.json` (aktives Return-Modell `val_accuracy: 0.4223`)
**Problem:** Der Quality-Check (`all_beat` / Baseline) ist rein kosmetisch im `ml_eval.md` und beeinflusst das Deployment **nicht**. Das aktive Return-Predictor-Modell hat eine Validation-Accuracy von **0.4223** — bei Up/Down-Klassifikation (50 % = Zufall) **schlechter als ein Münzwurf**.
**Failure-Szenario:** Ein Modell, das in allen Quantilen schlechter als die Konstant-Baseline ist, wird produktiv und treibt Live-Signale.
**Fix:** `active`/`latest` nur bei Überschreiten eines Baseline-Schwellwerts setzen; sonst altes Modell behalten.

### W2-C-03 — Risk-Agent-Veto wird in der Signal-Aggregation ignoriert
**Ort:** `backend/application/agents/signal_director.py:152-163`
**Problem:** `_synthesize` nutzt `risk.approve` nur als Confidence-Nudge (`1.0 if approve else 0.3`); die Trade-Action kommt allein aus der Engine, `size_factor = min(base_size, risk.max_size)`.
**Failure-Szenario:** LLM liefert `RiskVerdict(approve=False, max_size=1.0, breaches=[...])` (schema-valid) → Position wird **trotzdem voll** eröffnet. Das explizite Risiko-Veto hat null Wirkung.
**Fix:** `if not risk.approve: action="HOLD"; size_factor=0.0` vor dem Bau des `TradeSignal`.

### W2-C-04 — Kritische Bugs überleben, weil die Tests den echten Pfad wegmocken
**Ort:** `test_signals_endpoint.py:103-156` (mockt `signal_service.evaluate`/`run_walkforward` komplett), `test_chat_service.py:159-194` (prüft nur `record`, nie `check_cap`), `test_alerts_endpoint.py:36-48` (ersetzt `AlertService` durch `MagicMock`)
**Problem:** Die drei Kern-Critical-Bugs C-01 (Zufallspreise), C-04 (Chat-Budget-Bypass), C-05 (Alerts-IDOR) sind durch vollständiges Wegmocken des getesteten Service **unsichtbar** — die Suite bleibt grün, obwohl die Bugs live sind.
**Failure-Szenario:** Grüne CI suggeriert Sicherheit; genau die gefährlichsten Defekte werden nie getestet.
**Fix:** Mindestens je ein Integrationstest gegen den **ungemockten** Pfad (echte Preise → Signal; übervoller Budget-Tracker → Block; zwei Owner → 404 bei Fremdzugriff).

## 🟠 HIGH (Welle 2)

### W2-H-01 — Datenleckage im Return-Predictor (kein Embargo zwischen Train/Val)
**Ort:** `scripts/train_return_predictor.py:267-281`; Label in `ml_feature_service.py:451-456`
**Problem:** Split rein nach `snapshot_date` (letzte 12 Monate = Val), aber Label = 12-Monats-Vorwärtsrendite, **ohne** Purging/Embargo. Trainings-Snapshots nahe Cutoff „sehen" die Kurs-Zukunft der Val-Periode.
**Failure-Szenario:** Val-Metriken systematisch zu optimistisch → falsche Modellauswahl + falsches Vertrauen ins Live-Modell.
**Fix:** Embargo ≥ Target-Horizont (12 Monate) zwischen Train- und Val-Block.

### W2-H-02 — Quantil-Embargo in Kalendertagen statt Handelstagen → Leakage
**Ort:** `scripts/train_quantile_model.py:82` vs. `ml_feature_service.py:691`
**Problem:** Target = 30 **Handelstage** (≈ 44 Kalendertage), Embargo nutzt `Timedelta(days=30)` = 30 **Kalendertage** (≈ 21 Handelstage). Doku/`meta` behaupten „30 Handelstage".
**Failure-Szenario:** Letzter Trainings-Snapshot reicht mit seinem Target ~14 Kalendertage in die Testperiode → Label-Overlap trotz „Purged CV".
**Fix:** Embargo in Handelstagen rechnen, ≥ Target-Horizont.

### W2-H-03 — MacroAgentV2 erfindet Makro-Zahlen bei Datenausfall
**Ort:** `backend/application/agents/macro_agent_v2.py:74, :159-174`
**Problem:** Bei `MacroService`-Fehler `_fallback(ticker, 0.25, 0.93)` → **hartkodierter Leitzins 0.25 % und CHF/EUR 0.93** landen unverändert in `MacroToolReport` und werden als reale Makrodaten präsentiert.
**Fix:** Bei Datenausfall Felder als `None`/„nicht verfügbar", keine Fantasiewerte.

### W2-H-04 — CointelligenceAgent reicht LLM-halluzinierte Preise als Fakten durch
**Ort:** `backend/application/agents/cointelligence_agent.py:262-266`
**Problem:** `price_chf`, `fear_greed`, `sharpe_*` werden aus dem LLM-JSON gelesen (`data.get("price_chf", 0)`), **nicht** aus dem autoritativen `tool_cache`. Das LLM kann einen Phantasie-BTC-Preis liefern, der ungefiltert an den User geht.
**Fix:** Numerische Felder immer aus dem Cache; LLM liefert nur `regime_signal`/`reasoning`.

### W2-H-05 — DataStewardAgent + Daily-Cron: persistiert nichts, meldet aber Erfolg
**Ort:** `backend/application/agents/data_steward_agent.py:67-80` (kein `repo.update`), `backend/scripts/data_steward_run.py:17-20` (No-Op-Stub, loggt nur „nur Logging-Modus")
**Problem:** Der täglich 06:00 UTC laufende Daten-Pflege-Job tut nichts; der Agent hängt Ticker an `refreshed`/`quarantined`, schreibt aber nie in die DB.
**Failure-Szenario:** Stale-Daten bleiben für immer stale; Monitoring sieht grüne Läufe → stille Funktionslücke.
**Fix:** Echte Persistenz/Quarantäne implementieren oder Cron entfernen (kein falsches Erfolgssignal).

### W2-H-06 — `alembic upgrade head` bei jedem Boot ohne Backup **und ohne Lock**
**Ort:** `scripts/backend-start.sh:13`
**Problem:** Ergänzt C-06/H-12: zusätzlich **kein Migrations-Lock** — bei mehreren Web-Instanzen können zwei `upgrade head` parallel laufen (Race/partielle Migration).
**Fix:** Pre-Migration-`pg_dump` + `pg_advisory_lock` oder dedizierter One-Off-Migrationsjob statt Boot-Pfad.

### W2-H-07 — Doppelte Alembic-Revisions-IDs 0031–0035 (latente kaputte Chain)
**Ort:** `prisma_v3_seed/alembic/0031..0035_*.py` byte-identisch zu `backend/alembic/versions/0031..0035_*.py`
**Problem:** Die Seed-Kopien liegen außerhalb von `script_location` (werden aktuell nicht ausgeführt), tragen aber dieselben `revision`-IDs. Werden sie (laut `README_SEED.md`) zurück nach `versions/` kopiert → „Multiple revisions for given argument" / mehrdeutige Chain.
**Fix:** `prisma_v3_seed/alembic/` löschen.

### W2-H-08 — prisma_v3_seed-Kopien divergieren von den neueren Live-Versionen
**Ort:** `prisma_v3_seed/pipeline/etl.py`, `adapters/eodhd_fundamentals_adapter.py`, `scripts/*.py` vs. Live-Baum
**Problem:** Totes, älteres Staging-Bundle (z. B. `validate_ohlcv` ohne float-Cast → `TypeError` bei String-OHLC; tote Variable `prev_key`). Edits an Seed-Kopien werden nie wirksam.
**Fix:** `prisma_v3_seed/{pipeline,adapters,scripts,workflows}/` löschen — einzige Quelle = Live-Baum.

### W2-H-09 — Aktiver Workflow ruft nicht existierende Scripts auf
**Ort:** `.github/workflows/historical-seed.yml:80,96,130`
**Problem:** Ruft `scripts/data_steward_run.py` (liegt nur in `backend/scripts/`), `scripts/signal_accuracy_run.py` und `scripts/snb_rate_update.py` (existieren nirgends) — meist ohne Skip-Guard.
**Failure-Szenario:** Geplante Jobs brechen mit „can't open file" ab; DataSteward/Signal-Accuracy/SNB-Updates laufen nie → veraltete Preis-/Makrodaten unbemerkt.
**Fix:** Scripts ergänzen oder Schritte entfernen/guarden; `data_steward_run.py`-Pfad korrigieren.

### W2-H-10 — MCP: fixer 30s-Timeout für synchronen Long-Running `/runs`
**Ort:** `backend/interfaces/mcp/rest_client.py:11`; Server `ranking_run_service.py:54-171`
**Problem:** `POST /api/v1/runs` läuft synchron (Fundamentals + Preise + 5 Modelle) vor 201; Client-Timeout hart 30s. Großes Universum → `ReadTimeout`, fälschlich als `UPSTREAM_UNAVAILABLE`, obwohl der Run serverseitig weiterläuft.
**Fix:** Timeout für POST konfigurierbar/höher; besser async-Run + Polling.

### W2-H-11 — Frontend/E2E-Tests ohne echte Verifikation
**Ort:** `frontend/lib/api/__tests__/crypto-signals.test.ts:13-163` (testet nur TS-Literale, ruft keine Client-Funktion auf), `frontend/e2e/run-history.spec.ts:9-19` (`test.skip(true)` greift in CI fast immer), `frontend/e2e/09-news.spec.ts:15-17` (Assertion trivial wahr, da der geklickte Button immer sichtbar bleibt)
**Problem:** Diese „Tests" suggerieren Coverage, prüfen aber faktisch nichts.
**Fix:** Echten Client mit gemocktem `fetch` aufrufen; Runs im global-setup seeden statt skippen; nur auf Ergebnis-/Leerzustand asserten.

## 🟡 MEDIUM (Welle 2)

- **W2-M-01** — Krypto-Sicherheitsregel (MVRV>5 / F&G>80 → CAUTION/AVOID) nur im Prompt, keine Python-Durchsetzung (`cointelligence_agent.py:77` vs. `:252-272`) → LLM kann `ACCUMULATE` bei F&G=95 liefern.
- **W2-M-02** — „Weighted Synthesis" ist irreführend: Technical/OnChain/Macro/Bull/Bear haben **null** Einfluss auf BUY/SELL/HOLD; nur ein Sentiment-Veto kann downgraden (`signal_director.py:105-111,152-157`). Doku überzeichnet.
- **W2-M-03** — Confidence zu ~20 % hartkodiert, ignoriert echtes Sentiment → HITL-Schwelle 0.65 fast immer unterschritten („Dauer-LOW CONFIDENCE") (`signal_director.py:133-144`).
- **W2-M-04** — Portfolio-Gewichte summieren nicht auf 1.0 bei <3 Positionen (`_MAX_WEIGHT=0.40`); n=2 → 0.80, 20 % unallokiert (`portfolio_agent.py:42-54`).
- **W2-M-05** — MacroRegime-Fallback (`NEUTRAL`) wird 1 h gecacht; nach LLM-Recovery bleibt das System bis zu 1 h fälschlich NEUTRAL (`macro_regime_agent.py:130-133`).
- **W2-M-06** — Sentiment: DB-NULL bei `fear_greed` → `TypeError`/500 außerhalb des try-Blocks, umgeht die zugesagte Fallback-Kette (`sentiment_analyst_agent.py:154,178`).
- **W2-M-07** — Tuning vergleicht gegen untuned-LGB statt gegen das beste Modell → schlechteres Modell kann XGBoost-Champion verdrängen (`train_return_predictor.py:590-595`).
- **W2-M-08** — `return_predictor_latest.joblib` ist Byte-Kopie eines versionierten Modells **neben** dem Pointer `latest.json` → können auseinanderdriften (Modell ≠ Meta) (`models/`).
- **W2-M-09** — Zwei parallele Modell-Registries: Datei `models/registry.json` vs. DB-Tabelle `model_registry` (0046) → zwei Sources of Truth.
- **W2-M-10** — Zeitzonen-Inkonsistenz: Stock-Snapshot schreibt `date.today()` (lokal), Lookup/Crypto nutzen UTC (`ml_feature_service.py:345` vs. `stock_signal_repository.py:51`) → Doppelzeilen oder „kein Signal heute" nahe Mitternacht.
- **W2-M-11** — Daily-Jobs melden Status `"ok"` auch bei `saved=0`/partiellen Fehlern; `saved` wird vor dem Commit gezählt (`crypto_daily_snapshot.py:113-125`, `stock_daily_snapshot.py:90-99`) → „erfolgreich" trotz leerer Tabelle.
- **W2-M-12** — Cron-Run-Status bleibt bei Hard-Crash dauerhaft auf `"running"` (kein `try/finally` um `finish_run`).
- **W2-M-13** — `config_additions.py` ist toter, divergierender Code (`dataset_source_fundamentals="auto"` vs. Live `"yf_derived"`); nie importiert.
- **W2-M-14** — MCP: rohe `KeyError`/`TypeError` statt `MCPError` bei verändertem REST-Schema (`tools/run_ranking.py:28-39`); kein Test prüft, dass der Auth-Guard am `POST /runs` verdrahtet ist (`test_runs_endpoint.py`).

## ⚪ LOW (Welle 2)

- **W2-L-01** — `RiskVerdict(approve=True, max_size=0)` bei SELL widersprüchlich (`risk_agent.py:188-203`).
- **W2-L-02** — Hartkodierter EUR/USD 1.08 in CHF/USD-Umrechnung (`cointelligence_agent.py:163`) → erfundener Kurs in Preisberechnung (verwandt mit C-02).
- **W2-L-03** — Checkpoint-Timeout wählt still `freie_mittel`→`privatperson`-Steuerprofil ohne User-Hinweis (`investment_director.py:184`).
- **W2-L-04** — `ADMIN_PASSWORD`-Rotation wirkungslos: `seed_admin` bricht bei existierendem Admin ab → altes Passwort gilt weiter (`seed_admin.py:42-45`).
- **W2-L-05** — 8,6 MB Binär-Modelle im Git, nicht ge-gitignored; verwaiste Binärdateien (`160223`, `160416`) von keiner Registry referenziert (`models/`).
- **W2-L-06** — MCP: `RESTClient.get` als `-> dict` annotiert, liefert aber Liste (`rest_client.py:34`); 503/429 fallen in generisches `INTERNAL` (`errors.py:33`).
- **W2-L-07** — Test-Platzhalter `assert True` (`test_operations_wiring.py:159`); `crypto-dashboard.spec.ts:20-24` prüft nur Tab-Labels, keine Daten.

---

# NACHTRAG zu TEIL 2 — ZUSÄTZLICHE LÖSUNGSWEGE

## Sprint 1b — ML-/Modell-Pipeline absichern (W2-C-01, W2-C-02, W2-H-01, W2-H-02, W2-M-07..M-09, W2-L-05)
**Beste Lösung:**
1. **Artefakte aus Git** → signiertes Object-Storage (Render Disk/S3) mit SHA256-Manifest; vor `joblib.load` Hash gegen das Manifest prüfen. `*.joblib` in `.gitignore`. (W2-C-01)
2. **Hartes Quality-Gate** im Trainings-Script: `active`/`latest`/`champion` nur setzen, wenn das Modell eine naive Baseline um einen definierten Mindestabstand schlägt (Pinball-Loss für Quantile, Top-Quartil-Recall > Zufall für Return). Vergleich immer gegen den **aktuellen Champion**, nicht gegen ein Zwischenmodell. (W2-C-02, W2-M-07)
3. **Leakage schließen:** Purged-CV mit Embargo ≥ Target-Horizont, gerechnet in **Handelstagen**, in beiden Trainings-Scripts. Eine gemeinsame Embargo-Utility, damit Doku und Code nicht auseinanderlaufen. (W2-H-01, W2-H-02)
4. **Eine Registry** kanonisch (DB), Datei daraus generiert; nur Pointer (`latest.json`), keine Byte-Kopie. Verwaiste Binärdateien entfernen. (W2-M-08, W2-M-09, W2-L-05)

## Sprint 2b — Agentic-Layer ehrlich & sicher machen (W2-C-03, W2-H-03..H-05, W2-M-01..M-06)
1. **Risiko-Invarianten in Python erzwingen** (nicht nur im Prompt): Risk-Veto → `HOLD`/`size=0`; Krypto-Safety-Regel nach dem Parsen hart anwenden. (W2-C-03, W2-M-01)
2. **„Iron Rule" konsequent:** numerische Fakten (Preise, Makro, F&G) immer aus dem autoritativen Cache, nie aus dem LLM-JSON; bei Datenausfall `None`/„nicht verfügbar" statt erfundener Zahlen. (W2-H-03, W2-H-04)
3. **DataSteward** echt verdrahten oder Cron + irreführenden Report entfernen. (W2-H-05)
4. **Synthese ehrlich benennen:** entweder Analysten-Signale wirklich in die Action/Confidence einfließen lassen (kalibriert) oder Doku/HITL-Schwelle anpassen. Fallback-Ergebnisse nicht (lang) cachen. (W2-M-02, W2-M-03, W2-M-05)

## Sprint 3b — Aufräumen & Betriebssicherheit (W2-H-06..H-09, W2-M-10..M-14, W2-L-*)
1. **`prisma_v3_seed/` löschen** (oder als read-only Archiv markieren) → räumt W2-H-07, W2-H-08, W2-M-13 und die Workflow-Falle auf einen Schlag. (Migrationen/Code liegen bereits live.)
2. **Workflows reparieren:** fehlende Scripts ergänzen/guarden, Pfade korrigieren. (W2-H-09)
3. **Boot-Migration:** Backup + Advisory-Lock, oder One-Off-Job. (W2-H-06)
4. **Snapshot-Jobs robust:** UTC-Datum überall; `finish_run` in `finally` mit Status aus dem Commit-Ergebnis; `partial`/`error` statt `ok` bei `saved < n`. (W2-M-10..M-12)
5. **MCP:** POST-Timeout erhöhen/Polling; Antworten validieren → `MCPError`. (W2-H-10, W2-M-14)

## Sprint 0b — Test-Suite vertrauenswürdig machen (W2-C-04, W2-H-11)
Dies ist **Voraussetzung**, damit die Fixes der Wellen 1+2 nicht wieder zurückregredieren:
- Für jeden Critical-Fix einen Test gegen den **ungemockten** Code-Pfad (Signals mit bekannten Preisen; Chat-Block bei vollem Budget; Alerts-Owner-Isolation mit zwei Usern; `POST /runs` ohne Header → 401).
- Frontend-„Literal-Tests" durch echte Client-Aufrufe mit gemocktem `fetch` ersetzen; bedingte E2E-Skips durch geseedete Fixtures.
- Coverage-`omit`-Liste verkleinern, damit Adapter/Repos im Gate sichtbar werden.

---

## Aktualisierte Sofort-Reihenfolge (Wellen 1 + 2)

1. **Daten-Integrität:** C-01/C-02 + **W2-C-02** (schlechtes Modell als Champion) + **W2-H-01/H-02** (Leakage) — alle Signale/Modelle sonst wertlos.
2. **Sicherheit:** C-03/C-05/H-01 + **W2-C-01** (pickle-RCE) + **W2-C-03** (Risk-Veto).
3. **Test-Vertrauen zuerst absichern (Sprint 0b)** — sonst regredieren die Fixes.
4. **Datenverlust verhindern:** C-06/H-12 + **W2-H-06** (Boot-Migration ohne Lock/Backup).
5. **Kosten:** C-04/H-08/H-09/H-13 + LLM-Halluzinationen W2-H-03/H-04.
6. **Aufräumen:** `prisma_v3_seed/` löschen, Workflows reparieren, Modelle aus Git.

---
---

# NACHTRAG — WELLE 3 (Tiefen-Deep-Dives)

Vier fokussierte Deep-Dives: **jede der 49 Alembic-Migrationen zeilenweise**, die **CH-Steuer-/Rebalancing-/Fonds-/
Portfolio-Fachlogik**, die **Domain-Scorer/Quant-Mathematik** und die **restlichen, bisher nicht tief geprüften
Services**. IDs mit Präfix `W3-`.

## 🔴 CRITICAL (Welle 3)

### W3-C-01 — Migration 0021 `downgrade()` crasht (doppeltes `drop_column`)
**Ort:** `backend/alembic/versions/0021_add_ml_feature_columns.py:41`
**Problem:** `upgrade()` fügt `return_1m` einmal hinzu (`:27`), `downgrade()` droppt es **zweimal** (`:33` und `:41`).
**Failure-Szenario:** `alembic downgrade` auf/unter 0021 bricht beim zweiten Drop mit `column "return_1m" does not exist` ab → die gesamte Downgrade-Kette ist unpassierbar (Rollback unmöglich).
**Fix:** Zeile 41 entfernen.

### W3-C-02 — Fonds-Vergleich liefert konstant Null-Metriken fürs Eigen-Portfolio (doppelt gebrochen)
**Ort:** `backend/interfaces/rest/routers/fonds_vergleich.py:24-25` + `backend/application/services/fonds_vergleich_service.py:102-108, :122`
**Problem:** Der Router instanziiert `FondsVergleichService()` **ohne** yfinance-Adapter → Guard `if … self._yf is None: return PortfolioCompareMetrics(0,0,None,0)`. Selbst mit Adapter ruft der Service `get_price_history(ticker, years=…)` auf, während die Signatur `get_price_history(ticker, days=252)` ist → `TypeError`, vom breiten `except` verschluckt → wieder Null.
**Failure-Szenario:** Portfolio [NESN 50 %, ROG 50 %] vs. „VIAC Global 100": Fonds = 9.5 %/Sharpe 0.55, Eigen-Portfolio = **0 % Rendite / 0 Vola / Sharpe null / 0 Drawdown**. Nutzer schließt, sein Portfolio sei wertlos/risikolos.
**Fix:** Adapter injizieren **und** `days=lookback_years*252` verwenden.

### W3-C-03 — `mean_variance` (Markowitz) läuft in der Praxis nie — fällt immer auf Risk-Parity zurück
**Ort:** `backend/application/agents/portfolio_agent.py:26, :107, :282`
**Problem:** `_fetch_histories` lädt nur `_PRICE_DAYS = 40` Kalendertage (≈ 27 Handelstage); `_mean_variance` verlangt `len(returns) >= 30` Handelstage → immer `return _risk_parity(...)`. Das Ergebnis wird trotzdem als `method="mean_variance"` etikettiert.
**Failure-Szenario:** API-Konsument wählt bewusst Markowitz/Sharpe-Maximierung (in der Doku beworben), bekommt aber immer inverse-Vol Risk-Parity unter falschem Label.
**Fix:** Für `mean_variance`/`risk_parity` ≥ 250 Handelstage laden; `_PRICE_DAYS` an die Methode koppeln.

### W3-C-04 — Falsche Schweizer Steuerformulare (DA-1 / Formular 103 vertauscht)
**Ort:** `backend/application/agents/steuer_agent.py:139-140` + `backend/infrastructure/llm/prompts/steuer_system.de.md.j2:15`
**Problem:** Für **CH-Aktien** empfiehlt der Code „DA-1 für Rückerstattung" und „VST-Rückerstattung via Formular 103". Fachlich falsch: **DA-1** gilt nur für pauschale Anrechnung **ausländischer** Quellensteuern; **Formular 103** ist die VST-Deklaration der **ausschüttenden Gesellschaft**, nicht das Rückforderungsmittel des Privatanlegers (der fordert über das **Wertschriftenverzeichnis** der Steuererklärung zurück). Der System-Prompt wiederholt den Fehler → auch der LLM-Pfad ist vergiftet.
**Failure-Szenario:** Privatperson mit NESN-Dividende wird zu Formular 103 angewiesen (füllt sie nie aus); die reale VST-Rückforderung (35 %) unterbleibt → Geld verloren.
**Fix:** CH-Titel → „VST-Rückforderung über das Wertschriftenverzeichnis"; DA-1 nur für ausländische Titel.

### W3-C-05 — Diversification-Score kippt Vorzeichen bei negativer Korrelation → beste Diversifizierer am schlechtesten gerankt
**Ort:** `backend/domain/models/diversification.py:101-106`
**Problem:** `denom = volatility + avg_corr` mit vorzeichenbehaftetem `avg_corr ∈ [-1,1]`; nur `denom == 0.0` wird maskiert, ein **negativer** Nenner nicht. `raw_scores = 2.0/denom`.
**Failure-Szenario:** Ticker A mit `avg_corr = -0.5`, Vola 0.317 → `denom = -0.183` → Score **-10.9**; Ticker C mit `+0.3` → Score **+3.24**. Der beste Diversifizierer (negativ korreliert) landet **hinter** dem schlechteren. Zusätzlich Singularität nahe `avg_corr ≈ -volatility` (Score → ±∞).
**Fix:** Score monoton fallend in Vola **und** Korrelation formulieren (z. B. `1/(1+vol)·(1-corr)`), Nenner-Vorzeichen absichern.

## 🟠 HIGH (Welle 3)

### W3-H-01 — 0029: `TRUNCATE` zerstört Daten, `NOT NULL` wird aber nie gesetzt; `CASCADE` löscht Kosten-/Audit-Log
**Ort:** `backend/alembic/versions/0029_auth_users.py:32-34, :60-66`
**Problem:** Kommentar sagt „wipe before adding NOT NULL", aber `user_id` bleibt `nullable=True` und wird nie auf NOT NULL migriert → das destruktive `TRUNCATE ×8 CASCADE` ist **umsonst**, Ownership nie erzwungen. Zusätzlich `ondelete="CASCADE"` auf `llm_call_log`/`decision_audit_log` → User-Löschung vernichtet Kosten-/Audit-Historie.
**Fix:** Backfill + `SET NOT NULL` oder TRUNCATE weglassen; für Audit-Tabellen `SET NULL`/`RESTRICT`.

### W3-H-02 — 0011: `backtest_results.model_run_id` ohne Foreign Key
**Ort:** `backend/alembic/versions/0011_create_backtest_results.py:24`
**Problem:** Reines `UUID` mit Index, aber **kein** FK auf `ranking_runs.id` (anders als `research_memos`/`memo_batch_jobs`). Erlaubt Waisen-Backtests; referenzielle Integrität nicht durchgesetzt.
**Fix:** FK mit passendem `ondelete` ergänzen.

### W3-H-03 — Systemisch: Geld/Preise als `Float` statt `Numeric`
**Ort:** u. a. `0031:32-35`, `0033:30-33`, `0032:32-43`, `0034:31,34`, `0024:26`, `0018:27,39`
**Problem:** OHLC-Preise, `eps_chf`/`market_cap_chf`/`pe_ratio`, `price_at_signal/eval` als `Float` (double). `0003` folgt bewusst der Geld-Regel (`Numeric(10,6)`) — alle Preistabellen brechen sie → Rundungsfehler in Preisen, Kennzahlen und Backtest-Renditen.
**Fix:** `Numeric(precision, scale)` für alle monetären Spalten.

### W3-H-04 — Fonds- vs. Custom-Sharpe/-Return sind methodisch nicht vergleichbar
**Ort:** `backend/application/services/fonds_vergleich_service.py:149-153` vs. `backend/infrastructure/seeds/viac_fonds_catalog.py:1-5`
**Problem:** Fonds-Kennzahlen = statische **5-Jahres**-Factsheet-Werte (Stand 2024, unbekannter Risk-free); Custom = **3-Jahre**, arithmetische Annualisierung, **aktueller** SNB-Risk-free. Zeiträume, Risk-free und Return-Definition unterscheiden sich → die nebeneinandergestellten Sharpe-Werte sind nicht kommensurabel.
**Fix:** Gleicher Zeitraum, gleicher Risk-free, gleiche Methodik für beide Seiten.

### W3-H-05 — Custom-Rendite via arithmetisches Mittel ×252 überschätzt (Volatility Drag)
**Ort:** `backend/application/services/fonds_vergleich_service.py:150`
**Problem:** `ann_return = mean(daily)*252` liegt systematisch über der geometrischen CAGR (Differenz ≈ ½σ²); Fonds-Werte sind geometrisch → struktureller Vorteil fürs Custom-Portfolio.
**Failure-Szenario:** σ≈30 % → ~4.5 Pp Überschätzung; reales 5 %-CAGR-Portfolio erscheint als „~9.5 %" und schlägt scheinbar den Fonds.
**Fix:** Geometrische Annualisierung `prod(1+r)^(252/n)-1` für die angezeigte Rendite.

### W3-H-06 — Portfolio-`MAX_WEIGHT` (0.40) wird bei ≤2 Positionen still verletzt
**Ort:** `backend/application/agents/portfolio_agent.py:25, :34-54`
**Problem:** Für n≤2 ist Summe=1.0 **und** ≤0.40 unlösbar; die Clamp-Schleife endet bei **[0.5, 0.5]** — Summe 1.0, aber jede Position 0.50 > MAX 0.40, ohne Warnung. Klumpenrisiko-Schutz wirkungslos.
**Fix:** Infeasible-Fall (`n*MAX < 1`) erkennen, MAX dynamisch lockern und im Ergebnis vermerken.

### W3-H-07 — CryptoScorer crasht bei kurzer Historie (`int(NaN)`)
**Ort:** `backend/domain/services/crypto_scorer.py:95-97`
**Problem:** `rolling(30).std()` → NaN bei < 31 Kerzen; `int(vol_30d // 20)` mit `vol_30d = NaN` wirft `ValueError: cannot convert float NaN to integer` → gesamter `score()` crasht für neue Coins.
**Fix:** NaN-Check vor `int()`, neutraler Fallback.

### W3-H-08 — `start_batch` crasht bei Runs mit unrankten Tickern (`int(None)`)
**Ort:** `backend/application/services/narrative_service.py:221`
**Problem:** `sorted(results, key=lambda r: int(r["total_rank"]))` — `total_rank` kann `None` sein (persistiert in `ranking_run_service.py:148`). `_build_universe_context` filtert `None` korrekt, `start_batch` nicht → jeder `POST …/batch` für ein Universe mit ≥1 datenlosen Ticker liefert HTTP 500.
**Fix:** Vor dem Sort `None` filtern.

### W3-H-09 — News-Ingestion persistiert Artikel VOR dem Embedding → dauerhaft ohne RAG-Index
**Ort:** `backend/application/services/news_ingestion_service.py:125-153, :207-228`
**Problem:** `save_article()` läuft **vor** `llm.embed()`. Bei transientem Voyage-Fehler bleibt der Artikel gespeichert, aber ohne Chunks/Embeddings; beim nächsten Lauf greift URL-Hash-Dedup → er wird nie mehr embedded → dauerhaft unsichtbar für News-RAG.
**Fix:** Erst embedden, dann Artikel+Chunks in einer Transaktion; bei Fehler löschen/als „needs_embedding" markieren.

### W3-H-10 — `CryptoAgentService.stream_analysis` umgeht Budget-Cap und Cost-Logging
**Ort:** `backend/application/services/crypto_agent_service.py:82-103`
**Problem:** Streaming-Pfad nutzt `self._llm.raw_client.messages.stream(...)` direkt — kein `check_cap()`, kein `record()` (anders als `analyze_brief`). Zweiter, unabhängiger Budget-Bypass neben `chat_service` (C-04).
**Fix:** Streaming-Kostenpfad über den `LLMClient` führen (Vorab-Check + Usage-Record am Stream-Ende).

## 🟡 MEDIUM (Welle 3)

**Alembic:**
- **W3-M-01** — 0021: 9 Feature-Spalten `nullable=True` ohne Backfill → bestehende `ml_features`-Zeilen `NULL`; „19-Feature"-Trainer ohne Imputing scheitert über historische Snapshots.
- **W3-M-02** — 0014/0023: `news_chunks.embedding` bekommt **nie** einen HNSW/IVFFlat-Index (anders als `embedding_chunks`/`swiss_rag_chunks`) → News-RAG-Similarity macht Full-Scan.
- **W3-M-03** — 0042: `downgrade` verengt `news_documents.source` VARCHAR(20)→(10) ungeguardet → schlägt fehl/trunkiert bei `CRYPTOPANIC`-Zeilen.
- **W3-M-04** — Uneinheitliche PK-Typen `String(36)` (0027/0028/0031–0036) vs. `postgresql.UUID` (Rest) → keine DB-UUID-Validierung, Typ-inkonsistente Joins.
- **W3-M-05** — 0037 zweigt von 0022 ab → zwei parallele Heads bis Merge 0049; Interleaving-Reihenfolge nicht deterministisch (aktuell unkritisch, künftige develop-Migration auf main-Tabelle bräche nichtdeterministisch).
- **W3-M-06** — 0044 erzeugt konzeptionelles Duplikat/irreführende Doku zu 0034 (`signal_outcomes` vs. `crypto_signal_outcomes`).

**Steuer/Rebalancing/Portfolio:**
- **W3-M-07** — Monte-Carlo-3a nutzt **1-Jahres-Trailing-Return als 40-Jahres-Drift** (`monte_carlo_service.py:131, :206-207`) → absurd optimistische Vorsorge-Endwerte.
- **W3-M-08** — GBM wendet die `-½σ²`-Itô-Korrektur **doppelt** an (`mu` bereits aus Log-Returns) (`monte_carlo_service.py:206-207`) → systematische Drift-Unterschätzung ~½σ².
- **W3-M-09** — Rebalancing ignoriert eidg. **Umsatzabgabe** (0.075 %/0.15 % nach Domizil) und Ganzzahligkeit/Mindestgebühren (`rebalancing_service.py:107-108`) → zu niedrige Kosten, unwirtschaftliche Mini-Trades vorgeschlagen.
- **W3-M-10** — VST (35 %) wird als Belastung dargestellt, ohne klarzustellen, dass sie für CH-Ansässige **voll rückforderbar** ist (effektiv 0) (`steuer_agent.py:132-143`); verstärkt W3-C-04.

**Scorer:**
- **W3-M-11** — CryptoScorer: fehlende SMI-Korrelation (Default 0.0) ergibt **maximalen** Diversifikationsbonus (+5) statt neutral (`crypto_scorer.py:31, :100-102`) → Score-Inflation, kann HOLD→BUY kippen.
- **W3-M-12** — QualityClassic mittelt nur **verfügbare** Z-Scores (`quality_classic.py:83-85`) → Ticker, denen die „schlechten" Kennzahlen fehlen, ranken künstlich besser (fehlende Daten = Bonus).
- **W3-M-13** — QualityClassic: Solo-Kennzahl (`len<2`) → `z=0.0` fließt in den Ticker-Mittelwert ein und zieht starke Profile Richtung 0 (`quality_classic.py:62-66`).
- **W3-M-14** — Diversification addiert dimensional inkonsistent (annualisierte Vola ~0.2–0.6 + rohe Korrelation ∈[-1,1]) ohne Normierung (`diversification.py:101-102`).

**Services:**
- **W3-M-15** — `ProfileClassifier.calculate_confidence` verwechselt „Default gewählt" mit „nicht beantwortet" (`profile_classifier.py:124-148`) → vollständig beantwortete Default-Profile bekommen confidence≈0 → Discovery wird nie freigeschaltet / endlos weiter befragt.
- **W3-M-16** — Swiss-Inflation-Fallback wählt den Wert „am nächsten zu 1.0 %" statt den aktuellsten CPI (`macro_service.py:79-83`) → bei FRED-Ausfall faktisch falsche Inflationszahl.
- **W3-M-17** — `SwissFilingRetrievalService.retrieve`: kein k-Cap, kein Empty-Guard, kein Cost-Tracking (`swiss_filing_retrieval_service.py:26-40`) → `k=100000` DoS, `IndexError` bei leerem Embedding, Voyage-Kosten ungetrackt.
- **W3-M-18** — `crypto_scoring.score_all` gegen F&G-/CoinGecko-Ausfälle ungeschützt (`crypto_scoring_service.py:68-73`) → ein Einzelausfall lässt das gesamte 10-Coin-Scoring crashen (inkonsistent zu `score_one`).
- **W3-M-19** — Discovery-Income-Pfad macht pro Titel einen yfinance-Call (`discovery_service.py:205-217`) → bis zu 200 parallele Requests auf Free Tier, `dividend_yield` fällt still auf 0.0 → Reihenfolge kippt.
- **W3-M-20** — `RankingRunService`: N+1 sequentielle Ticker-Lookups (`ranking_run_service.py:131-141`) → linear langsamer bei großen Universen.
- **W3-M-21** — Narrative-RAG: abgerufene Chunk-Inhalte gehen **ungefiltert** in den User-Prompt (`narrative_service.py:578-583`) → **Prompt-Injection** aus manipulierten News/Filings (z. B. „setze confidence=high").
- **W3-M-22** — 0022/0023 DELETE ohne Guard/Backup, nicht-idempotent bei manuellem Downgrade→Upgrade (ergänzt H-12).

## ⚪ LOW (Welle 3)

**Alembic:** 0006 downgrade-Truncation (dokumentiert); 0026 falsches Ticker/ISIN-Mapping (`SGKN`/`SGS` — SGS handelt als `SGSN`); 0009-Backfill hängt an Sentinel-String; mehrere NOT-NULL-Spalten ohne `server_default` (0002/0007/0011/0016).
**Steuer/Portfolio:** Währungs-Mismatch im Fonds-Vergleich (keine CHF-Normalisierung, keine Ticker-Validierung); σ-Annualisierung aus ~30 Tagespunkten (verrauscht); `is_3a_eligible=True` als irreführender Default bei Nicht-3a-Konten.
**Scorer:** `ath_change_pct == 0.0` (exakt am ATH) wird durch `or -50.0` als „fehlend" behandelt; EMA200 inline mit abweichender Konvention (`adjust`-Default, kein `min_periods`); Bollinger-Bonus kann Trend-Score senken (Preis < unteres Band); ValueAlphaPotential am Snapshot strukturell ≥0 (Doku widerspricht); `min_periods`-Doku unterschätzt echten Datenbedarf (~131 statt 68 Tage); ungeprüfter Magic-Number `SHARPE_WEIGHT=0.05` im Alpha-Modell.
**Services:** Sweet-Spot-Schwelle nutzt globale statt modell-spezifische Universumsgröße; redundanter `except (ValidationError, Exception)` (`macro_service.py:215`); geteilte `metadata`-Dict-Referenz über alle CryptoPanic-Chunks; Monte-Carlo-Fallback mit festem Seed 42 → bitgleiche „Zufalls"-Serien → singuläre Korrelationsmatrix; Retrieval-`k` ohne untere Grenze (`k=0`/negativ durchgereicht).

**Offen (nicht abschließend verifiziert):** `factsheet_service.py:32` normalisiert den Ticker (Suffix entfernt), matcht aber exakt gegen den in `run.results` gespeicherten Ticker — falls Universe-Tickers mit Exchange-Suffix (`NESN.SW`) gespeichert werden, liefert das Factsheet dauerhaft `snapshot=None`. Erfordert Prüfung der konkreten Seed-Tickerformate.

---

# NACHTRAG zu TEIL 2 — LÖSUNGSWEGE WELLE 3

## Sprint 2c — Fach-/Quant-Korrektheit (W3-C-02..C-05, W3-H-04..H-07, W3-M-07..M-14)
1. **Fonds-Vergleich reparieren:** Adapter injizieren, `days`-Signatur korrigieren, **beide** Seiten mit gleicher Methodik/Zeitraum/Risk-free und **geometrischer** Annualisierung; Preise nach CHF normalisieren. (W3-C-02, W3-H-04/H-05)
2. **Markowitz echt laufen lassen:** genügend Historie (≥250 Handelstage) laden oder Methode ehrlich labeln. (W3-C-03)
3. **Diversification-Score neu formulieren** (monoton fallend in Vola & Korrelation, Vorzeichen abgesichert, dimensional normiert). (W3-C-05, W3-M-14)
4. **Monte-Carlo:** langfristige gedämpfte Kapitalmarkterwartung statt 1y-Trailing; `-½σ²` nur einmal anwenden. (W3-M-07, W3-M-08)
5. **Scorer härten:** NaN-/Missing-Daten neutral behandeln (CryptoScorer NaN-Crash, SMI-Default, QualityClassic-Coverage). (W3-H-07, W3-M-11..M-13)
6. **CH-Steuerwissen korrigieren:** DA-1/Formular-103-Fehler in Code **und** Prompt beheben; VST-Rückforderbarkeit klarstellen; Umsatzabgabe + Ganzzahligkeit im Rebalancing. (W3-C-04, W3-M-09, W3-M-10)

## Sprint 3c — Migrationen sauber & sicher (W3-C-01, W3-H-01..H-03, W3-M-01..M-06, Low)
1. **0021-Downgrade-Crash sofort fixen** (Zeile 41 löschen) — sonst ist die Kette nicht rückrollbar. (W3-C-01)
2. **0029 nachziehen:** entweder Ownership wirklich erzwingen (Backfill + NOT NULL) oder das umsonstige TRUNCATE entfernen; Audit-Tabellen auf `SET NULL`/`RESTRICT`. (W3-H-01)
3. **Referenzielle Integrität:** FK für `backtest_results.model_run_id`. (W3-H-02)
4. **Geld → `Numeric`** in allen Preistabellen (neue Migration mit `ALTER COLUMN … TYPE numeric`). (W3-H-03)
5. **News-RAG-Index** (HNSW auf `news_chunks.embedding`), PK-Typen vereinheitlichen, 0042-Downgrade guarden. (W3-M-02..M-04)

## Sprint 3d — Service-Robustheit (W3-H-08..H-10, W3-M-15..M-22)
- Crash-Guards (`int(None)`/`int(NaN)`), Budget-Pfad für `CryptoAgentService`-Stream, Embed-vor-Persist bei News, k-Caps/Empty-Guards/Cost-Tracking in allen RAG-Services, RAG-Kontext als untrusted markieren (Prompt-Injection), N+1 → Bulk-Lookup, ProfileClassifier auf Completeness umstellen, Inflations-Fallback deterministisch.

---
---

# ABSCHLUSS — KONSOLIDIERTER MASSNAHMENPLAN

## Gesamtbild nach 3 Wellen

Das Audit umfasst **~146 verifizierte Befunde** über **alle** Subsysteme. Die Architektur bleibt solide; die Probleme
sind konkrete Fehl-Verdrahtungen, fehlende Guards und — der rote Faden — **Features, die real etwas anderes (oder
nichts) tun, als sie vorgeben**: Signale aus Zufallszahlen, Backtests mit inflationierter Performance, ein Champion-
Modell schlechter als Zufall, ein Fonds-Vergleich der 0 % ausweist, „Markowitz" das nie läuft, ein Risk-Veto ohne
Wirkung, ein Daten-Steward der nichts tut, LLM-Agenten die Zahlen erfinden. Für eine **Finanzplattform** ist dieses
Muster das eigentliche Kernrisiko — mehr noch als jede einzelne Sicherheitslücke.

## Die 5 Leitplanken (Prinzipien für alle Fixes)

1. **Nie erfundene Zahlen ausliefern.** Fehlen echte Daten → `503`/„nicht verfügbar", niemals Stub/Zufall/Halluzination.
2. **Invarianten in Code erzwingen, nicht im Prompt** (Risk-Veto, Safety-Regeln, Steuerlogik).
3. **Ein einziger erzwungener Kostenpfad** — kein direkter `raw_client`-Zugriff, der den Cap umgeht.
4. **Kein automatischer Datenverlust** — destruktive Migrationen aus dem Boot-Pfad, mit Backup + Lock.
5. **Tests gegen den echten Pfad** — kein Wegmocken des getesteten Verhaltens; sonst regrediert jeder Fix.

## Priorisierte Roadmap (Reihenfolge)

| Prio | Sprint | Inhalt | Kern-IDs |
|------|--------|--------|----------|
| **0** | Test-Vertrauen (0b) | Tests gegen ungemockte Pfade, bevor irgendetwas gefixt wird | W2-C-04, W2-H-11 |
| **1** | Daten-Integrität | Echte Preise/FX; ML-Quality-Gate + Leakage; Diversification-Score; Fonds-Vergleich; Markowitz | C-01, C-02, W2-C-02, W2-H-01/02, W3-C-02/03/05 |
| **2** | Sicherheit & Zugriff | Alerts-Owner+SSRF; Admin-Key aus Bundle; pickle-RCE; Risk-Veto; Token-Cookie | C-03, C-05, H-01, W2-C-01, W2-C-03, C-07 |
| **3** | Datenverlust verhindern | Boot-Migration entkoppeln + Backup/Lock; 0021-Downgrade; 0029; FK; Geld→Numeric | C-06, H-12, W2-H-06, W3-C-01, W3-H-01/02/03 |
| **4** | Kostenkontrolle | Reservierungs-Cap (TOCTOU); Chat- & Crypto-Stream-Bypass; Schätzung; `tool_api_key` | C-04, H-08/09/13, W2-H-03/04, W3-H-10 |
| **5** | Fach-/Quant-Korrektheit | Steuerformulare; Rebalancing-Kosten; Monte-Carlo; Annualisierung; Scorer-NaN | W3-C-04, W3-H-04/05/07, W3-M-07..M-13 |
| **6** | Robustheit & Aufräumen | Crash-Guards, RAG-Härtung, N+1, `prisma_v3_seed/` löschen, Modelle aus Git, Workflows | diverse W2/W3 |

## Sofort-Hotfixes (< 1 Tag, hoher Impact / geringes Risiko)

- `W3-C-01` — Zeile `0021:41` löschen (Downgrade-Kette entsperren).
- `L-01`/`W2-C-02` — Quality-Gate-Zeile in den Trainings-Scripts (schlechtes Modell nicht mehr aktivieren).
- `C-03` — `NEXT_PUBLIC_API_KEY` entfernen; `MissingApiKeyBanner` löschen.
- `H-11` — `JWT_SECRET` in die zwei Worker-Workflows eintragen (Boot-Crash beheben).
- `W2-H-05` — Data-Steward-Cron deaktivieren, bis er echt implementiert ist (kein falsches Grün).
- `W3-C-02` — yfinance-Adapter in `fonds_vergleich`-Router injizieren + `days`-Signatur.

---

*Ende des Audits. Erstellt über 3 Wellen mit 13 spezialisierten Audit-Agenten + manueller Kern-Sicherheitsprüfung.
Alle Befunde am Code verifiziert; kein Code wurde im Rahmen des Audits verändert.*
