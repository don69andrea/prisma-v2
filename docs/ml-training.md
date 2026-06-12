# ML-Training: Return Predictor

**Letzte Aktualisierung:** 2026-06-12  
**Modell-Version:** `return_predictor_lightgbm_20260612_175826.joblib`  
**Autoren:** Andrea Petretta

---

## Inhaltsverzeichnis

1. [Überblick](#1-überblick)
2. [Architektur der Trainingspipeline](#2-architektur-der-trainingspipeline)
3. [Feature Engineering](#3-feature-engineering)
4. [Trainings-Universum](#4-trainings-universum)
5. [Makro-Features und Markt-Routing](#5-makro-features-und-markt-routing)
6. [Fundamentaldaten: SimFin-Integration](#6-fundamentaldaten-simfin-integration)
7. [Walk-Forward-Validierung](#7-walk-forward-validierung)
8. [Modellauswahl und Hyperparameter](#8-modellauswahl-und-hyperparameter)
9. [Ergebnisentwicklung](#9-ergebnisentwicklung)
10. [Training ausführen](#10-training-ausführen)
11. [Produktions-Deployment](#11-produktions-deployment)
12. [Bekannte Einschränkungen](#12-bekannte-einschränkungen)
13. [Nächste Schritte](#13-nächste-schritte)

---

## 1. Überblick

Der **Return Predictor** ist ein ML-Klassifikator, der Aktien in drei Rendite-Klassen einteilt:

| Klasse | Bedeutung | Signal in der App |
|--------|-----------|-------------------|
| `2` (Top) | Oberstes Quartil der 12M-Vorwärtsrendite | `OUTPERFORM` |
| `1` (Mid) | Mittlere 50% | `NEUTRAL` |
| `0` (Bottom) | Unterstes Quartil | `UNDERPERFORM` |

Das Modell wird **offline** auf einem MacBook trainiert und als `.joblib`-Artifact in `models/` eingecheckt. Render lädt das Artifact beim Startup. Die Inferenz läuft in Echtzeit für jeden `/api/v1/decisions`-Request.

### Aktuelle Modellperformance

| Metrik | Random Baseline | v1 (CH-only, 3J) | v2 (CH+EU+US, 8J) | v3 (+ SimFin) |
|--------|----------------|-------------------|---------------------|---------------|
| Accuracy | 33.3% | 37.1% | 43.1% | 41.1% |
| **Top-Quartil-Recall** | 33.3% | 34.5% | 50.2% | **61.4%** |
| Trainingszeilen | — | ~600 | 14'665 | 14'665 |
| Features | — | 15 | 19 | 19 |
| Bestes Modell | — | LightGBM | XGBoost | LightGBM |

**Top-Quartil-Recall** ist die primäre Metrik: Wie viele der tatsächlichen Top-Quartil-Aktien identifiziert das Modell korrekt? Für ein Stock-Picking-System ist das relevanter als Gesamt-Accuracy.

---

## 2. Architektur der Trainingspipeline

```
scripts/train_return_predictor.py
    │
    ├── Ticker-Auswahl (--market ch|eu|us|all)
    │       CH: SMI-20 + SMIM (40 Ticker)
    │       EU: DAX + CAC + AEX + FTSE + IBEX + MIB + OMX (86 Ticker)
    │       US: S&P500 Mega/Large Caps (45 Ticker)
    │
    ├── MLFeatureService.build_dataset()
    │       │
    │       ├── yfinance.download(ticker, 9 Jahre)
    │       │       Preishistorie: Close, Volume
    │       │
    │       ├── SimFinAdapter.get_fundamentals_on_date()  [US: echte Daten]
    │       │   └── _stub_fundamentals()                  [CH/EU: aktueller yfinance-Stand]
    │       │
    │       ├── SwissQuantScorer.score()
    │       │       Berechnet 5 Quant-Scores aus Fundamentaldaten
    │       │
    │       └── Monatliche Snapshots (Monatsanfänge)
    │               Pro Snapshot: 19 Features + Forward-Return-Label
    │
    ├── Walk-Forward-Split (letzte 12 Monate = Validation)
    │
    ├── Modelltraining
    │       ├── XGBoost (n_estimators=200, max_depth=4)
    │       └── LightGBM (n_estimators=200, num_leaves=15)
    │
    ├── Modell-Selektion (höchster Top-Quartil-Recall gewinnt)
    │
    └── models/return_predictor_latest.joblib  →  Render Free-Tier
```

### Zeitliche Struktur eines Trainings-Snapshots

```
|← Lookback-Window (252+ Tage) →|  snap_date  |← Forward-Window (252 Tage) →|
                                       │
                                 Feature-Vektor:
                                 - Technische Features aus Lookback-Preisen
                                 - Fundamentaldaten: Stand am snap_date
                                   (SimFin: Publish Date ≤ snap_date)
                                       │
                                 Target-Label:
                                 Return 252 Handelstage nach snap_date
                                 → Quartil-Klasse (0/1/2)
```

---

## 3. Feature Engineering

### 3.1 Feature-Vektor (19 Features)

Alle Features befinden sich in `backend/domain/value_objects/ml_feature_vector.py`.

#### Quant-Scores (5 Features)

Berechnet durch `SwissQuantScorer` aus Fundamentaldaten. Skala: 0–10.

| Feature | Berechnung | Quelle |
|---------|-----------|--------|
| `quant_score` | Komposit-Score (gewichteter Durchschnitt) | SwissQuantScorer |
| `score_rendite` | Dividend Yield + EPS-Wachstum | Fundamentaldaten |
| `score_sicherheit` | Niedrige Volatilität + stabile Bilanz | Fundamentaldaten |
| `score_wachstum` | EPS-Wachstum + Umsatzwachstum | Fundamentaldaten |
| `score_substanz` | P/B + P/E vs. Sektordurchschnitt | Fundamentaldaten |

#### Technische Features (12 Features)

Alle aus der Preishistorie berechnet, **kein zusätzlicher API-Call** bei Inferenz.

| Feature | Berechnung | Interpretation |
|---------|-----------|----------------|
| `return_12m` | `(P_t / P_{t-252}) - 1` | Jahres-Momentum |
| `return_6m` | `(P_t / P_{t-126}) - 1` | Halbjahres-Momentum |
| `return_3m` | `(P_t / P_{t-63}) - 1` | Quartals-Momentum |
| `return_1m` | `(P_t / P_{t-21}) - 1` | Kurzfrist-Momentum |
| `vol_30d` | Annualisierte Std-Abw. der Tagesrenditen (30T) | Aktuelle Volatilität |
| `vol_90d` | Annualisierte Std-Abw. der Tagesrenditen (90T) | Strukturelle Volatilität |
| `rsi_14` | Relative Strength Index (14 Perioden) | Overbought/Oversold |
| `price_to_52w_high` | `P_t / max(P_{t-252..t})` | Nähe zum Jahreshoch |
| `vol_trend` | `mean(Volume_{t-20}) / mean(Volume_{t-60})` | Volumen-Momentum |
| `macd_hist` | `(EMA12 - EMA26 - EMA9) / P_t` | Momentum-Shift (normiert) |
| `bb_position` | `(P_t - BB_lower) / (BB_upper - BB_lower)` | Bollinger-Band-Position |
| `drawdown_12m` | `min((P_t / max(P_{t..t-252})) - 1)` | Max. Drawdown, Bereich [−1, 0] |

Alle Momentum-Features sind **price-normalized** oder **dimensionslos** — das Modell ist dadurch preisunabhängig und kann Aktien mit sehr unterschiedlichen Kursniveaus vergleichen.

#### Makro-Features (2 Features)

| Feature | Berechnung | Details |
|---------|-----------|---------|
| `snb_rate` | Zentralbank-Leitzins zum Snapshot-Datum | SNB für CH, ECB für EU, Fed für US |
| `chf_eur` | FX-Kurs zum Snapshot-Datum | CHF/EUR für CH; 1.0 für EUR-Zone; USD/CHF für US; GBP/CHF für UK |

Die Makro-Historien sind als statische Listen im Code hinterlegt (keine Netzwerkabhängigkeit beim Training). Quellen: SNB, ECB, Fed (alle öffentlich verfügbar).

### 3.2 Feature-Berechnung bei Inferenz vs. Training

| | Training (`build_dataset`) | Inferenz (`build_features`) |
|--|--------------------------|----------------------------|
| Preishistorie | yfinance, 9 Jahre Download | yfinance, 400 Tage Download |
| Fundamentaldaten | SimFin (US) + yfinance-Stub (CH/EU) | yfinance-Stub (aktuell) |
| Snapshot-Zeitpunkt | Historisch (Monatsanfänge) | Heute |
| Forward-Return | Verfügbar (12M) → Label | Nicht verfügbar → None |

### 3.3 Target-Label

```python
fwd_ret = (price_in_252_days / price_today) - 1

# Cross-sectional Quartil pro Snapshot-Datum:
target_class = pd.qcut(fwd_ret_per_snapshot, q=[0, 0.25, 0.75, 1.0], labels=[0, 1, 2])
```

Die Quartil-Grenzen werden **pro Snapshot-Datum** berechnet (cross-sectional, nicht über die Zeit). Das stellt sicher, dass jedes Datum gleichviele Klasse-0, Klasse-1 und Klasse-2-Labels hat — unabhängig davon, ob es ein Bullen- oder Bärenmarktjahr war.

---

## 4. Trainings-Universum

### 4.1 Tickers nach Markt

| Markt | Anzahl | Index/Quelle | yfinance-Format |
|-------|--------|-------------|-----------------|
| **CH** | 40 | SMI-20 + SMIM Mid Caps | `NESN.SW`, `NOVN.SW` |
| **EU/DE** | 20 | DAX-40 Hauptwerte | `SAP.DE`, `SIE.DE` |
| **EU/FR** | 15 | CAC-40 Hauptwerte | `OR.PA`, `MC.PA` |
| **EU/NL** | 8 | AEX Hauptwerte | `ASML.AS`, `HEIA.AS` |
| **EU/UK** | 15 | FTSE-100 Hauptwerte | `AZN.L`, `SHEL.L` |
| **EU/ES** | 10 | IBEX-35 Hauptwerte | `SAN.MC`, `IBE.MC` |
| **EU/IT** | 10 | FTSE MIB Hauptwerte | `ENI.MI`, `ENEL.MI` |
| **EU/SE** | 8 | OMX Stockholm Hauptwerte | `ERIC-B.ST`, `VOLV-B.ST` |
| **US** | 45 | S&P500 Mega/Large Caps | `AAPL`, `MSFT`, `NVDA` |
| **Total** | **171** | — | — |

### 4.2 Warum EU- und US-Aktien im Training?

Das Modell lernt hauptsächlich **technische Muster** (Momentum, Volatilität, RSI, MACD, Bollinger Bands). Diese Muster sind **marktunabhängig** — Momentum-Anomalien funktionieren in jedem liquiden Markt ähnlich.

Mit nur 40 CH-Tickern und 8 Jahren = ~3'600 Trainingszeilen. Mit 163 Tickern = ~14'665 Zeilen. Mehr Cross-Sectional-Breite pro Snapshot-Datum macht die Quartil-Labels robuster und reduziert Overfitting auf Schweizer Marktspezifika.

**Wichtig:** Das Modell wird **ausschliesslich für Schweizer Aktien** im Prod-Betrieb verwendet. EU/US-Ticker sind reine Trainingsbehelfe.

### 4.3 Delisted / nicht verfügbare Ticker

Einige Ticker in der Liste sind delisted oder haben ungenügende yfinance-Daten. Das Training überspringt diese automatisch (`Zu wenig Daten für X, überspringe`). Betroffen:

- **CH**: HELN, DUFN, SOFN, CSGN (Credit Suisse, delisted 2023), MBTN
- **NL**: ING.AS, DSM.AS (Preishistorie nicht verfügbar via yfinance)
- **IT**: STM.MI (volatil, rate-limited)

Effektiv im Training: **163 von 171** Tickern (Stand 2026-06-12).

---

## 5. Makro-Features und Markt-Routing

### 5.1 Zentralbank-Leitzins (`snb_rate`-Feature)

Das Feature `snb_rate` im `MLFeatureVector` kodiert je nach Markt einen anderen Zinssatz. Das Modell lernt die allgemeine Beziehung "Leitzins → Aktienrendite".

```python
# ml_feature_service.py
"snb_rate": (
    _fed_rate_on(snap_date) if _market == "us"
    else _ecb_rate_on(snap_date) if _market == "eu"
    else _snb_rate_on(snap_date)
),
```

Alle drei Historien (`_SNB_RATE_HISTORY`, `_ECB_RATE_HISTORY`, `_FED_RATE_HISTORY`) sind als statische Listen im Code hinterlegt — keine API-Abhängigkeit beim Training.

### 5.2 FX-Kurs (`chf_eur`-Feature)

Das Feature `chf_eur` kodiert das FX-Risiko aus Sicht eines CHF-Investors.

| Markt | Suffix | Wert | Begründung |
|-------|--------|------|-----------|
| CH | `.SW` | Historischer CHF/EUR-Kurs | Primäres Exposure |
| EU/EUR-Zone | `.DE`, `.PA`, `.AS`, `.MC`, `.MI` | `1.0` | Kein FX-Risiko innerhalb Eurozone (relativ zu EUR) |
| UK | `.L` | Historischer GBP/CHF-Kurs | GBP-denominiert |
| Schweden | `.ST` | `0.094` (approx. SEK/CHF) | SEK-denominiert |
| US | — | Historischer USD/CHF-Kurs | USD-denominiert |

FX-Historien (`_chf_eur_on`, `_usd_chf_on`, `_gbp_chf_on`) sind ebenfalls als statische Lookup-Tabellen implementiert.

---

## 6. Fundamentaldaten: SimFin-Integration

### 6.1 Das Point-in-Time Problem

Ohne SimFin lädt `_stub_fundamentals()` die **aktuellen** yfinance-Fundamentaldaten (P/E, P/B, EPS) und verwendet sie für **alle** historischen Trainings-Snapshots. Das ist methodisch falsch:

```
Problem: P/E von AAPL im Trainings-Snapshot Januar 2020 = P/E von AAPL im Juni 2026
         → Das Modell lernt keine zeitliche Dynamik in Bewertungen
         → score_rendite, score_sicherheit werden faktisch nutzlose Features
```

**Messbare Konsequenz (v1, CH-only):**
- `score_rendite` Feature Importance: **5.0** (praktisch Rauschen)
- `vol_90d` Feature Importance: **749.0** (dominiert alles)
- Technische Features erklärten 95%+ des Modells, Fundamentals ~5%

### 6.2 SimFin Free-Tier-Realität

Das `derived`-Dataset von SimFin (fertig berechnete P/E, P/B, EPS) ist **Premium-only**. Der Free Tier bietet:

| Dataset | Free Tier | Coverage |
|---------|-----------|----------|
| `income/quarterly` | ✅ | US: ~47'000 Zeilen; DE: ~94 Zeilen; CH: nicht vorhanden |
| `balance/quarterly` | ✅ | US: ~47'000 Zeilen; analog wie income |
| `shareprices/daily` | ✅ | US: ~6'200'000 Zeilen; EU/CH: nicht vorhanden |
| `derived/quarterly` | ❌ Premium | — |

### 6.3 Lösung: Eigenberechnung aus Rohdaten (US)

Der `SimFinAdapter` (`backend/infrastructure/adapters/simfin_adapter.py`) berechnet P/E, P/B, EPS und Dividendenrendite selbst:

```
P/E  = Adj. Close / EPS_TTM
       EPS_TTM = Σ(Net Income (Common) letzte 4 Quartale) / Shares (Diluted)

P/B  = Adj. Close / Buchwert pro Aktie
       Buchwert = Total Equity / Shares (Diluted)

Div% = Σ(Dividenden letzte 12 Monate) / Adj. Close
```

**Point-in-Time Korrektheit:**  
Für jeden historischen Snapshot wird ausschliesslich `Publish Date` verwendet (nicht `Report Date`). Ein Quartalsbericht mit Report Date 30. September wird typischerweise erst 4–6 Wochen später publiziert. Nur ab `Publish Date` war die Information am Markt verfügbar.

**Plausibilitätsfilter:**  
- P/E > 500 → `None` (Ausreisser / negativer EPS durch Sondereffekte)
- P/B > 100 → `None` (Datenfehler)
- In diesen Fällen: Fallback auf `_stub_fundamentals()`

### 6.4 Scope und Auswirkung

| | CH-Ticker (40) | EU-Ticker (86) | US-Ticker (45) |
|-|----------------|----------------|----------------|
| SimFin-Coverage | Nicht vorhanden | Zu spärlich | Vollständig |
| Fundamentaldaten-Quelle | yfinance-Stub | yfinance-Stub | SimFin Point-in-Time |
| Point-in-Time korrekt | ❌ | ❌ | ✅ |

~28% der Trainingszeilen (US-Anteil) profitieren von echten historischen Fundamentaldaten. CH- und EU-Trainingszeilen verwenden weiterhin den aktuellen yfinance-Stand als Näherung.

### 6.5 Lazy-Loading und Caching

Der Adapter lädt die drei US-Datasets (income, balance, shareprices) **einmalig** beim ersten US-Ticker-Aufruf und hält sie im Speicher. Die ~6'200'000 Preiszeilen werden nach Ticker gruppiert (`dict[str, pd.DataFrame]`) für O(1)-Lookup bei jedem Snapshot.

```
Erster US-Ticker-Aufruf:  ~45s (Download + Gruppierung)
Alle weiteren US-Aufrufe:  ~0ms (In-Memory-Lookup)
```

---

## 7. Walk-Forward-Validierung

```
Gesamte Zeitreihe (8 Jahre, Monatsanfänge):
│────────────────────────────────────── Train ──────────────────────────────────│── Val ──│
                                                                                 ↑
                                                                         cutoff = max_date - 12M

Train: 12'709 Zeilen
Val:    1'956 Zeilen (letzte 12 Monate)
```

Die letzten 12 Monate der Zeitreihe dienen als Validation-Set. Das simuliert das reale Szenario: das Modell wird auf historischen Daten trainiert und auf zukünftigen Daten evaluiert (kein Data Leakage durch Cross-Validation).

**Primäre Metrik:** Top-Quartil-Recall (`= korrekt identifizierte Top-Aktien / alle echten Top-Aktien`)  
**Sekundäre Metrik:** Gesamt-Accuracy (3-Klassen)

---

## 8. Modellauswahl und Hyperparameter

### 8.1 Kandidaten-Modelle

Beide Modelle werden trainiert. Das Modell mit höherem Top-Quartil-Recall auf dem Validation-Set gewinnt.

#### XGBoost (Standard-Konfiguration)

```python
XGBClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    objective="multi:softmax",
    num_class=3,
    random_state=42,
)
```

#### LightGBM (Standard-Konfiguration)

```python
LGBMClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_samples=10,
    num_leaves=15,
    objective="multiclass",
    num_class=3,
    class_weight="balanced",
    random_state=42,
)
```

`class_weight="balanced"` bei LightGBM kompensiert die leichte Klassen-Ungleichheit (Bottom-Klasse hat oft etwas mehr Samples als Top-Klasse).

### 8.2 Optuna Hyperparameter-Tuning (optional)

Mit `--tune` startet eine Optuna-Studie (50 Trials, TPE-Sampler) für LightGBM. Die Zielfunktion ist der negative Top-Quartil-Recall.

**Suchraum:**

| Hyperparameter | Bereich |
|----------------|---------|
| `n_estimators` | 100–600 |
| `max_depth` | 3–8 |
| `num_leaves` | 15–63 |
| `learning_rate` | 0.01–0.15 (log-uniform) |
| `subsample` | 0.5–1.0 |
| `colsample_bytree` | 0.5–1.0 |
| `min_child_samples` | 5–40 |
| `reg_alpha` | 1e-8–1.0 (log-uniform) |
| `reg_lambda` | 1e-8–1.0 (log-uniform) |

---

## 9. Ergebnisentwicklung

### 9.1 Iterationen

**v1 — Ausgangszustand (CH-only, 15 Features, 3 Jahre)**
- 20 CH-Ticker × 3 Jahre × 12 Monate ≈ 600 Trainingszeilen
- Feature Importance: technische Features dominieren 95%+
- Fundamentals (score_rendite, score_sicherheit) sind faktisch Rauschen
- Top-Quartil-Recall: **34.5%** (kaum besser als Zufall)

**v2 — Datenmenge (CH+EU+US, 19 Features, 8 Jahre)**
- 163 Ticker × 8 Jahre × 12 Monate ≈ 14'665 Zeilen
- 4 neue Features: `macd_hist`, `bb_position`, `return_1m`, `drawdown_12m`
- Markt-aware Makro: SNB/ECB/Fed je nach Markt
- Top-Quartil-Recall: **50.2%** (+15.7 Prozentpunkte)

**v3 — SimFin Point-in-Time (aktuelle Version)**
- Gleiche Datenmenge, aber US-Fundamentaldaten historisch korrekt
- P/E, P/B, EPS aus income/balance/shareprices berechnet (Publish-Date-korrekt)
- Top-Quartil-Recall: **61.4%** (+11.2 Prozentpunkte vs. v2, +26.9 vs. v1)

### 9.2 Aktuelle Feature Importance (v3, LightGBM)

Top-5 nach split-basierter Importance:

| Rang | Feature | Importance | Interpretation |
|------|---------|-----------|----------------|
| 1 | `drawdown_12m` | 1086 | Stärkster Prädiktor: Aktien mit tiefem Drawdown erholen sich |
| 2 | `return_12m` | 692 | 12M-Momentum (klassischer Faktor) |
| 3 | `vol_90d` | 653 | Strukturelle Volatilität (Risikoindikator) |
| 4 | `return_6m` | 510 | Halbjahres-Momentum |
| 5 | `snb_rate` | 501 | Makro-Regime ist signifikant |

Fundamentals (`score_*`) sind jetzt für US-Snapshots korrekt historisch — ihre Importance steigt in Zukunft weiter wenn mehr SimFin-Coverage aktiviert wird.

---

## 10. Training ausführen

### Voraussetzungen

```bash
# Python-Pakete (in bestehendem Environment)
pip install lightgbm xgboost yfinance simfin joblib numpy pandas scikit-learn

# Aus dem Projekt-Root
cd /path/to/prisma-v2
```

### Kommandos

```bash
# Standard: nur CH-Ticker, 8 Jahre (schnell, ~5 Minuten)
python scripts/train_return_predictor.py

# Volles Universum: CH + EU + US, 8 Jahre, SimFin (~25 Minuten)
python scripts/train_return_predictor.py --market all --years 8 \
    --simfin-key b0f8e6ee-7dca-4ff4-96c0-799a9503cd00

# Mit Optuna-Tuning (~60 Minuten, empfohlen für bestes Modell)
python scripts/train_return_predictor.py --market all --years 8 \
    --simfin-key b0f8e6ee-7dca-4ff4-96c0-799a9503cd00 --tune

# Nur Dataset bauen, kein Training (für Debugging)
python scripts/train_return_predictor.py --market all --dry-run

# Einzelne Ticker
python scripts/train_return_predictor.py --tickers NESN NOVN ROG UBSG --years 5
```

### Argumente

| Argument | Default | Beschreibung |
|----------|---------|-------------|
| `--market` | `ch` | `ch`, `eu`, `us`, oder `all` |
| `--years` | `8` | Jahre historischer Daten |
| `--simfin-key` | `None` | SimFin API-Key (kostenlos: simfin.com) |
| `--tune` | `False` | Optuna Hyperparameter-Suche (50 Trials) |
| `--dry-run` | `False` | Nur Dataset bauen, kein Modell trainieren |
| `--tickers` | SMI+SMIM | Explizite Ticker-Liste (überschreibt `--market`) |

### Laufzeit-Erwartungen

| Konfiguration | Laufzeit | Einschränkung |
|---------------|----------|---------------|
| `--market ch` | ~5 Min | yfinance Rate-Limiting |
| `--market all` | ~20 Min | SimFin US-Download (einmalig ~45s) |
| `--market all --tune` | ~60 Min | Optuna 50 Trials |

**yfinance Rate-Limiting:** Yahoo Finance drosselt bei wiederholten Anfragen (typischerweise nach 2–3 aufeinanderfolgenden Trainingsläufen). Fehlermeldung: `YFRateLimitError: Too Many Requests`. Die Tickers werden dann automatisch übersprungen. Lösung: 30–60 Minuten warten vor dem nächsten Trainingslauf.

### SimFin-Erstnutzung

Beim ersten Lauf mit `--simfin-key` werden die US-Datasets heruntergeladen und lokal gecacht:

```
~/.simfin_cache/us-income-quarterly.csv   (~15 MB)
~/.simfin_cache/us-balance-quarterly.csv  (~15 MB)
~/.simfin_cache/us-shareprices-daily.csv  (~200 MB)
```

Ab dem zweiten Lauf werden die Caches genutzt (kein Re-Download). Der Cache hat kein automatisches Ablaufdatum — bei Bedarf manuell löschen.

### Output

```
models/
├── return_predictor_latest.joblib          # Symlink auf bestes Modell
├── return_predictor_latest.json            # Metadaten (Accuracy, Features, Datum)
├── return_predictor_xgboost_YYYYMMDD_HHMMSS.joblib
└── return_predictor_lightgbm_YYYYMMDD_HHMMSS.joblib
```

Die JSON-Metadaten enthalten:

```json
{
    "model_type": "lightgbm",
    "trained_at": "20260612_175826",
    "accuracy": 0.411,
    "top_quartile_recall": 0.614,
    "n_features": 19,
    "feature_names": ["quant_score", "score_rendite", ...],
    "tickers": ["NESN", "NOVN", ...]
}
```

---

## 11. Produktions-Deployment

### Modell-Deployment-Prozess

Das Modell wird **manuell über das Render-Dashboard** deployt. Ein CLI-Deployment hat sich nicht bewährt (Authentifizierungsprobleme).

**Schritte:**

1. Neues Modell trainieren (lokaler Trainingslauf)
2. `models/return_predictor_latest.joblib` committen und pushen:
   ```bash
   git add models/return_predictor_latest.joblib models/return_predictor_latest.json
   git commit -m "feat: retrain model — recall XX%"
   git push
   ```
3. **Render Dashboard** → Service `prisma-v2-backend` → **Manual Deploy**

### Kritischer Hinweis: Feature-Shape-Kompatibilität

Das `.joblib`-Modell ist auf eine bestimmte Anzahl Features trainiert. Wenn `MLFeatureVector.FEATURE_NAMES` geändert wird (neue Features hinzugefügt oder entfernt), **muss** das Modell neu trainiert werden, **bevor** der neue Code deployt wird.

Aktuell: **19 Features**. Ein Mismatch führt zu einem `ValueError: X has X features but model was fitted with Y features` im Prod-Betrieb.

**Deployment-Reihenfolge bei Feature-Änderungen:**
```
1. Features in MLFeatureVector + ml_feature_service.py ändern
2. Training ausführen → neues .joblib
3. BEIDE zusammen committen und deployen (Code + Modell)
   → nie Code ohne passendes Modell oder Modell ohne passenden Code deployen
```

### Render Free-Tier Constraints

- **RAM:** 512 MB — das Modell (~1 MB `.joblib`) ist unproblematisch
- **CPU:** Shared — Inferenz dauert <100ms pro Request
- **Concurrency:** `asyncio.Semaphore(4)` begrenzt parallele yfinance-Calls

---

## 12. Bekannte Einschränkungen

### Point-in-Time Bias (CH + EU, ~72% der Trainingszeilen)

CH- und EU-Ticker verwenden weiterhin aktuelle yfinance-Fundamentaldaten für alle historischen Snapshots. Das bedeutet: P/E von Nestlé im Trainings-Snapshot 2019 = heutiger P/E von Nestlé. Das Modell kann keine zeitliche Dynamik in Bewertungen für diese Titel lernen.

**Auswirkung:** `score_rendite` und `score_sicherheit` variieren für CH/EU-Ticker nur cross-sektional (zwischen Firmen), nicht über die Zeit.

**Lösung:** SimFin Premium ($10–20/Monat) würde das `derived`-Dataset für alle Märkte liefern. Alternativ: eigene Berechnung aus income/balance für EU (sobald SimFin ausreichende EU-Coverage hat).

### SimFin Historik-Tiefe (US)

SimFin US income/balance-Daten starten typischerweise ~2019. Snapshots vor 2019 fallen für US-Ticker auf den yfinance-Stub zurück.

### Delisted Ticker in der Liste

~8 Ticker in der Default-Liste sind delisted (CSGN, HELN, ING.AS etc.). Sie werden beim Training automatisch übersprungen aber erzeugen Log-Warnungen.

### yfinance Rate-Limiting

Bei 3+ aufeinanderfolgenden Trainingsläufen drosselt Yahoo Finance. Betrifft ~5–10 Ticker pro Lauf. Workaround: 30–60 Minuten Pause zwischen Läufen.

---

## 13. Nächste Schritte

| Priorität | Massnahme | Erwartete Verbesserung |
|-----------|-----------|------------------------|
| Hoch | SimFin Premium für CH/EU `derived`-Daten | +5–10% Top-Quartil-Recall |
| Mittel | Optuna-Tuning (`--tune`) für aktuelles Modell | +2–5% |
| Mittel | Sektor-Feature hinzufügen (Tech/Finance/Health etc.) | Modell lernt Sektor-Rotation |
| Niedrig | Quartals-Rebalancing der Snapshot-Dates | Weniger zeitliche Korrelation |
| Niedrig | Ensemble (XGBoost + LightGBM + Random Forest) | Robustere Vorhersagen |

---

*Dieses Dokument wird bei jedem signifikanten Trainingslauf aktualisiert. Entscheidungen zu Datenquellen und Architektur sind in `docs/adr/0008-ml-training-data-strategy.md` dokumentiert.*
