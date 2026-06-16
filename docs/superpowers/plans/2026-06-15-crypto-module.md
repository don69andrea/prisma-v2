# Krypto-Modul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eigenständiges Krypto-Analyse-Modul in PRISMA V2 — 10 Top-Kryptos mit CryptoScorer (Technisch + Sentiment), separater /crypto-Seite und vollständiger REST-API.

**Architecture:** Hexagonal — neuer Domain-Layer (CryptoScorer) parallel zu SwissQuantScorer, drei Infrastruktur-Adapter (CoinGecko, yFinance, Fear&Greed), Application-Service orchestriert alles, FastAPI-Router + Next.js-Frontend spiegeln das bestehende Aktien-Muster.

**Tech Stack:** Python 3.12 · FastAPI · pycoingecko · pandas-ta · httpx · cachetools · Next.js 14 App Router · React Query · Tailwind CSS · Lucide React

**Branch:** `feat/crypto-module`  
**Target release:** `v2.2.0` (minor bump — neues Feature-Modul)

---

## File Map

### Neu erstellt (Backend)
| Datei | Verantwortung |
|-------|--------------|
| `backend/domain/entities/crypto_asset.py` | CryptoAsset Dataclass |
| `backend/domain/value_objects/crypto_signal.py` | CryptoSignal frozen Dataclass |
| `backend/domain/ports/crypto_data_provider.py` | Port-Interface (Protocol) |
| `backend/domain/services/crypto_scorer.py` | Score-Logik 0–100 |
| `backend/infrastructure/adapters/fear_greed_adapter.py` | alternative.me Fear&Greed |
| `backend/infrastructure/adapters/yfinance_crypto.py` | OHLCV + Technische Indikatoren |
| `backend/infrastructure/adapters/coingecko_adapter.py` | Marktdaten CHF via CoinGecko |
| `backend/application/services/crypto_scoring_service.py` | Orchestrierung aller Datenquellen |
| `backend/interfaces/rest/schemas/crypto.py` | Pydantic Response-Modelle |
| `backend/interfaces/rest/routers/crypto.py` | REST Endpoints /api/v1/crypto/* |
| `backend/alembic/versions/0024_create_crypto_signals.py` | DB-Tabelle crypto_signals |
| `backend/tests/unit/test_crypto_scorer.py` | Unit-Tests CryptoScorer |
| `backend/tests/integration/test_crypto_endpoints.py` | Integrationstests HTTP-Layer |

### Modifiziert (Backend)
| Datei | Änderung |
|-------|---------|
| `pyproject.toml` | pycoingecko, pandas-ta, cachetools hinzufügen |
| `.env.example` | COINGECKO_API_KEY, CRYPTO_FEATURE_ENABLED |
| `backend/config.py` | coingecko_api_key + crypto_feature_enabled Settings |
| `backend/interfaces/rest/app.py` | crypto-Router registrieren |
| `backend/interfaces/rest/dependencies.py` | DI-Funktionen für Crypto-Services |

### Neu erstellt (Frontend)
| Datei | Verantwortung |
|-------|--------------|
| `frontend/lib/api/crypto.ts` | API-Client für /api/v1/crypto/* |
| `frontend/components/crypto/FearGreedGauge.tsx` | Halbkreis-Gauge 0–100 |
| `frontend/components/crypto/CryptoSignalCard.tsx` | Signal-Karte Simple Mode |
| `frontend/components/crypto/ScoreBreakdown.tsx` | Score-Komponenten Accordion |
| `frontend/components/crypto/CryptoProRow.tsx` | Tabellenzeile Pro Mode |
| `frontend/app/crypto/page.tsx` | Next.js Server Component |
| `frontend/app/crypto/crypto-client.tsx` | Client Component mit React Query |
| `frontend/e2e/15-crypto.spec.ts` | Playwright E2E Test |

### Modifiziert (Frontend)
| Datei | Änderung |
|-------|---------|
| `frontend/app/nav-links.tsx` | Krypto. Link in ANALYSIEREN-Gruppe |

---

## Task 1: Branch erstellen + Python-Dependencies hinzufügen

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Branch von main abzweigen**

```bash
git checkout main
git pull origin main
git checkout -b feat/crypto-module
```

- [ ] **Step 2: pycoingecko, pandas-ta, cachetools in pyproject.toml eintragen**

In `pyproject.toml` unter `dependencies` am Ende der Liste hinzufügen:

```toml
    "pycoingecko>=3.1.0",
    "pandas-ta>=0.3.14b0",
    "cachetools>=5.3.0",
```

Die vollständige `dependencies`-Liste sieht dann so aus (Ausschnitt — nur die neuen Zeilen):
```toml
    "apscheduler>=3.10",
    "pycoingecko>=3.1.0",
    "pandas-ta>=0.3.14b0",
    "cachetools>=5.3.0",
```

- [ ] **Step 3: Dependencies installieren**

```bash
uv pip install pycoingecko>=3.1.0 "pandas-ta>=0.3.14b0" "cachetools>=5.3.0"
```

Erwartete Ausgabe: `Successfully installed pycoingecko-... pandas-ta-... cachetools-...`

- [ ] **Step 4: Import-Test**

```bash
python -c "from pycoingecko import CoinGeckoAPI; import pandas_ta; from cachetools import TTLCache; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "feat(crypto): add pycoingecko, pandas-ta, cachetools dependencies"
```

---

## Task 2: Config + .env.example ergänzen

**Files:**
- Modify: `backend/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Settings in backend/config.py ergänzen**

In der `Settings`-Klasse nach `sendgrid_api_key` folgende Felder einfügen:

```python
    # CoinGecko API Key (optional — Free Tier: 30 Req/min, 10.000/Monat)
    coingecko_api_key: str = ""

    # Krypto-Feature aktivieren (default: true)
    crypto_feature_enabled: bool = True
```

- [ ] **Step 2: .env.example ergänzen**

Am Ende der `.env.example`-Datei hinzufügen:

```bash
# CoinGecko API Key (kostenlos: https://www.coingecko.com/en/api/pricing)
# Optional — ohne Key: Demo Tier (30 Req/min, 10.000/Monat), reicht für PRISMA.
COINGECKO_API_KEY=

# Krypto-Modul aktivieren (default: true)
CRYPTO_FEATURE_ENABLED=true
```

- [ ] **Step 3: Verify Settings laden ohne Fehler**

```bash
python -c "from backend.config import get_settings; s = get_settings(); print(s.crypto_feature_enabled, repr(s.coingecko_api_key))"
```

Erwartete Ausgabe: `True ''`

- [ ] **Step 4: Commit**

```bash
git add backend/config.py .env.example
git commit -m "feat(crypto): add COINGECKO_API_KEY and CRYPTO_FEATURE_ENABLED config"
```

---

## Task 3: Domain Layer — CryptoAsset, CryptoSignal, Port-Interface

**Files:**
- Create: `backend/domain/entities/crypto_asset.py`
- Create: `backend/domain/value_objects/crypto_signal.py`
- Create: `backend/domain/ports/crypto_data_provider.py`

- [ ] **Step 1: CryptoAsset Entity erstellen**

Datei `backend/domain/entities/crypto_asset.py`:

```python
"""CryptoAsset — Domain-Entity für eine Kryptowährung."""
from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_CRYPTOS: list[tuple[str, str, str, str, bool]] = [
    # (ticker_coingecko, ticker_yfinance, name, kategorie, has_six_etp)
    ("bitcoin",      "BTC-CHF",  "Bitcoin",      "Layer1/Store of Value", True),
    ("ethereum",     "ETH-CHF",  "Ethereum",     "Layer1/Smart Contract", True),
    ("solana",       "SOL-USD",  "Solana",       "Layer1/High Speed",     True),
    ("ripple",       "XRP-USD",  "XRP",          "Payment/Layer1",        True),
    ("cardano",      "ADA-USD",  "Cardano",      "Layer1/ESG",            True),
    ("polkadot",     "DOT-USD",  "Polkadot",     "Layer0/Interop",        True),
    ("chainlink",    "LINK-USD", "Chainlink",    "DeFi/Oracle",           False),
    ("avalanche-2",  "AVAX-USD", "Avalanche",    "Layer1/Subnets",        True),
    ("uniswap",      "UNI-USD",  "Uniswap",      "DeFi/DEX",              False),
    ("bitcoin-cash", "BCH-USD",  "Bitcoin Cash", "Payment",               True),
]


@dataclass
class CryptoAsset:
    """Repräsentiert eine Kryptowährung mit Live-Marktdaten."""

    ticker_cg: str
    ticker_yf: str
    name: str
    symbol: str
    kategorie: str
    has_six_etp: bool

    price_chf: float | None = None
    market_cap_chf: float | None = None
    volume_24h_chf: float | None = None
    price_change_24h_pct: float | None = None
    price_change_7d_pct: float | None = None
    ath_change_pct: float | None = None
    market_cap_rank: int | None = None
```

- [ ] **Step 2: CryptoSignal Value Object erstellen**

Datei `backend/domain/value_objects/crypto_signal.py`:

```python
"""CryptoSignal — Scoring-Ergebnis für eine Kryptowährung."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class CryptoSignal:
    """Immutabler Value Object: Signal + Score + Metriken für ein Krypto-Asset."""

    ticker: str
    name: str
    signal: Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]
    score: float
    score_components: dict[str, float]
    signal_reason_de: str
    fear_greed_value: int
    fear_greed_label: str
    rsi_14: float
    macd_signal: Literal["bullish", "bearish"]
    volatility_30d_pct: float
    correlation_smi_1y: float
    has_six_etp: bool
    price_chf: float | None
    market_cap_chf: float | None
    price_change_24h_pct: float | None
    price_change_7d_pct: float | None
    ath_change_pct: float | None
    market_cap_rank: int | None
    timestamp: datetime
```

- [ ] **Step 3: Port-Interface erstellen**

Datei `backend/domain/ports/crypto_data_provider.py`:

```python
"""Port-Interface für Krypto-Datenquellen (Hexagonale Architektur)."""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class CryptoDataProvider(Protocol):
    """Abstraktion über alle externen Krypto-Datenquellen."""

    async def get_technicals(self, ticker_yf: str, days: int = 365) -> pd.DataFrame:
        """OHLCV + technische Indikatoren für ein Asset."""
        ...

    async def get_smi_correlation(self, ticker_yf: str, days: int = 365) -> float:
        """Korrelation zum SMI über `days` Tage (Pearson, -1 bis 1)."""
        ...
```

- [ ] **Step 4: Import-Smoke-Test**

```bash
python -c "
from backend.domain.entities.crypto_asset import CryptoAsset, SUPPORTED_CRYPTOS
from backend.domain.value_objects.crypto_signal import CryptoSignal
from backend.domain.ports.crypto_data_provider import CryptoDataProvider
print('Domain layer OK, Cryptos:', len(SUPPORTED_CRYPTOS))
"
```

Erwartete Ausgabe: `Domain layer OK, Cryptos: 10`

- [ ] **Step 5: Commit**

```bash
git add backend/domain/entities/crypto_asset.py \
        backend/domain/value_objects/crypto_signal.py \
        backend/domain/ports/crypto_data_provider.py
git commit -m "feat(crypto): add CryptoAsset entity, CryptoSignal VO, CryptoDataProvider port"
```

---

## Task 4: CryptoScorer Unit Tests schreiben (TDD — Tests first)

**Files:**
- Create: `backend/tests/unit/test_crypto_scorer.py`

- [ ] **Step 1: Test-Datei mit Fixtures erstellen**

Datei `backend/tests/unit/test_crypto_scorer.py`:

```python
"""Unit-Tests für CryptoScorer — alle Score-Komponenten und Signal-Schwellen."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.domain.entities.crypto_asset import CryptoAsset


def _make_asset(**kwargs) -> CryptoAsset:
    defaults = dict(
        ticker_cg="bitcoin", ticker_yf="BTC-CHF", name="Bitcoin",
        symbol="BTC", kategorie="Layer1", has_six_etp=True,
        price_chf=50000.0, market_cap_chf=1e12, volume_24h_chf=5e9,
        price_change_24h_pct=1.0, price_change_7d_pct=5.0,
        ath_change_pct=-30.0, market_cap_rank=1,
    )
    return CryptoAsset(**{**defaults, **kwargs})


def _make_technicals(
    rsi: float = 50.0,
    macd_above_signal: bool = True,
    close_trend: str = "up",
    volume_trend: str = "flat",
) -> pd.DataFrame:
    n = 300
    close_base = 50000.0
    if close_trend == "up":
        close = [close_base * (1 + i * 0.001) for i in range(n)]
    elif close_trend == "down":
        close = [close_base * (1 - i * 0.001) for i in range(n)]
    else:
        close = [close_base] * n

    if volume_trend == "up":
        volume = [1e6 * (1 + i * 0.002) for i in range(n)]
    else:
        volume = [1e6] * n

    df = pd.DataFrame({
        "Open": close, "High": close, "Low": close, "Close": close, "Volume": volume,
    })
    df["RSI_14"] = rsi
    macd_val = 100.0 if macd_above_signal else -100.0
    df["MACD_12_26_9"] = macd_val
    df["MACDs_12_26_9"] = 0.0
    ema20 = close_base * 0.98
    ema50 = close_base * 0.96
    df["EMA_20"] = ema20
    df["EMA_50"] = ema50
    df["BBU_20_2.0"] = close_base * 1.05
    df["BBL_20_2.0"] = close_base * 0.95
    return df


# ---------------------------------------------------------------------------
# RSI-Score Tests
# ---------------------------------------------------------------------------

class TestRsiScore:
    def test_oversold_returns_10(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(25.0) == 10.0

    def test_near_oversold_returns_8(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(40.0) == 8.0

    def test_neutral_returns_5(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(50.0) == 5.0

    def test_near_overbought_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(65.0) == 3.0

    def test_overbought_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._rsi_score(75.0) == 0.0


# ---------------------------------------------------------------------------
# Fear & Greed Score Tests
# ---------------------------------------------------------------------------

class TestFearGreedScore:
    def test_extreme_fear_returns_12(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(20) == 12.0

    def test_fear_returns_9(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(35) == 9.0

    def test_neutral_returns_6(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(50) == 6.0

    def test_greed_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(70) == 3.0

    def test_extreme_greed_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._fear_greed_score(85) == 0.0


# ---------------------------------------------------------------------------
# Momentum Score Tests
# ---------------------------------------------------------------------------

class TestMomentumScore:
    def test_strong_up_returns_15(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(25.0) == 15.0

    def test_moderate_up_returns_12(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(15.0) == 12.0

    def test_small_up_returns_9(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(7.0) == 9.0

    def test_flat_positive_returns_6(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(2.0) == 6.0

    def test_small_negative_returns_3(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(-3.0) == 3.0

    def test_large_negative_returns_0(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        scorer = CryptoScorer()
        assert scorer._momentum_score(-10.0) == 0.0


# ---------------------------------------------------------------------------
# Signal-Schwellen Tests
# ---------------------------------------------------------------------------

class TestSignalThresholds:
    def setup_method(self):
        from backend.domain.services.crypto_scorer import CryptoScorer
        self.scorer = CryptoScorer()

    def _score(self, **asset_kwargs) -> float:
        asset = _make_asset(**asset_kwargs)
        tech = _make_technicals(rsi=28.0, macd_above_signal=True, close_trend="up")
        score, _ = self.scorer.score(asset, tech, fear_greed=20, correlation_smi_1y=0.1)
        return score

    def test_high_score_produces_strong_buy(self):
        score = self._score(price_change_7d_pct=25.0, market_cap_rank=1, ath_change_pct=-20.0)
        assert score >= CryptoScorer.STRONG_BUY_THRESHOLD

    def test_score_is_bounded_0_to_100(self):
        asset = _make_asset(price_change_7d_pct=100.0)
        tech = _make_technicals(rsi=10.0)
        score, _ = self.scorer.score(asset, tech, fear_greed=0, correlation_smi_1y=0.0)
        assert 0.0 <= score <= 100.0

    def test_score_components_sum_matches_total(self):
        asset = _make_asset()
        tech = _make_technicals()
        score, components = self.scorer.score(asset, tech, fear_greed=50, correlation_smi_1y=0.2)
        assert abs(sum(components.values()) - score) < 1.0


# ---------------------------------------------------------------------------
# generate_signal_reason Tests
# ---------------------------------------------------------------------------

class TestSignalReason:
    def test_oversold_rsi_buy_reason_mentions_rsi(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("BUY", "Bitcoin", 65.0, rsi=28.0, fear_greed=50, change_7d=5.0)
        assert "RSI" in reason
        assert "Bitcoin" in reason

    def test_extreme_fear_buy_reason_mentions_angst(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("BUY", "Ethereum", 70.0, rsi=55.0, fear_greed=15, change_7d=2.0)
        assert "Angst" in reason

    def test_hold_reason_mentions_neutral(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("HOLD", "Bitcoin", 50.0, rsi=50.0, fear_greed=50, change_7d=1.0)
        assert "50" in reason

    def test_overbought_sell_reason_mentions_rsi(self):
        from backend.domain.services.crypto_scorer import generate_signal_reason
        reason = generate_signal_reason("SELL", "Bitcoin", 20.0, rsi=78.0, fear_greed=80, change_7d=-5.0)
        assert "RSI" in reason
```

- [ ] **Step 2: Tests laufen lassen — müssen FAIL sein (Klasse existiert nicht)**

```bash
python -m pytest backend/tests/unit/test_crypto_scorer.py -v 2>&1 | head -30
```

Erwartete Ausgabe: `ModuleNotFoundError: No module named 'backend.domain.services.crypto_scorer'` oder `ImportError`

- [ ] **Step 3: Commit der Tests**

```bash
git add backend/tests/unit/test_crypto_scorer.py
git commit -m "test(crypto): add failing unit tests for CryptoScorer (TDD)"
```

---

## Task 5: CryptoScorer implementieren (Tests zum Bestehen bringen)

**Files:**
- Create: `backend/domain/services/crypto_scorer.py`

- [ ] **Step 1: crypto_scorer.py erstellen**

Datei `backend/domain/services/crypto_scorer.py`:

```python
"""CryptoScorer — technisch-sentimentaler Score für Kryptowährungen (0–100)."""
from __future__ import annotations

import pandas as pd

from backend.domain.entities.crypto_asset import CryptoAsset


class CryptoScorer:
    """Bewertet Kryptowährungen auf einer Skala von 0–100.

    Signal-Schwellen:
      STRONG_BUY  >= 75
      BUY         >= 60
      HOLD        >= 40
      SELL        >= 25
      STRONG_SELL  < 25
    """

    STRONG_BUY_THRESHOLD = 75
    BUY_THRESHOLD = 60
    HOLD_THRESHOLD = 40
    SELL_THRESHOLD = 25

    def score(
        self,
        asset: CryptoAsset,
        technicals: pd.DataFrame,
        fear_greed: int,
        correlation_smi_1y: float = 0.0,
    ) -> tuple[float, dict[str, float]]:
        """Berechnet den Gesamtscore und gibt (score, components) zurück."""
        components: dict[str, float] = {}

        # ── 1. MOMENTUM (max 30 Pt) ──────────────────────────────
        rsi = float(technicals["RSI_14"].iloc[-1])
        rsi_score = self._rsi_score(rsi)

        macd_val = float(technicals["MACD_12_26_9"].iloc[-1])
        macd_sig = float(technicals["MACDs_12_26_9"].iloc[-1])
        macd_score = 5.0 if macd_val > macd_sig else 0.0

        mom_7d = asset.price_change_7d_pct or 0.0
        momentum_score = self._momentum_score(mom_7d)

        components["momentum"] = rsi_score + macd_score + momentum_score

        # ── 2. TREND (max 25 Pt) ─────────────────────────────────
        close = technicals["Close"]
        last_close = float(close.iloc[-1])
        ema20 = float(technicals["EMA_20"].iloc[-1])
        ema50 = float(technicals["EMA_50"].iloc[-1])
        ema200 = float(close.ewm(span=200).mean().iloc[-1])

        trend_score = 0.0
        if last_close > ema20:
            trend_score += 5.0
        if last_close > ema50:
            trend_score += 7.0
        if last_close > ema200:
            trend_score += 8.0
        if ema20 > ema50:
            trend_score += 5.0

        bb_upper = float(technicals["BBU_20_2.0"].iloc[-1])
        bb_lower = float(technicals["BBL_20_2.0"].iloc[-1])
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (last_close - bb_lower) / bb_range
            trend_score = min(25.0, trend_score + round(bb_position * 5))

        components["trend"] = min(25.0, trend_score)

        # ── 3. SENTIMENT (max 20 Pt) ─────────────────────────────
        fg_score = self._fear_greed_score(fear_greed)
        vol_trend = self._volume_trend_score(technicals)
        components["sentiment"] = fg_score + vol_trend

        # ── 4. MARKT (max 15 Pt) ─────────────────────────────────
        rank = asset.market_cap_rank or 50
        rank_score = float(max(0, 10 - max(0, rank - 10) // 5))
        ath_pct = abs(asset.ath_change_pct or -50.0)
        ath_score = float(min(5.0, ath_pct // 20))
        components["markt"] = rank_score + ath_score

        # ── 5. RISIKO (max 10 Pt) ────────────────────────────────
        returns = close.pct_change().dropna()
        vol_30d = float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100)
        vol_score = float(max(0.0, 5.0 - int(vol_30d // 20)))

        # Niedrige Korrelation zum SMI = Diversifikationsbonus (0–5 Pt)
        corr_abs = abs(correlation_smi_1y)
        corr_score = float(max(0.0, 5.0 * (1.0 - corr_abs)))
        components["risiko"] = vol_score + round(corr_score, 1)

        total = float(sum(components.values()))
        return min(100.0, max(0.0, total)), components

    def _rsi_score(self, rsi: float) -> float:
        """RSI: Oversold (< 30) = 10 Pt, Overbought (> 70) = 0 Pt."""
        if rsi < 30:
            return 10.0
        if rsi < 45:
            return 8.0
        if rsi < 55:
            return 5.0
        if rsi < 70:
            return 3.0
        return 0.0

    def _fear_greed_score(self, fg: int) -> float:
        """Contrarian: Extreme Fear (Einstiegsgelegenheit) = höchster Score."""
        if fg <= 25:
            return 12.0
        if fg <= 40:
            return 9.0
        if fg <= 60:
            return 6.0
        if fg <= 75:
            return 3.0
        return 0.0

    def _momentum_score(self, change_7d_pct: float) -> float:
        """7-Tage-Preismomentum (0–15 Pt)."""
        if change_7d_pct > 20:
            return 15.0
        if change_7d_pct > 10:
            return 12.0
        if change_7d_pct > 5:
            return 9.0
        if change_7d_pct > 0:
            return 6.0
        if change_7d_pct > -5:
            return 3.0
        return 0.0

    def _volume_trend_score(self, technicals: pd.DataFrame) -> float:
        """Volumen-Trend: Steigendes Volumen bei steigendem Preis = 8 Pt."""
        if "Volume" not in technicals.columns or len(technicals) < 14:
            return 4.0
        close = technicals["Close"]
        volume = technicals["Volume"]
        vol_recent = float(volume.iloc[-7:].mean())
        vol_prior = float(volume.iloc[-14:-7].mean())
        price_up = float(close.iloc[-1]) > float(close.iloc[-7])
        vol_up = vol_recent > vol_prior * 1.05
        if vol_up and price_up:
            return 8.0
        if not vol_up and not price_up:
            return 2.0
        return 4.0


def generate_signal_reason(
    signal: str,
    asset_name: str,
    score: float,
    rsi: float,
    fear_greed: int,
    change_7d: float,
) -> str:
    """Generiert einen 1-Satz deutschen Signalgrund ohne LLM."""
    fg_text = (
        "Extreme Angst am Markt"
        if fear_greed < 25
        else "Angststimmung"
        if fear_greed < 40
        else "neutrale Stimmung"
        if fear_greed < 60
        else "Gier am Markt"
    )

    if signal in ("STRONG_BUY", "BUY"):
        if rsi < 35:
            return f"{asset_name} ist technisch überverkauft (RSI {rsi:.0f}) — historisch ein Einstiegssignal."
        if fear_greed < 30:
            return f"Extreme Angst am Markt schafft Einstiegsgelegenheit für {asset_name}."
        return f"{asset_name} zeigt starkes 7-Tage-Momentum (+{change_7d:.1f}%) bei Score {score:.0f}/100."

    if signal == "HOLD":
        return f"{asset_name} in neutralem Bereich (Score {score:.0f}/100) — {fg_text}, kein klarer Trigger."

    if rsi > 70:
        return f"{asset_name} ist technisch überkauft (RSI {rsi:.0f}) — Vorsicht bei neuem Kapital."
    return f"{asset_name} zeigt schwaches Momentum bei {fg_text} — Rücksetzer möglich."
```

- [ ] **Step 2: Tests ausführen — müssen PASS sein**

```bash
python -m pytest backend/tests/unit/test_crypto_scorer.py -v
```

Erwartete Ausgabe: Alle Tests `PASSED`. Bei Abweichungen Implementierung korrigieren bis alle grün sind.

- [ ] **Step 3: Commit**

```bash
git add backend/domain/services/crypto_scorer.py
git commit -m "feat(crypto): implement CryptoScorer with momentum/trend/sentiment/markt/risiko scoring"
```

---

## Task 6: FearGreedAdapter implementieren

**Files:**
- Create: `backend/infrastructure/adapters/fear_greed_adapter.py`

- [ ] **Step 1: FearGreedAdapter erstellen**

Datei `backend/infrastructure/adapters/fear_greed_adapter.py`:

```python
"""Fear & Greed Index-Adapter via alternative.me (kostenlos, kein API-Key)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

_logger = logging.getLogger(__name__)

_URL = "https://api.alternative.me/fng/?limit=1&format=json"
_CACHE_TTL_SECONDS = 3600


class FearGreedAdapter:
    """Ruft den Crypto Fear & Greed Index von alternative.me ab.

    Cacht das Ergebnis 1 Stunde (Index wird täglich aktualisiert).
    Fallback auf Wert 50 (Neutral) wenn API nicht erreichbar.
    """

    def __init__(self) -> None:
        self._cached: dict | None = None
        self._cached_at: datetime | None = None

    async def get_current(self) -> dict:
        """Gibt {"value": int, "label": str, "timestamp": str} zurück."""
        now = datetime.now(tz=UTC)
        if self._cached_at and (now - self._cached_at).total_seconds() < _CACHE_TTL_SECONDS:
            return self._cached  # type: ignore[return-value]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_URL)
                resp.raise_for_status()
                data = resp.json()["data"][0]
                result: dict = {
                    "value": int(data["value"]),
                    "label": data["value_classification"],
                    "timestamp": data["timestamp"],
                }
                self._cached = result
                self._cached_at = now
                return result
        except Exception:
            _logger.warning("FearGreedAdapter: API nicht erreichbar — Fallback 50/Neutral")
            return {"value": 50, "label": "Neutral", "timestamp": now.isoformat()}
```

- [ ] **Step 2: Import-Smoke-Test**

```bash
python -c "from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/adapters/fear_greed_adapter.py
git commit -m "feat(crypto): add FearGreedAdapter (alternative.me, 1h cache, neutral fallback)"
```

---

## Task 7: YFinanceCryptoAdapter implementieren

**Files:**
- Create: `backend/infrastructure/adapters/yfinance_crypto.py`

- [ ] **Step 1: YFinanceCryptoAdapter erstellen**

Datei `backend/infrastructure/adapters/yfinance_crypto.py`:

```python
"""yFinance-Adapter für Krypto-OHLCV und technische Indikatoren (pandas-ta)."""
from __future__ import annotations

import asyncio
import logging

import pandas as pd
import pandas_ta as ta  # noqa: F401 — registriert DataFrame-Extension
import yfinance as yf
from cachetools import TTLCache

_logger = logging.getLogger(__name__)

_TECH_CACHE: TTLCache = TTLCache(maxsize=50, ttl=300)
_CHF_PAIRS = {"BTC-CHF", "ETH-CHF"}
_CHF_USD_RATE_TICKER = "CHFUSD=X"


class YFinanceCryptoAdapter:
    """Historische OHLCV + Technische Indikatoren für Kryptowährungen.

    Bevorzugt CHF-Pairs (BTC-CHF, ETH-CHF). Für USD-Pairs: automatische
    CHF-Umrechnung via CHFUSD=X mit Fallback 0.90.
    """

    async def get_technicals(self, ticker_yf: str, days: int = 365) -> pd.DataFrame:
        """Lädt OHLCV + RSI(14), MACD(12,26,9), BB(20,2), EMA(20,50)."""
        cache_key = (ticker_yf, days)
        if cache_key in _TECH_CACHE:
            return _TECH_CACHE[cache_key]

        df = await self._download(ticker_yf, days)
        if df is None or df.empty:
            usd_ticker = ticker_yf.replace("-CHF", "-USD")
            df = await self._download(usd_ticker, days)
            if df is not None and not df.empty:
                rate = await self._get_chf_usd_rate()
                df["Close"] = df["Close"] * rate
                df["Open"] = df["Open"] * rate
                df["High"] = df["High"] * rate
                df["Low"] = df["Low"] * rate

        if df is None or df.empty:
            _logger.warning("YFinanceCryptoAdapter: keine Daten für %s", ticker_yf)
            return pd.DataFrame()

        # Flatten MultiIndex-Columns (yfinance >= 0.2.40 gibt Tuple-Columns zurück)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.bbands(length=20, std=2.0, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)

        df = df.dropna(subset=["RSI_14", "MACD_12_26_9"])
        _TECH_CACHE[cache_key] = df
        return df

    async def get_smi_correlation(self, ticker_yf: str, days: int = 365) -> float:
        """Pearson-Korrelation zwischen Krypto und SMI über `days` Tage."""
        try:
            crypto_df, smi_df = await asyncio.gather(
                self._download(ticker_yf, days),
                self._download("^SSMI", days),
            )
            if crypto_df is None or crypto_df.empty or smi_df is None or smi_df.empty:
                return 0.0
            if isinstance(crypto_df.columns, pd.MultiIndex):
                crypto_df.columns = [col[0] for col in crypto_df.columns]
            if isinstance(smi_df.columns, pd.MultiIndex):
                smi_df.columns = [col[0] for col in smi_df.columns]
            combined = pd.DataFrame(
                {"crypto": crypto_df["Close"], "smi": smi_df["Close"]}
            ).dropna()
            return float(combined.corr().iloc[0, 1])
        except Exception:
            _logger.warning("SMI-Korrelation für %s nicht berechenbar", ticker_yf)
            return 0.0

    async def _download(self, ticker: str, days: int) -> pd.DataFrame | None:
        try:
            return await asyncio.to_thread(
                yf.download,
                ticker,
                period=f"{days}d",
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            _logger.warning("yFinance Download fehlgeschlagen: %s", ticker)
            return None

    async def _get_chf_usd_rate(self) -> float:
        df = await self._download(_CHF_USD_RATE_TICKER, 2)
        if df is None or df.empty:
            return 0.90
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        return float(df["Close"].iloc[-1])
```

- [ ] **Step 2: Import-Test**

```bash
python -c "from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/adapters/yfinance_crypto.py
git commit -m "feat(crypto): add YFinanceCryptoAdapter with pandas-ta indicators and CHF fallback"
```

---

## Task 8: CoinGeckoAdapter implementieren

**Files:**
- Create: `backend/infrastructure/adapters/coingecko_adapter.py`

- [ ] **Step 1: CoinGeckoAdapter erstellen**

Datei `backend/infrastructure/adapters/coingecko_adapter.py`:

```python
"""CoinGecko API-Adapter für Marktdaten in CHF (Free Tier, kein API-Key nötig)."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from pycoingecko import CoinGeckoAPI

_logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 600


class CoinGeckoAdapter:
    """Wrapper um die CoinGecko API mit 10-Minuten-Cache.

    Ein einziger Batch-Call für alle 10 Coins schont das Free-Tier-Limit.
    """

    def __init__(self, api_key: str = "") -> None:
        self._cg = CoinGeckoAPI(api_key=api_key)
        self._market_cache: list[dict] | None = None
        self._market_cached_at: datetime | None = None

    async def get_market_data(
        self, coin_ids: list[str], vs_currency: str = "chf"
    ) -> list[dict]:
        """Markt-Daten für mehrere Coins in einem API-Call (Batch)."""
        now = datetime.now(tz=UTC)
        if (
            self._market_cached_at
            and (now - self._market_cached_at).total_seconds() < _CACHE_TTL_SECONDS
            and self._market_cache is not None
        ):
            return self._market_cache

        try:
            result: list[dict] = await asyncio.to_thread(
                self._cg.get_coins_markets,
                vs_currency=vs_currency,
                ids=",".join(coin_ids),
                order="market_cap_desc",
                per_page=50,
                page=1,
                sparkline=False,
                price_change_percentage="24h,7d",
            )
            self._market_cache = result
            self._market_cached_at = now
            return result
        except Exception:
            _logger.warning("CoinGeckoAdapter: API-Call fehlgeschlagen")
            return self._market_cache or []
```

- [ ] **Step 2: Import-Test**

```bash
python -c "from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/adapters/coingecko_adapter.py
git commit -m "feat(crypto): add CoinGeckoAdapter with 10-min cache and graceful fallback"
```

---

## Task 9: CryptoScoringService implementieren

**Files:**
- Create: `backend/application/services/crypto_scoring_service.py`

- [ ] **Step 1: CryptoScoringService erstellen**

Datei `backend/application/services/crypto_scoring_service.py`:

```python
"""CryptoScoringService — orchestriert alle Datenquellen und berechnet CryptoSignals."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import pandas as pd

from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS, CryptoAsset
from backend.domain.services.crypto_scorer import CryptoScorer, generate_signal_reason
from backend.domain.value_objects.crypto_signal import CryptoSignal
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter

_logger = logging.getLogger(__name__)


class CryptoScoringService:
    """Orchestriert CoinGecko, yFinance und Fear&Greed für alle 10 Kryptos."""

    def __init__(
        self,
        cg_adapter: CoinGeckoAdapter,
        yf_adapter: YFinanceCryptoAdapter,
        fg_adapter: FearGreedAdapter,
        scorer: CryptoScorer,
    ) -> None:
        self._cg = cg_adapter
        self._yf = yf_adapter
        self._fg = fg_adapter
        self._scorer = scorer

    async def score_all(self) -> list[CryptoSignal]:
        """Berechnet Scores für alle 10 unterstützten Kryptos parallel."""
        fear_greed = await self._fg.get_current()
        fg_value = fear_greed["value"]
        fg_label = fear_greed["label"]

        coin_ids = [c[0] for c in SUPPORTED_CRYPTOS]
        market_data = await self._cg.get_market_data(coin_ids)
        market_map = {d["id"]: d for d in market_data}

        tech_tasks = [self._yf.get_technicals(c[1]) for c in SUPPORTED_CRYPTOS]
        corr_tasks = [self._yf.get_smi_correlation(c[1]) for c in SUPPORTED_CRYPTOS]

        all_tech = await asyncio.gather(*tech_tasks, return_exceptions=True)
        all_corr = await asyncio.gather(*corr_tasks, return_exceptions=True)

        results: list[CryptoSignal] = []
        for i, (cg_id, yf_ticker, name, kategorie, has_etp) in enumerate(SUPPORTED_CRYPTOS):
            tech = all_tech[i] if not isinstance(all_tech[i], Exception) else pd.DataFrame()
            corr = all_corr[i] if not isinstance(all_corr[i], Exception) else 0.0
            if isinstance(tech, pd.DataFrame) and tech.empty:
                _logger.warning("Keine Technikaldaten für %s — übersprungen", yf_ticker)
                continue

            mkt = market_map.get(cg_id, {})
            asset = CryptoAsset(
                ticker_cg=cg_id,
                ticker_yf=yf_ticker,
                name=name,
                symbol=yf_ticker.split("-")[0],
                kategorie=kategorie,
                has_six_etp=has_etp,
                price_chf=mkt.get("current_price"),
                market_cap_chf=mkt.get("market_cap"),
                volume_24h_chf=mkt.get("total_volume"),
                price_change_24h_pct=mkt.get("price_change_percentage_24h"),
                price_change_7d_pct=mkt.get("price_change_percentage_7d_in_currency"),
                ath_change_pct=mkt.get("ath_change_percentage"),
                market_cap_rank=mkt.get("market_cap_rank"),
            )

            score, components = self._scorer.score(
                asset, tech, fg_value, correlation_smi_1y=float(corr)  # type: ignore[arg-type]
            )
            signal = _score_to_signal(score)

            rsi = float(tech["RSI_14"].iloc[-1]) if "RSI_14" in tech.columns else 50.0
            macd_val = float(tech["MACD_12_26_9"].iloc[-1]) if "MACD_12_26_9" in tech.columns else 0.0
            macd_sig_val = float(tech["MACDs_12_26_9"].iloc[-1]) if "MACDs_12_26_9" in tech.columns else 0.0
            returns = tech["Close"].pct_change().dropna()
            vol_30d = float(returns.rolling(30).std().iloc[-1] * (365**0.5) * 100) if len(returns) >= 30 else 0.0

            reason = generate_signal_reason(
                signal=signal,
                asset_name=name,
                score=score,
                rsi=rsi,
                fear_greed=fg_value,
                change_7d=asset.price_change_7d_pct or 0.0,
            )

            results.append(
                CryptoSignal(
                    ticker=yf_ticker.split("-")[0],
                    name=name,
                    signal=signal,  # type: ignore[arg-type]
                    score=round(score, 1),
                    score_components={k: round(v, 1) for k, v in components.items()},
                    signal_reason_de=reason,
                    fear_greed_value=fg_value,
                    fear_greed_label=fg_label,
                    rsi_14=round(rsi, 1),
                    macd_signal="bullish" if macd_val > macd_sig_val else "bearish",
                    volatility_30d_pct=round(vol_30d, 1),
                    correlation_smi_1y=round(float(corr), 3),  # type: ignore[arg-type]
                    has_six_etp=has_etp,
                    price_chf=asset.price_chf,
                    market_cap_chf=asset.market_cap_chf,
                    price_change_24h_pct=asset.price_change_24h_pct,
                    price_change_7d_pct=asset.price_change_7d_pct,
                    ath_change_pct=asset.ath_change_pct,
                    market_cap_rank=asset.market_cap_rank,
                    timestamp=datetime.now(tz=UTC),
                )
            )

        return sorted(results, key=lambda x: x.score, reverse=True)

    async def score_one(self, ticker_symbol: str) -> CryptoSignal | None:
        """Einzelsignal für einen Ticker (z.B. 'BTC', 'ETH')."""
        all_signals = await self.score_all()
        return next((s for s in all_signals if s.ticker == ticker_symbol.upper()), None)


def _score_to_signal(score: float) -> str:
    if score >= CryptoScorer.STRONG_BUY_THRESHOLD:
        return "STRONG_BUY"
    if score >= CryptoScorer.BUY_THRESHOLD:
        return "BUY"
    if score >= CryptoScorer.HOLD_THRESHOLD:
        return "HOLD"
    if score >= CryptoScorer.SELL_THRESHOLD:
        return "SELL"
    return "STRONG_SELL"
```

- [ ] **Step 2: Import-Test**

```bash
python -c "from backend.application.services.crypto_scoring_service import CryptoScoringService; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/application/services/crypto_scoring_service.py
git commit -m "feat(crypto): add CryptoScoringService orchestrating all data sources"
```

---

## Task 10: REST Schema + Router + Registrierung

**Files:**
- Create: `backend/interfaces/rest/schemas/crypto.py`
- Create: `backend/interfaces/rest/routers/crypto.py`
- Modify: `backend/interfaces/rest/dependencies.py`
- Modify: `backend/interfaces/rest/app.py`

- [ ] **Step 1: Pydantic Schema erstellen**

Datei `backend/interfaces/rest/schemas/crypto.py`:

```python
"""Pydantic Response-Modelle für /api/v1/crypto/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from backend.domain.value_objects.crypto_signal import CryptoSignal


class CryptoSignalResponse(BaseModel):
    ticker: str
    name: str
    signal: str
    score: float
    score_components: dict[str, float]
    signal_reason_de: str
    price_chf: float | None
    market_cap_chf: float | None
    price_change_24h_pct: float | None
    price_change_7d_pct: float | None
    ath_change_pct: float | None
    market_cap_rank: int | None
    rsi_14: float
    macd_signal: str
    volatility_30d_pct: float
    correlation_smi_1y: float
    fear_greed_value: int
    fear_greed_label: str
    has_six_etp: bool
    timestamp: str

    @classmethod
    def from_domain(cls, signal: CryptoSignal) -> "CryptoSignalResponse":
        return cls(
            ticker=signal.ticker,
            name=signal.name,
            signal=signal.signal,
            score=signal.score,
            score_components=signal.score_components,
            signal_reason_de=signal.signal_reason_de,
            price_chf=signal.price_chf,
            market_cap_chf=signal.market_cap_chf,
            price_change_24h_pct=signal.price_change_24h_pct,
            price_change_7d_pct=signal.price_change_7d_pct,
            ath_change_pct=signal.ath_change_pct,
            market_cap_rank=signal.market_cap_rank,
            rsi_14=signal.rsi_14,
            macd_signal=signal.macd_signal,
            volatility_30d_pct=signal.volatility_30d_pct,
            correlation_smi_1y=signal.correlation_smi_1y,
            fear_greed_value=signal.fear_greed_value,
            fear_greed_label=signal.fear_greed_label,
            has_six_etp=signal.has_six_etp,
            timestamp=signal.timestamp.isoformat(),
        )
```

- [ ] **Step 2: REST Router erstellen**

Datei `backend/interfaces/rest/routers/crypto.py`:

```python
"""REST-Router für /api/v1/crypto/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.interfaces.rest.dependencies import (
    get_coingecko_adapter,
    get_crypto_scoring_service,
    get_fear_greed_adapter,
)
from backend.interfaces.rest.schemas.crypto import CryptoSignalResponse

router = APIRouter(prefix="/api/v1/crypto", tags=["crypto"])


@router.get("/signals", response_model=list[CryptoSignalResponse])
async def get_crypto_signals(
    service: CryptoScoringService = Depends(get_crypto_scoring_service),
) -> list[CryptoSignalResponse]:
    """PRISMA-Signale für alle 10 unterstützten Kryptowährungen (sortiert nach Score)."""
    signals = await service.score_all()
    return [CryptoSignalResponse.from_domain(s) for s in signals]


@router.get("/signals/{ticker}", response_model=CryptoSignalResponse)
async def get_crypto_signal(
    ticker: str = Path(..., pattern=r"^[A-Z]{2,10}$"),
    service: CryptoScoringService = Depends(get_crypto_scoring_service),
) -> CryptoSignalResponse:
    """Einzelnes Signal für einen Ticker (z.B. BTC, ETH, SOL)."""
    signal = await service.score_one(ticker.upper())
    if signal is None:
        raise HTTPException(status_code=404, detail=f"{ticker} nicht unterstützt oder keine Daten.")
    return CryptoSignalResponse.from_domain(signal)


@router.get("/fear-greed")
async def get_fear_greed(
    adapter: FearGreedAdapter = Depends(get_fear_greed_adapter),
) -> dict:
    """Aktueller Crypto Fear & Greed Index (0–100)."""
    return await adapter.get_current()


@router.get("/market")
async def get_crypto_market(
    cg: CoinGeckoAdapter = Depends(get_coingecko_adapter),
) -> list[dict]:
    """Markt-Übersicht für alle 10 Kryptos: Preis CHF, Market Cap, 24h/7d Änderung."""
    from backend.domain.entities.crypto_asset import SUPPORTED_CRYPTOS
    return await cg.get_market_data([c[0] for c in SUPPORTED_CRYPTOS])
```

- [ ] **Step 3: DI-Funktionen in dependencies.py einfügen**

In `backend/interfaces/rest/dependencies.py` am Ende der Datei (vor dem letzten `require_admin_api_key` Block) einfügen:

Zunächst die Imports ergänzen (ganz oben in der Import-Sektion):
```python
from backend.infrastructure.adapters.coingecko_adapter import CoinGeckoAdapter
from backend.infrastructure.adapters.fear_greed_adapter import FearGreedAdapter
from backend.infrastructure.adapters.yfinance_crypto import YFinanceCryptoAdapter
from backend.application.services.crypto_scoring_service import CryptoScoringService
from backend.domain.services.crypto_scorer import CryptoScorer
```

Dann am Ende der Datei die DI-Funktionen einfügen:
```python
# ---------------------------------------------------------------------------
# Crypto Module DI-Chain
# ---------------------------------------------------------------------------

_fear_greed_adapter: FearGreedAdapter | None = None
_coingecko_adapter: CoinGeckoAdapter | None = None
_yfinance_crypto_adapter: YFinanceCryptoAdapter | None = None


def _get_fear_greed_singleton() -> FearGreedAdapter:
    global _fear_greed_adapter
    if _fear_greed_adapter is None:
        _fear_greed_adapter = FearGreedAdapter()
    return _fear_greed_adapter


def _get_coingecko_singleton() -> CoinGeckoAdapter:
    global _coingecko_adapter
    if _coingecko_adapter is None:
        from backend.config import get_settings
        _coingecko_adapter = CoinGeckoAdapter(api_key=get_settings().coingecko_api_key)
    return _coingecko_adapter


def _get_yfinance_crypto_singleton() -> YFinanceCryptoAdapter:
    global _yfinance_crypto_adapter
    if _yfinance_crypto_adapter is None:
        _yfinance_crypto_adapter = YFinanceCryptoAdapter()
    return _yfinance_crypto_adapter


async def get_fear_greed_adapter() -> FearGreedAdapter:
    return _get_fear_greed_singleton()


async def get_coingecko_adapter() -> CoinGeckoAdapter:
    return _get_coingecko_singleton()


async def get_yfinance_crypto_adapter() -> YFinanceCryptoAdapter:
    return _get_yfinance_crypto_singleton()


async def get_crypto_scoring_service() -> CryptoScoringService:
    return CryptoScoringService(
        cg_adapter=_get_coingecko_singleton(),
        yf_adapter=_get_yfinance_crypto_singleton(),
        fg_adapter=_get_fear_greed_singleton(),
        scorer=CryptoScorer(),
    )
```

- [ ] **Step 4: Crypto-Router in app.py registrieren**

In `backend/interfaces/rest/app.py` den Import ergänzen:
```python
from backend.interfaces.rest.routers import (
    # ... bestehende imports ...
    crypto,
)
```

Und in `create_app()` nach `app.include_router(alerts.router, dependencies=_auth)` einfügen:
```python
    app.include_router(crypto.router, dependencies=_auth)
```

- [ ] **Step 5: Syntax-Check**

```bash
python -c "from backend.interfaces.rest.app import create_app; app = create_app(); print('App OK, routes:', len(app.routes))"
```

Erwartete Ausgabe: `App OK, routes: <Zahl > 40>`

- [ ] **Step 6: Commit**

```bash
git add backend/interfaces/rest/schemas/crypto.py \
        backend/interfaces/rest/routers/crypto.py \
        backend/interfaces/rest/dependencies.py \
        backend/interfaces/rest/app.py
git commit -m "feat(crypto): add REST schema, router /api/v1/crypto/*, DI chain, register in app"
```

---

## Task 11: Alembic Migration 0024

**Files:**
- Create: `backend/alembic/versions/0024_create_crypto_signals.py`

- [ ] **Step 1: Migration erstellen**

Datei `backend/alembic/versions/0024_create_crypto_signals.py`:

```python
"""0024 — create crypto_signals table for daily snapshots.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crypto_signals",
        sa.Column("id", sa.UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("signal", sa.String(20), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("price_chf", sa.Float, nullable=True),
        sa.Column("fear_greed_value", sa.Integer, nullable=True),
        sa.Column("rsi_14", sa.Float, nullable=True),
        sa.Column("volatility_30d_pct", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_crypto_signals_ticker_date",
        "crypto_signals",
        ["ticker", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_crypto_signals_ticker_date", table_name="crypto_signals")
    op.drop_table("crypto_signals")
```

- [ ] **Step 2: Migration-Syntax prüfen (ohne DB-Verbindung)**

```bash
python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('m', 'backend/alembic/versions/0024_create_crypto_signals.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print('revision:', m.revision, '| down_revision:', m.down_revision)
"
```

Erwartete Ausgabe: `revision: 0024 | down_revision: 0023`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0024_create_crypto_signals.py
git commit -m "feat(crypto): add alembic migration 0024 for crypto_signals table"
```

---

## Task 12: Integration Tests für /api/v1/crypto/*

**Files:**
- Create: `backend/tests/integration/test_crypto_endpoints.py`

- [ ] **Step 1: Integration-Test erstellen**

Datei `backend/tests/integration/test_crypto_endpoints.py`:

```python
"""Integrationstests für /api/v1/crypto/* — HTTP-Schicht ohne externe APIs."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.domain.value_objects.crypto_signal import CryptoSignal
from datetime import datetime, UTC

pytestmark = pytest.mark.asyncio


def _make_signal(ticker: str = "BTC", score: float = 65.0) -> CryptoSignal:
    return CryptoSignal(
        ticker=ticker,
        name="Bitcoin" if ticker == "BTC" else ticker,
        signal="BUY",
        score=score,
        score_components={"momentum": 20.0, "trend": 18.0, "sentiment": 14.0, "markt": 8.0, "risiko": 5.0},
        signal_reason_de="Test-Signal.",
        fear_greed_value=35,
        fear_greed_label="Fear",
        rsi_14=42.0,
        macd_signal="bullish",
        volatility_30d_pct=45.0,
        correlation_smi_1y=0.15,
        has_six_etp=True,
        price_chf=50000.0,
        market_cap_chf=1e12,
        price_change_24h_pct=1.5,
        price_change_7d_pct=5.0,
        ath_change_pct=-30.0,
        market_cap_rank=1,
        timestamp=datetime.now(tz=UTC),
    )


@pytest.fixture
def mock_crypto_service():
    service = AsyncMock()
    service.score_all.return_value = [_make_signal("BTC", 65.0), _make_signal("ETH", 58.0)]
    service.score_one.return_value = _make_signal("BTC", 65.0)
    return service


@pytest.fixture
async def crypto_client(mock_crypto_service) -> AsyncClient:
    from httpx import ASGITransport
    from backend.interfaces.rest.app import create_app
    from backend.interfaces.rest.dependencies import get_crypto_scoring_service

    app = create_app()
    app.dependency_overrides[get_crypto_scoring_service] = lambda: mock_crypto_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_get_signals_returns_200(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    assert response.status_code == 200


async def test_get_signals_returns_list(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 2


async def test_get_signals_has_required_fields(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals", headers={"X-API-Key": "test"})
    first = response.json()[0]
    for field in ["ticker", "signal", "score", "score_components", "rsi_14", "fear_greed_value", "has_six_etp"]:
        assert field in first, f"Missing field: {field}"


async def test_get_signal_by_ticker_returns_200(crypto_client: AsyncClient) -> None:
    response = await crypto_client.get("/api/v1/crypto/signals/BTC", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    assert response.json()["ticker"] == "BTC"


async def test_get_signal_invalid_ticker_returns_404(crypto_client: AsyncClient, mock_crypto_service) -> None:
    mock_crypto_service.score_one.return_value = None
    response = await crypto_client.get("/api/v1/crypto/signals/UNKNOWN", headers={"X-API-Key": "test"})
    assert response.status_code == 404


async def test_get_fear_greed_returns_200(crypto_client: AsyncClient) -> None:
    with patch(
        "backend.infrastructure.adapters.fear_greed_adapter.FearGreedAdapter.get_current",
        new_callable=AsyncMock,
        return_value={"value": 35, "label": "Fear", "timestamp": "1234567890"},
    ):
        response = await crypto_client.get("/api/v1/crypto/fear-greed", headers={"X-API-Key": "test"})
    assert response.status_code == 200
    body = response.json()
    assert "value" in body
    assert "label" in body


async def test_get_market_returns_200(crypto_client: AsyncClient) -> None:
    with patch(
        "backend.infrastructure.adapters.coingecko_adapter.CoinGeckoAdapter.get_market_data",
        new_callable=AsyncMock,
        return_value=[{"id": "bitcoin", "current_price": 50000}],
    ):
        response = await crypto_client.get("/api/v1/crypto/market", headers={"X-API-Key": "test"})
    assert response.status_code == 200
```

- [ ] **Step 2: Tests ausführen (ohne DB)**

```bash
python -m pytest backend/tests/integration/test_crypto_endpoints.py -v
```

Erwartete Ausgabe: Alle Tests `PASSED`.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_crypto_endpoints.py
git commit -m "test(crypto): add integration tests for /api/v1/crypto/* endpoints"
```

---

## Task 13: Frontend API Client

**Files:**
- Create: `frontend/lib/api/crypto.ts`

- [ ] **Step 1: crypto.ts erstellen**

Datei `frontend/lib/api/crypto.ts`:

```typescript
import { apiFetch } from './client';

export interface CryptoSignal {
  ticker: string;
  name: string;
  signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';
  score: number;
  score_components: {
    momentum: number;
    trend: number;
    sentiment: number;
    markt: number;
    risiko: number;
  };
  signal_reason_de: string;
  price_chf: number | null;
  market_cap_chf: number | null;
  price_change_24h_pct: number | null;
  price_change_7d_pct: number | null;
  ath_change_pct: number | null;
  market_cap_rank: number | null;
  rsi_14: number;
  macd_signal: 'bullish' | 'bearish';
  volatility_30d_pct: number;
  correlation_smi_1y: number;
  fear_greed_value: number;
  fear_greed_label: string;
  has_six_etp: boolean;
  timestamp: string;
}

export interface FearGreedData {
  value: number;
  label: string;
  timestamp: string;
}

export async function getCryptoSignals(): Promise<CryptoSignal[]> {
  return apiFetch<CryptoSignal[]>('/api/v1/crypto/signals');
}

export async function getCryptoSignal(ticker: string): Promise<CryptoSignal> {
  return apiFetch<CryptoSignal>(`/api/v1/crypto/signals/${ticker}`);
}

export async function getFearGreed(): Promise<FearGreedData> {
  return apiFetch<FearGreedData>('/api/v1/crypto/fear-greed');
}

export function signalColor(signal: CryptoSignal['signal']): string {
  switch (signal) {
    case 'STRONG_BUY': return '#00c853';
    case 'BUY':        return '#7ee787';
    case 'HOLD':       return '#ffa657';
    case 'SELL':       return '#f85149';
    case 'STRONG_SELL': return '#da3633';
  }
}

export function signalLabel(signal: CryptoSignal['signal']): string {
  switch (signal) {
    case 'STRONG_BUY': return 'STRONG BUY';
    case 'BUY':        return 'BUY';
    case 'HOLD':       return 'HOLD';
    case 'SELL':       return 'SELL';
    case 'STRONG_SELL': return 'STRONG SELL';
  }
}

export function fearGreedLabel(value: number): string {
  if (value <= 25) return 'Extreme Angst';
  if (value <= 40) return 'Angst';
  if (value <= 60) return 'Neutral';
  if (value <= 75) return 'Gier';
  return 'Extreme Gier';
}

export function fearGreedColor(value: number): string {
  if (value <= 25) return '#7ee787';
  if (value <= 40) return '#a5f3b4';
  if (value <= 60) return '#ffa657';
  if (value <= 75) return '#f85149';
  return '#da3633';
}
```

- [ ] **Step 2: TypeScript-Check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i 'crypto' | head -10; echo "Exit: $?"
```

Erwartete Ausgabe: Keine Fehler zu `crypto.ts`. Exit-Code 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/crypto.ts
git commit -m "feat(crypto): add frontend API client with types and signal/fear-greed helpers"
```

---

## Task 14: Frontend-Komponenten

**Files:**
- Create: `frontend/components/crypto/FearGreedGauge.tsx`
- Create: `frontend/components/crypto/CryptoSignalCard.tsx`
- Create: `frontend/components/crypto/ScoreBreakdown.tsx`
- Create: `frontend/components/crypto/CryptoProRow.tsx`

- [ ] **Step 1: FearGreedGauge erstellen**

Datei `frontend/components/crypto/FearGreedGauge.tsx`:

```tsx
'use client';

import { fearGreedColor, fearGreedLabel } from '@/lib/api/crypto';
import { cn } from '@/lib/utils';

interface FearGreedGaugeProps {
  value: number;
  label: string;
  className?: string;
}

export function FearGreedGauge({ value, label, className }: FearGreedGaugeProps) {
  const color = fearGreedColor(value);
  const germanLabel = fearGreedLabel(value);
  const pct = Math.min(100, Math.max(0, value));

  // Halbkreis: 180° = 0–100. Rotation = pct * 1.8 - 90 (Start links)
  const rotation = pct * 1.8 - 90;

  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <div className="relative w-40 h-20 overflow-hidden">
        {/* Hintergrund-Halbkreis */}
        <div
          className="absolute inset-0 rounded-t-full"
          style={{
            background: 'conic-gradient(from 180deg at 50% 100%, #7ee787 0deg, #ffa657 90deg, #f85149 180deg)',
            opacity: 0.25,
          }}
        />
        {/* Nadel */}
        <div
          className="absolute bottom-0 left-1/2 w-0.5 h-16 origin-bottom rounded-full transition-transform duration-700"
          style={{
            backgroundColor: color,
            transform: `translateX(-50%) rotate(${rotation}deg)`,
          }}
        />
        {/* Mittelpunkt */}
        <div
          className="absolute bottom-0 left-1/2 w-3 h-3 rounded-full -translate-x-1/2 translate-y-1/2"
          style={{ backgroundColor: color }}
        />
      </div>
      <div className="text-center">
        <div className="text-2xl font-black tabular-nums" style={{ color }}>
          {value}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">{germanLabel}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: CryptoSignalCard erstellen**

Datei `frontend/components/crypto/CryptoSignalCard.tsx`:

```tsx
'use client';

import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';
import { cn } from '@/lib/utils';

interface CryptoSignalCardProps {
  signal: CryptoSignal;
}

export function CryptoSignalCard({ signal }: CryptoSignalCardProps) {
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);
  const pct = Math.round(signal.score);

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-bold text-base">{signal.name}</div>
          <div className="text-xs text-muted-foreground">{signal.ticker}</div>
        </div>
        {/* Score-Donut */}
        <div className="flex flex-col items-center shrink-0">
          <div
            className="text-xl font-black tabular-nums"
            style={{ color }}
          >
            {pct}
          </div>
          <div className="text-[10px] text-muted-foreground">/100</div>
        </div>
      </div>

      {/* Score Bar */}
      <div className="h-1.5 w-full rounded-full bg-[#21262d] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>

      {/* Signal Badge */}
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full border"
          style={{
            color,
            borderColor: color + '50',
            backgroundColor: color + '20',
          }}
        >
          {label}
        </span>
        {signal.has_six_etp && (
          <span className="text-[10px] text-[#8b949e] border border-[#30363d] rounded px-1.5 py-0.5">
            SIX ETP
          </span>
        )}
      </div>

      {/* Signal Reason */}
      <p className="text-xs text-muted-foreground leading-relaxed">
        {signal.signal_reason_de}
      </p>
    </div>
  );
}
```

- [ ] **Step 3: ScoreBreakdown erstellen**

Datei `frontend/components/crypto/ScoreBreakdown.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { type CryptoSignal } from '@/lib/api/crypto';
import { cn } from '@/lib/utils';

const COMPONENT_LABELS: Record<string, { label: string; max: number; color: string }> = {
  momentum: { label: 'Momentum',  max: 30, color: '#58a6ff' },
  trend:    { label: 'Trend',     max: 25, color: '#3fb950' },
  sentiment:{ label: 'Sentiment', max: 20, color: '#ffa657' },
  markt:    { label: 'Markt',     max: 15, color: '#bc8cff' },
  risiko:   { label: 'Risiko',    max: 10, color: '#79c0ff' },
};

interface ScoreBreakdownProps {
  signal: CryptoSignal;
}

export function ScoreBreakdown({ signal }: ScoreBreakdownProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded border border-border/40 overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-muted-foreground hover:bg-muted/30 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span>Score-Aufschlüsselung</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 flex flex-col gap-2">
          {Object.entries(COMPONENT_LABELS).map(([key, { label, max, color }]) => {
            const val = signal.score_components[key as keyof typeof signal.score_components] ?? 0;
            const pct = Math.round((val / max) * 100);
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground w-16 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-[10px] tabular-nums text-muted-foreground w-10 text-right">
                  {val}/{max}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: CryptoProRow erstellen**

Datei `frontend/components/crypto/CryptoProRow.tsx`:

```tsx
'use client';

import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';

interface CryptoProRowProps {
  signal: CryptoSignal;
}

function fmt(n: number | null, decimals = 2): string {
  if (n == null) return '—';
  return n.toLocaleString('de-CH', { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
}

function fmtPct(n: number | null): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

function pctColor(n: number | null): string {
  if (n == null) return '';
  return n > 0 ? 'text-[#7ee787]' : n < 0 ? 'text-[#f85149]' : 'text-muted-foreground';
}

export function CryptoProRow({ signal }: CryptoProRowProps) {
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);

  return (
    <tr className="border-b border-border/30 hover:bg-muted/20 transition-colors text-sm">
      <td className="py-2 px-3">
        <div className="font-mono font-bold">{signal.ticker}</div>
        <div className="text-[10px] text-muted-foreground">{signal.name}</div>
      </td>
      <td className="py-2 px-3">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full border whitespace-nowrap"
          style={{ color, borderColor: color + '50', backgroundColor: color + '20' }}
        >
          {label}
        </span>
      </td>
      <td className="py-2 px-3 tabular-nums">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-12 rounded-full bg-[#21262d] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${Math.round(signal.score)}%`, backgroundColor: color }}
            />
          </div>
          <span className="text-xs">{signal.score}</span>
        </div>
      </td>
      <td className="py-2 px-3 tabular-nums text-right">
        {signal.price_chf != null ? `CHF ${fmt(signal.price_chf, 0)}` : '—'}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_24h_pct)}`}>
        {fmtPct(signal.price_change_24h_pct)}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_7d_pct)}`}>
        {fmtPct(signal.price_change_7d_pct)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.rsi_14.toFixed(1)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.volatility_30d_pct.toFixed(1)}%
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.correlation_smi_1y.toFixed(2)}
      </td>
    </tr>
  );
}
```

- [ ] **Step 5: TypeScript-Check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E 'components/crypto' | head -10; echo "TS Exit: $?"
```

Erwartete Ausgabe: Keine Fehler zu `components/crypto`. Exit-Code 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/crypto/
git commit -m "feat(crypto): add FearGreedGauge, CryptoSignalCard, ScoreBreakdown, CryptoProRow"
```

---

## Task 15: /crypto Seite + Nav-Link

**Files:**
- Create: `frontend/app/crypto/page.tsx`
- Create: `frontend/app/crypto/crypto-client.tsx`
- Modify: `frontend/app/nav-links.tsx`

- [ ] **Step 1: page.tsx erstellen**

Datei `frontend/app/crypto/page.tsx`:

```tsx
import { Suspense } from 'react';
import type { Metadata } from 'next';
import { CryptoClient } from './crypto-client';

export const metadata: Metadata = {
  title: 'Krypto',
};

export default function CryptoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Krypto.</h1>
        <p className="text-sm text-muted-foreground mt-1">
          10 Top-Kryptowährungen — technisch-sentimentale PRISMA-Signale in CHF
        </p>
      </div>
      <Suspense>
        <CryptoClient />
      </Suspense>
    </div>
  );
}
```

- [ ] **Step 2: crypto-client.tsx erstellen**

Datei `frontend/app/crypto/crypto-client.tsx`:

```tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { Bitcoin } from 'lucide-react';

import { getCryptoSignals, getFearGreed } from '@/lib/api/crypto';
import { FearGreedGauge } from '@/components/crypto/FearGreedGauge';
import { CryptoSignalCard } from '@/components/crypto/CryptoSignalCard';
import { CryptoProRow } from '@/components/crypto/CryptoProRow';
import { ScoreBreakdown } from '@/components/crypto/ScoreBreakdown';
import { Skeleton } from '@/components/ui/skeleton';
import { usePrismaMode } from '@/hooks/usePrismaMode';

const DISCLAIMER = `⚠️ Kryptowährungen sind hochvolatile Spekulations-Assets. Kein 3a-Instrument. Kein gesetzliches Zahlungsmittel in der Schweiz. Kapitalgewinne für Privatanleger steuerfrei (CH) — Vermögen ist steuerpflichtig (ESTV-Jahreswert). PRISMA-Signale sind keine Anlageberatung. Nur für freies Vermögen geeignet.`;

export function CryptoClient() {
  const { mode } = usePrismaMode();

  const { data: signals, isLoading: signalsLoading, error: signalsError } = useQuery({
    queryKey: ['crypto-signals'],
    queryFn: getCryptoSignals,
    staleTime: 10 * 60 * 1000,
  });

  const { data: fearGreed, isLoading: fgLoading } = useQuery({
    queryKey: ['fear-greed'],
    queryFn: getFearGreed,
    staleTime: 60 * 60 * 1000,
  });

  const buySignals = signals?.filter((s) =>
    s.signal === 'STRONG_BUY' || s.signal === 'BUY'
  ).slice(0, 3) ?? [];

  return (
    <div className="space-y-6">
      {/* Fear & Greed */}
      <div className="rounded-lg border border-border/50 bg-card p-4 flex flex-col sm:flex-row items-center gap-4">
        <div>
          <div className="text-sm font-medium">Crypto Fear &amp; Greed Index</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Contrarian-Indikator: Extreme Angst = Einstiegsgelegenheit
          </div>
        </div>
        <div className="ml-auto">
          {fgLoading || !fearGreed ? (
            <Skeleton className="w-40 h-24" />
          ) : (
            <FearGreedGauge value={fearGreed.value} label={fearGreed.label} />
          )}
        </div>
      </div>

      {/* Simple Mode: Top-3 BUY-Signale */}
      {mode === 'simple' && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Beste Einstiegschancen
          </h2>
          {signalsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}
            </div>
          ) : signalsError ? (
            <p className="text-sm text-red-400">Signale konnten nicht geladen werden.</p>
          ) : buySignals.length === 0 ? (
            <p className="text-sm text-muted-foreground">Keine BUY-Signale aktuell.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {buySignals.map((s) => <CryptoSignalCard key={s.ticker} signal={s} />)}
            </div>
          )}
        </div>
      )}

      {/* Pro Mode: Vollständige Tabelle */}
      {mode === 'pro' && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Alle Signale (Pro)
          </h2>
          {signalsLoading ? (
            <Skeleton className="h-64" />
          ) : signalsError ? (
            <p className="text-sm text-red-400">Signale konnten nicht geladen werden.</p>
          ) : (
            <div className="rounded-lg border border-border/50 overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border/40 text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium">Asset</th>
                    <th className="text-left py-2 px-3 font-medium">Signal</th>
                    <th className="text-left py-2 px-3 font-medium">Score</th>
                    <th className="text-right py-2 px-3 font-medium">Preis</th>
                    <th className="text-right py-2 px-3 font-medium">24h</th>
                    <th className="text-right py-2 px-3 font-medium">7d</th>
                    <th className="text-right py-2 px-3 font-medium">RSI</th>
                    <th className="text-right py-2 px-3 font-medium">Vola</th>
                    <th className="text-right py-2 px-3 font-medium">SMI-Korr</th>
                  </tr>
                </thead>
                <tbody>
                  {signals?.map((s) => <CryptoProRow key={s.ticker} signal={s} />)}
                </tbody>
              </table>
            </div>
          )}

          {/* Score-Breakdown Accordion für Pro */}
          {signals && signals.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Score-Aufschlüsselung
              </h3>
              {signals.slice(0, 5).map((s) => (
                <div key={s.ticker} className="flex flex-col gap-1">
                  <span className="text-xs font-medium">{s.name} ({s.ticker})</span>
                  <ScoreBreakdown signal={s} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Disclaimer — immer sichtbar */}
      <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/80 leading-relaxed">
        {DISCLAIMER}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Nav-Link in nav-links.tsx einfügen**

In `frontend/app/nav-links.tsx` bei `NAV_GROUPS_SIMPLE` in der `ANALYSIEREN`-Gruppe:
```typescript
// Vorher:
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
    ],
// Nachher:
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
      { href: '/crypto',   label: 'Krypto.' },
    ],
```

Und bei `NAV_GROUPS_PRO` in der `ANALYSIEREN`-Gruppe:
```typescript
// Vorher:
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
      { href: '/research', label: 'Research' },
    ],
// Nachher:
    links: [
      { href: '/rankings', label: 'Rankings' },
      { href: '/stocks',   label: 'Aktien' },
      { href: '/research', label: 'Research' },
      { href: '/crypto',   label: 'Krypto.' },
    ],
```

- [ ] **Step 4: TypeScript-Check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E 'crypto|nav-links' | head -10; echo "TS Exit: $?"
```

Erwartete Ausgabe: Keine Fehler. Exit-Code 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/crypto/ frontend/app/nav-links.tsx
git commit -m "feat(crypto): add /crypto page with simple/pro mode and nav link"
```

---

## Task 16: E2E-Test

**Files:**
- Create: `frontend/e2e/15-crypto.spec.ts`

- [ ] **Step 1: E2E-Test erstellen**

Datei `frontend/e2e/15-crypto.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Krypto-Seite', () => {
  test('Seite lädt und zeigt Header', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByRole('heading', { name: 'Krypto.' })).toBeVisible();
  });

  test('Fear & Greed Bereich ist sichtbar', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByText('Crypto Fear & Greed Index')).toBeVisible();
  });

  test('Disclaimer ist immer sichtbar', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByText(/Kein 3a-Instrument/)).toBeVisible();
  });

  test('Nav-Link Krypto. ist in ANALYSIEREN sichtbar', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Krypto.' })).toBeVisible();
  });

  test('Nav-Link führt zu /crypto', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Krypto.' }).click();
    await expect(page).toHaveURL('/crypto');
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/e2e/15-crypto.spec.ts
git commit -m "test(crypto): add Playwright E2E tests for /crypto page"
```

---

## Task 17: Version-Bump + Gesamter Unit-Test-Lauf + PR

**Files:**
- Modify: `pyproject.toml` (version bump)
- Modify: `backend/interfaces/rest/routers/health.py` (APP_VERSION Bump)

- [ ] **Step 1: Version in pyproject.toml auf 2.2.0 setzen**

In `pyproject.toml` die Zeile:
```toml
version = "2.1.0"
```
ersetzen durch:
```toml
version = "2.2.0"
```

- [ ] **Step 2: Unit-Tests + Integration-Tests lokal ausführen**

```bash
python -m pytest backend/tests/unit/test_crypto_scorer.py backend/tests/integration/test_crypto_endpoints.py -v
```

Erwartete Ausgabe: Alle Tests `PASSED`. Bei Fehlern korrigieren, dann neu ausführen.

- [ ] **Step 3: Ruff-Linting prüfen**

```bash
python -m ruff check backend/domain/entities/crypto_asset.py \
  backend/domain/value_objects/crypto_signal.py \
  backend/domain/ports/crypto_data_provider.py \
  backend/domain/services/crypto_scorer.py \
  backend/infrastructure/adapters/fear_greed_adapter.py \
  backend/infrastructure/adapters/yfinance_crypto.py \
  backend/infrastructure/adapters/coingecko_adapter.py \
  backend/application/services/crypto_scoring_service.py \
  backend/interfaces/rest/schemas/crypto.py \
  backend/interfaces/rest/routers/crypto.py
```

Erwartete Ausgabe: Keine Fehler. Bei Linting-Fehlern: `python -m ruff check --fix <file>` anwenden.

- [ ] **Step 4: Frontend TypeScript-Check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20; echo "TS Exit: $?"
```

Erwartete Ausgabe: Exit-Code 0 (oder nur nicht-krypto-bezogene Warnings).

- [ ] **Step 5: Version-Commit**

```bash
git add pyproject.toml
git commit -m "chore: bump version to 2.2.0 for Krypto-Modul release"
```

- [ ] **Step 6: Branch pushen**

```bash
git push -u origin feat/crypto-module
```

- [ ] **Step 7: Pull Request erstellen**

```bash
gh pr create \
  --title "feat: Krypto-Modul v2.2.0 — 10 Assets, CryptoScorer, /crypto Seite" \
  --body "$(cat <<'EOF'
## Summary
- Neues eigenständiges Krypto-Analyse-Modul parallel zum Aktien-System
- CryptoScorer (0–100): Momentum + Trend + Sentiment + Markt + Risiko
- 3 neue Infrastruktur-Adapter: CoinGecko, yFinance/pandas-ta, Fear&Greed
- 4 REST-Endpoints: /api/v1/crypto/signals, /signals/{ticker}, /fear-greed, /market
- Frontend: /crypto Seite mit Simple-Mode (Top-3 Cards) und Pro-Mode (Tabelle + Accordion)
- Alembic Migration 0024 (crypto_signals Tabelle, Phase 1 als RAM-Cache)
- Regulatorischer Disclaimer (Pflicht, permanent sichtbar)

## Test plan
- [ ] `python -m pytest backend/tests/unit/test_crypto_scorer.py -v` — alle grün
- [ ] `python -m pytest backend/tests/integration/test_crypto_endpoints.py -v` — alle grün
- [ ] Frontend: `/crypto` in Simple-Mode aufrufen, Disclaimer sichtbar
- [ ] Frontend: Mode auf Pro wechseln, Tabelle + Accordion sichtbar
- [ ] Nav-Link `Krypto.` in ANALYSIEREN-Gruppe klickbar

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8: Git-Tag für Release setzen (nach PR-Merge)**

```bash
git checkout main
git pull origin main
git tag -a v2.2.0 -m "Krypto-Modul: CryptoScorer, 10 Assets, /crypto Seite"
git push origin v2.2.0
```

---

## Self-Review Checklist

### Spec-Coverage
| Spec-Abschnitt | Task |
|---------------|------|
| 1.3 Hexagonale Architektur | Task 3–9 |
| 2.1 Supported Assets (10 Cryptos) | Task 3 (SUPPORTED_CRYPTOS) |
| 2.2 CryptoAsset Entity | Task 3 |
| 2.3 CryptoSignal Value Object | Task 3 |
| 3.2 CryptoScorer Score-Logik | Task 5 |
| 3.3 Signal-Reason Generator | Task 5 (generate_signal_reason) |
| 4.1 CoinGeckoAdapter | Task 8 |
| 4.2 FearGreedAdapter | Task 6 |
| 4.3 YFinanceCryptoAdapter + pandas-ta | Task 7 |
| 5.1 CryptoScoringService | Task 9 |
| 5.2 REST Endpoints (signals, ticker, fg, market) | Task 10 |
| 5.3 Pydantic Response Schema | Task 10 |
| 6.1 Nav-Link | Task 15 |
| 6.2 Seiten-Struktur (Simple + Pro Mode) | Task 15 |
| 6.3 FearGreedGauge | Task 14 |
| 6.3 CryptoSignalCard | Task 14 |
| 6.3 CryptoProRow | Task 14 |
| 6.3 ScoreBreakdown Accordion | Task 14 |
| 7.1 Alembic Migration 0024 | Task 11 |
| 8 Config + .env.example | Task 2 |
| 9 Regulatorischer Disclaimer | Task 15 (crypto-client.tsx) |
| 13 Dependencies | Task 1 |
| Sprint 3: backtest/{ticker} | ⚠️ Nicht implementiert (Stub) — in Phase 2 |

> **Hinweis:** `/api/v1/crypto/backtest/{ticker}` wurde bewusst ausgelassen (Sprint 3 = optional). Kann als separater PR in Phase 2 implementiert werden.

### Type-Konsistenz
- `CryptoSignal.signal` → `Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]` — konsistent in VO, Response-Schema und Frontend-Type
- `CryptoScorer.score()` → `(asset, technicals, fear_greed, correlation_smi_1y=0.0)` — `correlation_smi_1y` überall als `float` (nicht optional)
- `score_components` → Dict mit Keys `momentum`, `trend`, `sentiment`, `markt`, `risiko` — konsistent in VO, Service, Schema, Frontend
- pandas-ta Column-Namen: `RSI_14`, `MACD_12_26_9`, `MACDs_12_26_9`, `BBU_20_2.0`, `BBL_20_2.0`, `EMA_20`, `EMA_50` — in Scorer und Adapter konsistent verwendet
