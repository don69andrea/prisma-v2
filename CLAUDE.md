# CLAUDE.md

## 🚦 LIVE STATUS — WER MACHT WAS

| # | Aufgabe | Person | Branch | Status | Blockiert durch |
|---|---------|--------|--------|--------|-----------------|
| R2.3-1 | Datenpipeline: SMI seeden + XGBoost trainieren | Andrea | `feature/andrea-datenpipeline` | 🔄 IN PROGRESS | — |
| R2.3-2 | /decision: echte BUY/HOLD/WATCH Signale | Andrea | `feature/andrea-datenpipeline` | ⬜ NEXT | R2.3-1 |
| R2.3-3 | Frontend: SignalBadge + PrismaScore + ExplainButton | Helin | `feature/helin-ux-components` | 🔄 IN PROGRESS | — |
| R2.3-4 | Frontend: Glassmorphism Cards + Loading-States | Helin | `feature/helin-ux-components` | ⬜ NEXT | — |
| R2.3-5 | Backend: InvestorProfile Model + DB Migration | Aurelius | `feature/aurelius-investorprofile` | ✅ DONE | — |
| R2.3-6 | Backend: DiscoveryService + API Endpoints | Aurelius | `feature/aurelius-investorprofile` | ✅ DONE | — |
| R2.4-1 | /start: Conversational Discovery Engine — 5 Turns | Andrea | `feature/andrea-discovery-engine` | ⬜ NEXT | — |
| R2.4-2 | /start: Brand Logo Grid + Risk-Feeling-Test + ProfileReveal | Helin | `feature/helin-discovery-ui` | ⬜ BLOCKED | R2.4-1 |
| R2.4-3 | Haiku-Klassifikation + Session-State + Konfidenz-Score | Aurelius | `feature/aurelius-discovery-agent` | ✅ DONE | — |
| R2.4-4 | Navigation: 5 Bereiche umstrukturieren | Helin | `feature/helin-navigation` | ⬜ NEXT | — |
| R2.4-5 | AuditTrail Komponente + Profil-Reveal Animation | Helin | `feature/helin-discovery-ui` | ⬜ BLOCKED | R2.4-2 |
| R2.4-6 | Makro-Agent + RAG verifizieren | Aurelius | `feature/aurelius-discovery-agent` | 🔄 IN PROGRESS | RAG-Teil wartet auf R2.3-1 |
| R2.5-1 | Demo-Flow + Präsentation | Alle | `feature/presentation` | ⬜ BLOCKED | Alle R2.4 |

---

Kurzkontext für Claude Code. **Quelle der Wahrheit ist `AGENTS.md`** — dieses File ergänzt nur Claude-spezifische Hinweise.

## Projekt in einem Satz

PRISMA V2 = quantitative Stock-Intelligence-Plattform für den Schweizer Markt (SMI/SMIM/SPI), Swiss Quant Scoring Engine + Claude-Narrative-Engine + VIAC 3a-Entscheidungsunterstützung. FHNW Capstone FS 2026.

## Vor jeder Aufgabe lesen

1. `AGENTS.md` — verbindliche Konventionen (Goldene Regeln, Security, Gitflow)
2. `docs/superpowers/plans/` — aktueller Implementierungsplan wenn vorhanden
3. `docs/superpowers/specs/` — Design-Docs für laufende Features

## Swiss Market Kontext

**Adapter:** `YFinanceSwissAdapter` (`backend/infrastructure/adapters/yfinance_swiss.py`) implementiert `SwissMarketDataProvider`-Port. Alle yfinance-Calls via `asyncio.to_thread()` (nicht `run_in_executor`). Ticker-Format: `NESN.SW` (SIX-Suffix).

**Scoring:** `SwissQuantScorer` (`backend/domain/services/swiss_quant_scorer.py`) berechnet value/income/quality-Scores mit SMI-kalibrierten Bändern → `SwissQuantScore` Value Object mit Signal BUY/HOLD/WATCH.

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

### Spec-First
Wenn der User eine neue Feature-Arbeit verlangt, **schreibe zuerst den Plan** nach `docs/superpowers/plans/YYYY-MM-DD-*.md`, committe ihn, und führe dann aus. Nutze `superpowers:brainstorming` → `superpowers:writing-plans` → `superpowers:subagent-driven-development`.

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
| **BUY/HOLD/WATCH** | Signal aus `SwissQuantScore.signal`: composite ≥70 / 40–69 / <40 |

## Wenn unsicher: fragen

Lieber eine präzise Nachfrage als eine falsche Annahme. Finanzmathematik verzeiht keine Ungenauigkeit.
