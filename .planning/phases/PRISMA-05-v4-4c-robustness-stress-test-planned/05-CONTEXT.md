# Phase 5: V4-4c Robustness & Stress-Test — Context

**Gathered:** 2026-06-23
**Status:** Ready for planning
**Source:** User-Brief Session-Start (Discuss-Phase via Prompt)

<domain>
## Phase Boundary

Diese Phase baut KEINE neuen Features. Sie prüft **ehrlich**, ob der V4-1-Edge (Trend + Vol-Targeting) robust ist oder fragil/überangepasst — durch eine dedizierte Robustheitsprüfung mit Harness-Skript und dokumentierten Ergebnissen.

**In-Scope:**
- `scripts/robustness_check.py` — neues Harness-Skript, das die bestehende Walk-Forward-Engine (backend/application/backtest/walkforward.py) wiederverwendent
- 4 Stress-Dimensionen (Kosten, Regime, Universum, Parameter)
- Ehrlicher Report in `docs/PRISMA_V4_FORTSCHRITT.md`
- Deterministische Tests (Look-Ahead-Guard gilt weiter)

**Out-of-Scope:**
- Kein Tuning der Parameter, um den Edge besser aussehen zu lassen
- Keine synthetischen Daten — echte yfinance-Daten oder klares Fail-Meldung
- Keine neuen REST-Endpoints, keine UI-Änderungen
- Kein Merge/complete-milestone vor "OK Execute"

</domain>

<decisions>
## Implementation Decisions

### D-01 — Kein Tuning (LOCKED — AGENTS.md Wissenschaftliche Ehrlichkeit)
Feste, a-priori Parameter. Kein nachträgliches Anpassen, um Ergebnisse zu verbessern.
Der Default-Trend-MA ist SMA(100) — dieser bleibt der Ankerpunkt; andere Fenster sind Varianten.

### D-02 — Echte Daten (LOCKED)
Yfinance-Daten aus dem bestehenden System (oder direkter yfinance-Download).
Falls Daten für einen Coin fehlen oder zu kurz sind: klar melden, NICHT synthetisch ersetzen.
Mindestlänge: min_train=252 Tage + 1 OOS-Periode; kürzere Reihen werden als "insufficient data" dokumentiert.

### D-03 — Stress-Dimension 1: Kosten-Sensitivität (LOCKED)
Three cost levels: 0.1%, 0.2%, 0.5% Round-Trip (in `costs`-Parameter: 0.001, 0.002, 0.005).
Für BTC und ETH (primär), auf Wunsch für alle 10 Coins.
Ergebnis: Sharpe/Calmar/MaxDD je Kostenstufe vs. exposure-matched Baseline.
Frage: "Überlebt der Edge höhere Kosten?"

### D-04 — Stress-Dimension 2: Regime-Splits (LOCKED)
Sub-Perioden: Bear 2018 (2018-01 bis 2018-12), Bull 2021 (2021-01 bis 2021-12),
Bear 2022 (2022-01 bis 2022-12), Bull 2023-24 (2023-01 bis 2024-12).
Je Regime: Sharpe + Calmar vs. exposure-matched Baseline.
Walk-Forward beibehalten (keine in-sample-Auswahl).
Frage: "Ist der Edge Regime-abhängig oder stabil?"

### D-05 — Stress-Dimension 3: Volles Universum (LOCKED)
Alle 10 Coins: BTC-USD, ETH-USD, BNB-USD, SOL-USD, XRP-USD, ADA-USD, AVAX-USD, MATIC-USD, DOT-USD, LINK-USD.
Pro Coin individueller Walk-Forward-Lauf + aggregierte Zusammenfassung (wie viele Coins schlagen Baseline?).
Coins mit unzureichenden Daten (<252+step Tage) werden als "insufficient" markiert, nicht synthetisch ersetzt.
Frage: "Edge nur für BTC/ETH oder breit?"

### D-06 — Stress-Dimension 4: Parameter-Stabilität (LOCKED)
Trend-Fenster: [50, 75, 100, 150, 200] für SMA (Schicht 2 Layer 1: trend_ma_signal).
Für BTC (primär), dann ETH.
Fester Ankerpunkt: 100 ist der Default (aus V4-1). Alle anderen sind Varianten.
Frage: "War 100 ein Cherry-Pick oder ist der Edge über Fenster stabil?"

### D-07 — Baselines (LOCKED)
Immer zwei Baselines gegen exposure-matched:
- Exposure-Matched: konstante Investitionsquote = Ø-Exposure der Strategie (bereits in walkforward.py)
- Buy&Hold: 100% investiert, kein Timing
Alle Ergebnisse netto nach Kosten.

### D-08 — Ehrliche Dokumentation (LOCKED — AGENTS.md)
Ergebnis in docs/PRISMA_V4_FORTSCHRITT.md, Abschnitt "V4-4c Robustheits-Harness":
- Edge-Klassifikation: robust / fragil / regime-abhängig (inkl. Begründung)
- Tabellen: eine je Stress-Dimension
- Falls fragil: klar kommunizieren, NICHT verschweigen

### D-09 — Look-Ahead-Guard (LOCKED)
Bestehendes Guard-System (backend/application/backtest/guards.py) gilt weiter.
Harness-Tests müssen deterministisch sein (kein random ohne Seed).

### D-10 — Harness-Struktur (Claude's Discretion bis auf Ziele)
- Einzelnes Skript: `scripts/robustness_check.py`
- Standalone (kein DB-Zugriff nötig, yfinance direkt)
- Ausgabe: konsolen-Tabellen + Rückgabe als dict für Tests
- Importierbar (testbar)
- Sections: KOSTEN / REGIME / UNIVERSUM / PARAMETER

### D-11 — Kein Merge, kein /gsd-complete-milestone (LOCKED — User-Instruktion)
Hartes Stopp nach dem Plan. Execute nur wenn User "OK Execute" schreibt.

### Claude's Discretion
- Interne Hilfsfunktionen für Daten-Subset nach Datumsbereich
- Logging-Format der Tabellen (pandas/tabulate/print)
- Test-Fixtures für schnelle CI-Ausführung (synthetische Preise für Unit-Tests OK, echte Daten für Integrations-Tests)
- Reihenfolge der Ausgabe in FORTSCHRITT.md

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bestehende Backtest-Engine
- `backend/application/backtest/walkforward.py` — `run_walkforward()` + `run_walkforward_with_details()`; costs-Parameter (default 0.001); min_train=252, step=63
- `backend/application/backtest/guards.py` — Look-Ahead-Guard

### Signal-Layer (Trend-MA)
- `backend/application/signals/signal_service.py` — SMA(100) für trend_ma_signal (Zeile 128); dies ist der Default-Trend-Fenster
- `backend/application/signals/indicators.py` — `sma(close, window)` Funktion
- `backend/application/signals/consensus.py` — `consensus_vote()` für 2-of-3 Voting
- `backend/application/signals/sizing.py` — `vol_target_size()`, `apply_sizing()`
- `backend/application/signals/vol_forecast.py` — Vol-Forecast-Modell

### Coin-Universum
- `backend/interfaces/rest/routers/signals.py` Zeile 60-71 — `_CRYPTO_UNIVERSE` (10 Coins): BTC-USD, ETH-USD, BNB-USD, SOL-USD, XRP-USD, ADA-USD, AVAX-USD, MATIC-USD, DOT-USD, LINK-USD

### Projekt-Regeln
- `AGENTS.md` — §1 Goldene Regeln, §8 Verbotene Patterns; insbesondere: kein API-Key im Code
- `docs/PRISMA_V4_FORTSCHRITT.md` — Ziel-Dokument für die Ergebnisse (append-only)
- `docs/PRISMA_V4_PROJEKTPLAN.md` — §6B Statistische ML-Tests (Ehrlichkeit), Baselines, Walk-Forward

### Bestehende Test-Patterns
- `backend/tests/unit/application/test_signal_engine.py` — Beispiel für Walkforward-Tests mit synthetischen Preisen

</canonical_refs>

<specifics>
## Specific Ideas

### Regime-Perioden (konkret)
- Bear 2018: 2018-01-01 bis 2018-12-31 (BTC -73%, klassischer Bärenmarkt)
- Bull 2021: 2021-01-01 bis 2021-12-31 (BTC ATH $69k)
- Bear 2022: 2022-01-01 bis 2022-12-31 (BTC -65%, Terra/Luna, FTX)
- Bull 2023-24: 2023-01-01 bis 2024-12-31 (BTC ETF-Boom, Halving)

### Trend-Fenster (konkret)
[50, 75, 100, 150, 200] — SMA in der consensus_vote-Logik

### Kosten-Stufen (konkret)
- Niedrig: 0.001 (0.1% RT, Default V4-1)
- Mittel: 0.002 (0.2% RT)
- Hoch: 0.005 (0.5% RT, konservative Annahme)

### Erwartetes Ergebnis-Format in FORTSCHRITT.md
Tabelle je Stress-Dimension:

| Kostenstufe | Sharpe (Strat) | Sharpe (ExpMatch) | Calmar (Strat) | Calmar (ExpMatch) | Edge? |
Tabelle Regime / Universum / Parameter ähnlich.

Abschluss: "Edge-Klassifikation: robust / fragil / regime-abhängig"

</specifics>

<deferred>
## Deferred Ideas

- Minuten-Daten für robustere Vol-Schätzung (→ V4-6 oder später)
- Bootstrap-Konfidenzintervalle für Sharpe (optional, falls Zeit)
- Direkte DB-Integration (aktuell: standalone mit yfinance)

</deferred>

---

*Phase: PRISMA-05-v4-4c-robustness-stress-test-planned*
*Context gathered: 2026-06-23 via User-Brief (Session-Start Prompt)*
