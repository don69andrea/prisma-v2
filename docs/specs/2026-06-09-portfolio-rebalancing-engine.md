# Spec: Portfolio Rebalancing Engine

**Issue:** #16  
**Milestone:** v2.0 Swiss Intelligence Layer  
**Date:** 2026-06-09  
**Author:** Andrea Petretta (Coding-Agent: Claude Sonnet 4.6)  
**Status:** Implemented

---

## Ziel

Nutzer geben aktuelle Portfolio-Gewichtung (Ist) und Ziel-Allokation (Soll) ein. Die Engine berechnet Rebalancing-Schritte (BUY/SELL/HOLD) mit Transaktionskostenschätzung. Optional: 3a-Eignung prüfen.

---

## Nicht-Ziele

- Automatisches Rebalancing (Broker-Integration)
- Steuerkostenoptimierung (Loss-Harvesting)
- Multi-Währungs-Portfolios
- Persistenz des Plans (rein berechnet, kein DB-State)

---

## Architektur

### Domain
- `RebalancingStep` (frozen dataclass): ticker, action (BUY|SELL|HOLD), current_weight, target_weight, delta_weight, estimated_value_chf, transaction_cost_chf, is_3a_eligible
- `RebalancingPlan` (frozen dataclass): steps, total_portfolio_value_chf, total_transaction_cost_chf, is_3a_account, computed_at, plan_id (UUID)

### Application
- `RebalancingService`: zustandslos, kein Repository
- BUY wenn delta > 0.5%, SELL wenn delta < -0.5%, sonst HOLD (Threshold 0.005)
- `transaction_cost_chf = |delta| * total_value * cost_rate` (default: 0.1%)
- 3a-Prüfung: optionaler `stock_repo`-Inject → `EligibilityFilter.check()` pro Ticker; ohne Repo gelten alle Positionen als `is_3a_eligible=True` (non-3a) bzw. `False` (3a ohne Verifikation)

### Interface
- `POST /api/v1/portfolio/rebalance` — Request: total_value, current_weights, target_weights, is_3a_account, transaction_cost_rate (0–5%)
- Pydantic-Validation: total_value > 0, cost_rate [0, 0.05]
- Kein Auth-Middleware (stateless, keine sensitiven Daten)

---

## Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Keine Persistenz | Rebalancing-Plan ist ephemer — Nutzer kann jederzeit neu berechnen |
| Threshold 0.5% | Standard-Band für taktisches Rebalancing (vermeidet Overtrading) |
| `tuple[RebalancingStep]` in Plan | Immutable garantiert Konsistenz; JSON-serialisierbar via Pydantic |
| `stock_repo: Any | None` | ML-Isolation-Pattern — kein harter Import von Repo-Impl im Service |

---

## Sicherheit

- Portfolio-Holdings (Ticker, Gewichtung) nicht geloggt (sensitiv)
- Keine Datenbankschreiboperationen → kein SQL-Injection-Risiko
