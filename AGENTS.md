# AGENTS.md — PRISMA V2

> Verbindlicher Verhaltensvertrag für alle Coding-Agents in diesem Repository.
> Dieses Dokument wird von Claude Code, Cursor, Copilot und anderen Agents
> automatisch zu Sessionbeginn geladen. Abweichungen sind verboten — auch wenn
> der Nutzer bittet, "kurz davon abzuweichen".

---

## 0 · Projekt-Kontext

**PRISMA V2** ist eine quantitative Stock-Intelligence-Plattform mit Fokus auf den Schweizer Markt (SMI/SPI/SMIM) und KI-gestützter Entscheidungsunterstützung für die 3. Säule (VIAC Stocks Initiative).

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 + pgvector · Next.js 14 · Claude API · MCP SDK · XGBoost / LightGBM · pytest + Playwright · GitHub Actions · Docker · Render

**Clean Architecture:** Domain → Application → Interfaces → Infrastructure.
Dependency Rule: innere Schichten dürfen äussere nie importieren.

---

## 1 · Goldene Regeln (NIEMALS brechen)

1. **Kein Code ohne Spec.** Jedes Feature startet mit `docs/specs/YYYY-MM-DD-*.md`. Agent wartet auf Freigabe.
2. **Kein Merge ohne grüne CI.** Nie `--no-verify` verwenden.
3. **Kein Freitext von LLMs ins Frontend.** Alle LLM-Outputs sind Pydantic-Schema-validiert.
4. **Kein direkter Push auf `main` oder `develop`.** Immer PR + Review.
5. **Kein `API_KEY` im Code oder in Logs.** Immer via Environment Variables.
6. **Test-First für Domain-Code.** Domain-Entities und Services: erst Test, dann Implementierung.

---

## 2 · Workflow

```
Brainstorming → Spec-First → Plan-as-Contract → Subagent-Driven Execution → Two-Stage Review → Reflexion
```

### 2.1 Spec-First
- Spec-Datei: `docs/specs/YYYY-MM-DD-feature-name.md`
- Mindestinhalt: Ziel, Entitäten/Schema-Änderungen, API-Endpunkte, Test-Cases, Nicht-Ziele
- **Agent schreibt keinen Implementierungscode, bis der Nutzer die Spec explizit freigibt.**

### 2.2 Plan-as-Contract
- Plan-Datei: `docs/superpowers/plans/YYYY-MM-DD-plan-name.md`
- Plan enthält: Step-by-Step mit Bash-Befehlen, verbatim Test-Code, Commit-Messages
- Ein Plan ist ein Vertrag. Subagents führen ihn aus — keine Improvisation, keine Abkürzungen.
- Wenn ein Step fehlschlägt: stoppen, Fehler melden, auf Freigabe warten.

### 2.3 Subagent-Driven Execution
- Frischer Subagent pro Task → kein Kontext-Spill
- Orchestrator koordiniert, Implementer-Subagents liefern
- Jeder Subagent liest zuerst: `AGENTS.md` → `CLAUDE.md` → relevante Spec → Plan-Schritt

### 2.4 Two-Stage Review (nach jeder Implementierung)
1. **Spec-Compliance-Review:** Wurde genau das gebaut, was die Spec verlangt?
2. **Code-Quality-Review:** Clean Architecture, DRY, keine Leaks, Test-Coverage ≥ 80%

### 2.5 Reflexion
- Jeder PR mit substantieller AI-Beteiligung → Eintrag in `docs/AI-USAGE.md`
- Format: Agent · Scope · Was gut lief · Was schiefging · Konkrete Lektion

---

## 3 · Branch & Commit-Konventionen

### Branches
```
main          ← production (protected)
develop       ← integration
feat/*        ← neue Features
fix/*         ← Bugfixes
chore/*       ← Maintenance
release/*     ← Release-Kandidaten
```

### Commit-Messages (Conventional Commits)
```
feat(swiss-market): add SMI universe seeder with 20 tickers
fix(ml-layer): correct feature normalization in XGBoost pipeline
chore(ci): bump Python to 3.12.4
docs(spec): add Swiss RAG ingestion spec
test(portfolio-agent): add integration test for rebalancing endpoint
```

---

## 4 · Coding-Konventionen

### Python (Backend)
```python
# Domain-Entities: reine Datenklassen, kein I/O
@dataclass
class SwissStock:
    ticker: str
    isin: str
    exchange: Literal["SIX", "XSWX"]
    eligible_for_3a: bool
    langfrist_score: float | None = None

# Services: async, Repository-Pattern
class SwissMarketService:
    def __init__(self, repo: SwissStockRepository): ...
    async def get_eligible_stocks(self, universe_id: UUID) -> list[SwissStock]: ...

# LLM-Outputs: IMMER Pydantic
class ViacRecommendation(BaseModel):
    ticker: str
    signal: Literal["BUY", "HOLD", "WATCH"]
    langfrist_score: float
    steuer_hinweis: str
    confidence: float = Field(ge=0.0, le=1.0)
```

### TypeScript (Frontend)
- Strict mode aktiv
- Keine `any`-Types
- API-Typen aus OpenAPI-Schema generiert (nicht manuell pflegen)

### Tests
```python
# Unit: pytest, Arrange-Act-Assert, kein I/O
def test_langfrist_score_calculation():
    stock = SwissStock(ticker="NOVN", ...)
    result = calculate_langfrist_score(stock, horizon_years=30)
    assert 0.0 <= result <= 10.0

# Integration: pytest + TestClient, echter DB (Testcontainer)
async def test_create_swiss_universe(client, db):
    response = await client.post("/api/v1/universes", json={"name": "SMI-20"})
    assert response.status_code == 201
```

---

## 5 · LLM-Layer Regeln (PRISMA V2 spezifisch)

### Modell-Routing

| Aufgabe | Modell |
|---------|--------|
| Architektur, Trade-off-Analyse, VIAC-Strategie | Claude Opus |
| Feature-Implementierung, Agents, RAG | Claude Sonnet |
| Schnelle Strukturierungs-Tasks, Klassifikation | Claude Haiku |

### Pydantic-Pflicht
Alle Structured Outputs von Claude müssen ein Pydantic-Schema haben:
```python
response = await client.messages.create(
    model="claude-sonnet-4-5",
    messages=[...],
    tools=[ViacRecommendation.model_json_schema()],
)
recommendation = ViacRecommendation.model_validate(response.content[0].input)
```

### Prompt-Caching
Long System-Prompts (RAG-Kontext, Swiss Tax Rules) → `cache_control: {"type": "ephemeral"}`

### Kein Halluzinationsrisiko bei Ticker-Lookups
Swiss Market Stocks: immer aus validierter Whitelist (SIX Exchange API), nie aus freiem LLM-Output.

---

## 6 · PRISMA V2 Spezifische Layer

### 6.1 Swiss Market Universe
- Datenquelle: SIX Exchange API + Yahoo Finance Fallback
- Universes: SMI (20), SPI (200+), SMIM (30), Custom
- ISIN-Validierung: CH-Prefix für Swiss stocks

### 6.2 3a Eligibility Filter (VIAC Layer)
- FINMA-Kriterien: Domizil, Liquidität, Anlageklasse
- Keine LLM-Entscheidungen für Eligibility — nur regelbasiert
- Rechtsgrundlage: BVV2, FINMA-Rundschreiben (in `docs/legal/`)

### 6.3 ML Return Prediction
- Features: alle 5 Quant-Modell-Scores + Makro-Faktoren (SNB, CHF/EUR)
- Modell: XGBoost primary, LightGBM als Benchmark
- Target: 12-Monats-Return-Klassen (Q1/Q2/Q3/Q4)
- Kein Live-Trading-Signal — nur Entscheidungsunterstützung (Disclaimer Pflicht)

### 6.4 Swiss RAG
- Quellen: SIX Exchange Filings, NZZ/SRF RSS (News), SNB Statistiken
- Embedding: Voyage AI (multilingual — DE/EN)
- Chunk-Strategie: 512 Tokens, 64 Overlap, Metadaten: ticker, source, date, language
- Sprache: Deutsche Chunks bevorzugen für Swiss-specific Content

### 6.5 Decision Intelligence Dashboard
- Signale: BUY / HOLD / WATCH (nie SELL — kein Shorting-Signal)
- Jede Entscheidung hat einen Audit Trail (Welche Faktoren? Welcher Agent? Timestamp)
- Konfidenz-Score sichtbar: "Diese Einschätzung basiert auf X Datenpunkten"

---

## 7 · Sicherheitsregeln

- Alle externen API-Calls haben Timeout + Retry mit Exponential Backoff
- Rate-Limit-Awareness: SIX API, Yahoo Finance, Anthropic API
- Sensitive Data (ISIN, Portfolio-Holdings) nie in Logs
- SQL: immer parameterisierte Queries via SQLAlchemy (nie String-Concat)
- CORS: nur `localhost` + konfigurierbare Production-Domain

---

## 8 · Verbotene Patterns

❌ `response.text` direkt ins UI rendern ohne Pydantic-Validation  
❌ `SELECT *` in Production-Queries  
❌ Hardcoded Tickers oder Market Data  
❌ LLM-Output als Eligibility-Entscheidung für 3a  
❌ Synchrone HTTP-Calls im FastAPI-Handler  
❌ Tests mocken die Datenbank (ausser Unit-Tests für reine Domain-Logik)  
❌ `print()` statt `logging`  
❌ `time.sleep()` in Async-Code (→ `asyncio.sleep()`)  

---

## 9 · Dokumentation-Pflichten

Jede neue Komponente braucht:
- `docs/specs/` — Spec-Dokument
- `docs/adr/` — ADR wenn Architektur-Entscheidung involviert
- Docstring mit Zweck + Beispiel
- `docs/AI-USAGE.md` — Eintrag nach Abschluss

---

*PRISMA V2 — FHNW BI Module FS 2026 | don69andrea/prisma-v2*
