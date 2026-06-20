# CLAUDE.md

## 🚦 LIVE STATUS — WER MACHT WAS

| # | Aufgabe | Person | Branch | Status | Blockiert durch |
|---|---------|--------|--------|--------|-----------------|
| R2.3-1 | Datenpipeline: SMI seeden + XGBoost trainieren | Andrea | `feature/andrea-datenpipeline` | ✅ DONE | — |
| R2.3-2 | /decision: echte BUY/HOLD/SELL Signale | Andrea | `feature/andrea-datenpipeline` | ✅ DONE | — |
| R2.3-3 | Frontend: SignalBadge + PrismaScore + ExplainButton | Helin | `feature/helin-ux-components` | ✅ DONE | — |
| R2.3-4 | Frontend: Glassmorphism Cards + Loading-States | Helin | `feature/helin-ux-components` | ✅ DONE | — |
| R2.3-5 | Backend: InvestorProfile Model + DB Migration | Aurelius | `feature/aurelius-investorprofile` | ✅ DONE | — |
| R2.3-6 | Backend: DiscoveryService + API Endpoints | Aurelius | `feature/aurelius-investorprofile` | ✅ DONE | — |
| R2.4-1 | /start: Conversational Discovery Engine — 5 Turns | Andrea | `feature/helin-discovery-ui` | ✅ DONE | — |
| R2.4-2 | /start: Brand Logo Grid + Risk-Feeling-Test + ProfileReveal | Helin | `feature/helin-discovery-ui` | ✅ DONE | — |
| R2.4-3 | Haiku-Klassifikation + Session-State + Konfidenz-Score | Aurelius | `feature/aurelius-discovery-agent` | ✅ DONE | — |
| R2.4-4 | Navigation: 5 Bereiche umstrukturieren | Helin | `feature/helin-navigation` | ✅ DONE | — |
| R2.4-5 | AuditTrail Komponente + Profil-Reveal Animation | Helin | `feature/helin-discovery-ui` | ✅ DONE | — |
| R2.4-6 | Makro-Agent + RAG verifizieren | Aurelius | `feature/aurelius-discovery-agent` | ✅ DONE | — |
| R2.5-1 | Demo-Flow + Präsentation | Alle | `feature/presentation` | 🔄 IN PROGRESS | — |
| R2.5-2 | ML-Overhaul: 163 Ticker, 19 Features, SimFin, 61.4% Recall | Andrea | `feat/issue-r25-ml-overhaul` | ✅ DONE | — |
| R2.5-3 | SHAP Explainability + Fundamentals Widget + Cleanup | Andrea | `feat/issue-r25-ml-shap` | 🔄 IN PROGRESS | — |
| R2.5-4 | Security + Performance Audit (rate limiting, CORS, auth) | T1 | `fix/security-performance-audit` | ✅ DONE (PR #154 → main) | — |
| R2.5-5 | Global API-Key Auth für /admin-Endpoints | T1 | `feat/global-api-auth` | ✅ DONE (PR #156 → main) | — |
| R2.5-6 | Chat Tool Hints + verbesserter Placeholder | T3 | `feat/chat-tool-hints` | ✅ DONE (PR #162 → develop) | — |
| R2.5-7 | Decision: strukturiertes Signal-Breakdown-Card (Quant/ML/Makro) | T3 | `feat/decision-signal-breakdown` | ✅ DONE (PR #164 → develop) | — |
| R2.5-8 | DiscoveryService: ESG- + Income-Preference-Gap schliessen | T2 | `feat/discovery-esg-income` | ✅ DONE (PR #177 → develop) | — |
| R2.5-9 | SHAP MiniBreakdown in Decision SignalCard (Top 3 Features) | T4 | `feat/shap-in-decision` | ✅ DONE (PR #179 → develop) | — |
| R2.5-10 | Monte Carlo Textinterpretation (server-computed) | T8 | `feat/montecarlo-text-v2` | ✅ DONE (PR #180 → develop) | — |
| R2.5-11 | WeightSensitivity + AllocationComparison wiring + orphan-fix | T18+T21 | `feat/wire-sensitivity-allocation` | ✅ DONE (PR #178 → develop) | — |
| R2.5-12 | ML 19→23 Features (pe_ratio, pb_ratio, div_yield, rev_growth) | Andrea | `feat/ml-simfin-fundamentals` | ✅ DONE (PR #175 + #182 → develop) | — |

---

Kurzkontext für Claude Code. **Quelle der Wahrheit ist `AGENTS.md`** — dieses File ergänzt nur Claude-spezifische Hinweise.

## Projekt in einem Satz

PRISMA V2 = quantitative Stock-Intelligence-Plattform für den Schweizer Markt (SMI/SMIM/SPI), Swiss Quant Scoring Engine + Claude-Narrative-Engine + VIAC 3a-Entscheidungsunterstützung. FHNW BI Module FS 2026 — Gruppenarbeit Andrea, Helin, Aurelius.

## Git Workflow (GitHub Flow)

- **`main`** = einziger stabiler Branch, Render deployt von hier, direkte Pushes gesperrt
- **`feat/issue-<nr>-<name>`** = ein Branch pro Task, von `main` abzweigen
- Fertig → PR → `main` (CI muss grün sein, 1 Review)
- **Niemals direkt auf `main` pushen**

```bash
git checkout main && git pull
git checkout -b feat/issue-<nr>-<kurzname>
# ... arbeiten ...
gh pr create --base main
```

## Vor jeder Aufgabe lesen

1. `AGENTS.md` — Coding-Konventionen (Python, TypeScript, Tests, Architecture)
2. `CLAUDE.md` STATUS-Block oben — wer macht was, was ist DONE
3. Den aktuellen Task aus dem STATUS-Block nehmen und starten

## Swiss Market Kontext

**Adapter:** `YFinanceSwissAdapter` (`backend/infrastructure/adapters/yfinance_swiss.py`) implementiert `SwissMarketDataProvider`-Port. Alle yfinance-Calls via `asyncio.to_thread()` (nicht `run_in_executor`). Ticker-Format: `NESN.SW` (SIX-Suffix).

**Scoring:** `SwissQuantScorer` (`backend/domain/services/swiss_quant_scorer.py`) berechnet value/income/quality-Scores mit SMI-kalibrierten Bändern → `SwissQuantScore` Value Object mit Signal BUY/HOLD/SELL.

**Seed-Daten:** `scripts/seed_smi_universe.py` — 20 SMI-Konstituenten. Offene ISIN-TODOs: ABBN, BALN (delisted), STMN.

**yfinance-Einschränkung:** `.info`-Dict liefert für `.SW`-Ticker kein `isin`-Feld (immer `None`). ISINs müssen manuell via SIX Exchange verifiziert werden.

## Schnellstart-Befehle

```bash
# Venv aktivieren (immer zuerst)
source /tmp/prisma-v2/venv/bin/activate

# Unit Tests
pytest backend/tests/unit -q

# Integration Tests (braucht laufende DB)
pytest backend/tests/integration -q

# Lint + Format-Check
ruff check backend/
ruff format --check backend/

# Einen einzelnen Test
pytest backend/tests/unit/domain/test_swiss_quant_scorer.py -v
```

## Claude-Code-spezifische Regeln

### Neue Features
Wenn der User eine neue Aufgabe verlangt: kurz den Plan skizzieren (in Chat), Freigabe abwarten, dann direkt implementieren. Kein separates Spec-File nötig.

### TDD-Pflicht
Für Domain-Code, Quant-Modelle, Application Services: Tests schreiben **bevor** die Implementierung existiert (Red-Green-Refactor). `pytestmark = pytest.mark.unit` in allen Unit-Test-Files.

### LLM-Features
- **Immer** Pydantic-Schema für Output. Kein Freitext ins Frontend.
- Prompt-Caching aktivieren (`cache_control: ephemeral`) bei wiederkehrenden System-Prompts.
- Für Tests: Fixture-Mode in `tests/fixtures/llm/` nutzen — nie gegen Live-API in CI.
- Modell-Wahl: `claude-haiku-4-5-20251001` für schnelle Tasks, `claude-sonnet-4-6` für Research-Synthese.

### Async-Pattern
```python
# RICHTIG — codebase-Konvention
result = await asyncio.to_thread(sync_function, arg)

# FALSCH — nicht verwenden
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, partial(sync_function, arg))
```

### Retry-Pattern
Kein `tenacity`. Manueller Retry: `_RETRIES = 2`, `_BASE_DELAY = 1.0`, Exponential Backoff (`base * 2**attempt`). Muster aus `YFinanceSwissAdapter._fetch_info()`.

### MCP-Server-Arbeit
MCP-Tools in `backend/interfaces/mcp/` liegen dünn über Application-Services. Keine Business-Logik im MCP-Layer.

## Workflow-Regeln (gelernt aus PR #190)

### 1. Kleinere PRs
Max. ~20 Dateien pro PR. Mehrere unabhängige Features → mehrere PRs. Grosse PRs = viele gleichzeitig kaputte Tests = schwer zu debuggen.

### 2. Tests im selben Commit wie der UI-Text
Wenn ein Label, Button-Text oder Komponentenname geändert wird: den dazugehörigen Test **im gleichen Commit** anpassen. Nie später.

### 3. Lokal prüfen vor dem Push
```bash
# Backend
ruff check backend/ && ruff format --check backend/ && mypy backend/

# Frontend
cd frontend && npx vitest run
```
Jeder fehlgeschlagene CI-Run = ~10 Min Wartezeit. Lokal dauert es 30 Sekunden.

### 4. main mergen bevor man lange arbeitet
```bash
git fetch origin && git merge origin/main
```
Am Anfang des Tages, nicht nach 20 CI-Runs. Branch-Divergenz erzeugt Konflikte und mypy-Fehler aus Code der nicht mal unser ist.

### 5. Platform-Unterschied ruff (macOS vs. Linux)
`ruff format` verhält sich bei Zeilen exakt an der `line-length`-Grenze unterschiedlich auf macOS (arm64) vs. Linux (x86_64 / CI). Nach einem Merge immer `ruff format backend/` auf Linux oder direkt in CI vertrauen — lokal auf macOS ist kein verlässlicher Check.

---

## Häufige Claude-Fehler in diesem Projekt (bitte vermeiden)

- Quant-Formeln aus dem Gedächtnis rekonstruieren statt aus dem Plan/Spec zu zitieren
- `yfinance` direkt im Application-Service aufrufen (→ muss über Port in Infrastructure)
- `if market_cap:` statt `if market_cap is not None:` (0 ist valider Wert)
- `run_in_executor` statt `asyncio.to_thread`
- LLM-Responses mit `response.content[0].text` ungeparst weiterreichen
- Datumshandling ohne Timezone (→ immer UTC-aware)
- Floats für Geldbeträge statt `Decimal`

## Glossar

| Begriff | Bedeutung |
|---------|-----------|
| **SMI** | Swiss Market Index — 20 grösste SIX-kotierte Titel |
| **SMIM** | Swiss Mid Caps Index — 30 mittlere Titel |
| **SPI** | Swiss Performance Index — Gesamtmarkt |
| **SIX** | Swiss Infrastructure and Exchange — Schweizer Börse |
| **XSWX** | MIC-Code für SIX Swiss Exchange (intern als `exchange`-Feld) |
| **3a** | Säule 3a — gebundene Vorsorge (steuerlich begünstigt), max. CHF 7'258/Jahr (2026) |
| **VIAC** | Swiss Life Vorsorge-App mit Einzeltitel-Selektion (VIAC Stocks Initiative) |
| **FINMA** | Eidgenössische Finanzmarktaufsicht — reguliert 3a-fähige Anlagen |
| **CH-ISIN** | Schweizer ISIN-Format: `CH` + 9 Ziffern + Luhn-Check-Digit |
| **BUY/HOLD/SELL** | Signal aus `SwissQuantScore.signal`: composite ≥70 / 40–69 / <40 |

## Wenn unsicher: fragen

Lieber eine präzise Nachfrage als eine falsche Annahme. Finanzmathematik verzeiht keine Ungenauigkeit.
