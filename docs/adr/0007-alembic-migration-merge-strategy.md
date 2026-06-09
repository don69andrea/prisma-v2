# ADR-0007: Alembic Migration Strategy für parallele Feature-Branches

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Andrea Petretta

## Kontext

Mehrere Feature-PRs (#42, #44, #47, #48) führen je eine neue Alembic-Migration ein. Da alle Branches von `develop` (head=0013) abzweigen, haben alle `down_revision = "0013"`. Das erzeugt beim Mergen auf develop eine **multiple-heads** Situation.

## Entscheidung

**Jede Feature-Branch-Migration zeigt auf den develop-Head zum Branch-Zeitpunkt (0013).**

Das ermöglicht CI-Isolation: jeder PR wird unabhängig gegen develop getestet und besteht. Multiple heads in develop werden nach Abschluss aller Merges mit einem `alembic merge` aufgelöst.

## Merge-Reihenfolge

Empfohlene Reihenfolge der PRs, die Alembic-Migrationen enthalten:

1. **PR #42** (oder #44) — Migration `0015` (ml_features)
2. **PR #47** — Migration `0016` (decision_audit_log)
3. **PR #48** — Migration `0017` (alerts)

Nach Abschluss aller Merges:
```bash
alembic merge -m "merge_v2_feature_heads" 0015 0016 0017
```

## Konsequenzen

- CI-Isolation bleibt erhalten (jeder PR grün)
- Manueller `alembic merge`-Schritt nach Merge-Abschluss nötig
- Alternative (Migrations quer-dependieren) bricht CI-Isolation → abgelehnt
