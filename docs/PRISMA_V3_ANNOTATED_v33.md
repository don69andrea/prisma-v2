# PRISMA V3 — Master Specification
**Erstellt:** 2026-06-20  
**Basis:** Vollaudit PRISMA V2 + Konzept-Session mit Andrea  
**Zweck:** Vollständige Umsetzungsgrundlage für Terminal Agents (Claude Code)  
**Zielgruppe:** FHNW BI Module — Bewertungskriterien: Agentic AI + ML + RAG + BI-Dashboard  

> **Wichtig für alle Agents:** Dieses Dokument ist die einzige Wahrheitsquelle für PRISMA V3.  
> Vor jeder Implementierung dieses Dokument lesen. Niemals von den hier definierten Architekturen abweichen.

---

> ## 🔴 CHALLENGE-LAYER V3.1 — Reviewer-Annotationen
> **Reviewer:** Konzept-Challenge gegen das tatsächliche Repo (`prisma-v2`, Stand 2026-06-20)
> **Status:** Original-Spec ist solide aufgebaut, hat aber mehrere **falsche Grundannahmen**, die das Projekt akademisch angreifbar machen.
>
> Dies ist die **Original-Spec + Reviewer-Layer**. Eingefügte Blöcke sind `> ⚡ **CHALLENGE [Nr]**` markiert.
> Der Originaltext bleibt unverändert. **Wo ein Challenge-Block einer Original-Aussage widerspricht, gilt der Challenge-Block.**
>
> **Die 6 kritischen Findings (Details in Kapiteln 15–22):**
> 1. **SimFin liefert KEINE Schweizer Fundamentaldaten im Free Tier** — der eigene `simfin_adapter.py` sagt das wörtlich (`Für CH/EU: SimFin Free Tier hat keine brauchbare Coverage → None → Stub-Fallback`). Der „offizielle Datensatz" existiert so nicht. → **CH-01**
> 2. **ML-Validierung nicht wasserdicht:** überlappende 30-Tage-Targets ohne Purging/Embargo → Leakage trotz Zeit-Split. → **CH-02**
> 3. **Backtest ohne Transaktionskosten / Schweizer Stempelabgabe / Slippage** → Alpha systematisch zu optimistisch. → **CH-03**
> 4. **Kein Survivorship-Bias-Handling** (heutige SMI-20 ≠ historische SMI-20). → **CH-04**
> 5. **„A/B-Test neues vs. altes Modell" ist nicht spezifiziert** und `ModelRegistry` kann es nicht — nur `set_active`. → **CH-05**
> 6. **Kein Position-Sizing / Risk-Layer** — System sagt „BUY", aber nie *wie viel*. Das ist die eigentliche Trading-Entscheidung. → **CH-06**
>
> Dazu: Datenmenge zu klein für 25+ Features, fehlende Baselines, unkalibrierte „73%-Wahrscheinlichkeit", Disclaimer-/Compliance-Lücke und Zusatz-Bugs (FIX-14…FIX-22).


---

## 0 · Projekt-Vision

PRISMA V3 ist ein **Evidence-Based Investment Intelligence System** für Schweizer Retail-Investoren.

**Kernunterschied zu V2:**
- V2: Signal-Anzeige-Tool ("RSI ist 42, Score ist 67")
- V3: Trading-Entscheidungs-Tool ("73% Wahrscheinlichkeit für +8% in 30 Tagen — basierend auf historisch validierten Mustern")

**Wichtig:** Die Metriken von Typ 1 (RSI, MACD, Score) sind die Input-Features für Typ 2. Sie ersetzen sich nicht — Typ 1 enriches Typ 2. Das Dashboard zeigt beides: die Rohdaten UND die Entscheidung.

**Dozenten-Anforderungen (FHNW BI Module):**
- ✅ Agentic AI (Multi-Agent Fan-out/Fan-in mit echtem LLM Tool-Use)
- ✅ Machine Learning basiert (LightGBM + Continuous Learning)
- ✅ RAG basiert (News + Swiss Filings + SNB-Kommuniqués)
- ✅ Datensatz verwenden und damit arbeiten (SimFin historische Fundamentals + yfinance historisch → PostgreSQL)
- ✅ Historische Daten + Live-Daten Zusammenspiel
- ✅ Als Hobby weiterführbar

**Scope:**
- Swiss Stocks: SMI-20 + SMIM-30 (SIX Exchange)
- Krypto: BTC, ETH, SOL, ADA, BNB, XRP, MATIC, DOT, AVAX, LINK (nur Coins — KEINE ETPs, KEINE ETFs)
- Märkte: nur diese zwei Kategorien, kein US-Stocks Ausbau

---

## 1 · Was bleibt, was fällt weg, was wird neu

### 1.1 BLEIBT (funktioniert gut, nur Bugfixes)

| Komponente | Was gut ist | Fix nötig |
|---|---|---|
| `MacroService` | Live-Daten von SNB/ECB/FRED — solide | PMI im Score verwenden |
| `CointelligenceAgent` | Tool-Use-Loop Architektur korrekt | Glassnode-Key + CHF/USD Fix |
| `CryptoPatternService` | Candlestick + Formation-Erkennung gut | max 14 Patterns ausbauen |
| `BacktestService` | Sharpe, CAGR, MaxDrawdown korrekt | Look-Ahead-Bias dokumentieren |
| `AlertService` | SendGrid-Integration funktioniert | — |
| `SteuerAgent` | Schweizer Steuerrecht korrekt | — |
| `NewsIngestionService` | RAG-Pipeline funktioniert | Embedding-Index-Mismatch Fix |
| `InvestmentDirector` | SSE-Streaming + HITL-Architektur | Concurrent-Checkpoint Fix |
| `LLMClient` + `CostTracker` | Korrekte Budget-Überwachung | — |

### 1.2 WIRD ERSETZT / KOMPLETT NEU GESCHRIEBEN

| Alt | Neu | Grund |
|---|---|---|
| `SwissQuantScorer` (absolut) | `SwissQuantScorer` (relativ) | P/E <15 passt zu keinem SMI-Titel |
| `SignalValidationService` (Momentum-Proxy) | `SignalAccuracyAgent` (echter Outcome-Tracker) | War kein echter PRISMA-Backtest |
| `DataStewardAgent` (toter Code) | `DataStewardAgent` (echter DB-Writer) | Schrieb nie in DB, wurde nie aufgerufen |
| `MacroAgentV2` (LLM für if/elif) | `MacroNewsAgent` (LLM mit echten News-Tools) | LLM-Overhead ohne Mehrwert |

### 1.3 WIRD NEU GEBAUT

- `SignalAccuracyAgent` (täglich, Continuous Learning Loop)
- `CryptoIntradayAgent` (alle 4h, auch Sa/So)
- `SNBRateUpdateAgent` (monatlich)
- `MacroNewsAgent` (LLM + RAG-News-Tool)
- Historischer Daten-Seed (einmalig)
- 4 neue DB-Tabellen

---

## 2 · Datenbankarchitektur (Das Fundament)

### 2.1 Das Problem mit V2

**yfinance-Daten werden nie in der DB gespeichert.** Bei jedem Request wird yfinance live abgerufen. Bei Yahoo-Blockade (passiert regelmässig auf Cloud-IPs) → Fehler. Die DB enthält nur berechnete Outputs (Signale, Scores, Memos), nie die Rohdaten.

**V3-Prinzip:** Die DB ist die primäre Datenquelle. yfinance/CoinGecko lädt nur noch täglich in die DB. Alle Berechnungen lesen aus der DB, nicht von externen APIs.

> ⚡ **CHALLENGE 01 — Der „offizielle Datensatz" trägt nicht (kritisch)**
> Die Spec macht SimFin-CH-Fundamentals zum Herzstück (Kap. 2.3, 4.2, 10). **Aber der bereits existierende `backend/infrastructure/adapters/simfin_adapter.py` dokumentiert selbst:**
> > *„Für CH/EU: SimFin Free Tier hat keine brauchbare Coverage → None → Stub-Fallback"* und *„derived/quarterly (P/E, P/B) → Premium-only, nicht verfügbar"*.
>
> Das heisst: Wer Kap. 10 wörtlich umsetzt, landet wieder beim `_stub_fundamentals()` — genau dem Look-Ahead-Bias, den V3 eliminieren will. **Bevor irgendeine ML-Pipeline gebaut wird, muss die Datenquelle empirisch verifiziert werden.** Optionen, in Reihenfolge der Empfehlung:
> 1. **SimFin Free auf ein US-Proxy-Universum** (z.B. S&P-Sektoren) als *methodischer* Datensatz für die ML-Demo, während Swiss-Live aus yfinance/echten Filings kommt. Akademisch sauber, weil reproduzierbar.
> 2. **SIX/Filings + yfinance `.info` quartalsweise** selbst zu Point-in-Time-Fundamentals aggregieren (Aufwand hoch, aber „echt schweizerisch").
> 3. **SimFin Premium / einen anderen Anbieter** (EOD Historical, Financial Modeling Prep) — Kostenfrage klären.
>
> **Pflicht-Task (Phase 0, vor allem anderen):** `scripts/verify_dataset_coverage.py` — lädt für 3 SMI-Titel die SimFin-Fundamentals und schreibt einen Coverage-Report (Anzahl Quartale, Null-Quote, ältestes/neuestes Datum). Erst wenn das grün ist, ist Kap. 4/10 baubar. Siehe Kap. 15.


### 2.2 Neue Tabellen (Migrationen 0031-0035)

#### Migration 0031 — `stock_price_history`
```sql
CREATE TABLE stock_price_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(20) NOT NULL,          -- NESN, NOVN etc.
    date        DATE NOT NULL,
    open        FLOAT NOT NULL,
    high        FLOAT NOT NULL,
    low         FLOAT NOT NULL,
    close       FLOAT NOT NULL,
    volume      BIGINT,
    currency    VARCHAR(3) DEFAULT 'CHF',
    source      VARCHAR(20) DEFAULT 'yfinance',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, date)
);
CREATE INDEX ix_stock_price_history_ticker_date ON stock_price_history (ticker, date DESC);
```

#### Migration 0032 — `stock_fundamentals`
```sql
CREATE TABLE stock_fundamentals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    period_end      DATE NOT NULL,             -- Ende des Quartals/Jahres
    period_type     VARCHAR(10) NOT NULL,      -- 'quarterly' | 'annual'
    pe_ratio        FLOAT,
    pb_ratio        FLOAT,
    ev_ebitda       FLOAT,
    roe             FLOAT,                     -- Return on Equity (%)
    debt_equity     FLOAT,                     -- Debt/Equity Ratio
    fcf_margin      FLOAT,                     -- Free Cashflow Margin (%)
    eps_chf         FLOAT,
    eps_growth_yoy  FLOAT,                     -- EPS YoY Growth (%)
    revenue_growth  FLOAT,
    dividend_yield  FLOAT,
    dividend_growth FLOAT,                     -- Dividend Growth YoY (%)
    market_cap_chf  FLOAT,
    source          VARCHAR(20) DEFAULT 'simfin',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, period_end, period_type)
);
CREATE INDEX ix_stock_fundamentals_ticker ON stock_fundamentals (ticker, period_end DESC);
```

#### Migration 0033 — `crypto_price_history`
```sql
CREATE TABLE crypto_price_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(20) NOT NULL,          -- BTC, ETH etc.
    timestamp   TIMESTAMPTZ NOT NULL,          -- Stündliche Genauigkeit
    interval    VARCHAR(5) NOT NULL,           -- '1h' | '4h' | '1d'
    open        FLOAT NOT NULL,
    high        FLOAT NOT NULL,
    low         FLOAT NOT NULL,
    close       FLOAT NOT NULL,
    volume      FLOAT,
    currency    VARCHAR(3) DEFAULT 'CHF',
    source      VARCHAR(20) DEFAULT 'yfinance',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, timestamp, interval)
);
CREATE INDEX ix_crypto_price_history_ticker_ts ON crypto_price_history (ticker, timestamp DESC);
```

#### Migration 0034 — `signal_outcomes`
```sql
CREATE TABLE signal_outcomes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker          VARCHAR(20) NOT NULL,
    asset_type      VARCHAR(10) NOT NULL,      -- 'stock' | 'crypto'
    signal_date     DATE NOT NULL,
    signal          VARCHAR(20) NOT NULL,      -- BUY | HOLD | SELL | STRONG_BUY | STRONG_SELL
    price_at_signal FLOAT NOT NULL,
    horizon_days    INT NOT NULL,              -- 7 | 30 | 90
    evaluation_date DATE,                     -- NULL bis zur Auswertung
    price_at_eval   FLOAT,
    actual_return   FLOAT,                     -- (price_at_eval / price_at_signal) - 1
    benchmark_ret   FLOAT,                     -- SMI/BTC Return im gleichen Zeitraum
    excess_return   FLOAT,                     -- actual_return - benchmark_ret (Alpha)
    was_correct     BOOLEAN,                   -- True wenn excess_return > 0 für BUY
    used_for_train  BOOLEAN DEFAULT FALSE,     -- Schon in Retraining eingeflossen?
    source_table    VARCHAR(30),               -- 'stock_daily_signals' | 'crypto_signals'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_signal_outcomes_ticker_date ON signal_outcomes (ticker, signal_date DESC);
CREATE INDEX ix_signal_outcomes_eval ON signal_outcomes (evaluation_date, used_for_train);
```

#### Migration 0035 — `macro_rates`
```sql
CREATE TABLE macro_rates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_type       VARCHAR(20) NOT NULL,      -- 'snb_policy' | 'ecb_deposit' | 'fed_funds'
    effective_date  DATE NOT NULL,
    rate_pct        FLOAT NOT NULL,
    source_url      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (rate_type, effective_date)
);
```

### 2.3 Initialer Daten-Seed (einmalig, Script)

```
scripts/seed_historical_prices.py
  → 7 Jahre SMI-20 Tagespreise (2018-01-01 bis heute)
  → 5 Jahre Krypto Tagespreise BTC/ETH/SOL/ADA/BNB/XRP
  → Schreibt in stock_price_history + crypto_price_history

scripts/seed_simfin_fundamentals.py
  → SimFin API: quartalsweise Fundamentaldaten 2015-2024
  → Alle SMI-20 + SMIM-30 Titel
  → Schreibt in stock_fundamentals
  → DAS ist der offizielle "Datensatz" für den Dozenten
```

**SimFin Setup:**
```python
# Kostenloser SimFin API-Key: https://simfin.com/api/v2/
# Liefert: Income Statement, Balance Sheet, Cash Flow quarterly seit 2010
# Ticker-Mapping: NESN → NESN (SimFin hat Schweizer Titel)
SIMFIN_API_KEY = os.environ["SIMFIN_API_KEY"]  # In Render Secrets setzen
```

---

## 3 · Neuer Swiss Quant Scorer

### 3.1 Das Problem mit V2

Kein einziger SMI-Titel erfüllt P/E < 15. Kein Pharma-Titel erfüllt P/B < 2. Dividend 40% Gewichtung macht Wachstumstitel systematisch schlechter. Quality Score = binary (EPS > 0 → 100 Punkte, egal ob EPS +2% oder +40%).

### 3.2 Neues Score-System: Relativ statt Absolut

**Prinzip:** Nicht gegen fixe Schwellwerte bewerten, sondern gegen:
1. Historisches Median des Titels selbst (letzten 3 Jahre)
2. Sektor-Durchschnitt (Pharma vs. Banken vs. Industrie)

**Neue Gewichtung:**

```python
# backend/domain/services/swiss_quant_scorer_v3.py

SCORE_WEIGHTS = {
    "momentum": 0.30,   # Relative Stärke vs SMI (war: 0%)
    "value":    0.30,   # Relative Bewertung vs eigener Historie (war: 40%)
    "quality":  0.25,   # ROE + FCF + Verschuldung (war: 20% mit binärem EPS)
    "income":   0.15,   # Dividende (war: 40%)
}

class SwissQuantScorerV3:
    
    def score(self, ticker: str, f: SwissFundamentals, 
              price_history: pd.DataFrame,
              sector_medians: dict) -> SwissQuantScore:
        
        momentum = self._score_momentum(price_history)    # 0-100
        value    = self._score_value(f, sector_medians)   # 0-100
        quality  = self._score_quality(f)                 # 0-100
        income   = self._score_income(f, sector_medians)  # 0-100
        
        composite = (
            momentum * 0.30 +
            value    * 0.30 +
            quality  * 0.25 +
            income   * 0.15
        )
        return SwissQuantScore(...)

    def _score_momentum(self, prices: pd.DataFrame) -> float:
        """Relative Stärke vs SMI über 3 Zeiträume."""
        close = prices["Close"]
        smi   = prices["SMI"]  # SMI-Index parallel laden (^SSMI)
        
        ret_1m  = self._rel_return(close, smi, 21)
        ret_3m  = self._rel_return(close, smi, 63)
        ret_12m = self._rel_return(close, smi, 252)
        
        # 52-Wochen Hoch/Tief Position (0 = am Tief, 1 = am Hoch)
        high_52w = close.tail(252).max()
        low_52w  = close.tail(252).min()
        hilo_pos = (close.iloc[-1] - low_52w) / (high_52w - low_52w + 1e-9)
        
        score = (
            self._map_return_to_score(ret_1m)  * 0.20 +
            self._map_return_to_score(ret_3m)  * 0.30 +
            self._map_return_to_score(ret_12m) * 0.30 +
            hilo_pos * 100                     * 0.20
        )
        return min(100.0, max(0.0, score))

    def _score_value(self, f: SwissFundamentals, sector_medians: dict) -> float:
        """Relativer Value vs Sektor-Median."""
        pe_score  = self._relative_score(f.pe_ratio, sector_medians.get("pe"), inverted=True)
        pb_score  = self._relative_score(f.pb_ratio, sector_medians.get("pb"), inverted=True)
        ev_score  = self._relative_score(f.ev_ebitda, sector_medians.get("ev_ebitda"), inverted=True)
        return pe_score * 0.40 + pb_score * 0.30 + ev_score * 0.30

    def _score_quality(self, f: SwissFundamentals) -> float:
        """ROE, FCF-Margin, Verschuldung — nicht mehr binär."""
        roe_score = self._map_roe_to_score(f.roe)           # 0-100
        fcf_score = self._map_fcf_to_score(f.fcf_margin)    # 0-100
        de_score  = self._map_de_to_score(f.debt_equity)    # 0-100, invertiert
        eps_g_score = self._map_growth_to_score(f.eps_growth_yoy)  # 0-100
        return roe_score * 0.30 + fcf_score * 0.30 + de_score * 0.20 + eps_g_score * 0.20

    def _score_income(self, f: SwissFundamentals, sector_medians: dict) -> float:
        """Dividende relativ zum Sektor + Dividend Growth."""
        yield_score  = self._relative_score(f.dividend_yield, sector_medians.get("div_yield"))
        growth_score = self._map_growth_to_score(f.dividend_growth)
        return yield_score * 0.60 + growth_score * 0.40
```

### 3.3 Sector Medians Service

```python
# backend/application/services/sector_median_service.py
# Berechnet Sektor-Mediane täglich aus stock_fundamentals-Tabelle
# Sektoren: pharma, banking, industrial, consumer, financial, tech
```

---

## 4 · ML-Pipeline (Überarbeitung)

### 4.1 Das Problem mit V2

- Training nutzt `_stub_fundamentals()` → aktuelle Fundamentals für historische Zeitpunkte (Look-Ahead-Bias)
- Feature-Target: forward_return_12m → zu lang für valides Trading-Signal
- Kein sauberer Train/Val/Test-Split dokumentiert
- Wenige Trainingsdaten (20 Titel × 3 Jahre = ~720 Snapshots)

### 4.2 Neue ML-Pipeline

**Datensatz (der offizielle für den Dozenten):**
```
SimFin quarterly Fundamentals 2015-2024
  + yfinance OHLCV daily 2015-2024 (aus stock_price_history)
  + SNB/ECB Makrodaten (aus macro_rates)
→ Feature Engineering: monatliche Snapshots, Point-in-Time korrekt
→ ~50 Titel × 12 Monate × 9 Jahre = ~5400 Snapshots
```

> ⛔ **ÜBERSCHRIEBEN durch TEIL F (Datenstrategie & ML — FINAL).** Die folgende 25+-Feature-Liste mit Fundamentals gilt NICHT mehr. Das ML nutzt nur Preis-/Technik- + Makro-Features; Fundamentals wandern in den Quant-Scorer. Maßgeblich ist TEIL F.

**Features (25+):**

Preisbasiert (aus stock_price_history, Point-in-Time korrekt):
- `return_1m`, `return_3m`, `return_6m`, `return_12m`
- `vol_30d`, `vol_90d`
- `rsi_14`
- `price_to_52w_high`
- `momentum_vs_smi_3m` (neu — relative Stärke)
- `bb_position`
- `macd_hist`
- `drawdown_12m`

Fundamental (aus stock_fundamentals, quartalsweise, Point-in-Time):
- `pe_ratio`, `pb_ratio`, `ev_ebitda` (neu)
- `roe` (neu), `debt_equity` (neu), `fcf_margin` (neu)
- `eps_growth_yoy` (neu), `revenue_growth`, `dividend_yield`, `dividend_growth` (neu)

Makro (aus macro_rates, Point-in-Time):
- `snb_rate`, `chf_eur`, `inflation_ch`

**Target (NEU):**
```python
# Nicht mehr: forward_return_12m in Bottom/Mid/Top Quartil
# Neu: relative Outperformance vs SMI in 30 Tagen
target = (stock_return_30d - smi_return_30d)
# Klassen: OUTPERFORM (> +2%), NEUTRAL (-2% bis +2%), UNDERPERFORM (< -2%)
```

**Train/Validate/Test Split:**
```
Train:    2015-01-01 bis 2022-12-31  (80% der Daten)
Validate: 2023-01-01 bis 2023-12-31  (Hyperparameter-Tuning)
Test:     2024-01-01 bis 2025-12-31  (Out-of-Sample, wird dem Dozenten gezeigt)
Live:     2026-01-01 →               (Produktionsbetrieb)
```

> ⚡ **CHALLENGE 02 — Zeit-Split allein verhindert kein Leakage (kritisch)**
> Das Target ist `return_30d - smi_return_30d`. Bei *monatlichen* Snapshots überlappen aufeinanderfolgende 30-Tage-Fenster fast vollständig. Zwei Konsequenzen:
> 1. **Label-Autokorrelation:** benachbarte Samples teilen denselben Forward-Zeitraum → das Modell sieht im Training faktisch die „Zukunft" benachbarter Test-Samples an der Split-Grenze. Reiner kalendarischer Cut reicht nicht.
> 2. **Korrektur:** **Purged & Embargoed Walk-Forward CV** (López de Prado). Zwischen Train- und Test-Block ein Embargo von ≥ Horizont-Länge (30 Tage) lassen; überlappende Samples purgen.
>
> Zusätzlich anzugeben (sonst nicht benotbar als „ML-basiert"):
> - **Baselines** gegen die das Modell antreten muss: (a) immer NEUTRAL, (b) Momentum-only, (c) der bestehende `SwissQuantScorerV3`. Ein LightGBM, das die Mehrheitsklasse nicht schlägt, ist wertlos.
> - **Klassen-Imbalance:** NEUTRAL (±2%) dominiert → `class_weight`/`is_unbalance`, und als Metrik **Macro-F1 + Confusion-Matrix**, nicht Accuracy.
> - **Stichprobengrösse ehrlich rechnen:** ~5400 Snapshots, aber durch Überlappung sind die *unabhängigen* Samples eher ~50 Titel × ~108 Monate / (30d-Block) ≈ deutlich weniger effektive Beobachtungen. Bei 25+ Features ist Regularisierung (max_depth klein, min_child_samples hoch, L1/L2) Pflicht, sonst Overfitting. Siehe Kap. 16.

```

**Modell:**
```python
# LightGBM (bleibt, ist gut)
# Neu: inkrementelles Retraining via warm_start
import lightgbm as lgb

# Ersttraining:
model = lgb.train(params, train_data, valid_sets=[val_data])

# Inkrementelles Retraining (wöchentlich + nach Continuous Learning):
model_updated = lgb.train(
    params,
    new_data,
    init_model=model,          # warm_start
    num_boost_round=50,        # nur wenige neue Runden
    valid_sets=[val_data],
)
```

### 4.3 Feature-Name-Validierung beibehalten

Das Feature-Mismatch-Check beim Modell-Laden (aus V2) ist gut — beibehalten:
```python
if stored_features != current_features:
    raise ValueError("Feature-Mismatch — Modell muss neu trainiert werden")
```

---

## 5 · Alle Agents — Vollständige Spezifikation

### 5.1 SignalAccuracyAgent (NEU — Höchste Priorität)

**Datei:** `backend/application/agents/signal_accuracy_agent.py`  
**Cron:** täglich 09:00 UTC (nach Marktöffnung, nach dem täglichen Snapshot)  
**Zweck:** Schliessen des Continuous-Learning-Loops

```python
class SignalAccuracyAgent:
    """
    Evaluiert täglich ob historische Signale korrekt waren.
    Triggert inkrementelles ML-Retraining wenn genug neue Outcomes vorliegen.
    """
    
    HORIZONTE = [7, 30, 90]    # Tage nach Signal → Auswertung
    KRYPTO_HORIZONTE = [7, 30] # Krypto: kein 90d-Horizont (zu volatil)
    MIN_WIN_RATE = 0.48        # Unter diesem Wert → Alert
    MIN_OUTCOMES_FOR_RETRAIN = 20  # Mindestanzahl neuer Outcomes für Retraining
    
    async def run_daily(self) -> AccuracyReport:
        # 1. POPULATE: Neue signal_outcomes-Zeilen für fällige Evaluationen
        await self._populate_pending_outcomes()
        
        # 2. EVALUATE: Fehlende price_at_eval befüllen
        await self._fill_evaluation_prices()
        
        # 3. CALCULATE: was_correct + excess_return berechnen
        await self._calculate_correctness()
        
        # 4. MONITOR: Win-Rate prüfen, Alert wenn < 48%
        report = await self._compute_win_rates()
        if report.win_rate_30d < self.MIN_WIN_RATE:
            await self._create_alert("Win-Rate unter Threshold", report)
        
        # 5. CONTINUOUS LEARNING: Retraining triggern wenn genug neue Daten
        new_outcomes = await self._count_new_untrainined_outcomes()
        if new_outcomes >= self.MIN_OUTCOMES_FOR_RETRAIN:
            await self._trigger_incremental_retrain(new_outcomes)
        
        return report
    
    async def _populate_pending_outcomes(self):
        """Für jeden BUY/SELL-Signal der fällig ist: neuen outcome-Eintrag erstellen."""
        for horizon in self.HORIZONTE:
            eval_date = date.today()
            signal_date = eval_date - timedelta(days=horizon)
            # Hole alle BUY/SELL Signale vom signal_date die noch kein outcome haben
            signals = await self._repo.get_signals_without_outcome(signal_date, horizon)
            for signal in signals:
                await self._repo.create_outcome_pending(signal, horizon, eval_date)
    
    async def _trigger_incremental_retrain(self, n_outcomes: int):
        """LightGBM warm_start mit neuen Outcome-Daten."""
        log.info("Triggere Retraining mit %d neuen Outcomes", n_outcomes)
        # Lädt neue Outcomes aus DB → Feature-Vektoren → lgb.train(..., init_model=current)
        # Speichert neues Modell als models/return_predictor_incremental_{date}.joblib
        # A/B-Vergleich: neues vs. altes auf letzten 90 Tagen
        # Wenn neues Modell besser: in registry.json als aktiv setzen
        ...

> ⚡ **CHALLENGE 05 — „A/B-Test" ist Wunschdenken, die Registry kann es nicht**
> `_trigger_incremental_retrain` behauptet „A/B-Vergleich neues vs. altes auf letzten 90 Tagen". Die reale `ModelRegistry` hat nur `register()`/`set_active()` — **keine Champion/Challenger-Logik, kein Shadow-Mode, kein Rollback.** Ausserdem: ein A/B auf *vergangenen* 90 Tagen ist kein A/B, sondern Backtest — und genau der Zeitraum, dessen Outcomes ins Retraining flossen → zirkulär.
>
> **Korrektur (Champion/Challenger statt Pseudo-A/B):**
> - Challenger wird **out-of-sample** auf Outcomes evaluiert, die *nach* seinem Trainings-Cutoff entstanden (Shadow-Mode: rechnet mit, beeinflusst keine User).
> - Promotion erst nach `N`≥30 unabhängigen Shadow-Outcomes UND signifikanter Verbesserung (nicht nur Punktschätzung — Konfidenzintervall/McNemar-Test).
> - Registry braucht `champion`, `challenger`, `promote()`, `rollback()` + Metrik-Historie pro Version.
> - **Warm-Start-Falle:** `init_model` + nur 50 Runden auf wenig neuen Daten driftet schnell. Lieber periodisches Voll-Retraining als Champion; Warm-Start nur als Challenger. Siehe Kap. 18.

    
    async def get_dashboard_stats(self) -> dict:
        """Für das Frontend-Dashboard."""
        return {
            "win_rate_7d":  await self._repo.win_rate(days=7),
            "win_rate_30d": await self._repo.win_rate(days=30),
            "win_rate_90d": await self._repo.win_rate(days=90),
            "alpha_vs_smi_30d": await self._repo.mean_excess_return(days=30),
            "total_evaluated": await self._repo.count_evaluated(),
            "model_version": self._model_registry.get_active_version(),
        }
```

**GitHub Action Eintrag:**
```yaml
- cron: "0 9 * * 1-5"   # 09:00 UTC Mo-Fr — SignalAccuracyAgent
```

**Neuer API-Endpoint:**
```
GET /api/v1/signals/accuracy
→ { win_rate_7d, win_rate_30d, win_rate_90d, alpha_vs_smi_30d, total_evaluated }
```

**Dashboard-Anzeige:**
```
"PRISMA Signals Performance (30 Tage)"
BUY-Signale: 63% Win-Rate | +1.8% Alpha vs SMI
Ausgewertet: 47 Signale
```

---

### 5.2 CryptoIntradayAgent (NEU)

**Datei:** `backend/scripts/crypto_intraday_snapshot.py`  
**Cron:** alle 4 Stunden, 7 Tage pro Woche  
**Zweck:** Intraday-Signale für BTC und ETH (täglich ist zu grob für Krypto-Trading)

```python
class CryptoIntradayAgent:
    TICKERS = ["BTC-USD", "ETH-USD"]
    INTERVAL = "1h"      # yfinance 1h-Kerzen
    PERIOD   = "7d"      # 7 Tage × 24h = 168 Datenpunkte für Indikatoren
    
    async def run_snapshot(self):
        for ticker in self.TICKERS:
            # 1. Lade 1h-OHLCV via yfinance
            df = yf.download(ticker, period="7d", interval="1h", auto_adjust=True)
            
            # 2. Intraday-Indikatoren (auf 1h-Basis)
            df = self._add_indicators(df)  # RSI, MACD, BB, EMA auf 1h
            
            # 3. Intraday Score (gleiche Logik wie CryptoScorer aber auf 1h)
            score, components = self._scorer.score(df, fear_greed, ...)
            
            # 4. Schreibe in crypto_price_history (interval='4h') UND
            #    in eigene Tabelle crypto_intraday_signals
            await self._repo.save_intraday(ticker, score, components)
        
        log.info("Intraday Snapshot fertig: BTC=%.1f ETH=%.1f", btc_score, eth_score)
```

**Neue GitHub Action:**
```yaml
crypto-intraday:
  name: "₿ Krypto Intraday (BTC/ETH, 4h)"
  runs-on: ubuntu-latest
  if: github.event.schedule == '0 */4 * * *'
  # Läuft alle 4h, auch Sa/So — Krypto schläft nicht
```

**Neue Tabelle `crypto_intraday_signals`:**
```sql
CREATE TABLE crypto_intraday_signals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker      VARCHAR(10) NOT NULL,
    signal      VARCHAR(20) NOT NULL,
    score       FLOAT NOT NULL,
    components  JSONB,
    rsi_1h      FLOAT,
    macd_1h     FLOAT,
    timestamp   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

### 5.3 SNBRateUpdateAgent (NEU)

**Datei:** `backend/scripts/snb_rate_update.py`  
**Cron:** 1. Montag des Monats, 03:00 UTC  
**Zweck:** Automatische Aktualisierung der Zinsdaten — eliminiert die Zwei-System-Inkonsistenz

```python
async def main():
    """Holt aktuelle SNB/ECB/Fed-Zinsen und schreibt in macro_rates-Tabelle."""
    from backend.infrastructure.adapters.snb_adapter import fetch_current_snb_rate
    from backend.infrastructure.adapters.ecb_fx_adapter import fetch_all_chf_rates
    
    snb_rate = await fetch_current_snb_rate()
    # Schreibe in macro_rates-Tabelle
    await repo.upsert_rate("snb_policy", date.today(), snb_rate, 
                           source_url="https://data.snb.ch/")
    
    # MLFeatureService liest künftig aus macro_rates statt aus hardcodierter Liste
    # → _SNB_RATE_HISTORY Liste in ml_feature_service.py wird deprecated
```

**Fix für die Zwei-System-Inkonsistenz:**  
`MLFeatureService._snb_rate_on()` und `_ECB_RATE_HISTORY` in `ml_feature_service.py` werden auf DB-Lesen umgestellt. Die hartcodierten Listen bleiben nur als Notfall-Fallback wenn die Tabelle leer ist.

---

### 5.4 MacroNewsAgent (Überarbeitung MacroAgentV2)

**Datei:** `backend/application/agents/macro_news_agent.py`  
**Zweck:** Echter LLM-Agent mit News-RAG — nicht mehr reine if/elif-Logik via LLM

**V2 Problem:** Gleiche Logik wie V1, nur teurer. Kein echter Mehrwert.  
**V3 Lösung:** V2 bekommt einen echten Tool `search_macro_news` der die RAG-Datenbank nach SNB-relevanten News durchsucht.

```python
_MACRO_TOOLS_V3 = [
    {
        "name": "get_snb_rate",
        "description": "Aktueller SNB-Leitzins aus der Datenbank.",
    },
    {
        "name": "get_chf_eur",  
        "description": "Aktueller CHF/EUR-Kurs (ECB-Quelle).",
    },
    {
        "name": "get_inflation_ch",
        "description": "Aktuelle Schweizer Inflationsrate YoY (FRED-Quelle).",
    },
    {
        "name": "search_macro_news",                          # ← NEU
        "description": "Sucht in der PRISMA-News-Datenbank nach makrorelevanten Artikeln der letzten 7 Tage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "days_back": {"type": "integer", "default": 7}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_ticker_export_profile",
        "description": "Gibt zurück ob Ticker exportlastig, inlandsfokussiert oder neutral ist.",
    },
]
```

**Wenn kein Mehrwert durch News:** MacroAgent V1 als Default verwenden (deterministisch, schnell, kein LLM-Overhead). MacroNewsAgent nur on-demand aktivieren wenn User explizit "aktuelle Marktnews berücksichtigen" anfragt.

---

### 5.5 DataStewardAgent (Komplettüberarbeitung)

**Datei:** `backend/application/agents/data_steward_agent.py`  
**Cron:** täglich 03:30 UTC (als erster Job, vor SMI Market Caps)  
**Problem in V2:** Nie aufgerufen, schreibt nie in DB, Quarantäne ohne Folgeaktion.

```python
class DataStewardAgent:
    """
    V3: Echter Datenpflege-Agent.
    1. Prüft Freshness aller Preisdaten
    2. Schreibt fehlende Daten aktiv in stock_price_history
    3. Erstellt Alert-Einträge für Quarantäne-Titel
    4. Triggert Refresh wenn Lücken gefunden
    """
    
    async def run_check(self) -> DataStewardReport:
        # 1. Hole alle Ticker die heute noch keinen Preis haben
        stale = await self._price_repo.get_stale_tickers(date.today())
        
        for ticker in stale:
            try:
                # 2. Lade Preis via yfinance
                price_data = await self._yf.get_ohlcv(ticker, days=5)
                
                # 3. Spike-Check (>15% = Quarantäne)
                last_price = await self._price_repo.get_last_price(ticker)
                change = abs(price_data.close - last_price) / last_price
                if change > 0.15:
                    await self._alert_repo.create(ticker, "PRICE_SPIKE", change)
                    quarantined.append(ticker)
                    continue
                
                # 4. SCHREIBE IN DB (V2 hat das nie gemacht!)
                await self._price_repo.upsert(ticker, date.today(), price_data)
                refreshed.append(ticker)
                
            except Exception as e:
                errors.append(f"{ticker}: {e}")
        
        return DataStewardReport(...)
```

---

### 5.6 CointelligenceAgent (Bugfixes)

**Datei:** `backend/application/agents/cointelligence_agent.py`  
**Fixes nötig:**

```python
# BUG FIX 1: CHF/USD korrekt berechnen
# ALT (falsch):
chf_usd = round(ctx.chf_eur / 1.08, 4)  # EUR/USD=1.08 hardcodiert

# NEU (korrekt):
from backend.infrastructure.adapters.ecb_fx_adapter import fetch_chf_usd
chf_usd = await fetch_chf_usd()  # Live von ECB SDW

# BUG FIX 2: MVRV-Z — Glassnode Key muss in Render Secrets gesetzt werden
# GLASSNODE_API_KEY als Secret in render.yaml + GitHub Actions
# Alternativ: Coinglass Free API als Fallback

# BUG FIX 3: Scope
# Nur BTC und ETH werden analysiert — das ist korrekt (User will keine ETP/ETF)
# Nicht auf andere SUPPORTED_CRYPTOS ausweiten
```

---

### 5.7 InvestmentDirector (Bugfix Concurrent Checkpoints)

**Datei:** `backend/application/agents/investment_director.py`  
**Problem:** `_checkpoints` und `_checkpoint_answers` sind instanz-variablen — bei shared Instance + concurrent requests können Checkpoint-IDs kollidieren.

```python
# FIX: ThreadSafe Checkpoint-Storage
import asyncio
from collections import defaultdict

class InvestmentDirector:
    def __init__(self, ...):
        self._checkpoints: dict[str, asyncio.Event] = {}
        self._checkpoint_answers: dict[str, str | None] = {}
        self._lock = asyncio.Lock()  # ← NEU
    
    async def resolve_checkpoint(self, checkpoint_id: str, answer: str) -> None:
        async with self._lock:  # ← NEU
            self._checkpoint_answers[checkpoint_id] = answer
            event = self._checkpoints.get(checkpoint_id)
        if event:
            event.set()
```

---

### 5.8 MacroIntelligenceAgent V1 (Fixes)

```python
# FIX 1: Inflation-Fallback darf nicht positiv sein
# ALT:
if ctx.inflation_ch is None:
    score += 10  # ← falscher positiver Bias bei API-Fehler

# NEU:
if ctx.inflation_ch is None:
    pass  # Score bleibt neutral (0 Punkte) wenn keine Daten
    reasons.append("CH-Inflation nicht verfügbar — kein Bonus")

# FIX 2: PMI im Score verwenden (war: berechnet aber nie genutzt)
if ctx.pmi_ch is not None:
    if ctx.pmi_ch >= 50:
        score += 5
        reasons.append(f"PMI im Expansionsbereich ({ctx.pmi_ch:.1f})")
    elif ctx.pmi_ch < 45:
        score -= 5
        reasons.append(f"PMI im Kontraktionsbereich ({ctx.pmi_ch:.1f})")

# FIX 3: _EXPORT_HEAVY Liste in gemeinsames Modul auslagern
# NEU: backend/domain/data/macro_profiles.py
# V1 und V2 importieren beide aus diesem Modul
```

---

### 5.9 CryptoScorer (ATH-Bug Fix)

**Datei:** `backend/domain/services/crypto_scorer.py`

```python
# BUG FIX: ATH-Score Logik
# ALT (invertiert — tiefer Drawdown = mehr Punkte):
ath_pct = abs(asset.ath_change_pct or -50.0)
ath_score = float(min(5.0, ath_pct // 20))

# ENTSCHEIDUNG nötig (zwei valide Optionen):

# Option A: Trend-following (nahe am ATH = Stärke = mehr Punkte)
ath_pct = abs(asset.ath_change_pct or -50.0)  # 0% = am ATH, 80% = weit weg
ath_score = max(0.0, 5.0 - ath_pct // 20)     # Am ATH: 5 Punkte, -80%: 1 Punkt

# Option B: Contrarian (explizit als Value-Signal dokumentiert)
# Wenn Option B gewählt: alle anderen Momentum-Dimensionen müssen auch Contrarian
# werden (sonst inkonsistentes Mischsignal). Empfehlung: Option A nehmen.

# EMPFEHLUNG: Option A implementieren
```

---

> ⚡ **CHALLENGE 04 — Survivorship Bias im Universum (kritisch für Validität)**
> Spec trainiert/backtestet auf „SMI-20 + SMIM-30" — aber implizit auf der *heutigen* Zusammensetzung. Titel, die 2015–2024 aus dem Index flogen (Credit Suisse!), fehlen. Dadurch lernt das Modell systematisch an Überlebenden → Alpha überschätzt, Krisensignale unterrepräsentiert. **Credit Suisse 2023 ist das didaktisch wertvollste Beispiel und darf nicht fehlen.**
> **Fix:** Universum **point-in-time** modellieren — Tabelle `index_constituents (index, ticker, valid_from, valid_to)`. Snapshots nur für Titel bilden, die *zum Snapshot-Datum* im Index waren. Mindestens delistete Titel (CSGN, etc.) manuell ergänzen. Siehe Kap. 19.

> ⚡ **CHALLENGE 06 — Das System trifft nie die eigentliche Trading-Entscheidung**
> Die Vision (Kap. 0) verspricht ein „Trading-Entscheidungs-Tool". Aber die ganze Spec endet bei `BUY/HOLD/SELL` + Wahrscheinlichkeit. **Es fehlt: Wie viel? Wann raus?** Ohne Position-Sizing und Exit-Logik ist es weiterhin ein Anzeige-Tool — nur mit mehr Nachkommastellen.
> **Ergänzung (neuer `RiskSizingService`):**
> - **Position-Sizing** aus Konfidenz × erwartetem Edge, gedeckelt (z.B. fractional Kelly / Vol-Targeting). Nie „all-in auf ein Signal".
> - **Stop-Loss / Take-Profit / Time-Stop** pro Signal (der `horizon_days` ist faktisch schon ein Time-Stop — explizit machen).
> - **Portfolio-Constraints:** max Gewicht/Titel, max Sektor-Exposure, CHF-Klumpenrisiko. `portfolio_agent.py` existiert bereits — andocken statt neu bauen.
> - **Kalibrierung:** die „73%-Wahrscheinlichkeit" (Kap. 0) muss kalibriert sein (Reliability-Diagram, Brier-Score), sonst ist die Zahl Fiktion. Siehe Kap. 20.


---

## 6 · Continuous Learning Loop (Vollständig)

```
Täglich Mo-Fr:
┌─────────────────────────────────────────────────────────┐
│ 04:00  DataStewardAgent  → Preise prüfen + DB updaten   │
│ 05:00  MLFeatureService  → Features aus DB berechnen    │
│ 06:00  NewsIngestion     → RAG-Index aktualisieren      │
│ 06:30  CryptoDailySnapshot → Tages-Signale berechnen    │
│ 07:00  StockDailySnapshot  → Aktien-Signale berechnen   │
│ 08:00  AlertEngine       → User-Alerts versenden        │
│ 09:00  SignalAccuracyAgent → Gestrige Signale evaluieren│
│                           → Win-Rate berechnen          │
│                           → Wenn >20 neue Outcomes:     │
│                             → LightGBM warm_start       │
│                             → A/B-Test neues vs. altes  │
│                             → Bei Verbesserung: deploy  │
└─────────────────────────────────────────────────────────┘

Alle 4h (auch Sa/So):
┌─────────────────────────────────────────────────────────┐
│ */4h  CryptoIntradayAgent → BTC/ETH 1h-Kerzen + Signal │
└─────────────────────────────────────────────────────────┘

Wöchentlich (Freitag 22:00):
┌─────────────────────────────────────────────────────────┐
│ Volles ML Retraining (LightGBM, alle Daten seit 2015)   │
│ Modell-Versionierung + Artifact Upload                  │
└─────────────────────────────────────────────────────────┘

Monatlich (1. Montag 03:00):
┌─────────────────────────────────────────────────────────┐
│ SNBRateUpdateAgent → SNB/ECB/Fed Zinsen in macro_rates  │
│ SimFin-Update → neue quartalsweise Fundamentaldaten     │
└─────────────────────────────────────────────────────────┘
```

---

## 7 · SignalValidationService → Echter Backtest

**V2-Problem:** Nutzt 20-Tage-Momentum als Proxy für PRISMA-Score — kein echter Test.

**V3-Fix:**
```python
# backend/application/services/signal_validation_service.py
# Umbenennen zu: SignalBacktestService

class SignalBacktestService:
    """
    Echter historischer Backtest basierend auf gespeicherten signal_outcomes.
    Liest aus signal_outcomes-Tabelle, nicht aus Momentum-Proxy.
    """
    
    async def get_backtest_stats(self, ticker: str, days: int = 365) -> BacktestStats:
        outcomes = await self._repo.get_outcomes(ticker, days=days)
        
        buy_outcomes = [o for o in outcomes if o.signal in ("BUY", "STRONG_BUY")]
        
        if len(buy_outcomes) < 5:
            return BacktestStats(insufficient_data=True)
        
        win_rate = sum(1 for o in buy_outcomes if o.was_correct) / len(buy_outcomes)
        avg_return = sum(o.actual_return for o in buy_outcomes) / len(buy_outcomes)
        avg_alpha = sum(o.excess_return for o in buy_outcomes) / len(buy_outcomes)
        
        return BacktestStats(
            ticker=ticker,
            n_signals=len(buy_outcomes),
            win_rate=win_rate,
            avg_return=avg_return,
            avg_alpha_vs_smi=avg_alpha,
            label=self._generate_label(win_rate, avg_alpha),
        )

> ⚡ **CHALLENGE 03 — Backtest/Outcome-Returns ohne Kosten = Phantom-Alpha (kritisch)**
> Weder `backtest_service.py` noch das neue `signal_outcomes`-Schema modellieren **Transaktionskosten**. Für Schweizer Retail ist das gravierend:
> - **Eidg. Stempelabgabe** 0.15% pro Seite auf CH-Titel (0.30% round-trip),
> - **Broker-Courtage** (typ. 0.1–0.5%),
> - **Spread/Slippage** (bei SMIM-Titeln und Krypto erheblich).
>
> Ein „+1.8% Alpha über 30 Tage" kann nach Kosten **negativ** sein. **Fix:** `signal_outcomes` um `cost_adjusted_return` und `net_excess_return` erweitern; ein zentrales `TransactionCostModel` (CH-Stocks / SMIM / Krypto getrennt). Das Dashboard-Widget (Kap. 8.1) muss **Netto-Alpha** zeigen, sonst führt es den Dozenten — und den User — in die Irre. Siehe Kap. 17.

```

---

## 8 · Dashboard — Was der Dozent sehen soll

Das Dashboard soll folgende Daten auf einen Blick zeigen (Dozenten-Vision: "viele Daten angereichert → Entscheidungshilfe"):

### 8.1 Signal-Performance Widget (NEU)
```
┌─────────────────────────────────────────────────────┐
│ PRISMA Signal Performance                           │
│ ────────────────────────────────────────────────── │
│ 30-Tage Win-Rate:  61%  ████████░░                  │
│ Alpha vs SMI:    +1.8%  (PRISMA schlägt Index)      │
│ Ausgewertete Signale: 47                            │
│ Modell-Version:  LightGBM v2026-06-20              │
└─────────────────────────────────────────────────────┘
```

### 8.2 Bitcoin Card (Beispiel Dozent: "Bitcoin Kurs + Faktoren → Signal")
```
┌─────────────────────────────────────────────────────┐
│ BTC/CHF   CHF 94'230   ▲ +2.3% (24h)               │
│                                                     │
│ Signal:  🟢 BUY        Score: 72/100                │
│                                                     │
│ Faktoren:                                           │
│ • Momentum:  +18  RSI 38 (überverkauft)             │
│ • Trend:     +22  Preis > EMA50, EMA200             │
│ • Sentiment: +15  Fear & Greed: 28 (Extreme Fear)   │
│ • Pattern:   +8   Bullish Engulfing erkannt          │
│ • Risiko:    +9   Niedrige SMI-Korrelation           │
│                                                     │
│ Intraday (1h): BUY ↑   [vor 2h berechnet]          │
│ MVRV-Z: 1.3 (FAIR)     Sharpe: 0.8 vs SMI: 0.4     │
│                                                     │
│ "RSI zeigt Überverkauf bei steigendem Volumen —     │
│  klassisches Kaufsignal in Fear-Phase."             │
│                                          [Analyse ▶]│
└─────────────────────────────────────────────────────┘
```

### 8.3 Aktien Card (NESN)
```
┌─────────────────────────────────────────────────────┐
│ NESN   CHF 82.50    ▲ +0.8% (24h)                  │
│                                                     │
│ Signal:  🟡 HOLD       Score: 54/100                │
│ ML-Pred: NEUTRAL (63% Konfidenz)                    │
│                                                     │
│ Score-Breakdown:                                    │
│ • Momentum:  38/100  Schwächer als SMI (-2.1%)      │
│ • Value:     62/100  P/E 18x (Sektor-Median: 20x)   │
│ • Quality:   71/100  ROE 12%, FCF-Margin 8%         │
│ • Income:    42/100  Div-Yield 2.8%                 │
│                                                     │
│ Win-Rate (letzte 90d): 58%  │  Alpha: +0.4% vs SMI  │
│ Makro: SNB 0% ✓  CHF stark ⚠ (Exporteur)           │
└─────────────────────────────────────────────────────┘
```

---

## 9 · Technische Fixes (alle offenen Bugs)

### 9.1 Bekannte Bugs die gefixt werden müssen

| ID | Datei | Problem | Fix |
|---|---|---|---|
| FIX-01 | `crypto_scorer.py` | ATH-Score invertiert | `max(0, 5 - ath_pct//20)` |
| FIX-02 | `cointelligence_agent.py` | CHF/USD hardcodiert | `await fetch_chf_usd()` |
| FIX-03 | `macro_agent.py` + `macro_agent_v2.py` | `_EXPORT_HEAVY` dupliziert | `from backend.domain.data.macro_profiles import EXPORT_HEAVY` |
| FIX-04 | `macro_agent.py` | Inflation-Fallback gibt +10 | `pass` statt `score += 10` |
| FIX-05 | `macro_agent.py` | PMI nie im Score | PMI-Block hinzufügen |
| FIX-06 | `ml_feature_service.py` | SNB-Rate hardcodiert | Aus `macro_rates`-Tabelle lesen |
| FIX-07 | `investment_director.py` | Checkpoint-Dict nicht thread-safe | `asyncio.Lock` hinzufügen |
| FIX-08 | `crypto_agent_service.py` | `max_tokens=120` zu knapp | `max_tokens=180` |
| FIX-09 | `backtest_service.py` | Datum-Range wird ignoriert | `get_prices(needed, start_date, end_date)` implementieren |
| FIX-10 | `decisions.py` | `_MAX_LIVE_TICKERS=12` vs Docstring 25 | Docstring auf 12 korrigieren |
| FIX-11 | `yfinance_swiss.py` | `dividend_yield_pct` 388% (CHF statt %) | Division durch Preis prüfen |
| FIX-12 | `news_ingestion_service.py` | Embedding-Index-Mismatch | Dimension-Check vor Insert |
| FIX-13 | `narrative_service.py` | Race-Condition Job-Status | TOCTOU fix mit `SELECT FOR UPDATE` |

### 9.2 Was in V2 korrekt ist (nicht anfassen)

- `LLMClient` + `CostTracker` → korrekt, beibehalten
- `snb_adapter.py` → korrekt, live von data.snb.ch
- `ecb_fx_adapter.py` → korrekt, live von ECB SDW
- `fred_adapter.py` → korrekt, live von FRED
- Prompt-Caching überall → korrekt
- `CryptoPatternService` → gut, ggf. ausbauen
- Alert-Engine + SendGrid → korrekt
- Alembic-Migrations 0001-0030 → nicht anfassen, nur neue hinzufügen

---

## 10 · SimFin Integration (Datensatz für Dozenten)

**Zweck:** Historische quartalsweise Fundamentaldaten für alle SMI/SMIM-Titel seit 2015.  
**Das ist der offizielle "Datensatz" des Projekts** — sauber, reproduzierbar, akademisch zitierbar.

```python
# scripts/seed_simfin_fundamentals.py
import simfin as sf

sf.set_api_key(os.environ["SIMFIN_API_KEY"])
sf.set_data_dir("~/simfin_data/")

# Income Statement: Revenue, EPS, Net Income
income = sf.load(dataset="income", variant="quarterly", market="ch")

# Balance Sheet: Total Assets, Debt, Equity
balance = sf.load(dataset="balance", variant="quarterly", market="ch")

# Cash Flow: FreeCashFlow, CapEx
cashflow = sf.load(dataset="cashflow", variant="quarterly", market="ch")

# Derived Metrics berechnen und in stock_fundamentals schreiben:
# ROE = Net Income / Shareholders Equity
# FCF Margin = Free Cash Flow / Revenue
# Debt/Equity = Total Debt / Shareholders Equity
# EPS Growth YoY = (EPS_q - EPS_q-4) / abs(EPS_q-4)
```

**Neues Secret in Render + GitHub Actions:**
```
SIMFIN_API_KEY = <kostenloser Key von simfin.com>
```

---

## 11 · GitHub Actions — Vollständige neue Konfiguration

```yaml
# .github/workflows/daily-data-seed.yml (Ergänzungen zu V2)

jobs:
  # NEU: 03:30 UTC — DataStewardAgent (V3)
  data-steward:
    cron: "30 3 * * 1-5"
    runs-on: ubuntu-latest
    
  # NEU: 09:00 UTC — SignalAccuracyAgent
  signal-accuracy:
    cron: "0 9 * * 1-5"
    needs: [stock-daily, crypto-daily]
    runs-on: ubuntu-latest

  # GEÄNDERT: Krypto jetzt auch Sa/So (war: nur Mo-Fr)
  crypto-daily:
    cron: "30 6 * * *"   # war: "30 6 * * 1-5"
    
  # NEU: Alle 4h, auch Sa/So
  crypto-intraday:
    cron: "0 */4 * * *"
    runs-on: ubuntu-latest
    
  # NEU: 1. Montag des Monats 03:00
  macro-rate-update:
    cron: "0 3 1-7 * 1"   # Ersten Montag im Monat
    runs-on: ubuntu-latest
```

---

## 12 · Neue Datei-Struktur (nur Ergänzungen, nichts umbenennen)

```
backend/
├── application/
│   ├── agents/
│   │   ├── signal_accuracy_agent.py        ← NEU
│   │   ├── macro_news_agent.py             ← NEU (ersetzt V2 als optionale Erweiterung)
│   │   └── [bestehende Agents bleiben]
│   └── services/
│       ├── sector_median_service.py        ← NEU
│       └── signal_backtest_service.py      ← NEU (ersetzt SignalValidationService)
├── domain/
│   ├── data/
│   │   └── macro_profiles.py              ← NEU (EXPORT_HEAVY, DOMESTIC_FOCUS)
│   └── services/
│       └── swiss_quant_scorer_v3.py       ← NEU (parallel zu V2, dann ersetzen)
├── infrastructure/
│   └── persistence/
│       └── repositories/
│           ├── price_history_repository.py ← NEU
│           ├── fundamentals_repository.py  ← NEU
│           └── signal_outcome_repository.py ← NEU
└── scripts/
    ├── seed_historical_prices.py          ← NEU (einmalig)
    ├── seed_simfin_fundamentals.py        ← NEU (einmalig + monatlich)
    ├── snb_rate_update.py                 ← NEU
    └── crypto_intraday_snapshot.py        ← NEU

backend/alembic/versions/
├── 0031_create_stock_price_history.py     ← NEU
├── 0032_create_stock_fundamentals.py      ← NEU
├── 0033_create_crypto_price_history.py    ← NEU
├── 0034_create_signal_outcomes.py         ← NEU
└── 0035_create_macro_rates.py             ← NEU
```

---

## 13 · Priorisierung für Terminal Agents

### Phase 1 — Fundament (zuerst, alles andere hängt davon ab)
1. **Migrationen 0031-0035** erstellen und ausführen
2. **`seed_historical_prices.py`** — 7 Jahre SMI + Krypto in DB
3. **`seed_simfin_fundamentals.py`** — SimFin-Datensatz laden
4. **`FIX-01` ATH-Score** in `crypto_scorer.py` korrigieren
5. **`FIX-06`** SNB-Rate aus `macro_rates`-Tabelle lesen
6. **`macro_profiles.py`** erstellen, V1+V2 darauf umstellen (FIX-03)

### Phase 2 — Neue Scoring-Logik
7. **`SwissQuantScorerV3`** mit relativer Bewertung implementieren
8. **`SectorMedianService`** erstellen
9. **ML-Pipeline** auf SimFin-Fundamentals + Point-in-Time-korrekten Features umstellen
10. **Train/Val/Test-Split** neu durchführen, Ergebnisse dokumentieren

### Phase 3 — Neue Agents
11. **`SignalAccuracyAgent`** + `signal_outcome_repository.py` + GitHub Action 09:00
12. **`DataStewardAgent`** V3 (echter DB-Writer) + GitHub Action 03:30
13. **`CryptoIntradayAgent`** + neue GitHub Action alle 4h + auch Sa/So
14. **`SNBRateUpdateAgent`** + GitHub Action monatlich

### Phase 4 — Dashboard + Qualität
15. **Signal Performance Widget** im Frontend
16. **Win-Rate API-Endpoint** `GET /api/v1/signals/accuracy`
17. **Restliche Bugfixes** FIX-02 bis FIX-13
18. **MacroNewsAgent** als optionale Erweiterung
19. **SimFin monatliches Update** einrichten

---

## 14 · Wichtige Constraints für Agents

1. **Niemals direkt auf `main` pushen.** Immer Feature-Branch → PR → CI grün → merge.
2. **Neue Features brauchen Unit-Tests.** Besonders: alle neuen Services + Repositories.
3. **Keine Breaking Changes an bestehenden API-Endpoints.** Nur neue Endpoints hinzufügen.
4. **LLM-Calls immer über `LLMClient`** — nie `anthropic.AsyncAnthropic()` direkt.
5. **Alle DB-Writes über Repository-Pattern** — nie direkt `session.execute()` in Services.
6. **Krypto = nur Coins** — keine ETPs, keine ETFs, keine iShares/VanEck-Produkte.
7. **SimFin-Daten sind point-in-time korrekt zu verwenden** — nie zukünftige Fundamentals für historische Snapshots nutzen.
8. **`_stub_fundamentals()`** in Training-Pfaden nicht mehr verwenden — immer SimFin-Daten.
9. **ML-Modell Änderungen** immer mit A/B-Test gegen aktuelles Modell validieren bevor deploy.
10. **PostgreSQL-Migrationsnummering:** nächste ist 0031 — nicht überspringen.

---

*PRISMA V3 — Master Specification | 2026-06-20 | Andrea Petretta | FHNW BI Module FS 2026*


---

# TEIL B · CHALLENGE & ERWEITERUNGEN (Reviewer-Layer V3.1)

> Die folgenden Kapitel 15–22 sind **neu**. Sie ersetzen nichts, sondern ergänzen Teil A um das,
> was zwischen „läuft" und „akademisch verteidigbar + real handelbar" fehlt. Reihenfolge = grobe Priorität.

---

## 15 · Datenstrategie — Quellen, Tiefe & Seed-Pipeline (ersetzt Kap. 2.3 & 10)

> ⛔ **Teilweise ÜBERSCHRIEBEN durch TEIL F.** Kurse/Krypto/Seed-Pipeline aus Kap. 15 gelten weiter. Die Fundamentals-Quellen-Diskussion (SimFin/EODHD/FMP, `dataset_source_fundamentals`) ist durch TEIL F final entschieden: keine historischen CH-Fundamentals, ML ohne Fundamentals. Bei Widerspruch gilt TEIL F.

Bezug: **CH-01 / FIX-14**. SimFin-CH-Free trägt nicht. Hier die konkrete, verdrahtete Lösung.

### 15.1 Wie viele Jahre zurück?

Faustregel: **so weit, dass mehrere Marktregime drin sind** (Crash, Seitwärts, Bull), aber nicht so weit, dass uralte Strukturbrüche das Modell verwässern.

| Datenart | Empfohlene Tiefe | Begründung (Regime-Abdeckung) |
|---|---|---|
| **CH-Aktien Kurse (daily)** | **2015 → heute (~11 J.)** | 2018-Selloff, COVID-Crash 2020, Zinswende 2022, **Credit-Suisse-Kollaps 2023** |
| **CH-Aktien Fundamentals (quarterly)** | **2015 → heute** | deckt ~40+ Quartale/Titel → genug für PIT-Features |
| **Krypto Kurse (daily)** | **2017 → heute (~9 J.)** | Bull 2017, Bär 2018, Bull 2020/21, LUNA/FTX-Crash 2022, ETF-2024 |
| **Krypto Kurse (1h, für Intraday-Agent)** | **2020 → heute (~6 J.)** | 1h-Tiefe vor 2020 lückenhaft; 6 J. reichen für Intraday-Indikatoren |

**Wichtig (Realismus statt Wunsch):** Mehr Jahre ≠ mehr *unabhängige* Trainingsbeispiele. Wegen der überlappenden 30-Tage-Targets (CH-02) ist die effektive Stichprobe klein. Tiefe hilft v.a. der **Regime-Diversität**, nicht der reinen Sample-Zahl. 2015 ist der pragmatische Kompromiss: tief genug für Krisen, kurz genug, dass die SMI-Zusammensetzung handhabbar bleibt.

### 15.2 Woher — pro Datenart die konkrete Quelle

> **Strategie: Bulk-Bootstrap aus Datensätzen + inkrementelles API-Update.** Der einmalige Historien-Seed kommt aus grossen CSV-Dumps (keine Rate-Limits). Danach holt der tägliche Cron nur noch die *neuen* Zeilen per API. Das passt exakt zum V3-Prinzip „DB ist primäre Quelle" (Kap. 2.1).

| Datenart | Bootstrap (einmalig, Bulk) | Inkrementell (täglich, API) |
|---|---|---|
| CH-Aktien Kurse | yfinance Bulk-Download ODER EODHD EOD-CSV | yfinance / EODHD EOD |
| CH-Aktien Fundamentals | **EODHD Fundamentals API** (CH-Coverage, standardisierte Statements) — Alternativ Twelve Data (XSWX) | EODHD monatlich (neue Quartale) |
| Krypto Kurse daily/1h | **CryptoDataDownload** CSV (Binance/Bitstamp, seit 2017) ODER Kraken ZIP | CoinGecko / Twelve Data |
| Makro (SNB/ECB/Fed) | bestehende Adapter (`snb_adapter`, `ecb_fx_adapter`, `fred_adapter`) | dieselben, via `SNBRateUpdateAgent` |

**Kaggle?** Ja, als *Referenz/Backup* nützlich (z.B. „14 cryptos hourly", S&P-Fundamentals-Dumps) und gut zitierbar für den Bericht. Aber Kaggle-Sets sind eingefroren (kein Live-Update) → nur für Bootstrap, nie als laufende Quelle. Für CH-Aktien gibt es auf Kaggle praktisch nichts Brauchbares → dort führt an einer API kein Weg vorbei.

### 15.3 `dataset_source`-Schalter (statt SimFin als gesetzt)

Kap. 2.3, 4.2, 10 bekommen einen Provider-Schalter, damit der ML-Datensatz nicht an einer Quelle hängt:

```python
# backend/config.py
DATASET_SOURCE_FUNDAMENTALS = os.getenv("DS_FUND", "eodhd")   # eodhd | twelvedata | simfin_us | yf_derived
DATASET_SOURCE_PRICES       = os.getenv("DS_PRICE", "yfinance")
DATASET_SOURCE_CRYPTO       = os.getenv("DS_CRYPTO", "cryptodatadownload")
```

`FundamentalsProvider`-Port existiert bereits (`backend/domain/ports/fundamentals_provider.py`) → pro Quelle ein Adapter dahinter. Der bestehende `simfin_adapter` bleibt als `simfin_us`-Option erhalten (für die saubere US-ML-Demo).

### 15.4 Die Seed-Pipeline (konkret)

```
scripts/
├── verify_dataset_coverage.py     # Phase 0 GATE — siehe 15.5, MUSS zuerst grün sein
├── seed_historical_prices.py      # CH-Aktien daily 2015→ in stock_price_history
├── seed_crypto_history.py         # Krypto daily(2017→) + 1h(2020→) in crypto_price_history
├── seed_fundamentals.py           # via dataset_source → stock_fundamentals (PIT: publish_date!)
└── _pipeline/
    ├── extract.py    # Quelle → rohes DataFrame (CSV-Dump ODER API)
    ├── normalize.py  # Spalten/Ticker/Währung/Timezone vereinheitlichen
    ├── validate.py   # Sanity: keine Nulls in OHLC, high>=low, Spike-Check, Lücken-Report
    └── load.py       # idempotenter UPSERT (ON CONFLICT DO NOTHING/UPDATE)
```

Ein generischer **ETL-Flow** für jede Datenart:
```python
def run_seed(source, normalizer, repo):
    raw   = extract(source)              # Bulk-CSV oder paginierte API
    clean = normalize(raw, normalizer)   # → einheitliches Schema
    report = validate(clean)             # Lücken/Spikes loggen, NICHT still droppen
    repo.bulk_upsert(clean)              # UNIQUE-Constraint macht es idempotent
    log_to_cron_run(report)              # Observability (Kap. 21)
```

**Designprinzipien:** idempotent (mehrfach laufbar ohne Duplikate dank `UNIQUE`-Constraints aus Kap. 2.2), resumebar (pro Ticker committen, nicht alles am Ende), und **laut bei Lücken** statt stillem Stub-Fallback (genau der V2-Fehler).

### 15.5 Phase 0 — Coverage-Gate (blockierend, vor allem anderen)

`scripts/verify_dataset_coverage.py`: lädt für je 3 SMI/SMIM-Titel die Fundamentals der gewählten Quelle und schreibt `docs/dataset_coverage.md` (Quartale, Null-Quote/Feld, ältestes/neuestes `publish_date`, ob pe/pb/roe berechenbar).
**Akzeptanz:** ≥ 20 Quartale mit < 20% Nulls/Titel → Quelle ok. Sonst nächste Quelle im Schalter (15.3) testen. **Erst wenn grün, ist Kap. 4/16 baubar.**

## 16 · ML-Methodik — sauber genug für die Bewertung

Bezug: **CH-02**. „ML-basiert" wird nur honoriert, wenn die Methodik standhält. Konkrete Pflichtbausteine:

**16.1 Validierung:** Purged & Embargoed Walk-Forward CV. Embargo = Horizont (30 Handelstage). Mehrere rollende Folds statt eines einzelnen Test-Blocks → robustere Schätzung + Streuung ausweisen.

**16.2 Baselines (immer mitlaufen lassen):** Majority-Class, Momentum-only, Quant-Score-only. Modell muss alle drei auf **Macro-F1** schlagen. Tabelle in `docs/ml_eval.md`.

**16.3 Metriken:** Macro-F1, Confusion-Matrix, pro-Klasse Precision/Recall. **Nicht** Accuracy (NEUTRAL dominiert). Zusätzlich finanziell: Information Coefficient (Rank-Korrelation Pred↔Realisierung) und Decile-Spread.

**16.4 Imbalance:** `is_unbalance=True` oder explizite `class_weight`. Schwelle ±2% empirisch prüfen (Klassenverteilung dokumentieren).

**16.5 Overfitting-Kontrolle:** bei effektiv kleiner Stichprobe (siehe CH-02) — `num_leaves` klein, `min_child_samples` hoch, `lambda_l1/l2 > 0`, Early-Stopping auf Val-Fold. Feature-Importance + SHAP für Interpretierbarkeit (auch ein Bewertungs-Plus: „erklärbar").

**16.6 Feature-Leakage-Audit:** jedes der 25+ Features einzeln darauf prüfen, dass es zum Snapshot-Datum bekannt war. Besonders: `dividend_growth`, `revenue_growth`, `eps_growth_yoy` brauchen den **publish_date**, nicht den period_end (der Adapter weiss das bereits — im Feature-Builder konsequent durchziehen).

**16.7 Reproduzierbarkeit:** fixe Seeds, `requirements.lock`, Datensatz-Hash im Modell-Metadata. Der Dozent muss `make train` ausführen und dieselben Zahlen sehen.

---

## 17 · Transaktionskosten-Modell (neu)

Bezug: **CH-03**. Neuer Baustein `backend/domain/services/transaction_cost_model.py`:

| Asset-Klasse | Stempelabgabe | Courtage (Annahme) | Spread/Slippage |
|---|---|---|---|
| CH-Aktie (SMI/SMIM) | 0.15% / Seite | 0.20% | 0.05–0.15% |
| Krypto | – | 0.15–0.50% | 0.10–0.50% |

`net_return = gross_return - round_trip_costs`. **`signal_outcomes` erweitern** um `cost_adjusted_return`, `net_excess_return` (Migration 0036). Dashboard-Widget (8.1) und Backtest (Kap. 7) zeigen **Netto**-Zahlen; Brutto nur als sekundäre Angabe. Win-Rate-Threshold (`MIN_WIN_RATE = 0.48`) auf Netto-Basis neu kalibrieren — brutto 48% kann netto < 45% sein.

---

## 18 · Champion/Challenger statt Pseudo-A/B (Registry-Erweiterung)

Bezug: **CH-05**. `ModelRegistry` erweitern: `champion`, `challenger`, `promote(reason, metrics)`, `rollback()`, Metrik-Historie je Version.

Ablauf:
1. Retraining erzeugt **Challenger** (nicht aktiv).
2. Challenger läuft **Shadow**: predicted parallel, Outcomes werden getrackt, beeinflusst keine User-Signale.
3. Nach ≥ 30 *unabhängigen* Shadow-Outcomes: Vergleich mit McNemar/Bootstrap-CI auf Netto-Metrik.
4. Nur bei signifikanter Verbesserung → `promote()`. Sonst Challenger verwerfen, Vorfall loggen.
5. `rollback()` wenn Champion live degradiert (Win-Rate-Alert aus 5.1 triggert).

**Warm-Start nur für Challenger.** Champion-Linie = periodisches Voll-Retraining (Freitag, Kap. 6), um Warm-Start-Drift zu vermeiden.

---

## 19 · Survivorship-Bias / Point-in-Time-Universum (neu)

Bezug: **CH-04**. Neue Tabelle (Migration 0037):

```sql
CREATE TABLE index_constituents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    index_name  VARCHAR(10) NOT NULL,   -- 'SMI' | 'SMIM'
    ticker      VARCHAR(20) NOT NULL,
    valid_from  DATE NOT NULL,
    valid_to    DATE,                    -- NULL = aktuell
    UNIQUE (index_name, ticker, valid_from)
);
```

Feature-/Backtest-Snapshots nur für Titel mit `valid_from <= snap <= COALESCE(valid_to, today)`. Mindestens delistete Titel (CSGN/Credit Suisse u.a.) seeden. **Didaktischer Gewinn:** Credit Suisse 2023 wird zum Vorzeige-Case, dass PRISMA Risiko *vor* dem Kollaps erkennt — oder ehrlich zeigt, dass es das nicht tat.

---

## 20 · Risk- & Position-Sizing-Layer (neu — schliesst die Vision)

Bezug: **CH-06**. Neuer `backend/domain/services/risk_sizing_service.py`, angedockt an bestehenden `portfolio_agent.py`.

- **Sizing:** `weight = clip(confidence * expected_edge / volatility, 0, max_weight)` (Vol-Targeting / fractional Kelly, konservativ gedeckelt).
- **Exits:** Stop-Loss (z.B. −2 ATR), Take-Profit, Time-Stop = `horizon_days`.
- **Portfolio-Constraints:** max % je Titel, max % je Sektor, CHF-Klumpen-Check, Krypto-Gesamtcap.
- **Kalibrierung der Wahrscheinlichkeit:** `CalibrationService` — Reliability-Diagram + Brier-Score; falls unkalibriert: Platt/Isotonic. Die im Dashboard gezeigte „73%" muss kalibriert sein, sonst aus dem UI entfernen.

Dashboard-Card (8.2/8.3) ergänzen um: „Empfohlene Position: 3.2% des Depots · Stop bei CHF 88'400 · Ziel CHF 102'000".

---

## 21 · Compliance, Disclaimer & Betrieb (fehlt komplett)

Ein an Retail-Investoren gerichtetes „Trading-Entscheidungs-Tool" braucht:
- **Disclaimer** (keine Anlageberatung, keine Garantie, Risikohinweis) sichtbar im UI + in jedem Alert/E-Mail. In CH rechtlich relevant (FIDLEG-Nähe) — im Bericht als bewusste Abgrenzung „nur Informationstool" erwähnen.
- **Datenquellen-Lizenzen:** yfinance/Yahoo ToS, SimFin-Lizenz, CoinGecko Attribution — kurz dokumentieren (`docs/data_licenses.md`).
- **Secrets-Hygiene:** `GLASSNODE_API_KEY`, `SIMFIN_API_KEY`, SendGrid — nur in Render/GH-Secrets, `.env.example` ohne Werte (prüfen, dass keine Keys committed sind).
- **Observability:** `cron_run_log` existiert — neue Agents (SignalAccuracy, Intraday, DataSteward) müssen dort Start/Ende/Fehler schreiben. Ein „Health"-Endpoint/Widget: welcher Cron lief wann zuletzt, Datenfrische pro Tabelle.
- **Backfill-Resilienz:** GitHub-Action-Cron ist *best effort* (kann ausfallen/verspäten). Jeder Agent muss idempotent sein und Lücken nachholen (`get_stale_tickers` deckt das für Preise ab — analog für Signals/Outcomes).

---

## 22 · Zusätzliche Bugs / Lücken (Ergänzung zur FIX-Tabelle 9.1)

| ID | Datei / Bereich | Problem | Fix |
|---|---|---|---|
| FIX-14 | `simfin_adapter.py` | CH/EU-Coverage faktisch leer → stiller Stub-Fallback im Training | Coverage-Gate (Kap. 15) + lautes Logging/Abort statt stillem Stub |
| FIX-15 | `ml_feature_service.py` | Überlappende 30d-Targets → Leakage | Purged/Embargoed CV (Kap. 16) |
| FIX-16 | `backtest_service.py` + `signal_outcomes` | Keine Transaktionskosten | `TransactionCostModel` + Netto-Spalten (Kap. 17) |
| FIX-17 | `model_registry.py` | Kein Champion/Challenger, kein Rollback | Registry erweitern (Kap. 18) |
| FIX-18 | Universum/Seed | Survivorship Bias | `index_constituents` PIT (Kap. 19) |
| FIX-19 | `crypto_intraday_snapshot.py` | yfinance 1h-Daten sind unzuverlässig/lückenhaft für Krypto; `period=7d,interval=1h` bricht oft ab | CoinGecko/Twelve-Data als Primärquelle für Intraday; yfinance nur Fallback |
| FIX-20 | GH Action Wochenend-Crons | Krypto-Jobs müssen Sa/So laufen (`* * *`, nicht `1-5`); Mehr-Cron-`if:`-Muster ist OK (Repo nutzt es bereits korrekt in `daily-data-seed.yml`) | Cron-Strings auf 7 Tage setzen, bestehendes `if: github.event.schedule==`-Muster beibehalten |
| FIX-21 | „73%-Wahrscheinlichkeit" (Vision/Dashboard) | Unkalibrierte Modell-Confidence als Wahrscheinlichkeit ausgegeben | Kalibrierung + Brier (Kap. 20) oder Zahl entfernen |
| FIX-22 | Alle neuen Agents | Keine Idempotenz-/Backfill-Garantie bei Cron-Ausfall | Idempotente Upserts + Lücken-Nachholung (Kap. 21) |

---

## 23 · Korrigierte Priorisierung (ersetzt Kap. 13 in der Reihenfolge)

> Kap. 13 ist gut, aber **CH-01 muss davor**. Sonst baut Phase 2 auf Stub-Daten.

- **Phase 0 (NEU, blockierend):** Kap. 15 Datenquelle verifizieren. Erst grün → weiter.
- **Phase 1:** wie Kap. 13, aber `index_constituents` (Kap. 19) zu den Migrationen dazu.
- **Phase 2:** ML-Pipeline **mit** Methodik-Bausteinen aus Kap. 16 (Baselines + Purged CV von Anfang an, nicht nachgerüstet).
- **Phase 2.5 (NEU):** `TransactionCostModel` (17) + `RiskSizingService` (20) — bevor das Dashboard Zahlen zeigt.
- **Phase 3:** Agents wie gehabt; Registry-Erweiterung (18) zusammen mit SignalAccuracyAgent.
- **Phase 4:** Dashboard zeigt **Netto + kalibriert**; Compliance/Observability (21).

---

## 24 · Was an der Original-Spec ausdrücklich gut ist

Damit der Challenge fair bleibt — diese Entscheidungen sind richtig und sollten **nicht** verwässert werden:
- DB-als-primäre-Quelle statt Live-yfinance (Kap. 2) — genau richtig, löst das reale Blockade-Problem.
- Relativer Scorer statt absoluter Schwellwerte (Kap. 3) — der absolute Ansatz war nachweislich kaputt für CH-Titel.
- Continuous-Learning-Loop als Konzept (Kap. 6) — stark, solange die Methodik (Kap. 16/18) sauber ist.
- Scope-Disziplin (nur SMI/SMIM + Coins, keine ETPs) — gut, hält das Projekt fokussiert.
- Clean-Architecture-Constraints (Kap. 14: Repository-Pattern, LLMClient-Zwang, keine `main`-Pushes) — beibehalten.

> **Fazit des Reviews:** PRISMA V3 ist konzeptionell auf dem richtigen Weg vom Anzeige- zum Entscheidungstool. Die Lücken sind nicht im *Ehrgeiz*, sondern in der *Validität*: echte Daten (CH-01), ehrliche Returns (CH-03), saubere ML-Methodik (CH-02), und der fehlende Schritt von „Signal" zu „Entscheidung mit Grösse und Risiko" (CH-06). Wer Teil B abarbeitet, hat ein Projekt, das nicht nur läuft, sondern auch einer kritischen Prüfung standhält.

---

---

# TEIL C · THINK OUTSIDE THE BOX — Reframes (V3.1, bewusst radikal)

> Auftrag von Andrea: konzeptionell challengen, auch wenn dadurch viel umgebaut werden muss.
> Die folgenden Ideen sind **Reframes**, keine Bugfixes. Jeder Block: *Idee → Warum besser → Umbau-Kosten → Empfehlung*.
> Markierung: 🟢 sofort sinnvoll · 🟡 lohnt sich, mittlerer Umbau · 🔴 grosser Umbau, strategisch.

## C1 · 🔴 Vom Klassifikator zur Verteilung (Quantil-Regression) — der wichtigste Reframe
**Idee:** Statt OUTPERFORM/NEUTRAL/UNDERPERFORM (Kap. 4.2) den **erwarteten 30-Tage-Excess-Return als Verteilung** vorhersagen — LightGBM mit `objective="quantile"` für P10/P50/P90.
**Warum besser:** Genau das löst gleich drei offene Probleme auf einmal:
- Die „73%-Wahrscheinlichkeit" (Vision, CH-06) wird **echt** ableitbar statt erfunden — `P(excess>0)` aus der Verteilung.
- **Position-Sizing** (CH-06) bekommt seinen Input umsonst: Size ∝ erwarteter Median / Spread (P90−P10) = Rendite-pro-Risiko.
- Die künstliche ±2%-Klassengrenze (CH-02) und die Imbalance-Probleme verschwinden.
**Umbau:** ML-Target, Loss, `ml_prediction`-Value-Object, Dashboard-Anzeige. Mittelgross, aber zentral.
**Empfehlung:** **Machen.** Das ist der Hebel von „Score-Tool mit ML-Deko" zu „echtem Entscheidungstool".

## C2 · 🟡 Learning-to-Rank statt Per-Titel-Vorhersage
**Idee:** Die reale Frage ist nicht „ist NESN absolut gut?", sondern „**welche k von 50 heute?**". LightGBM `objective="lambdarank"`, gruppiert pro Tag, Ziel = Cross-Section-Ranking nach Forward-Excess.
**Warum besser:** Matcht exakt die Portfolio-Entscheidung, ist robuster gegen Marktdrift (relativ statt absolut) und liefert direkt eine Top-k-Watchlist.
**Umbau:** Dataset-Gruppierung + Eval (NDCG, Decile-Spread). Kombinierbar mit C1 (erst ranken, dann sizen).
**Empfehlung:** Als zweites Modell neben C1; im Champion/Challenger (Kap. 18) gegeneinander testen.

## C3 · 🟢 Conformal Prediction für ehrliche Konfidenz
**Idee:** Modell-Output mit **Split-Conformal** kalibrieren → verteilungsfreie Abdeckungsgarantie (z.B. „80%-Intervall hält in 80% der Fälle").
**Warum besser:** Akademisch sehr stark und billig nachrüstbar; ersetzt die unkalibrierte Softmax-„Konfidenz" (FIX-21). Macht jede gezeigte Wahrscheinlichkeit verteidigbar.
**Umbau:** Klein — ein `ConformalCalibrator` um das bestehende Modell. **Empfehlung: machen, niedrig hängende Frucht.**

## C4 · 🟡 Regime-Bewusstsein (der Credit-Suisse-Test)
**Idee:** Ein **Markt-Regime-Feature** (Risk-On/Off via SMI-Vol, Yield-Spread, Drawdown-State; optional simple HMM) als Feature ODER separate Modelle pro Regime.
**Warum besser:** Ein über alle Regime gemitteltes Modell ist in genau den Momenten schwach, die zählen (2020, 2022, CS-2023). Mit Regime-State lernt es „in Stress-Phasen anders".
**Umbau:** 1–2 Features + optional Regime-Routing. **Empfehlung:** mindestens das Feature; Routing optional.

## C5 · 🟡 News-RAG als Feature, nicht nur als Agent
**Idee:** Die bestehende News-/Filing-RAG-Pipeline liefert pro Titel/Tag ein **News-Surprise-/Sentiment-Feature** direkt in den ML-Vektor (Embedding-Aggregat + Sentiment-Score), statt News nur im optionalen MacroNewsAgent (Kap. 5.4) zu nutzen.
**Warum besser:** Verbindet die RAG-Anforderung des Dozenten *messbar* mit der Prediction (statt RAG als getrenntes Schaufenster). Echtes „Daten angereichert → Entscheidung".
**Umbau:** Feature-Builder + PIT-Sauberkeit der News-Timestamps. **Empfehlung:** stark fürs BI-Modul (RAG + ML in einem).

## C6 · 🟢 Ein Backtest-Kern statt zwei Wahrheiten
**Idee:** `signal_outcomes` (live) und `SignalBacktestService` (historisch) auf **eine** event-getriebene Engine mit dem `TransactionCostModel` (Kap. 17) stützen. Live = Spezialfall des Backtests „bis heute".
**Warum besser:** Keine Divergenz zwischen „was wir backtesten" und „was wir live messen". Eine Netto-Equity-Kurve als Single Source of Truth.
**Umbau:** mittel — aber verhindert genau die V2-Krankheit zweier Signal-Wahrheiten. **Empfehlung: machen.**

## C7 · 🟢 Paper-Trading-Shadow als Champion/Challenger-Ausbau
**Idee:** Challenger (Kap. 18) läuft nicht nur als Prediction-Shadow, sondern als **simuliertes Netto-Depot** mit dem Risk-Layer (Kap. 20). Promotion-Kriterium = bessere *Netto-Equity-Kurve* out-of-sample.
**Warum besser:** Bewertet Modelle an dem, was zählt (Geld nach Kosten), nicht an Klassen-Accuracy. Liefert dem Dozenten genau die „PRISMA schlägt SMI"-Kurve.
**Umbau:** klein, sobald C6 + Risk-Layer stehen. **Empfehlung: machen.**

## C8 · 🟡 LLM als Critic/Explainer, nicht als Prädiktor
**Idee:** Klare Rollentrennung — Zahlen kommen aus ML/Quant, der LLM macht (a) Narrative und (b) einen **Red-Team-Check**: „widersprechen aktuelle News dem Quant-Signal?" → Confidence-Dämpfung statt eigener Zahl.
**Warum besser:** Schärft die Agentic-AI-Story (Tool-Use mit echtem Zweck), vermeidet LLM-für-if/elif (das V2-Problem, Kap. 5.4), und macht Signale robuster.
**Umbau:** klein, baut auf bestehender Agent-Architektur. **Empfehlung: machen.**

## C9 · 🟢 Unified Asset Abstraction (Aktie & Krypto)
**Idee:** Gemeinsames `AssetFeatureSet` + Scorer-Interface; Daily/Intraday als Parameter, nicht als Copy-Paste-Agent.
**Warum besser:** Halbiert den neuen Code (CryptoIntradayAgent vs CryptoScorer vs StockScorer), eine Test-Suite. **Empfehlung:** beim Bauen der neuen Agents gleich so anlegen.

## C10 · 🟢 Decision Ledger (Reproduzierbarkeit & Erklärbarkeit)
**Idee:** Jedes Signal wird mit `model_version`, `feature_snapshot_hash` und Top-SHAP-Treibern gespeichert.
**Warum besser:** Volle Auditierbarkeit, das Dashboard kann historisch „warum BUY?" zeigen, und der Dozent kann jedes Resultat reproduzieren — starkes BI-Argument. **Empfehlung: machen, billig.**

### Empfohlenes „Outside-the-box"-Paket (realistischer Scope)
**Kern (hoher Nutzen/Aufwand):** C1 (Quantil) + C3 (Conformal) + C6 (ein Backtest-Kern) + C7 (Paper-Shadow) + C10 (Ledger).
**Wenn Zeit bleibt:** C5 (News-Feature) und C8 (LLM-Critic) — beide stärken die BI-Modul-Kriterien (RAG + Agentic) direkt.
**Optional/Forschung:** C2 (Ranking), C4 (Regime).

> Konsequenz für die Architektur: C1+C6+C7 zusammen verschieben das System von „Signal anzeigen" zu
> „kalibrierte Entscheidung mit Grösse, Stop und nachweisbarer Netto-Performance". Das ist der eigentliche Sprung auf das nächste Level.

---

# TEIL D · AGENT-KICKOFF — Build-Ready-Checkliste

> Diese Spec (Teil A + B + C + D) ist die einzige Wahrheitsquelle. Begleitende Code-Skelette liegen im
> Liefer-Paket `prisma_v3_seed/` (Migrationen 0031–0035, Pipeline, Seed-Skripte, EODHD-Adapter, GH-Workflow) —
> in die Repo-Pfade aus `prisma_v3_seed/README_SEED.md §1` kopieren.

## D1 · Definition of Done (pro PR)
- Feature-Branch → PR → CI grün → Review → merge. **Nie auf `main`** (Kap. 14.1).
- Unit-Tests für jeden neuen Service/Repository (Kap. 14.2). Coverage der neuen Datei ≥ vorhandenes Repo-Niveau.
- Keine Breaking Changes an bestehenden Endpoints (Kap. 14.3); nur additiv.
- DB-Writes über Repository-Pattern, LLM über `LLMClient` (Kap. 14.4/14.5).
- Bei ML-Änderung: A/B bzw. Champion/Challenger-Nachweis (Kap. 18) im PR-Text.

## D2 · Build-Reihenfolge (ersetzt Kap. 13 & 23, finale Version)
1. **Phase 0 — GATE:** `verify_dataset_coverage.py` → `docs/dataset_coverage.md` grün. Fundamentals-Quelle in `config` fixieren. *Blockiert alles.*
2. **Fundament:** Migrationen 0031–0035 (+ `index_constituents`, CH-04) → `alembic upgrade head`. Seed-Skripte laufen lassen. FIX-01, FIX-06, `macro_profiles.py` (FIX-03).
3. **Daten-Layer-Tests:** Seed-Idempotenz, PIT-Korrektheit (publish_date), Coverage-Report im Repo.
4. **ML-Reframe:** C1 (Quantil-Target) + Purged/Embargoed CV (Kap. 16) + Baselines. **Erst hier ML, nicht früher.**
5. **Ökonomie:** `TransactionCostModel` (17) + `RiskSizingService` (20) + `ConformalCalibrator` (C3).
6. **Backtest-Kern:** C6 (eine Engine) → speist `signal_outcomes` netto.
7. **Agents:** SignalAccuracy (+ Champion/Challenger 18 + Paper-Shadow C7), DataSteward, CryptoIntraday, SNBRate — als `AssetFeatureSet` (C9). GH-Workflow aus dem Paket aktivieren.
8. **Dashboard + Compliance:** Netto + kalibriert anzeigen, Decision Ledger (C10), Disclaimer/Observability (21).

## D3 · Secrets (Render + GitHub Actions)
`EODHD_API_KEY` (neu), `FMP_API_KEY` (vorhanden), `SIMFIN_API_KEY`, `GLASSNODE_API_KEY`, `COINGECKO_API_KEY`,
`RENDER_DATABASE_URL`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `SENDGRID_API_KEY`. Keine Keys committen (Kap. 21).

## D4 · Akzeptanz-Gates fürs Gesamtsystem (was „fertig" heisst)
- `docs/dataset_coverage.md` zeigt eine bestandene Quelle **oder** dokumentiert bewusst den US-Proxy.
- `docs/ml_eval.md`: Modell schlägt alle 3 Baselines auf Macro-F1/IC, Purged-CV mit Streuung.
- Netto-Equity-Kurve (nach Kosten) out-of-sample 2024–2025 vorhanden und im Dashboard sichtbar.
- Win-Rate/Alpha im Dashboard sind **Netto**; jede gezeigte Wahrscheinlichkeit ist kalibriert (Brier im Report).
- Alle neuen Crons schreiben in `cron_run_log`; ein Health-Blick zeigt Datenfrische pro Tabelle.

---

# TEIL E · IMPLEMENTATION CONTRACTS (C1 · C3 · C6)

> Verbindliche Schnittstellen für die drei Kern-Reframes. Ein Agent baut **genau diese Signaturen**
> und schreibt die genannten Tests. Alles andere (interne Helfer) frei. Datentypen: Python 3.12, async wo DB.

## E1 · Contract — C1 Quantil-Regression (ersetzt das 3-Klassen-Target)

> ⛔ **Feature-Set ÜBERSCHRIEBEN durch TEIL F §F2/§F3.** Quantil-Target, Monotonie, `MLPrediction`, prob_outperform und Tests bleiben exakt gültig. NUR die Feature-Liste ändert sich: `feature_cols` enthält KEINE Fundamentals (nur Preis/Technik/Makro). Alles andere in E1 unverändert.

**Ziel:** Pro (Ticker, Datum) eine Verteilung des 30-Tage-Excess-Returns vs. SMI vorhersagen.

### E1.1 Value Object — `backend/domain/value_objects/ml_prediction.py` (erweitern)
```python
@dataclass(frozen=True)
class MLPrediction:
    ticker: str
    as_of: date
    q10: float            # 10%-Quantil des 30d-Excess-Return (z.B. -0.04)
    q50: float            # Median
    q90: float            # 90%-Quantil
    prob_outperform: float  # P(excess>0), abgeleitet aus der Verteilung, 0..1
    expected_edge: float    # = q50 (Bequemlichkeits-Alias)
    uncertainty: float      # = q90 - q10 (Spread, Risiko-Proxy)
    model_version: str
    feature_hash: str       # für Decision Ledger (C10)
```

### E1.2 Target-Builder — in `ml_feature_service.py`
```python
def build_target_excess_30d(close: pd.Series, smi_close: pd.Series, snap: pd.Timestamp) -> float | None:
    """Forward 30-Handelstage Excess-Return vs SMI. None wenn < 30 Tage Zukunft
    vorhanden (am Datensatz-Rand). PIT: nutzt nur Daten ab snap+1."""
```
- Ersetzt `target_class`. `forward_return_12m`/Quartil-Logik entfernen aus dem Trainingspfad.
- Überlappung dokumentiert → Purged/Embargoed CV (Kap. 16) ist Pflicht.

### E1.3 Training — `scripts/train_quantile_model.py`
```python
# 3 LightGBM-Modelle, gemeinsame Features, objective="quantile":
#   alpha=0.1 -> q10 ; alpha=0.5 -> q50 ; alpha=0.9 -> q90
# Persistenz: models/quantile_{q10,q50,q90}_{YYYY-MM-DD}.joblib
# registry.register(..., meta={"type":"quantile","cv":"purged_embargo","features":[...]})
def train(dataset: pd.DataFrame, feature_cols: list[str]) -> dict[str, Path]: ...
```
**Monotonie-Pflicht:** q10 ≤ q50 ≤ q90 erzwingen (nach Predict sortieren), sonst inkonsistente Verteilung.

### E1.4 Prediction — `ml_prediction_service.py`
```python
async def predict(self, ticker: str, as_of: date) -> MLPrediction | None: ...
# prob_outperform = Anteil der Verteilung > 0; einfachste valide Schätzung:
#   lineare Interpolation der CDF aus (q10,q50,q90). Dokumentieren als Approximation.
```

### E1.5 Akzeptanz / Tests (`tests/unit/test_quantile_*`)
- `q10<=q50<=q90` für 100 zufällige Inputs (nach Monotonie-Fix).
- `prob_outperform in [0,1]`; bei q50>0 ⇒ prob>0.5.
- Pinball-Loss je Quantil auf Test-Fold < Baseline (konstante Quantile aus Train-Verteilung).
- Feature-Mismatch beim Laden wirft `ValueError` (bestehender Check, Kap. 4.3, beibehalten).

---

## E2 · Contract — C3 Conformal-Kalibrierung

**Ziel:** Verteilungsfreie Abdeckungsgarantie auf die Quantil-Intervalle aus C1 (CQR).

### E2.1 `backend/application/services/conformal_calibrator.py`
```python
class ConformalCalibrator:
    def fit(self, cal_q10: np.ndarray, cal_q90: np.ndarray, cal_y: np.ndarray,
            alpha: float = 0.2) -> None:
        """Conformalized Quantile Regression. Nonconformity:
        E_i = max(cal_q10 - y, y - cal_q90); Korrektur Q = (1-alpha)-Quantil von E.
        Speichert self._q. Kalibrierungs-Set ist OUT-OF-TRAIN (eigener Zeitblock)."""
    def calibrate(self, q10: float, q90: float) -> tuple[float, float]:
        """return (q10 - self._q, q90 + self._q) — garantiert ~ (1-alpha) Coverage."""
    @property
    def empirical_coverage(self) -> float: ...  # auf Holdout, für docs/ml_eval.md
```

### E2.2 Integration
- Läuft NACH C1, VOR Anzeige. `MLPrediction.q10/q90` werden mit den kalibrierten Werten überschrieben; `uncertainty` neu berechnen.
- `prob_outperform` zusätzlich gegen Brier-Score reporten (FIX-21).

### E2.3 Akzeptanz / Tests
- Auf synthetischem Holdout: `empirical_coverage ≈ 1-alpha ± 0.05`.
- `calibrate` verbreitert das Intervall nie negativ (q10' ≤ q90').
- `docs/ml_eval.md` enthält Coverage + Brier-Tabelle.

---

## E3 · Contract — C6 Ein Backtest-Kern (Single Source of Truth)

**Ziel:** Live-Outcomes und historischer Backtest aus EINER event-getriebenen Engine, netto nach Kosten.

### E3.1 `backend/application/services/backtest_engine.py`
```python
@dataclass(frozen=True)
class Fill:
    ticker: str; date: date; side: str; price: float; cost: float  # cost vom TransactionCostModel

@dataclass(frozen=True)
class EquityCurve:
    dates: list[date]; equity: list[float]
    cagr: float; sharpe: float; max_drawdown: float
    net_alpha_vs_benchmark: float

class BacktestEngine:
    def __init__(self, prices_repo, cost_model: TransactionCostModel, benchmark: str): ...
    async def run(self, signals: list[SignalEvent], start: date, end: date,
                  sizing: RiskSizingService) -> EquityCurve:
        """Iteriert Tag für Tag: Signale -> Sizing -> Fills (mit Kosten) ->
        Mark-to-Market aus prices_repo. KEINE Look-Ahead: an Tag d nur Daten <= d."""
    async def outcomes_from(self, curve_run) -> list[dict]:
        """Erzeugt signal_outcomes-Zeilen (netto: cost_adjusted_return,
        net_excess_return) — dieselbe Logik, die SignalAccuracyAgent live nutzt."""
```

### E3.2 Konsequenz
- `SignalBacktestService` (Kap. 7) und `SignalAccuracyAgent._populate_pending_outcomes` (5.1)
  rufen **diese** Engine. Kein zweiter Return-Rechenpfad. Live = `run(..., end=today)`.
- `backtest_service.py` (alt) wird auf die Engine umgestellt oder deprecated (FIX-09 entfällt damit).

### E3.3 Akzeptanz / Tests
- Determinismus: gleicher Input ⇒ bytegleiche EquityCurve.
- Kosten wirken: Engine mit Kosten=0 vs. realen Kosten ⇒ zweitere Equity strikt ≤ erstere.
- Look-Ahead-Test: künstlicher Preis-Spike an Tag d+1 darf Fill an Tag d NICHT verändern.
- Netto-`signal_outcomes` stimmen mit der Equity-Kurve überein (Reconciliation-Test).

---

---

# TEIL F · DATENSTRATEGIE & ML — FINAL (überschreibt alle Widersprüche)

> **Diese Sektion ist die letzte und maßgebliche Wahrheit zu Daten und ML.** Wo Kap. 2/4/10/15
> oder die C1-Contract widersprechen, gilt TEIL F. Grund: es gibt keine gratis, point-in-time-
> korrekten *historischen Schweizer Fundamentaldaten* — alle Free-Anbieter sind US-only
> (SimFin Free, FMP Free) oder kostenpflichtig für CH (EODHD/FMP Ultimate). Wir bauen NICHT
> auf Daten, die wir nicht sauber haben. Punkt.

## F1 · Datenstrategie (drei klare Rollen, keine Optionen)

| Datenart | Quelle | Rolle | PIT? |
|---|---|---|---|
| **CH-Aktien Kurse** (daily, ab 2015) | yfinance (`.SW`), Bootstrap + täglich | Basis für ML + Anzeige | ✅ |
| **Krypto Kurse** (1d ab 2017, 1h ab 2020) | CryptoDataDownload CSV → CoinGecko inkrementell | Basis für Krypto-Signale | ✅ |
| **Makro** (SNB/ECB/Fed, CHF, Inflation) | bestehende Adapter → `macro_rates` | ML-Feature + macro_score | ✅ |
| **CH-Fundamentals** | yfinance `.info` (aktueller Snapshot) | **NUR** Quant-Scorer + Dashboard-Anzeige | ❌ (nur aktuell) |

- **Kein Bezahl-Account, kein FMP/EODHD-Key.** FMP Free = US-only, CH erst im teuersten Tier.
- **`simfin_us`**: NICHT mehr Fundament. Höchstens optionales Nebenexperiment (US-Fundamentals→Rendite-Demo). Aus dem Hauptpfad raus.
- **`seed_fundamentals.py` / SimFin-Seed**: optional. Für den Hauptpfad nicht nötig.
- **`dataset_source_fundamentals`**: bleibt als Config existent (Phase-0-Infra), Default praktisch irrelevant für ML. Anzeige-Fundamentals kommen aus yfinance-derived.

## F2 · ML — final (was es ist)

**Echtes überwachtes Lernen, nur ehrlich auf Schweizer Daten skaliert.**

- **Modell:** LightGBM (bleibt). Continuous Learning, Champion/Challenger (Kap. 18), Conformal (C3), eine Backtest-Engine (C6) — **alles aus Teil C/E gilt weiter.**
- **Target:** 30-Tage-Excess-Return vs. SMI, als Verteilung (C1 Quantil-Regression: q10/q50/q90 → `prob_outperform`). Unverändert.
- **Feature-Set (NEU, ~12–15 Features, alle PIT-frei & gratis):**
  - Preis/Technik aus `stock_price_history`: `return_1m/3m/6m/12m`, `vol_30d/90d`, `rsi_14`,
    `price_to_52w_high`, `momentum_vs_smi_3m`, `bb_position`, `macd_hist`, `drawdown_12m`.
  - Makro aus `macro_rates`: `snb_rate`, `chf_eur`, `inflation_ch`.
  - Optional später: Regime-Feature (C4), News-Sentiment-Feature aus der RAG (C5).
- **KEINE Fundamental-Features im ML** (pe, pb, ev_ebitda, roe, debt_equity, fcf_margin,
  eps_growth, revenue_growth, dividend_yield, dividend_growth → alle raus aus dem ML-Vektor).

**Warum das besser ist, nicht schlechter:**
1. Das Modell ist über die Sache, die es vorhersagt — **Schweizer** Titel mit **Schweizer** Daten. Kein US→CH-Transferproblem.
2. Kleinerer Feature-Satz auf kleiner effektiver Stichprobe = **weniger Overfitting** (die 25+-Ambition war durch nicht-beschaffbare Fundamentals aufgebläht).
3. Für 30-Tage-Horizonte sind Technik/Makro der stärkere Hebel; Fundamentals wirken eher langfristig — und wirken hier über den Quant-Score weiter mit.

## F3 · Wie Fundamentals trotzdem voll mitwirken (die saubere Trennung)

Deine Architektur trennt das bereits: `stock_daily_signals` hat `quant_score`, `ml_score`, `macro_score` getrennt. Die finale Strategie passt nahtlos:

| Engine | Speist | Datenbasis |
|---|---|---|
| **ml_score** | Technik/Makro-Vorhersage (kalibrierte Verteilung, „73%") | Preis + Makro (PIT) |
| **quant_score** | Fundamentale Bewertung (relativer Value vs. Sektor/Historie, SwissQuantScorerV3 Kap. 3) | yfinance-Fundamentals (aktuell) |
| **macro_score** | Makro-Kontext | `macro_rates` |

→ Die drei verschmelzen zum Endsignal (`weighted_score`) wie im Spec vorgesehen. **Fundamentals sind nicht weg — nur im richtigen Topf.**

## F4 · Was sich konkret im Code/Spec ändert

1. **`ml_feature_service.py`**: Fundamental-Feature-Builder aus dem Trainings-/Inferenzpfad entfernen. Preis/Makro-Features behalten. `_stub_fundamentals()` ganz raus (war eh verboten, jetzt obsolet).
2. **Kap. 4.2 Feature-Liste**: gilt nur noch in der F2-Variante (Fundamentals gestrichen).
3. **C1-Contract (E1)**: `feature_cols` = nur Preis/Technik/Makro. Quantil-Logik, Monotonie, `MLPrediction`, Tests unverändert.
4. **SwissQuantScorerV3 (Kap. 3)**: unverändert wichtig — bekommt yfinance-Fundamentals (aktuell) statt SimFin-Historie. `sector_medians` aus den aktuellen Fundamentals der Universumstitel.
5. **`seed_fundamentals.py` / simfin**: optional markieren, nicht im kritischen Pfad.
6. **Dashboard-Cards (Kap. 8.3)**: Fundamental-Zahlen (P/E, ROE, Div-Yield) kommen aus yfinance-derived; ML-Pred-Zeile kommt aus dem Technik/Makro-Modell. Beides nebeneinander — wie schon gezeichnet.

## F5 · Phase-0-Arbeit ist nicht verloren

Migrationen 0031–0035, ETL-Pipeline, der Quellen-Schalter und die Repos bleiben nützlich:
`stock_fundamentals` wird jetzt von yfinance-derived (aktuell) befüllt statt von SimFin-Historie;
`crypto_price_history`/`stock_price_history` sind unverändert das Fundament. Nur die *Bedeutung*
von `simfin_us` schrumpft von „offizieller Datensatz" auf „optionales Experiment".

## F6 · Dozenten-Kriterien bleiben erfüllt

- **ML** ✅ Schweizer LightGBM (Technik/Makro), Quantil-Target, Purged-CV, Continuous Learning.
- **RAG** ✅ News/Filings; optional als ML-Feature (C5).
- **Datensatz** ✅ Schweizer Kurshistorie ab 2015 + Krypto — real, reproduzierbar, gross genug.
- **Agentic** ✅ unverändert (SignalAccuracy, DataSteward, Intraday, Macro).
- **Fundamentals sichtbar** ✅ über Quant-Score + Dashboard.

---

---

# TEIL G · ÜBERARBEITETER UMSETZUNGSPLAN (nach ML-Befunden, Stand 2026-06-20)

> Diese Sektion aktualisiert den Plan auf Basis der tatsächlich gebauten Phasen 0–2 und der
> ML-Testergebnisse. Vollständige Testdoku separat in **`PRISMA_V3_ML_BEFUNDE.md`**.
> TEIL G ist der aktuelle Fahrplan; wo er TEIL D widerspricht, gilt TEIL G.

## G1 · Was wir jetzt wissen (Stand der Realität)

**Gebaut & in `main` (Phase 0–2):** Datenbank-Fundament + Seed-Pipeline; PIT-Universum (30 Titel
inkl. delistete); Kurse (Aktien/Krypto) + Makro in der DB; ML-Pipeline mit Purged-CV-Harness.

**ML-Befund (Details in BEFUNDE.md):**
1. ML ist **kein zuverlässiger Return-Prädiktor** — Aktien wie Krypto, sauber gegen Baselines getestet.
2. ML liefert **messbares Regime-/Risiko-Timing** bei Krypto (Calmar 1.81 vs 1.12 exposure-matched; 2022 −9% vs −33%).
3. **Momentum trägt Signal** (schlägt das ML im direktionalen F1).

**Der entscheidende Punkt:** Die Vision-Kennzahl „historisch validierte Win-Rate / Wahrscheinlichkeit"
(Kap. 0) misst NICHT das ML allein, sondern das **kombinierte Signal** (quant + ml + macro) über
`signal_outcomes` + Backtest. **Das ist noch nicht gebaut/gemessen.** Aus dem ML-Einzelbefund darf
nicht auf das Gesamtprodukt geschlossen werden.

## G2 · Ehrliche Rollen der drei Engines (Konsequenz)

| Engine | Rolle nach Befund | Gewichtung |
|---|---|---|
| **quant_score** | Relative Bewertung (Value/Quality vs Sektor/Historie) | trägt |
| **ml_score** | KRYPTO: Risiko-/Regime-Filter (Exposure drosseln in Gefahrphasen). AKTIEN: gering | situativ |
| **macro_score** | Makro-Kontext (SNB/CHF/Inflation) | trägt |

`ml_score` ist also ein **Risiko-Overlay**, kein Return-Orakel. Im UI ehrlich framen: „reduziert
Drawdown / Regime-Timing", nicht „sagt Preis voraus".

## G3 · Nächste Schritte — priorisiert

**Phase 3 (JETZT) — der eigentliche Produkt-Test:**
- Signal-Aggregation (`weighted_score` aus quant/ml/macro, ehrliche Gewichte nach G2).
- `signal_outcomes` + EIN Backtest-Kern (TEIL C §C6) → echte, netto-of-cost Win-Rate/Alpha.
- SignalAccuracyAgent (Kap. 5.1) befüllt/evaluiert Outcomes.
- **Erst hier** wird messbar, ob PRISMA als Gesamtsystem einen Edge hat. Das ist der ehrliche „evidence-based"-Beleg.

**Verbesserungshebel fürs ML (parallel/danach, je nach Phase-3-Ergebnis):**
1. **News-RAG-Features (C5)** — die bestehende RAG nicht nur als Schaufenster, sondern als Feature
   (Sentiment/News-Surprise). Das ist das, was Momentum NICHT weiß → realistischster Weg zu echtem
   Vorhersage-Signal. **Höchste Priorität unter den Hebeln.**
2. **Cross-Sectional Ranking bei Aktien (C2)** — „welcher der 30 Titel relativ vorn" ist lernbarer
   als absolute Returns; bei Aktien genug Titel. Noch nie getestet.
3. **Momentum + ML-Ensemble** — Momentum fängt Trend, ML managt Risiko. Zusammen statt gegeneinander.

**Phase 4 — Dashboard + Explainability** (siehe G4) + Compliance.

## G4 · NEU — Visuelle Chart-Analyse & Explainability (Komponente)

> Begründung: Die stärkste Bewertungsachse des BI-Moduls ist „viele Daten → nachvollziehbare
> Entscheidung". Eine visuelle, automatisierte Chart-Analyse adressiert das direkt — und sie ist
> **ehrlich von Natur aus**: sie *visualisiert* die Indikatoren/Muster, die zur Entscheidung führen,
> statt Vorhersagekraft zu behaupten. Sie stärkt Explainability, nicht Alpha.

**Was es ist:** Pro Titel/Coin ein automatisch erzeugter, **annotierter Chart** (Candlestick +
Overlays + erkannte Muster + Signal-Marker) plus eine kurze, vom Agent generierte Text-Begründung.

**Bausteine (vieles existiert schon):**
- **Indikatoren/Muster:** `CryptoPatternService` (Candlestick + Formationen) ist da und wird ausgebaut.
  Für Aktien dieselben Indikatoren anwenden (RSI, MACD, Bollinger, MAs). Bibliothek: **TA-Lib**
  (200+ Indikatoren, 60+ Candlestick-Patterns) oder pandas-ta; Rendering: **mplfinance**.
- **Annotierter Chart (Explainability-Kern):** Candlestick + Bollinger-Bänder + RSI-/MACD-Subplots,
  markiert: erkannte Muster (z.B. „Bullish Engulfing"), Support/Resistance, gleitende Durchschnitte,
  und der Punkt, an dem das Signal kippte. Annotationen sparsam + konsistent (Legende/Farbschema).
- **Chart-Analyse-Agent:** liest die berechneten Indikatoren/Muster und erzeugt eine strukturierte,
  textuelle Lesart („RSI 38 = überverkauft bei steigendem Volumen; Preis testet unteres Bollinger-Band").
  Stärkt die Agentic-AI-Achse, ohne Vorhersage zu behaupten.

**Gilt für beide Anlageklassen:** Krypto (vorhanden, ausbauen) UND Aktien (neu, gleiche Technik).

**Ehrliche Abgrenzung (wichtig):** Technische Analyse hat akademisch schwache prognostische Validität
(Markteffizienz). Daher als **Decision-Support / Explainability** positionieren, nicht als Alpha-Quelle —
konsistent mit dem ML-Befund. Die Charts erklären die Datenlage; die Entscheidung trägt das kombinierte
Signal (G2) + die Backtest-Evidenz (Phase 3).

**Aufwand:** mittel, niedriges Risiko, hoher Demo-/Notenwert. Reuse von `CryptoPatternService` + Standardbibliotheken.

## G5 · Reflexion — wird das Endresultat gut?

Ja, und zwar gerade *wegen* der Ehrlichkeit. Das Endprodukt ist nicht „ML schlägt den Markt"
(unhaltbar), sondern ein **angereichertes, nachvollziehbares Entscheidungs-Support-System**:
- viele Datenquellen (Kurse, Makro, On-Chain, News-RAG) in einer Sicht gebündelt,
- ein ehrliches Signal mit **backtest-validierter** Win-Rate (Phase 3),
- ein **Risiko-Overlay**, das nachweislich Drawdown reduziert (Krypto 2022),
- **visuelle Erklärbarkeit** pro Titel (G4),
- **Agentic AI + RAG** durchgängig.

Das trifft die Modul-Kriterien voll und ist gegen kritische Prüfung robust — weil jede Behauptung
belegt und sauber abgegrenzt ist. Der ML-„Misserfolg" als Return-Prädiktor ist im Gesamtbild kein
Mangel, sondern Teil einer methodisch sauberen Geschichte.

---

## G6 · ML-Endbefund (final, 2026-06-21) — überschreibt frühere ML-Annahmen

> Volldoku: `PRISMA_V3_ML_BEFUNDE.md`. Dieser Abschnitt ist die maßgebliche, abschließende
> Aussage zum ML. Wo Kap. 0/4 oder frühere Teile dem widersprechen, gilt G6.

**Befund:** Nach rigoroser Prüfung (Aktien-Quantil, Krypto v1/v2, Monats-Signal-Backtest,
strikter täglicher Walk-Forward) gibt es **keinen robusten, generalisierbaren ML-Edge** auf den
verfügbaren Daten — weder Return-Vorhersage noch generalisierbares Regime-Timing.

**Zentrale Lehre — In-Sample-Optimismus:** Der vielversprechende Phase-2-Wert (Calmar 1.81, Purged CV)
kollabierte im strikten Walk-Forward auf **Calmar 0.35** — *unter* der Exposure-Matched-Baseline (0.66).
Die Purged-CV-Folds hatten über Expanding-Window indirekt Zugang zu Crash-Daten. Echter Timing-Skill
nur in 1 von 4 OOS-Folds (2023–24). Das ist der eigentliche wissenschaftliche Befund.

**Konsequenzen (verbindlich):**
1. **`ml_score` in Produktion = aus/minimal.** Keine Alpha- oder Timing-Behauptung im UI.
2. **Das ML bleibt als dokumentierte Forschungskomponente** (saubere Pipeline + ehrliche
   Negativ-Evaluation) — erfüllt „ML-basiert" voll und zeigt Methodik-Kompetenz.
3. **Kein weiteres ML-Tuning** als Projektpfad. Einziger optionaler Rest-Hebel: News-RAG-Features
   (C5), nicht projektkritisch.
4. **Produktwert + Note** kommen aus: angereicherter Datensicht, Agentic AI, RAG, Quant-Score als
   Decision-Support und **visueller Chart-Analyse/Explainability (G4)** — nicht aus einem Alpha-Modell.

**Projektvorgaben:** weiterhin voll erfüllt (Agentic ✓, ML-basiert ✓ inkl. ehrlicher Evaluation,
RAG ✓, Datensatz/Historisch+Live ✓). Der Negativbefund ist akademisch eine Stärke, kein Mangel.

---

*Challenge-Layer V3.1 · Reviewer-Annotationen zu PRISMA V3 Master Spec · 2026-06-20*
