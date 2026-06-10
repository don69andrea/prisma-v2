# Portfolio Intelligence Agent — Design Spec

**Status:** Approved  
**Issue:** #15  
**Milestone:** v2.1 ML Intelligence Layer  
**Date:** 2026-06-09

---

## Ziel

Aus einem abgeschlossenen Ranking-Run die Top-N-Picks extrahieren und daraus eine gewichtete Portfolio-Allokation berechnen. Zwei Methoden stehen zur Wahl: Score-Weighted (einfach, direkt aus Quant-Score) und Risk-Parity (Gewichtung umgekehrt proportional zur historischen Volatilität). Der Agent generiert eine deutschsprachige Begründung via LLM.

---

## Architektur

```
POST /api/v1/portfolio/allocate
    ↓
PortfolioAgent (application/agents/portfolio_agent.py)
    ├── RankingRunService.get_rankings(run_id)       → Top-N nach total_rank
    ├── SwissStockRepository.get_by_ticker()         → 3a-Filter
    ├── YFinanceSwissAdapter.get_price_history()     → Volatilität (Risk-Parity)
    ├── Optimierung: _score_weighted() | _risk_parity()
    └── LLMClient.messages_create()                  → Pydantic-validierte Narrative
```

Clean Architecture: Agent lebt in `application/agents/` (kein direkter DB-Zugriff; nutzt bestehende Services und Repos via DI).

---

## Domain Value Objects

### `PortfolioPosition`
```python
@dataclass(frozen=True)
class PortfolioPosition:
    ticker: str
    weight: float          # 0.05–0.40, Summe = 1.0 über alle Positionen
    quant_score: float
    is_3a_eligible: bool
    rationale_de: str      # LLM-generiert, Pydantic-validiert
```

### `PortfolioAllocation`
```python
@dataclass(frozen=True)
class PortfolioAllocation:
    run_id: UUID
    method: str            # "score_weighted" | "risk_parity"
    positions: tuple[PortfolioPosition, ...]
    overall_rationale_de: str   # LLM-generiert, Pydantic-validiert
    computed_at: datetime
    eligible_only: bool
```

---

## Optimierungsmethoden

### Score-Weighted (default)
```
w_raw_i = quant_score_i
w_i = w_raw_i / Σ w_raw_j          # Normalisierung
w_i = clamp(w_i, 0.05, 0.40)       # Min/Max-Constraint
w_i = re-normalisieren              # nach Clamp
```

### Risk-Parity (vereinfacht)
Gewichtung umgekehrt proportional zur 30-Tage-Volatilität (Annualisiert):
```
σ_i = std(daily_returns_30d) × √252
w_raw_i = 1 / σ_i
w_i = w_raw_i / Σ w_raw_j          # Normalisierung
w_i = clamp(w_i, 0.05, 0.40)       # Min/Max-Constraint
w_i = re-normalisieren
```
Fallback bei fehlenden Preisdaten: gleichgewichtete Position (1/N).

---

## LLM-Narrative (Pydantic-validiert)

**Pydantic-Schema für LLM-Output:**
```python
class _NarrativeOutput(BaseModel):
    overall: str = Field(..., min_length=20, max_length=600)
    positions: dict[str, str]   # {ticker: rationale, max_length=200 je}
```

**Prompt-Kontext:** Methode, Top-3-Positionen mit Gewicht + Quant-Score, Makro-Klima (optional).  
**Fallback:** Wenn LLM fehlschlägt → statische Textformel, kein Error.

---

## REST Endpoint

```
POST /api/v1/portfolio/allocate
Content-Type: application/json

{
  "run_id": "uuid",
  "top_n": 10,           // default 10, max 20
  "eligible_only": false, // nur 3a-eligible Titel
  "method": "score_weighted"  // oder "risk_parity"
}
```

Response: `PortfolioAllocationResponse` (Pydantic, alle LLM-Felder validated).

---

## Constraints & Sicherheit

- Keine API_KEY in Logs; keine Ticker/Gewichte in Logs (ISIN-/Portfolio-Privacy)
- Alle LLM-Outputs via `_NarrativeOutput.model_validate()` — kein Freetext ans Frontend
- Timeout + Retry: YFinance-Aufrufe mit `days=40` (30d Daten + Puffer)
- `top_n` ≥ 2, ≤ 20 (Feldvalidierung in Pydantic-Request)
- Gewichte: Σ = 1.0 ± 0.001 (Toleranz für Float-Arithmetik)

---

## Tests

- Unit: `_normalize_weights()`, `_score_weighted()`, `_risk_parity()` mit Mock-Preisdaten
- Unit: LLM-Fallback bei ValidationError und bei Exception
- Unit: 3a-Filter entfernt ineligible Ticker vor Optimierung
- Unit: `top_n` > verfügbare Rankings → alle verfügbaren nutzen

---

## Dateien

| Datei | Aktion |
|---|---|
| `backend/domain/value_objects/portfolio_allocation.py` | NEU |
| `backend/application/agents/portfolio_agent.py` | NEU |
| `backend/interfaces/rest/schemas/portfolio.py` | NEU |
| `backend/interfaces/rest/routers/portfolio.py` | NEU |
| `backend/interfaces/rest/app.py` | MODIFY |
| `backend/tests/unit/application/test_portfolio_agent.py` | NEU |
