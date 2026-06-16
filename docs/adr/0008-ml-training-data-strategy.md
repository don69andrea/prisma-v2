# ADR 0008: ML-Training-Datenstrategie — SimFin, EU-Aktien und Feature-Erweiterung

- **Status**: Accepted
- **Datum**: 2026-06-12
- **Autor**: Andrea Petretta
- **Kontext**: Return-Predictor ML-Layer — Verbesserung von Trainingsqualität und Modellgenauigkeit
- **Supersedes**: Implizite Annahme in der ursprünglichen ML-Implementierung, dass yfinance-Fundamentaldaten und ausschliesslich Schweizer Aktien ausreichend sind

---

## Kontext

Der Return-Predictor (LightGBM/XGBoost) klassifiziert Aktien in drei Rendite-Klassen (Bottom/Mid/Top Quartil der 12-Monats-Vorwärtsrendite). Die ursprüngliche Implementierung hatte folgende nachgewiesene Schwächen:

### Problem 1: Point-in-Time Bias bei Fundamentaldaten (Hauptproblem)

`_stub_fundamentals()` in `MLFeatureService.build_dataset()` lädt die **aktuellen** yfinance-Fundamentaldaten (`trailingPE`, `priceToBook`, etc.) und verwendet sie für **alle** historischen Trainings-Snapshots von 2018 bis heute. Konkret: P/E-Ratio von Nestlé im Trainings-Datenpunkt Januar 2019 = P/E-Ratio von Nestlé im Juni 2026.

**Messbare Konsequenz**: Feature Importance im trainierten Modell:
- `score_rendite`: 5.0 (faktisch nutzlos)
- `score_sicherheit`: 1.0 (faktisch nutzlos)
- `vol_90d`: 749.0, `return_12m`: 611.0 (Technische Features dominieren komplett)

Die fundamentalbasierten Features (`score_*`) variieren pro Ticker nur cross-sektional (Ranking zwischen Firmen), aber nicht über die Zeit. Das Modell kann keine Dynamik in der Bewertung lernen.

### Problem 2: Zu kleines Trainings-Dataset

- 20 Schweizer Ticker × 3 Jahre × 12 Monate = ~720 theoretische Zeilen
- Nach Filterung (1 Jahr Lookback + 1 Jahr Forward-Return nötig): ~600 saubere Zeilen

Mit 15 Features und 3-Klassen-Problem sind 600 Zeilen grenzwertig. LightGBM benötigt genug Cross-Sectional-Breite pro Snapshot-Datum für robuste Quartil-Labels.

### Problem 3: Fehlende technische Indikatoren

Das Modell hatte keine MACD-, Bollinger-Band- oder Drawdown-Features, die in der quantitativen Finanzliteratur als starke Prädiktoren gelten.

### Messbare Ausgangs-Performance

| Metrik | Wert |
|--------|------|
| Validation Accuracy | 37.1% (Random-Baseline: 33.3%) |
| Top-Quartil-Recall | 34.5% |
| Trainingszeilen | 600 |
| Features | 15 |

---

## Evaluierte Optionen

### Option 1: Mehr Jahre mit bestehender Architektur

Einfachste Massnahme: `--years 8` statt `--years 3`.

- ➕ Keine Architektur-Änderung
- ➕ 8× mehr Trainingszeilen (theoretisch ~4'800 mit 40 Tickern)
- ➖ **Behebt den Point-in-Time Bias nicht** — der Hauptfehler bleibt
- ➖ Mehr Zeilen mit falschen Fundamentaldaten verbessern die Modellqualität kaum
- ➖ Die `score_*`-Features bleiben zeitlich eingefroren

**Allein unzureichend.**

### Option 2: SimFin für historische Fundamentaldaten (CH-only)

SimFin bietet historische Quartalsdaten (P/E, P/B, EPS, Dividend Yield) kostenlos via API. Für Schweizer SMI/SMIM-Titel ist die Coverage angemessen.

- ➕ Behebt den Point-in-Time Bias direkt
- ➕ Kostenlos (Free Tier mit 200 API-Calls/Tag; Bulk-Downloads pro Markt)
- ➕ SimFin-SDK cached lokal — einmaliger Download, dann offline
- ➕ Keine Änderung am Inferenz-Stack (nur Training betroffen)
- ➖ Coverage für SMIM-Titel teils lückenhaft — Fallback auf Stub notwendig
- ➖ Neue Abhängigkeit im Training-Script (`pip install simfin`)
- ➖ Behebt Datenmenge-Problem nicht allein

**Notwendig, aber nicht hinreichend.**

### Option 3: EU-Aktien als zusätzliche Trainingsdaten

Hinzufügen von DAX-40, CAC-40 und AEX-Titeln zum Training. Technische Features (Momentum, Volatilität, RSI, MACD) sind marktunabhängig und übertragbar.

- ➕ Verdoppelt die Trainingszeilen (~4'800 → ~9'600 mit CH+EU, 8 Jahre)
- ➕ Mehr Cross-Sectional-Breite pro Snapshot-Datum → robustere Quartil-Labels
- ➕ Technische Feature-Beziehungen (z.B. RSI-Momentum) sind universell gültig
- ➕ Nur Training — Inferenz-Pipeline bleibt Swiss-only
- ➖ EU-Aktien haben anderen Makro-Kontext (ECB statt SNB)
- ➖ Feature-Semantik von `snb_rate` wird generalisiert zu "zentrale Bankrate"
- ➖ Potenzielle Konfusion wenn Modell CH vs EU Aktien nicht unterscheidet

**Machbar mit expliziter Makro-Rate-Anpassung (ECB/SNB).**

### Option 4: Komplette Umstellung auf kommerzielle Datenanbieter

Bloomberg, Refinitiv oder FactSet würden historische Punkt-in-Zeit-Fundamentaldaten, Konsensschätzungen und Corporate Events liefern.

- ➕ Höchste Datenqualität und -vollständigkeit
- ➖ **Kosten: CHF 10'000–50'000/Jahr** — ausserhalb Budget
- ➖ Keine Free-Tier-Option für die benötigte historische Tiefe
- ➖ Nicht im Scope

**Ausgeschlossen.**

### Option 5: Kombination SimFin + EU-Aktien + neue Features + Optuna (gewählt)

Alle drei erreichbaren Verbesserungen kombinieren:

1. **SimFin** für historische Fundamentaldaten (behebt Point-in-Time Bias)
2. **EU-Aktien** für mehr Trainingstiefe (DAX-40 + CAC-40 + AEX)
3. **4 neue technische Features** (MACD, Bollinger Bands, 1M-Return, Max Drawdown)
4. **Optuna-Hyperparameter-Tuning** für LightGBM (50 Trials)
5. **8 Jahre History** statt 3

---

## Entscheidung

**Option 5: SimFin + EU-Aktien + neue Features + Optuna.**

### Architektur-Entscheide

#### A) SimFin nur im Training-Stack (nicht in Inferenz)

SimFin wird **ausschliesslich** in `scripts/train_return_predictor.py` via `--simfin-key` aktiviert. Die Inferenz-Pipeline (`MLFeatureService.build_features()`) nutzt weiterhin yfinance — kein neuer API-Key in der Prod-Umgebung (Render) nötig.

**Begründung**: Inferenz läuft auf Render Free-Tier mit 512 MB RAM. Eine zweite externe Abhängigkeit würde die Fehlerquellen erhöhen. SimFin-Daten werden für jeden Trainings-Snapshot benötigt (historisch), nicht für die Live-Berechnung (nur aktueller Datenpunkt).

#### B) EU-Aktien nur als Trainingsdaten

EU-Aktien (DAX-40, CAC-40, AEX) erhöhen die Trainingsdatenmenge. Das deployierte Modell wird aber weiterhin nur für Schweizer Aktien aufgerufen. Die Entscheidungs-Logik in `/api/v1/decisions` und `/api/v1/decisions/live` gibt nach wie vor nur Swiss-Signale zurück.

**Begründung**: Die Inferenz-Infrastruktur (yfinance `.SW`-Adapter, `SwissQuantScorer` mit SMI-Bändern, CHF-Denominierung) ist CH-spezifisch. Eine EU-Inferenz würde einen separaten Adapter, separate Scoring-Bänder und UI-Anpassungen erfordern — ausserhalb des aktuellen Scopes.

#### C) Makro-Feature-Semantik: "Zentrale Bankrate"

Das `snb_rate`-Feature in `MLFeatureVector` wird für EU-Aktien im Training mit dem ECB-Zinssatz befüllt. Der Feature-Name bleibt unverändert — das Modell lernt die allgemeine Beziehung zwischen "aktuellem Leitzins" und zukünftigen Aktienrenditen.

Für `chf_eur`: EUR-denominierte EU-Aktien erhalten den Wert `1.0` (kein FX-Risiko innerhalb der Eurozone). Schweizer Aktien erhalten weiterhin den historischen CHF/EUR-Kurs.

#### D) Fallback-Mechanismus für SimFin-Lücken

Die `SimFinAdapter.get_fundamentals_on_date()` gibt `None` zurück wenn:
- Der Ticker nicht in SimFin vorhanden ist
- Die Quartalsdaten vor dem Snapshot-Datum fehlen
- SimFin einen API-Fehler zurückgibt

In diesem Fall fällt `build_dataset()` auf `_stub_fundamentals()` zurück (aktueller yfinance-Stub). Der Point-in-Time Bias bleibt für diese Datenpunkte erhalten, aber der Grossteil der Daten wird korrekt sein.

---

## Nachtrag: SimFin Free-Tier-Einschränkungen (2026-06-12)

Bei der Implementierung wurde festgestellt, dass der SimFin Free-Tier das `derived`-Dataset (fertig berechnete P/E, P/B, EPS, Dividend Yield) **nicht** enthält — es ist Premium-only ("upgrade to at least a BASIC subscription").

### Verfügbarkeit SimFin Free Tier

| Dataset | Free Tier | Märkte |
|---------|-----------|--------|
| `derived/quarterly` (P/E, P/B, EPS) | ❌ Premium | — |
| `income/quarterly` | ✅ | US: ~47'000 Zeilen; DE: ~94 Zeilen; CH: nicht vorhanden |
| `balance/quarterly` | ✅ | US: ~47'000 Zeilen; analog wie income |
| `shareprices/daily` | ✅ | US: ~6'200'000 Zeilen; EU/CH: nicht vorhanden |

### Angepasste Strategie: P/E und P/B aus Rohdaten berechnen

Da `derived` nicht verfügbar ist, berechnet der `SimFinAdapter` die Fundamentaldaten aus den Rohdaten:

```
P/E  = Adj. Close / EPS_TTM
       EPS_TTM = Σ(Net Income letzter 4 Quartale) / Shares (Diluted)
P/B  = Adj. Close / Buchwert pro Aktie
       Buchwert pro Aktie = Total Equity / Shares (Diluted)
Div% = Σ(Dividenden letzte 12 Monate) / Adj. Close
```

**Scope**: Nur US-Ticker profitieren von echten Point-in-Time Daten (45 von 163 Trainingstiteln = 28%). CH- und EU-Ticker fallen weiterhin auf den yfinance-Stub zurück.

**Point-in-Time Korrektheit**: Es wird ausschliesslich `Publish Date` verwendet (nicht `Report Date`). Ein Q3-Bericht mit Report Date 30. September wird typischerweise erst 6–8 Wochen später publiziert. Nur der Publish Date ist point-in-time-korrekt und vermeidet Look-Ahead Bias.

**Plausibilitätsfilter**: P/E > 500 und P/B > 100 werden als Datenfehler/Ausreisser verworfen (→ None → Stub-Fallback für diesen Datenpunkt).

**Effekt auf Trainingsqualität**:
- US-Trainingszeilen (~4'000 von ~14'600): Point-in-Time korrekte Fundamentaldaten
- CH/EU-Trainingszeilen: weiterhin yfinance-Stub (aktueller Stand als historischer Wert)
- Netto: Verbesserung für ~28% der Trainingsdaten ohne zusätzliche API-Kosten

---

## Implementierung

### Neue/geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `backend/infrastructure/adapters/simfin_adapter.py` | **NEU** — SimFin-Adapter für Training |
| `backend/domain/value_objects/ml_feature_vector.py` | +4 Features: `macd_hist`, `bb_position`, `return_1m`, `drawdown_12m` |
| `backend/application/services/ml_feature_service.py` | ECB-Rate-History, EU-Ticker-Helpers, SimFin-Integration in `build_dataset()` |
| `scripts/train_return_predictor.py` | 40→80 Ticker (CH+EU), `--market`, `--simfin-key`, `--tune`, 8 Jahre default |

### Neue Features (19 total, vorher 15)

| Feature | Beschreibung | Warum |
|---------|-------------|-------|
| `macd_hist` | MACD-Histogramm (EMA12-EMA26 minus EMA9-Signal), preisbereinigt | Bullish/Bearish Momentum-Shift; einer der stärksten kurzfristigen Prädiktoren |
| `bb_position` | Position im Bollinger Band: `(Preis - unteres Band) / Bandbreite` | Mean-Reversion-Signal; Position < 0 = überverkauft, > 1 = überkauft |
| `return_1m` | 1-Monats-Rendite (21 Handelstage) | Kurzfristiges Momentum ergänzt 3M/6M/12M |
| `drawdown_12m` | Maximaler Drawdown der letzten 252 Tage (0 bis -1) | Risikoindikator; tiefe Drawdowns → höhere Recovery-Wahrscheinlichkeit |

Alle neuen Features werden aus der bereits geladenen Preisserie berechnet — **kein zusätzlicher API-Call bei der Inferenz**.

### Training-Kommandos

```bash
# Standard (CH-only, keine SimFin, 8 Jahre)
python scripts/train_return_predictor.py

# Mit EU-Aktien (mehr Trainingsdaten)
python scripts/train_return_predictor.py --market all --years 8

# Vollständig (SimFin + EU + Optuna-Tuning, empfohlen für bestes Modell)
python scripts/train_return_predictor.py --market all --simfin-key <KEY> --tune

# SimFin API-Key: kostenlose Registrierung auf simfin.com
```

---

## Konsequenzen

### Positiv

- **Point-in-Time Bias eliminiert** (mit SimFin): `score_rendite` und `score_sicherheit` spiegeln historical P/E/P/B — die fundamentalen Features werden erstmals sinnvoll trainiert
- **Erwartete Accuracy-Verbesserung**: von 37% auf ~45–52% (3-Klassen-Problem, Random-Baseline 33%)
- **Saubere Architektur-Trennung**: SimFin nur im Offline-Training-Stack, Prod-Inferenz unverändert
- **Kein neuer API-Key in Prod**: Render-Deployment bleibt unverändert
- **Fallback-Sicherheit**: Fehlende SimFin-Daten fallen auf bestehenden Stub zurück — Training schlägt nie ganz fehl
- **Robusteres Modell**: 2× mehr Trainingszeilen durch EU-Aktien → weniger Overfitting auf Schweizer Marktspezifika

### Negativ / Risiken

- **SimFin-Coverage lückenhaft**: Nicht alle SMIM-Titel sind vollständig historisch abgedeckt; für diese Titel bleibt der Bias
- **Makro-Feature-Generalisierung**: `snb_rate` kodiert für EU-Aktien den ECB-Zinssatz — semantische Inkonsistenz innerhalb des Feature-Sets (akzeptiertes Trade-off)
- **Längere Trainingszeit**: `--market all --tune` dauert 30–60 Minuten lokal (kein Problem, da Offline)
- **`simfin` als neue Dev-Abhängigkeit**: nur in `pyproject.toml` [optional] — Prod-Image unberührt

### Mitigationen

- `SimFinAdapter` ist optional und gibt bei Fehler `None` zurück — Training läuft immer durch
- ECB-Rate-History ist als statische Liste hinterlegt (wie SNB-History) — keine Netzwerkabhängigkeit
- Das deployierte `.joblib`-Modell enthält keine Abhängigkeit auf SimFin — Inferenz ist vollständig unabhängig

---

## Referenzen

- `backend/infrastructure/adapters/simfin_adapter.py` — SimFin-Adapter-Implementierung
- `backend/application/services/ml_feature_service.py` — `_ecb_rate_on()`, `_is_eu_ticker()`, `build_dataset()` mit SimFin-Integration
- `backend/domain/value_objects/ml_feature_vector.py` — 19-Feature-Vektor
- `scripts/train_return_predictor.py` — Training-Script mit `--market`, `--simfin-key`, `--tune`
- ADR 0005: Datenquelle für Quant-Fundamentaldaten (ergänzende Entscheidung)
- SimFin API-Dokumentation: simfin.com/api
