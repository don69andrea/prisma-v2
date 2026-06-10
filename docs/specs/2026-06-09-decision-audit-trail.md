# Spec: Decision Audit Trail — Erklärbarkeit

**Issue:** #19  
**Milestone:** v2.0 Swiss Intelligence Layer  
**Date:** 2026-06-09  
**Author:** Andrea Petretta (Coding-Agent: Claude Sonnet 4.6)  
**Status:** Implemented

---

## Ziel

Jede BUY/HOLD/WATCH-Entscheidung wird mit vollständiger Begründung persistiert: Quant-Score, ML-Score, Makro-Score, gewichtete Gesamtscore, 3a-Eignung, Datum. Audit Trail ist abrufbar via REST.

---

## Nicht-Ziele

- LLM-generierte Begründungen (nur regelbasiert)
- User-spezifischer Audit Trail (kein Auth-Layer)
- Zeitreihen-Visualisierung (Frontend deferred)

---

## Architektur

### Domain
- `DecisionAuditRecord` Entity: id, ticker, signal, weighted_score, quant_score, ml_score, macro_score, is_3a_eligible, snapshot_date, computed_at, explanation_de
- `DecisionAuditRepository` ABC

### Application
- `DecisionAuditService.__init__`: `audit_repo` + optionale Repos/Services (all `Any | None`)
- `compute_and_save(ticker)`: berechnet Score via `SwissQuantScorer` (Fallback wenn kein ML), `_snb_macro_score()`, Gewichtung 0.45/0.35/0.20, generiert `explanation_de`, persistiert
- **ML-Isolation-Pattern**: `feature_service` und `prediction_service` sind `Any | None` — kein Module-Level-Import von ML-Typen die nur in ungemergten PRs existieren

### Scoring-Logik
```
weighted_score = quant_score * 0.45 + ml_score * 0.35 + macro_score * 0.20
BUY:  weighted_score >= 65
HOLD: weighted_score >= 40
WATCH: weighted_score < 40
```

### Infrastructure
- `SQLADecisionAuditRepository`: asyncio-kompatibel, Index auf ticker + computed_at
- Alembic Migration `0016_create_decision_audit_log` (down_revision: **0015**)

### Interface
- `GET /api/v1/decisions/{ticker}/audit?limit=N` → Letzten N Entscheidungen
- `POST /api/v1/decisions/{ticker}/audit` → Neu berechnen und speichern (201)

---

## Entscheidungen

| Entscheidung | Begründung |
|---|---|
| `Any | None` für ML-Services | ML-Layer noch nicht auf develop — verhindert ImportError bei CI |
| `SwissFundamentals(all None)` Fallback | `SwissQuantScorer.score()` erfordert Objekt, nicht None |
| `explanation_de` als SQL Text | Max. ~500 Zeichen, kein JSON nötig |
| Migration 0016 folgt 0015 | ML-Features-Tabelle wird zuerst angelegt (0015) |
