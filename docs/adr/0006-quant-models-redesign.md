# ADR 0006: Quant-Modelle für Free-Tier-Daten neu wählen

- **Status**: Accepted
- **Datum**: 2026-04-27
- **Kontext**: PR #26, Spec `docs/specs/2026-04-27-quant-models-redesign.md`. Motiviert durch den Free-Tier-Daten-Constraint aus [ADR 0005](./0005-data-source-quant-fundamentals.md).

## Kontext

Die ursprüngliche Modell-Liste der Design-Spec v1.1 (siehe `docs/specs/2026-04-21-prisma-capstone-design.md` §6) enthielt fünf Modelle:

1. Quality Classic — Fundamentaldaten-Snapshot
2. Quality AI — Lasso-Regression mit rollendem 2-Jahres-Fenster, Forward-Returns als Ziel
3. Alpha — Performance vs. Benchmark über 5 Horizonte
4. Anti-Cyclical — P/E + P/B unter eigenem 3-Jahres-Median
5. Diversification — Ledoit-Wolf-Shrinkage-Kovarianz

Beim ernsten Daten-Verfügbarkeits-Check (Yahoo Finance gratis + FinancialModelingPrep Free Tier, kein Bezahl-Datenfeed) zeigt sich:

- **Quality AI** braucht **point-in-time** Fundamentaldaten (as-reported, ohne Restatements). FMP Free liefert nur aktuelle Snapshots; FMP Starter (~$30–50/Mo) liefert Historicals **ohne dokumentiertes Restatement-Flag** → Look-Ahead-Bias unvermeidbar. Saubere PIT-Quellen (Bloomberg, SIX) sind nicht im Capstone-Budget.
- **Anti-Cyclical** braucht historische P/E-Reihen (mind. 3 Jahre rolling). FMP Free liefert kein Historical, Yahoo liefert für CH-Tickers (.SW) keine zuverlässigen historischen Ratios.

Damit sind **2 von 5 Modellen mit gratis verfügbaren Daten nicht implementierbar oder nur mit erheblichem Bias-Risiko**.

## Entscheidung

Zwei Modelle aus dem MVP entfernen, zwei neue ersetzen, Diversification bleibt:

| # | Modell | Kategorie | Vorher / Neu | Daten |
|---|---|---|---|---|
| 1 | Quality Classic | Quality | bleibt | Yahoo + FMP Free |
| 2 | Alpha | Trend | bleibt | Yahoo only |
| 3 | **Trend Momentum** | Trend | **NEU** (war Stretch §19) | Yahoo only |
| 4 | **Value Alpha Potential** | Value | **NEU** (war Stretch §19) | Yahoo only |
| 5 | Diversification | Risk | bleibt | Yahoo only |

**Trend Momentum** (EWMA halflife=63d auf relativen Returns vs. equal-weighted Universe) und **Value Alpha Potential** (rolling max 252d-Alpha minus current Alpha) waren ursprünglich als Stretch-Goals in §19 dokumentiert. Sie wandern in den MVP, weil sie nur Tagespreise brauchen — die einzige Datenkategorie, die Yahoo zuverlässig auch für Schweizer Tickers liefert.

**Default-Gewichte** in §7.2 werden auf gleichgewichtet umgestellt (je 0.20).

## Optionen, die wir verworfen haben

### Option A: Quality AI behalten, FMP Starter kaufen
- **Pro**: einziges echtes ML-Modell im MVP, Gewicht für 40%-Achse
- **Contra**: $30–50/Monat, ohne PIT-Garantie weiterhin Look-Ahead-Bias-Risiko, Kosten nicht im Capstone-Budget
- **Verworfen**: Bias-Problem bleibt selbst mit Bezahl-Tier ungelöst

### Option B: Quality AI mit dokumentiertem Bias behalten
- **Pro**: 5 Modelle bleiben original
- **Contra**: Backtest-Ergebnisse nicht vertrauenswürdig, Demo-Risiko (Reviewer fragt nach Restatement-Handling, wir haben keine Antwort)
- **Verworfen**: Glaubwürdigkeit > Modell-Vielfalt

### Option C: Anti-Cyclical mit Self-Built-History (jeden Run historisieren, 3J aufbauen)
- **Pro**: Pipeline-Trick, kostet nichts
- **Contra**: braucht 3 Jahre Laufzeit bis valid → in 12 Wochen nicht testbar
- **Verworfen**: scheitert an Capstone-Zeit

### Option D: Auf 4 Modelle runtergehen (nur die wirklich freien)
- **Pro**: maximaler Daten-Vertrauensgrad
- **Contra**: Quality-Pillar fällt komplett raus (kein Quality Classic), Bewertungsachse "Business-Logik & Domänenmodell" (5%) wird dünn
- **Verworfen**: Quality Classic geht mit Yahoo + FMP-Free-Snapshot zumindest annähernd, Modell-Vielfalt rechtfertigt 1 von 250 FMP-Calls/Tag

## Folgen

### Vorteile
- Alle 5 Modelle in CI deterministisch testbar (Trend Momentum + Value Alpha Potential haben reine Preis-Inputs → Golden-Datasets trivial reproduzierbar)
- Keine externen Bezahl-Subscriptions, Capstone-Budget bleibt unter $20
- Pillar-Verteilung wird Trend-lastig (×2) — bewusst akzeptiert, weil beide Trend-Modelle bewusst gegensätzlich konzipiert sind (Alpha = absolut/Sharpe-gewichtet, Trend Momentum = relativ/EWMA)

### Nachteile
- ML-Modell (Lasso) fällt raus → 40%-Achse muss diesen Verlust durch Layer 2 (Multi-Agent) und Layer 3 (MCP) kompensieren
- Risk-Pillar nur noch durch Diversification abgedeckt (×1 statt potenziell ×2)
- Mean-Reversion-Logik (Value Alpha Potential) kann Junk-Stocks hoch ranken — Master-Rank-Aggregation muss das durch Quality + Diversification austarieren

### Migration
- ✅ Spec `docs/specs/2026-04-27-quant-models-redesign.md` (commit `7f93095`)
- ⏳ Update `docs/specs/2026-04-21-prisma-capstone-design.md` §6/§7/§8.1/§13/§18/§19
- ⏳ Update `docs/specs/2026-04-28-narrative-engine.md` §5.2/§10.2
- ⏳ Update `docs/specs/2026-04-28-mcp-server.md` §4.1/§4.3
- ⏳ Update `README.md` Z.11, `frontend/app/page.tsx` Z.19
- ⏳ Skeleton-Domain-Code in `backend/domain/models/` + leere TDD-Tests
- ⏳ env-Migration `FINNHUB_API_KEY` → `FMP_API_KEY` in `.env`-Template

### Reversibel?
Ja. Falls nach Wochen 5–6 ein Bezahl-Datenfeed verfügbar wird (Sponsoring, Nachverhandlung), können Quality AI / Anti-Cyclical via Spec-Update + ADR-Supersedes wieder rein. Beide standen bis 2026-04-27 schon ausformuliert in der Design-Spec.

## Referenzen
- Spec: `docs/specs/2026-04-27-quant-models-redesign.md`
- Original-Design: `docs/specs/2026-04-21-prisma-capstone-design.md` §6, §19
- PR: #26
- Daten-Feasibility-Check: agent-recherche dokumentiert in PR-Diskussion
