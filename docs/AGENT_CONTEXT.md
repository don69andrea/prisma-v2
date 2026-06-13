# PRISMA V2 — Agent Context & Improvement Roadmap

> **Zweck dieses Dokuments:** Persistenter Kontext für alle zukünftigen Agent-Sessions.
> Enthält die vollständige Analyse vom 13. Juni 2026, alle gefundenen Schwachstellen,
> und den priorisierten Aufgabenkatalog. Vor jeder neuen Session zuerst dieses File lesen.

---

## 1. Was PRISMA V2 ist

PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer Markt
(SMI/SMIM/SPI) — entwickelt als Gruppenarbeit im Modul **Business Intelligence** an der
FHNW Hochschule für Wirtschaft (FS 2026) von Andrea Petretta, Helin und Aurelius.

**Das ist kein Capstone-Projekt. Das ist Business Intelligence.**

Technische Basis stammt aus PRISMA V1 (Einzelarbeit). V2 baut darauf auf und erweitert
es um den BI-Layer.

---

## 2. Was der Dozent bewertet (Prof. Dr. Manuel Renold)

Vier Hauptkriterien, die im System **sichtbar und demo-fähig** sein müssen:

| # | Kriterium | Unsere Umsetzung |
|---|---|---|
| 1 | **Agentic AI** | Discovery Agent (5 Turns), Portfolio Agent, Macro Agent, Steuer Agent |
| 2 | **ML-Based Intelligence** | LightGBM/XGBoost Return Predictor, 3 Klassen, Walk-Forward, SHAP |
| 3 | **RAG-Based Knowledge** | pgvector + Voyage AI, SIX Filings, Swiss News, SEC Filings |
| 4 | **Decision Intelligence Dashboard** | BUY/HOLD/WATCH mit Audit Trail, Quant 45% + ML 35% + Makro 20% |

---

## 3. Tech-Stack (vollständig)

| Kategorie | Technologie |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic |
| Datenbank | PostgreSQL 16 · pgvector · Redis (für PDF-Report-Cache) |
| AI / LLM | Claude API (Sonnet 4.6 / Haiku 4.5) · Voyage AI Embeddings |
| ML | LightGBM · XGBoost · scikit-learn · SHAP |
| Frontend | Next.js 14 (App Router) · TypeScript · Tailwind CSS · React Query |
| Datenquellen | yfinance (.SW-Ticker) · SimFin · SIX Exchange · SNB API · RSS-Feeds |
| DevOps | GitHub Actions · Render (autoDeploy) · Docker Compose |
| Tests | pytest (704 Unit-Tests) · Playwright (E2E) · Vitest |

---

## 4. Datenbankschema (21 Migrationen, 15 Modelle)

| Tabelle | Beschreibung |
|---|---|
| `stocks` | Aktien-Stammdaten inkl. ISIN, SIX-Ticker, CH-spezifische Felder |
| `universes` | SMI/SMIM/SPI/custom Aktien-Universen |
| `ranking_runs` | Scoring-Durchläufe mit Status und Ergebnissen |
| `research_memos` | LLM-generierte Research-Memos (DE/EN) |
| `memo_batch_jobs` | Async-Batch-Jobs mit Fortschrittsverfolgung |
| `backtest_results` | Historische Backtest-Ergebnisse vs. SMI |
| `alerts` | Ticker-Alerts mit Trigger, Schwellenwert, Kanal |
| `investor_profiles` | Investorprofil-Sessions (Anlagehorizont, ESG, Einkommen) |
| `decision_audit_log` | BUY/HOLD/WATCH-Verlauf mit Begründungen und Timestamps |
| `llm_call_log` | Kosten-Tracking aller LLM-Aufrufe |
| `ml_features` | Gecachte ML-Features (19 Features pro Ticker) |
| `embedding_chunks` | pgvector für RAG (SEC-Filings) |
| `swiss_filing_chunks` | pgvector für SIX-Jahresberichte |
| `news_articles` + `news_chunks` | Nachrichtenartikel + Chunks für semantische Suche |

---

## 5. UI-Seiten (15 Routen)

| Route | Beschreibung | Status |
|---|---|---|
| `/start` | Einstiegsseite / Onboarding | ✅ |
| `/discover` | Investor-Profiling: 5-Schritt konversationeller Flow | ⚠️ Bug (siehe §7) |
| `/dashboard` | Overview: Runs-Tabelle, Stats-Cards, Makro-Widget | ✅ |
| `/universes` | Universum-Verwaltung (SMI/SMIM/SPI/custom) | ✅ |
| `/rankings` | Ranking-Ergebnisse pro Run mit Filterung | ✅ |
| `/stocks` | Aktien-Liste mit Filter und Suche | ✅ |
| `/news` | Nachrichtenartikel mit semantischer RAG-Suche | ✅ |
| `/research` | Research-Memos Generierung und Ansicht | ⚠️ Bug (Memo-Button) |
| `/backtest` | Backtest vs. SMI-Benchmark | ✅ |
| `/fonds` | VIAC-Fonds vs. Custom-Portfolio-Vergleich | ✅ |
| `/decision` | BUY/HOLD/WATCH-Signale mit LLM-Erklärung | ✅ |
| `/alerts` | Alert-Verwaltung | ⚠️ Webhook nicht implementiert |
| `/portfolio` | Portfolio-Allokation (3 Methoden) | ✅ |
| `/portfolio/simulator` | Monte Carlo Simulator | ❌ LEER |
| `/steuer` | Schweizer Steuereinschätzung via RAG-Agent | ✅ |

---

## 6. API-Endpunkte (24 Router-Module)

`health`, `chat` (SSE-Streaming), `reports` (PDF), `discovery`, `stocks`,
`eligibility`, `dividends`, `fundamentals`, `universes`, `admin`, `runs`,
`backtests`, `rag` (SEC + Swiss), `steuer`, `news`, `ml`, `decisions`,
`decision_audit`, `macro`, `portfolio` (allocate + monte-carlo + rebalance),
`fonds_vergleich`, `alerts`, `memos`

---

## 7. KRITISCHE BUGS (muss vor Demo behoben sein)

### BUG-1 (KRITISCH): Portfolio Simulator Page ist leer
- **Datei:** `frontend/src/app/portfolio/simulator/page.tsx` (oder Pfad prüfen)
- **Problem:** Route existiert, aber Page-Komponente ist leer / not implemented
- **Was fehlen muss:** Monte Carlo Simulator UI (Geometric Brownian Motion, 1-40 Jahre,
  10k Simulationen) mit Konfidenzintervall-Chart und Ergebnisinterpretation als Text
- **Backend:** Endpunkt `POST /api/v1/portfolio/monte-carlo` ist vorhanden ✅
- **Priorität:** Hoch — Demo-Kernpunkt

### BUG-2 (KRITISCH): Discovery Engine ruft Legacy-Endpoints auf
- **Datei:** `frontend/src/app/discover/` (Turn-by-Turn-Calls prüfen)
- **Problem:** Frontend ruft alte Endpunkte auf statt der neuen Turn-by-Turn-API
- **Symptom:** Discovery Flow läuft nicht korrekt durch
- **Fix:** Frontend auf neue API umstellen; Backend-Endpunkt-Mapping prüfen
- **Quelle:** `docs/OPEN_ITEMS.md`

### BUG-3 (HOCH): Memo-Button für Nutzer ohne model_run_id permanent disabled
- **Datei:** Research-Seite, Button-Logik
- **Problem:** Button ist disabled wenn kein `model_run_id` vorhanden — aber
  für Discovery-Nutzer die keinen Ranking Run gemacht haben, ist er immer disabled
- **Fix:** Fallback-Logik für Nutzer ohne Run, oder Run automatisch triggern

### BUG-4 (HOCH): /stocks/{ticker}/prices ist ein Stub
- **Datei:** `backend/interfaces/api/v1/stocks.py` (oder ähnlich)
- **Problem:** Endpunkt gibt Dummy-Daten zurück, keine echten Kurszeitreihen
- **Fix:** yfinance-Integration für Preisverlauf einbauen
- **Impact:** Aktien-Detailseite zeigt keine echten Charts

### BUG-5 (MITTEL): Webhook-Delivery für Alerts nicht implementiert
- **Datei:** Alerts-Backend-Service
- **Problem:** `kanal`-Feld "Webhook" vorhanden, aber Versandlogik fehlt
- **Fix:** HTTP-POST bei Alert-Trigger implementieren

### BUG-6 (MITTEL): LLMRateLimiterMiddleware doppelt registriert
- **Datei:** `backend/app.py`
- **Problem:** Middleware wird zweimal in `app.py` registriert (im Code als Bug kommentiert)
- **Fix:** Duplikat entfernen

---

## 8. FEATURE-ANALYSE: Was funktioniert, was muss besser werden

### 8.1 Quant Scoring Engine (5 Modelle) — STATUS: GUT

**Was existiert:** Alpha, Diversification, Quality Classic, Trend Momentum,
Value Alpha Potential — alle mit Z-Score-Normierung.

**Problem:** Score-Zusammensetzung ist im UI nicht sichtbar. Nutzer sieht eine
Zahl, versteht nicht warum.

**Verbesserung:**
- Score-Breakdown-Karte im Decision-Dashboard: "Quant Score 8.2: Alpha +2.1σ,
  Momentum +1.8σ, Quality +0.9σ, Value -0.3σ, Diversification +1.1σ"
- Tooltip-Erklärungen pro Score direkt in der UI
- Sensitivitätsanalyse: "Was passiert wenn ich Quant-Gewicht auf 60% stelle?"

---

### 8.2 ML-Modell (LightGBM/XGBoost) — STATUS: GUT, UI-seitig unvollständig

**Was existiert:** 19-Feature-Klassifikator, 61.4% Top-Quartil-Recall,
SHAP-Werte, Walk-Forward-Validation, `POST /api/v1/ml/predict`

**Problem:** SHAP ist backend-seitig vorhanden, aber UI-seitig nicht prominent
sichtbar. 61.4% Recall muss kontextualisiert werden (Baseline = 25% Random).

**Verbesserung:**
- SHAP-Waterfall-Chart direkt im Signal-Detail (nicht nur separater Endpunkt)
- Feature-Importance-Visualisierung auf der ML-Seite
- Erklärtext: "Das Modell ist 2.5× besser als Zufall (61.4% vs. 25% Baseline)"
- ML-Konfidenz pro Signal als Badge: "ML: OUTPERFORM (p=0.72)"

---

### 8.3 Claude API / AI-Features — STATUS: SEHR GUT

**Was existiert:**
- Research-Memos (Sonnet 4.6, Tool-Use, Jinja2-Templates DE/EN, Batch)
- Signal-Erklärung (Haiku 4.5)
- Portfolio Intelligence Agent (Rebalancing-Pläne)
- Discovery/Profiling (Haiku, 5-Schritt konversationell)
- Steuer-Agent (RAG, Verrechnungs-/Einkommens-/Vermögenssteuer)
- Universe-Suggestion
- Chat-Assistent (SSE-Streaming, 6 Tools: search, filter, factsheet, macro,
  compare, ranking)

**Problem:** Die 6 Chat-Tools sind mächtig, aber im Chat-Interface nicht
kommuniziert. Nutzer weiss nicht was der Chat kann.

**Verbesserung:**
- Tooltip/Hinweis im Chat: "Ich kann Aktien suchen, vergleichen, Factsheets
  laden, Makrokontext geben und Rankings anzeigen"
- Budget-Anzeige im Chat: "Kosten dieser Session: ~$0.02" (didaktisch)
- Steuer-Agent Output als strukturierte Tabelle statt Fliesstext

---

### 8.4 Portfolio-Features — STATUS: GUT, aber Simulator fehlt

**Was existiert:** Allocation (Score-Weighted, Risk-Parity, Mean-Variance),
Monte Carlo (10k Simulationen, 1-40 Jahre), Rebalancing Agent.

**Problem:** Portfolio Simulator Page ist leer (BUG-1).
Monte Carlo Ergebnisse brauchen Interpretation als Text.

**Verbesserung:**
- Monte Carlo: "Mit 80% Wahrscheinlichkeit liegt dein Portfolio in 10 Jahren
  zwischen CHF X und CHF Y" als strukturierter Text
- Methodenvergleich: Pie-Charts für alle 3 Allocation-Methoden nebeneinander
- Unterschied zwischen den 3 Methoden erklären (Tooltip)

---

### 8.5 Swiss Market / VIAC / Steuer — STATUS: GUT

**Was existiert:** VIAC Fonds-Vergleich, 3a-Eligibility (BVV2 Art. 53),
Steuer-Agent, Swiss Filings RAG (SIX Jahresberichte).

**Verbesserung:**
- 3a-Eligibility mit Begründung: "Nicht eligible: Marktkapitalisierung < 100M CHF"
- Steuer-Output als Tabelle (Steuersatz %, geschätzter Betrag CHF)
- RAG-Quellenangaben mit Link zum Original-Dokument in der UI

---

### 8.6 Decision Dashboard — STATUS: GUT, aber Erklärbarkeit fehlt

**Was existiert:** BUY/HOLD/WATCH Signale, LLM-Erklärung, Audit Log.

**Problem:** Der Weg Quant-Score → ML → Makro → Signal ist nicht visuell
dargestellt. Nutzer sieht das Ergebnis, nicht den Denkweg.

**Verbesserung (DEMO-KRITISCH):**
- Strukturierte Signal-Karte: "BUY weil Quant: 8.2 (strong), ML: OUTPERFORM
  (p=0.72), Makro: neutral" — nicht nur LLM-Fliesstext
- Visuelle Signal-Formel: Balkendiagramm Quant 45% / ML 35% / Makro 20%
- SHAP-Waterfall direkt im Decision-Detail einblenden

---

### 8.7 Backtest — STATUS: BASIS OK

**Verbesserung:**
- Performance-Chart (Kumulierte Returns PRISMA vs. SMI über Zeit)
- Sharpe-Ratio und Max-Drawdown als Key-Metrics
- Multi-Backtest: "Quant only" vs. "Quant+ML" vs. "Quant+ML+Makro" vergleichen

---

### 8.8 Alerts — STATUS: UNVOLLSTÄNDIG

**Problem:** Webhook-Delivery nicht implementiert (BUG-5).

**Verbesserung:**
- Alert-Test-Button: "Sende Test-Notification jetzt"
- Alert-Verlauf: "Alert ausgelöst am 12.06.2026 um 14:32"

---

### 8.9 Discover / Investor Profiling — STATUS: MUSS BUG-2 FIXEN

**Was existiert:** 5-Schritt konversationeller Flow, Haiku-Klassifikation,
Session-State.

**Problem:** Legacy-Endpoints (BUG-2). Nach Abschluss fehlt der Übergang
zu personalisierten Empfehlungen.

**Verbesserung:**
- Nach Flow-Abschluss: Direkt zu personalisierten Empfehlungen weiterleiten
- Profil persistent anzeigen auf anderen Seiten: "Du bist: Langfrist-Investor,
  ESG-bevorzugt" als kleines Badge in der Navigation

---

### 8.10 RAG (SEC/Swiss/News) — STATUS: GUT, UI-Presentaion verbesserbar

**Problem:** RAG-Quellenangaben nicht prominent in der UI.

**Verbesserung:**
- Quellenangaben immer anzeigen: "Basierend auf Nestlé Geschäftsbericht 2024,
  Seite 12 [Link]"
- News-Seite: Hinweis "Semantische Suche via RAG" als Badge

---

## 9. OFFENE AUFGABEN (Priorisiert)

### P0 — Vor Demo zwingend

| # | Aufgabe | Datei/Bereich |
|---|---|---|
| T1 | Portfolio Simulator Page implementieren | `frontend/src/app/portfolio/simulator/` |
| T2 | Discovery Engine auf neue Turn-by-Turn-API umstellen | `frontend/src/app/discover/` |
| T3 | Signal-Breakdown-Karte ins Decision-Dashboard | `frontend/src/app/decision/` |
| T4 | SHAP-Waterfall im Signal-Detail UI | Decision-Detailansicht |
| T5 | Memo-Button Fallback-Logik (ohne model_run_id) | Research-Seite |
| T6 | Demo-Flow R2.5-1 fertigstellen | `feature/presentation` |

### P1 — Hohe Priorität

| # | Aufgabe | Datei/Bereich |
|---|---|---|
| T7 | Preiszeitreihe Stub durch echte yfinance-Daten ersetzen | `backend/interfaces/api/v1/stocks.py` |
| T8 | Monte Carlo Ergebnisinterpretation als Text | Portfolio Simulator |
| T9 | 3 Services mit Unit-Tests abdecken | factsheet, news_retrieval, ranking_run |
| T10 | E2E-Tests nach Navigation-Umbau aktualisieren | Playwright-Tests |

### P2 — Mittlere Priorität

| # | Aufgabe | Datei/Bereich |
|---|---|---|
| T11 | Webhook-Delivery für Alerts implementieren | Alerts-Backend-Service |
| T12 | Chat-Interface: Tooltip mit Tool-Übersicht | Chat-Komponente |
| T13 | RAG-Quellenangaben mit Link in UI | Alle RAG-Outputs |
| T14 | LLMRateLimiterMiddleware-Duplikat entfernen | `backend/app.py` |
| T15 | Steuer-Output als strukturierte Tabelle | Steuer-Seite |
| T16 | 3a-Eligibility mit Begründungstext | Stocks-Detail |

### P3 — Nice to have

| # | Aufgabe |
|---|---|
| T17 | Multi-Backtest-Vergleich (Quant only / +ML / +Makro) |
| T18 | Sensitivitätsanalyse für Signal-Gewichtung |
| T19 | Budget-Anzeige im Chat (Kosten dieser Session) |
| T20 | Profil-Badge in Navigation nach Discovery-Abschluss |
| T21 | Methodenvergleich: 3 Allocation-Methoden nebeneinander |

---

## 10. DOKUMENTATION BEREINIGEN (Altlasten aus V1)

Die folgenden Begriffe/Sektionen sind Überbleibsel aus PRISMA V1 und müssen
aus allen Markdown-Files entfernt werden:

**Zu entfernende Begriffe:**
- "Capstone" (nur eine Erwähnung erlaubt, als kurze technische Herkunftsnotiz)
- "Spec-First" / "Spec before Code" / "Plan-as-Contract"
- "Two-Stage Review"
- "AI-USAGE.md" (Verweise darauf)
- "Superpowers" / "docs/superpowers/"
- "Subagent-Driven Execution"
- "Brainstorming skill"

**Betroffene Files (mit grep prüfen):**
```bash
grep -ri "capstone" . --include="*.md" -l
grep -ri "spec-first\|plan-as-contract\|two-stage review\|ai-usage\|superpowers" . --include="*.md" -l
```

**README.md: Spezifische Änderungen**

1. Einleitungsabsatz ersetzen durch:
   > PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer
   > Markt (SMI/SMIM/SPI) — entwickelt im BI-Modul der FHNW (FS 2026) von Andrea
   > Petretta, Helin und Aurelius.

2. Sektion "DAS CAPSTONE-FUNDAMENT" → umbenennen zu "WAS BEREITS EXISTIERT"
   (Inhalt aus dem Kontext-Dokument in §2 dieses Files verwenden)

3. Link zu `SheylaSam/prisma-capstone` komplett löschen

4. Workflow-Abschnitt mit "Brainstorming → Spec-First → Plan-as-Contract" löschen

5. Dokumentations-Tabelle mit AI-USAGE.md/docs/specs/docs/adr/ löschen

6. Entwicklungs-Workflow ersetzen durch:
   ```
   feature/andrea-*  ──┐
   feature/helin-*   ──┼──► develop ──► main
   feature/aurelius-* ─┘
   ```

7. Ganz am Ende, nach Disclaimer, vor Footer: Einzige erlaubte Herkunftsnotiz:
   > *Technische Basis: PRISMA V1 lieferte Clean Architecture, 5 Quant-Modelle,
   > Narrative Engine und Multi-Agent-Pipeline. V2 baut darauf auf.*

**AGENTS.md:** Prüfen ob V1-spezifische Prozessregeln vorhanden; nur V2-relevante
behalten.

**CONTRIBUTING.md:** "Spec before Code", "AI-USAGE.md documentation", "Two-Stage
Review" — alle drei entfernen. Ersetzen durch: PR-Pflicht, CI-Gates, Coverage 80%.

---

## 11. CI/CD & QUALITÄT

- **Coverage-Mindestanforderung:** 80% (`fail_under=80` in pyproject.toml)
- **Linter:** ruff (Zeilenlänge 100, Python 3.12-Target)
- **Type-Checking:** mypy strict mode
- **CI-Gates auf develop:** "Backend Lint & Typecheck" + "Backend Unit Tests" müssen grün sein
- **Deployment:** Render (autoDeploy: true), Backend + Frontend

---

## 12. TEAM & BRANCHES

| Person | Branch-Prefix | Zuständigkeit |
|---|---|---|
| Andrea | `feature/andrea-*` | Datenpipeline, Signale, ML, Backend-Core |
| Helin | `feature/helin-*` | Frontend, UX, Navigation, Discovery-UI |
| Aurelius | `feature/aurelius-*` | InvestorProfile, Discovery-Agent, Macro-RAG |

Alle Feature-Branches → `develop` → `main`.
Kein direkter Push auf `develop` oder `main`.

---

## 13. DEMO-FLOW (User Journey)

```
/start → /discover → /stocks/[ticker] → /decision → /portfolio
```

**Zwei User-Typen:**
- 🧭 **Entdecker** — Discovery-Flow (5 Schritte), dann geführte Empfehlungen
- 🎯 **Kenner** — direkte Suche, sofort zu /stocks oder /decision

**Demo-Script:** `docs/DEMO-SCRIPT.md` — 10-15 Min Live-Demo

---

## 14. SIGNALFORMEL

```
Final Score = Quant 45% + ML 35% + Makro 20%

BUY  : Score ≥ 70
HOLD : Score 40–69
WATCH: Score < 40
```

---

*Dokument erstellt: 13. Juni 2026*
*Erstellt durch: Multi-Agent-Analyse (3 parallele Agents)*
*Nächste Aktualisierung: Nach Demo / Sprint-Abschluss*
