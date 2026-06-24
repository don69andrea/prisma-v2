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

1. **Kein direkter Push auf `main` oder `develop`.** Immer via Feature-Branch + PR — auch für kleine Fixes.
2. **Kein Merge ohne grüne CI.** Nie `--no-verify` verwenden.
3. **Kein Freitext von LLMs ins Frontend.** Alle LLM-Outputs sind Pydantic-Schema-validiert.
4. **Kein direkter Push auf `main` oder `develop`.** Immer PR + Review.
5. **Kein `API_KEY` im Code oder in Logs.** Immer via Environment Variables.
6. **Test-First für Domain-Code.** Domain-Entities und Services: erst Test, dann Implementierung.

## Goldene Regel: Wissenschaftliche Ehrlichkeit & Feature-Gating

1. Jedes signal-/performance-relevante Feature (ML-Score, Meta-Label, Sentiment) ist standardmäßig
   AUS (Flag/Env-Var), bis es im STRIKTEN Walk-Forward, netto nach Kosten, gegen die exposure-matched
   Baseline einen Vorteil zeigt (Sharpe UND Calmar, oder Kosten-/Trade-Senkung ohne Performance-Verlust).
2. Befunde ehrlich in docs/PRISMA_V4_FORTSCHRITT.md — auch Negativbefunde. Kein Überoptimieren.
3. Modell-Updates nur per Champion/Challenger (neue Version nur bei echtem OOS-Vorteil aktiv).
4. Im UI/Output kein Alpha/Edge behaupten, der nicht OOS belegt ist. Decision-Support, Disclaimer-Pflicht.
5. Standard für jede "hilft das?"-Aussage: strikter Walk-Forward + Baselines (Buy&Hold, exposure-matched)
   + Netto-Kosten + ausgewiesene N/Konfidenz.

---

## 2 · Workflow

```
feature/* → develop → main
```

1. Branch vom aktuellen `develop` erstellen: `git checkout -b feature/name-aufgabe`
2. Implementieren, testen (`pytest` / `vitest`)
3. PR nach `develop` — kurze Beschreibung was geändert wurde
4. Nach Merge: Branch löschen

Jeder Agent liest zu Sessionbeginn `CLAUDE.md` (STATUS-Block) und `AGENTS.md`, dann direkt starten.

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
- Signale SMI/3a-Universum: BUY / HOLD / WATCH (nie SELL — kein Shorting-Signal)
- Signale Krypto-Universum: BUY / HOLD / SELL, wobei SELL = raus/cash (KEIN Shorting)
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

---

*PRISMA V2 — FHNW BI Module FS 2026 | don69andrea/prisma-v2*
