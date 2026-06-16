# PRISMA V2 — Krypto Feature Extension: Historisierung + Pattern Intelligence + Agent-Analyse
> **Korrigierte Version — 2026-06-16.** Gegen den echten Code-Stand auf `main` verifiziert.
> Repo: `https://github.com/don69andrea/prisma-v2.git` — Branch `main`.

---

## Kontext & Zielzustand

Das bestehende Krypto-Modul (`v2.2.0`) ist **vollständig stateless**: jeder API-Call berechnet Signale neu aus Live-Daten, ohne Persistierung, ohne historischen Kontext, ohne Pattern-Erkennung und ohne KI-gestützte Interpretation.

**Ziel:** Zwei Erweiterungspakete implementieren:

| Paket | Bezeichnung | Kern |
|-------|-------------|------|
| **EXT-1** | Historical Signal Tracking | Bestehende `crypto_signals`-Tabelle erweitern + Cron-Snapshot + Trend-UI |
| **EXT-3** | Pattern Intelligence + Agent-Analyse | Chart-Formationen + 2 robuste Candlestick-Muster + LLM Chart-Agent |

**Pattern-Scope (Entscheidung):** Nur die statistisch robusteren Muster — Einzelkerzen-Muster (Doji, Hammer, Hanging Man, Shooting Star etc.) haben in 24/7-Krypto-Märkten eine schwache eigenständige Trefferquote und werden bewusst weggelassen.

- **Chart-Formationen (7):** Golden Cross, Death Cross, RSI Overbought/Oversold, MACD Bullish/Bearish Crossover, Preis über/unter EMA200, Bollinger-Band Squeeze, Volumen-Breakout
- **Candlestick-Muster (2, mehrkerzig mit Bestätigung):** Bullish/Bearish Engulfing, Morning Star/Evening Star

## Korrekturen gegenüber der ursprünglichen Fassung

Diese Punkte wurden gegen den echten Code-Stand (2026-06-16, `main`) verifiziert und mussten korrigiert werden:

1. **Kein API-Key im Klartext.** `ANTHROPIC_API_KEY` ist bereits Teil der Backend-Konfiguration (siehe `backend/config.py` / `.env`). Falls er fehlt: manuell und sicher im eigenen `.env` setzen, niemals in einem Dokument oder Skript hardcoden.
2. **`crypto_signals` existiert bereits** seit Migration `0024_create_crypto_signals.py` (aktueller Alembic-Head: `0024`). Spalten: `id (UUID, pk)`, `ticker`, `signal`, `score`, `price_chf`, `fear_greed_value` (nicht `fear_greed_index`!), `rsi_14`, `volatility_30d_pct`, `created_at`, Index `ix_crypto_signals_ticker_date` auf `(ticker, created_at)`. Migrationspfad ist `backend/alembic/versions/`, nicht `backend/infrastructure/persistence/migrations/versions/`. → Neue Migration ist `0025`, `down_revision="0024"`, **`ALTER TABLE`** (neue Spalten ergänzen), keine neue Tabelle.
3. **`pandas-ta` ist tot.** Commit `53aaa658` hat es am 2026-06-16 bewusst entfernt — es zog `numba`+`llvmlite` (~500MB) mit und verursachte OOM-Crashes auf Render Free Tier. Sämtliche Pattern-/Indikator-Berechnung muss **nativ mit pandas/numpy** erfolgen, im Stil von `backend/infrastructure/adapters/yfinance_crypto.py` (`_rsi`, `_macd`, `_bbands`, `_ema`).
4. **Async-Pattern:** `await asyncio.to_thread(...)`, nicht `loop.run_in_executor(...)` (Projekt-Konvention, siehe CLAUDE.md).
5. **Repositories committen nie selbst** (`self._db.commit()` entfernt) — die Session-Lifecycle-Schicht (Route/Dependency) übernimmt das, wie bei allen bestehenden Repositories in diesem Projekt.
6. **`render.yaml`-Cron-Format:** echtes Format nutzt `runtime: docker`, `dockerfilePath: ./Dockerfile.backend`, `dockerCommand` (nicht `runtime: python` / `buildCommand`/`startCommand`).
7. **Score-Skala-Konflikt gelöst:** Die bestehenden 5 Dimensionen (Momentum 30 / Trend 25 / Sentiment 20 / Markt 15 / Risiko 10 = 100) bleiben **unverändert**. Pattern wird **kein 6. hartes Dimension-Cap**, sondern ein **begrenzter additiver Modifikator** (`-7.5` bis `+7.5`), der auf die Summe der 5 Dimensionen addiert und danach auf `[0, 100]` geclampt wird. Dadurch bleiben STRONG_BUY/BUY/HOLD/SELL-Schwellen (75/60/40/25) unverändert gültig, und die bestehenden Tests für die 5 Kern-Dimensionen brechen nicht. Der bestehende Invarianten-Test (`sum(components) == score`) muss leicht angepasst werden auf `score == clamp(sum(components.values()), 0, 100)`.
8. **LLM-Konventionen:** Freitext-Streaming für die Agent-Analyse ist **kein** Verstoss gegen "kein Freitext ins Frontend" — `backend/interfaces/rest/routers/chat.py` macht das bereits genauso (SSE mit rohen Text-Tokens). Trotzdem: System-Prompt mit `cache_control: ephemeral` cachen (wiederkehrender Prompt, 10 Ticker/Tag im Cron + on-demand), und LLM-Tests über Fixtures in `backend/tests/fixtures/llm/` laufen lassen, nie gegen die Live-API in CI.

---

# EXT-1: Historical Signal Tracking

## Ziel
Jeden Krypto-Score täglich in der (bereits existierenden) DB-Tabelle persistieren. Ermöglicht:
- Trend-Visualisierung (wann wurde BUY → HOLD → SELL?)
- Rückblick der letzten 30/90 Tage pro Asset
- Persönliche Validierung: stimmen die erkannten Patterns mit der späteren Preisentwicklung überein?
- Basis für echte Backtests (später, optional)

## EXT-1.1 — Migration 0025: `crypto_signals` erweitern

`backend/alembic/versions/0025_extend_crypto_signals.py`:

```python
"""extend crypto_signals with pattern + agent columns

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crypto_signals", sa.Column("components", JSONB, nullable=True))
    op.add_column("crypto_signals", sa.Column("price_change_24h", sa.Float(), nullable=True))
    op.add_column("crypto_signals", sa.Column("macd_signal", sa.String(10), nullable=True))
    op.add_column("crypto_signals", sa.Column("detected_patterns", JSONB, nullable=True))
    op.add_column("crypto_signals", sa.Column("pattern_score", sa.Float(), nullable=True))
    op.add_column("crypto_signals", sa.Column("agent_analysis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("crypto_signals", "agent_analysis")
    op.drop_column("crypto_signals", "pattern_score")
    op.drop_column("crypto_signals", "detected_patterns")
    op.drop_column("crypto_signals", "macd_signal")
    op.drop_column("crypto_signals", "price_change_24h")
    op.drop_column("crypto_signals", "components")
```

Bestehende Spalten (`id` UUID, `ticker`, `signal`, `score`, `price_chf`, `fear_greed_value`, `rsi_14`, `volatility_30d_pct`, `created_at`) bleiben unverändert — `created_at` dient weiterhin als Zeitstempel (kein separates `recorded_at`).

```bash
source venv/bin/activate
alembic upgrade head   # → "Running upgrade 0024 -> 0025"
```

## EXT-1.2 — Domain Model

`backend/domain/models/crypto_signal_record.py` — Feldnamen exakt an bestehende Spalten angepasst (inkl. `fear_greed_value`, `id: str | None` für UUID):

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class CryptoSignalRecord:
    """Persistierter Krypto-Signal-Snapshot (täglich, ein Eintrag pro Ticker pro Tag)."""

    ticker: str
    signal: str
    score: float
    components: dict = field(default_factory=dict)
    price_chf: Optional[float] = None
    price_change_24h: Optional[float] = None
    fear_greed_value: Optional[int] = None
    rsi_14: Optional[float] = None
    macd_signal: Optional[str] = None
    volatility_30d_pct: Optional[float] = None
    detected_patterns: List[str] = field(default_factory=list)
    pattern_score: Optional[float] = None
    agent_analysis: Optional[str] = None
    created_at: Optional[datetime] = None
    id: Optional[str] = None
```

## EXT-1.3 — Repository (committed NICHT selbst)

`backend/infrastructure/persistence/repositories/crypto_signal_repository.py` — Upsert per Ticker+Tag, ohne `self._db.commit()` (Session-Lifecycle macht das):

```python
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.domain.models.crypto_signal_record import CryptoSignalRecord


class CryptoSignalRepository:
    def __init__(self, db: Session):
        self._db = db

    def save(self, record: CryptoSignalRecord) -> None:
        """Upsert: ein Snapshot pro Ticker pro Kalendertag (UTC). Committed NICHT selbst."""
        today = datetime.now(timezone.utc).date()
        existing = self._db.execute(
            text(
                "SELECT id FROM crypto_signals "
                "WHERE ticker = :ticker AND DATE(created_at AT TIME ZONE 'UTC') = :today "
                "LIMIT 1"
            ),
            {"ticker": record.ticker, "today": today},
        ).fetchone()

        params = self._to_params(record)
        if existing:
            params["id"] = existing.id
            self._db.execute(
                text(
                    "UPDATE crypto_signals SET "
                    "signal = :signal, score = :score, components = :components::jsonb, "
                    "price_chf = :price_chf, price_change_24h = :price_change_24h, "
                    "fear_greed_value = :fg, rsi_14 = :rsi, macd_signal = :macd, "
                    "volatility_30d_pct = :vol, detected_patterns = :patterns::jsonb, "
                    "pattern_score = :pattern_score, agent_analysis = :agent_analysis "
                    "WHERE id = :id"
                ),
                params,
            )
        else:
            self._db.execute(
                text(
                    "INSERT INTO crypto_signals "
                    "(ticker, signal, score, components, price_chf, price_change_24h, "
                    "fear_greed_value, rsi_14, macd_signal, volatility_30d_pct, "
                    "detected_patterns, pattern_score, agent_analysis) VALUES "
                    "(:ticker, :signal, :score, :components::jsonb, :price_chf, :price_change_24h, "
                    ":fg, :rsi, :macd, :vol, :patterns::jsonb, :pattern_score, :agent_analysis)"
                ),
                params,
            )

    def get_history(self, ticker: str, days: int = 30) -> List[CryptoSignalRecord]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._db.execute(
            text(
                "SELECT * FROM crypto_signals "
                "WHERE ticker = :ticker AND created_at >= :since "
                "ORDER BY created_at ASC"
            ),
            {"ticker": ticker, "since": since},
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_latest_all(self) -> List[CryptoSignalRecord]:
        rows = self._db.execute(
            text(
                "SELECT DISTINCT ON (ticker) * FROM crypto_signals "
                "ORDER BY ticker, created_at DESC"
            )
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def _to_params(self, r: CryptoSignalRecord) -> dict:
        return {
            "ticker": r.ticker,
            "signal": r.signal,
            "score": r.score,
            "components": json.dumps(r.components),
            "price_chf": r.price_chf,
            "price_change_24h": r.price_change_24h,
            "fg": r.fear_greed_value,
            "rsi": r.rsi_14,
            "macd": r.macd_signal,
            "vol": r.volatility_30d_pct,
            "patterns": json.dumps(r.detected_patterns),
            "pattern_score": r.pattern_score,
            "agent_analysis": r.agent_analysis,
        }

    def _row_to_record(self, row) -> CryptoSignalRecord:
        return CryptoSignalRecord(
            id=str(row.id),
            ticker=row.ticker,
            signal=row.signal,
            score=row.score,
            components=row.components or {},
            price_chf=row.price_chf,
            price_change_24h=row.price_change_24h,
            fear_greed_value=row.fear_greed_value,
            rsi_14=row.rsi_14,
            macd_signal=row.macd_signal,
            volatility_30d_pct=row.volatility_30d_pct,
            detected_patterns=row.detected_patterns or [],
            pattern_score=row.pattern_score,
            agent_analysis=row.agent_analysis,
            created_at=row.created_at,
        )
```

## EXT-1.4 — History-Endpoints

Ergänzen in `backend/interfaces/rest/routers/crypto.py` (Session-Commit erfolgt über die bestehende `get_db`-Dependency, nicht im Repo):

```python
from backend.infrastructure.persistence.repositories.crypto_signal_repository import CryptoSignalRepository

@router.get("/history/{ticker}", summary="Signal-History (letzte N Tage)")
async def get_signal_history(
    ticker: str,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    repo = CryptoSignalRepository(db)
    records = repo.get_history(ticker.upper(), days=days)
    return [
        {
            "date": r.created_at.date().isoformat() if r.created_at else None,
            "signal": r.signal,
            "score": round(r.score, 1),
            "price_chf": r.price_chf,
            "fear_greed_value": r.fear_greed_value,
            "rsi_14": round(r.rsi_14, 1) if r.rsi_14 else None,
            "detected_patterns": r.detected_patterns,
            "pattern_score": r.pattern_score,
        }
        for r in records
    ]


@router.get("/history", summary="Letzter Signal-Stand aller Ticker")
async def get_latest_signals_overview(db: Session = Depends(get_db)):
    repo = CryptoSignalRepository(db)
    records = repo.get_latest_all()
    return [
        {
            "ticker": r.ticker,
            "signal": r.signal,
            "score": round(r.score, 1),
            "price_chf": r.price_chf,
            "price_change_24h": r.price_change_24h,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "detected_patterns": r.detected_patterns,
            "agent_analysis": r.agent_analysis,
        }
        for r in records
    ]
```

## EXT-1.5 — Daily Cron: `prisma-crypto-daily`

`backend/scripts/crypto_daily_snapshot.py` — ruft Scoring + Pattern-Erkennung + Agent-Kurzanalyse auf und persistiert (committet einmal am Ende über die Session, nicht im Repo):

```python
#!/usr/bin/env python3
"""Krypto Daily Snapshot. Läuft täglich via Render Cron, persistiert alle 10 Signale."""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crypto_daily_snapshot")


async def main() -> None:
    from backend.application.services.crypto_scoring_service import CryptoScoringService
    from backend.application.services.crypto_pattern_service import CryptoPatternService
    from backend.application.services.crypto_agent_service import CryptoAgentService
    from backend.infrastructure.persistence.repositories.crypto_signal_repository import (
        CryptoSignalRepository,
    )
    from backend.infrastructure.persistence.database import get_db_session
    from backend.domain.models.crypto_signal_record import CryptoSignalRecord

    log.info("=== Krypto Daily Snapshot gestartet ===")

    scoring_svc = CryptoScoringService()
    pattern_svc = CryptoPatternService()
    agent_svc = CryptoAgentService()

    try:
        results = await scoring_svc.score_all()
    except Exception as exc:
        log.error(f"score_all() fehlgeschlagen: {exc}")
        sys.exit(1)

    db = next(get_db_session())
    repo = CryptoSignalRepository(db)

    saved = 0
    for result in results:
        try:
            ticker = result.ticker
            patterns, pattern_score = await pattern_svc.detect(ticker)
            agent_text = await agent_svc.analyze_brief(ticker, result, patterns)

            record = CryptoSignalRecord(
                ticker=ticker,
                signal=result.signal,
                score=result.score,
                components=result.components or {},
                price_chf=getattr(result, "price_chf", None),
                price_change_24h=getattr(result, "price_change_24h", None),
                fear_greed_value=getattr(result, "fear_greed_value", None),
                rsi_14=getattr(result, "rsi_14", None),
                macd_signal=getattr(result, "macd_signal", None),
                volatility_30d_pct=getattr(result, "volatility_30d_pct", None),
                detected_patterns=patterns,
                pattern_score=pattern_score,
                agent_analysis=agent_text,
            )
            repo.save(record)
            saved += 1
            log.info(f"  OK {ticker}: {result.signal} ({result.score:.1f})")
        except Exception as exc:
            log.error(f"  FEHLER {ticker}: {exc}")

    db.commit()
    log.info(f"=== Snapshot fertig: {saved}/{len(results)} gespeichert ===")


if __name__ == "__main__":
    asyncio.run(main())
```

`render.yaml` — neuer Cron-Job im selben Format wie `prisma-news-ingestion` (Docker-basiert, nicht `runtime: python`):

```yaml
  - type: cron
    name: prisma-crypto-daily
    runtime: docker
    dockerfilePath: ./Dockerfile.backend
    branch: main
    plan: free
    schedule: "30 6 * * *"
    dockerCommand: python -m backend.scripts.crypto_daily_snapshot
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: prisma-db
          property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false
```

(Exakte `envVars`-Liste an die bestehende `prisma-news-ingestion`-Definition in `render.yaml` anpassen — dort nachschauen, welche Keys tatsächlich gebraucht werden, z.B. auch `COINGECKO_API_KEY` falls gesetzt.)

## EXT-1.6 — Frontend: Trend-Sparkline

`frontend/hooks/useCryptoHistory.ts`:

```typescript
import { useEffect, useState } from 'react';

export interface CryptoHistoryPoint {
  date: string;
  signal: string;
  score: number;
  price_chf: number | null;
  rsi_14: number | null;
  detected_patterns: string[];
}

export function useCryptoHistory(ticker: string, days = 14) {
  const [data, setData] = useState<CryptoHistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    fetch(`/api/v1/crypto/history/${ticker}?days=${days}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [ticker, days]);

  return { data, loading };
}
```

`frontend/components/crypto/SignalSparkline.tsx` — kleine SVG-Sparkline (Score-Verlauf, letzter Punkt farbig nach Signal), wird als neue Spalte in `CryptoProRow` (Pro-Tabelle) bzw. im Score-Breakdown-Accordion eingebunden. Implementierungsdetail bleibt wie ursprünglich skizziert (reine Darstellungslogik, keine technischen Korrekturen nötig).

---

# EXT-3: Pattern Intelligence + Agent Chart-Analyse

## Ziel
Das bestehende 5-Dimensionen-Scoring um echte Pattern-Erkennung erweitern, **ohne `pandas-ta`**:
- 7 Chart-Formationen + 2 mehrkerzige Candlestick-Muster (siehe Scope-Entscheidung oben)
- Pattern-Modifikator (`-7.5`..`+7.5`) additiv auf den bestehenden 0–100-Score, geclampt
- `CryptoChartAgent`: Claude Haiku analysiert Signal + erkannte Patterns → 2 Sätze DE
- Streaming-Endpoint `POST /api/v1/crypto/analyze/{ticker}` mit SSE (Vorbild: `chat.py`)

## EXT-3.1 — Native Pattern Detection (kein pandas-ta)

Zuerst: gemeinsame Indikator-Helper aus `yfinance_crypto.py` wiederverwendbar machen (die Funktionen `_rsi`, `_macd`, `_bbands`, `_ema` existieren dort bereits — sie liefern volle Serien zurück, nicht nur den letzten Wert; für Crossover-Erkennung brauchen wir die letzten 2 Werte, die bereits vorhanden sind).

`backend/application/services/crypto_pattern_service.py`:

```python
"""
CryptoPatternService: Erkennt Chart-Formationen + 2 Candlestick-Muster
nativ mit pandas/numpy (kein pandas-ta — wurde wegen OOM auf Render entfernt).
Gibt (liste_erkannter_pattern_namen, pattern_modifier[-7.5..+7.5]) zurück.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

import pandas as pd

from backend.infrastructure.adapters.yfinance_crypto import (
    YFinanceCryptoAdapter,
    _ema,
    _macd,
    _rsi,
    _bbands,
)

log = logging.getLogger(__name__)

# Gewichtung pro erkanntem Pattern (bullish positiv, bearish negativ)
PATTERN_WEIGHTS = {
    "GOLDEN_CROSS": 2.5,
    "DEATH_CROSS": -2.5,
    "RSI_OVERSOLD": 1.5,
    "RSI_OVERBOUGHT": -1.5,
    "MACD_BULLISH": 1.5,
    "MACD_BEARISH": -1.5,
    "PRICE_ABOVE_EMA200": 1.0,
    "PRICE_BELOW_EMA200": -1.0,
    "BB_SQUEEZE": 0.5,            # neutral — Volatilität erwartet, keine Richtung
    "VOL_BREAKOUT": 1.5,
    "BULLISH_ENGULFING": 2.0,
    "BEARISH_ENGULFING": -2.0,
    "MORNING_STAR": 2.5,
    "EVENING_STAR": -2.5,
}


class CryptoPatternService:
    def __init__(self):
        self._adapter = YFinanceCryptoAdapter()

    async def detect(self, ticker: str) -> Tuple[List[str], float]:
        df = await self._adapter.get_ohlcv(ticker, period="3mo", interval="1d")
        if df is None or len(df) < 10:
            return [], 0.0

        detected: List[str] = []
        raw = 0.0

        chart_patterns, chart_raw = self._detect_chart_patterns(df)
        detected.extend(chart_patterns)
        raw += chart_raw

        candle_patterns, candle_raw = self._detect_candlestick_patterns(df)
        detected.extend(candle_patterns)
        raw += candle_raw

        modifier = max(-7.5, min(7.5, raw))
        return detected[:10], round(modifier, 1)

    def _detect_chart_patterns(self, df: pd.DataFrame) -> Tuple[List[str], float]:
        patterns: List[str] = []
        score = 0.0
        close, volume = df["Close"], df["Volume"]

        ema20, ema50, ema200 = _ema(close, 20), _ema(close, 50), _ema(close, 200)
        rsi = _rsi(close, 14)
        macd_line, signal_line, _hist = _macd(close)
        _mid, upper, lower = _bbands(close)

        last_close = close.iloc[-1]

        if len(ema20) > 1 and len(ema50) > 1:
            if ema20.iloc[-1] > ema50.iloc[-1] and ema20.iloc[-2] <= ema50.iloc[-2]:
                patterns.append("GOLDEN_CROSS")
                score += PATTERN_WEIGHTS["GOLDEN_CROSS"]
            elif ema20.iloc[-1] < ema50.iloc[-1] and ema20.iloc[-2] >= ema50.iloc[-2]:
                patterns.append("DEATH_CROSS")
                score += PATTERN_WEIGHTS["DEATH_CROSS"]

        if not rsi.empty:
            if rsi.iloc[-1] < 30:
                patterns.append("RSI_OVERSOLD")
                score += PATTERN_WEIGHTS["RSI_OVERSOLD"]
            elif rsi.iloc[-1] > 70:
                patterns.append("RSI_OVERBOUGHT")
                score += PATTERN_WEIGHTS["RSI_OVERBOUGHT"]

        if len(macd_line) > 1 and len(signal_line) > 1:
            if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
                patterns.append("MACD_BULLISH")
                score += PATTERN_WEIGHTS["MACD_BULLISH"]
            elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
                patterns.append("MACD_BEARISH")
                score += PATTERN_WEIGHTS["MACD_BEARISH"]

        if not ema200.empty and not pd.isna(ema200.iloc[-1]):
            if last_close > ema200.iloc[-1]:
                patterns.append("PRICE_ABOVE_EMA200")
                score += PATTERN_WEIGHTS["PRICE_ABOVE_EMA200"]
            else:
                patterns.append("PRICE_BELOW_EMA200")
                score += PATTERN_WEIGHTS["PRICE_BELOW_EMA200"]

        if not upper.empty and not lower.empty:
            bb_width = (upper.iloc[-1] - lower.iloc[-1]) / last_close
            if bb_width < 0.05:
                patterns.append("BB_SQUEEZE")
                score += PATTERN_WEIGHTS["BB_SQUEEZE"]

        if len(volume) >= 21:
            avg_vol = volume.iloc[-21:-1].mean()
            if volume.iloc[-1] > 1.5 * avg_vol:
                patterns.append("VOL_BREAKOUT")
                score += PATTERN_WEIGHTS["VOL_BREAKOUT"]

        return patterns, score

    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> Tuple[List[str], float]:
        """Nur Engulfing + Morning/Evening Star — bewusst beschränkt auf mehrkerzige,
        bestätigte Muster (siehe Scope-Entscheidung im Plan)."""
        patterns: List[str] = []
        score = 0.0
        o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
        if len(df) < 3:
            return patterns, score

        o1, c1 = o.iloc[-2], c.iloc[-2]
        o2, c2 = o.iloc[-1], c.iloc[-1]

        # Bullish Engulfing: vorherige Kerze bearish, aktuelle bullish und umschliesst sie voll
        if c1 < o1 and c2 > o2 and c2 >= o1 and o2 <= c1:
            patterns.append("BULLISH_ENGULFING")
            score += PATTERN_WEIGHTS["BULLISH_ENGULFING"]
        # Bearish Engulfing: umgekehrt
        elif c1 > o1 and c2 < o2 and o2 >= c1 and c2 <= o1:
            patterns.append("BEARISH_ENGULFING")
            score += PATTERN_WEIGHTS["BEARISH_ENGULFING"]

        # Morning/Evening Star: 3-Kerzen-Muster (Trend, kleine Mittelkerze, Gegenbewegung)
        o0, c0 = o.iloc[-3], c.iloc[-3]
        body0 = abs(c0 - o0)
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)
        if body0 > 0 and body1 < body0 * 0.3:
            if c0 < o0 and c2 > o2 and body2 > body0 * 0.5:
                patterns.append("MORNING_STAR")
                score += PATTERN_WEIGHTS["MORNING_STAR"]
            elif c0 > o0 and c2 < o2 and body2 > body0 * 0.5:
                patterns.append("EVENING_STAR")
                score += PATTERN_WEIGHTS["EVENING_STAR"]

        return patterns, score
```

## EXT-3.2 — Pattern-Modifikator in `CryptoScorer` integrieren

`backend/domain/services/crypto_scorer.py` — Pattern ist **kein 6. Cap**, sondern additiver Modifikator nach der bestehenden Summe:

```python
def score(
    self,
    asset: str,
    technicals: dict,
    fear_greed: int,
    correlation_smi_1y: float = 0.0,
    pattern_modifier: float | None = None,  # NEU: -7.5..+7.5, optional
) -> CryptoScore:
    components = {
        "momentum": self._momentum_score(...),   # unverändert, max 30
        "trend": self._trend_score(...),          # unverändert, max 25
        "sentiment": self._sentiment_score(...),  # unverändert, max 20
        "markt": self._market_score(...),         # unverändert, max 15
        "risiko": self._risk_score(...),           # unverändert, max 10
    }
    if pattern_modifier is not None:
        components["pattern"] = round(pattern_modifier, 1)

    raw_total = sum(components.values())
    total = max(0.0, min(100.0, raw_total))  # clamp — Schwellen 75/60/40/25 bleiben gültig
    ...
```

`backend/tests/unit/test_crypto_scorer.py` — bestehender Invarianten-Test anpassen:
```python
# Vorher: assert abs(sum(components.values()) - score) < 1.0
# Nachher (Clamp berücksichtigen):
expected = max(0.0, min(100.0, sum(components.values())))
assert abs(expected - score) < 1.0
```

`CryptoScoringService` — Pattern-Detection vor dem Score-Aufruf ausführen:

```python
from backend.application.services.crypto_pattern_service import CryptoPatternService

class CryptoScoringService:
    def __init__(self):
        ...
        self._pattern_svc = CryptoPatternService()

    async def score_one(self, ticker: str) -> CryptoScore:
        ...
        patterns, modifier = await self._pattern_svc.detect(ticker)
        score = self._scorer.score(..., pattern_modifier=modifier)
        score.detected_patterns = patterns
        return score
```

## EXT-3.3 — `CryptoAgentService` (LLM-Analyse, mit Prompt-Caching)

`backend/application/services/crypto_agent_service.py`:

```python
"""
CryptoAgentService: Claude Haiku analysiert Krypto-Signale + erkannte Patterns.
Gibt eine 2-Sätze deutsche Kurzanalyse zurück. System-Prompt ist gecached
(cache_control: ephemeral), da er pro Cron-Lauf 10x und zusätzlich on-demand
wiederverwendet wird.
"""
from __future__ import annotations

import logging
import os
from typing import List, AsyncIterator

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist ein präziser Krypto-Analyst bei einer Schweizer Finanzplattform (PRISMA).
Deine Aufgabe: Schreibe eine kurze, faktenbasierte Einschätzung auf Deutsch (max. 2 Sätze).
- Beziehe dich auf konkrete Zahlen (Score, RSI, erkannte Patterns)
- Kein Hype, keine Empfehlungen ("kaufen"/"verkaufen")
- Sachlich, klar, unter 60 Wörtern
- Schreibe im Präsens"""


def _build_prompt(ticker: str, signal_data: dict, patterns: List[str]) -> str:
    pattern_str = ", ".join(patterns[:5]) if patterns else "Keine"
    return (
        f"Analysiere {ticker}:\n"
        f"- Signal: {signal_data.get('signal', '?')} (Score: {signal_data.get('score', 0):.1f}/100)\n"
        f"- RSI: {signal_data.get('rsi_14', '?')}\n"
        f"- MACD: {signal_data.get('macd_signal', '?')}\n"
        f"- Fear & Greed Index: {signal_data.get('fear_greed_value', '?')}\n"
        f"- Erkannte Patterns: {pattern_str}\n"
        f"Schreibe 2 Sätze auf Deutsch."
    )


class CryptoAgentService:
    def __init__(self):
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def analyze_brief(self, ticker: str, signal_data, patterns: List[str]) -> str:
        if not self._api_key:
            return ""
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            data = {
                "signal": signal_data.signal,
                "score": signal_data.score,
                "rsi_14": getattr(signal_data, "rsi_14", None),
                "macd_signal": getattr(signal_data, "macd_signal", None),
                "fear_greed_value": getattr(signal_data, "fear_greed_value", None),
            }
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=120,
                system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": _build_prompt(ticker, data, patterns)}],
            )
            return msg.content[0].text.strip()
        except Exception as exc:
            log.warning(f"CryptoChartAgent analyze_brief fehlgeschlagen ({ticker}): {exc}")
            return ""

    async def stream_analysis(self, ticker: str, signal_data: dict, patterns: List[str]) -> AsyncIterator[str]:
        if not self._api_key:
            yield "Agent nicht verfügbar (API Key fehlt)."
            return
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self._api_key)
            prompt = _build_prompt(ticker, signal_data, patterns)
            with client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as exc:
            log.error(f"CryptoChartAgent stream fehlgeschlagen ({ticker}): {exc}")
            yield f"Analyse nicht verfügbar ({exc})."
```

**Tests:** nutze `backend/tests/fixtures/llm/` für den Happy-Path (gemockte Anthropic-Response), nicht nur den "kein API-Key"-Pfad — Konvention laut CLAUDE.md ("nie gegen Live-API in CI").

## EXT-3.4 — Streaming-Endpoint `POST /api/v1/crypto/analyze/{ticker}`

Identisch zur ursprünglichen Fassung (SSE, Vorbild `chat.py`), keine technischen Korrekturen nötig — Ergänzung in `backend/interfaces/rest/routers/crypto.py`.

## EXT-3.5 — Frontend: Agent-Analyse Komponente

Identisch zur ursprünglichen Fassung (`useCryptoAgentAnalysis`-Hook + `CryptoAgentPanel`-Komponente), Integration ins Score-Breakdown-Accordion in `crypto-client.tsx` (Pro-Mode) — keine technischen Korrekturen nötig.

## EXT-3.6 — Schema-Erweiterung

`backend/interfaces/rest/schemas/crypto.py` — `CryptoSignalResponse` um `detected_patterns: list[str]`, `pattern_score: float | None`, `agent_analysis: str | None` ergänzen (`from_domain()` entsprechend erweitern).

## EXT-3.7 — `YFinanceCryptoAdapter.get_ohlcv()` ergänzen

Existiert noch nicht. **Mit `asyncio.to_thread`, nicht `run_in_executor`** (Projekt-Konvention):

```python
async def get_ohlcv(self, ticker: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame | None:
    """Rohe OHLCV-Daten für Pattern-Analyse (uncached)."""
    try:
        df = await asyncio.to_thread(
            yf.download, ticker, period=period, interval=interval, progress=False, auto_adjust=True,
        )
        if df is None or df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df
    except Exception as exc:
        log.warning(f"get_ohlcv {ticker}: {exc}")
        return None
```

---

# Deployment & Tests

```bash
source venv/bin/activate
alembic upgrade head
uvicorn backend.interfaces.rest.app:app --reload --port 8000

curl -s "http://localhost:8000/api/v1/crypto/history/BTC-CHF?days=7" -H "X-API-Key: $(grep ^API_KEY .env | cut -d= -f2)" | python3 -m json.tool
python3 -c "
import asyncio
from backend.application.services.crypto_pattern_service import CryptoPatternService
svc = CryptoPatternService()
patterns, modifier = asyncio.run(svc.detect('BTC-CHF'))
print('Patterns:', patterns, '| Modifier:', modifier)
"
python3 backend/scripts/crypto_daily_snapshot.py
```

```bash
cd frontend && npm run dev
npx playwright test --grep "crypto"
```

## Checkliste

| # | Aufgabe | Erwartetes Resultat |
|---|---------|---------------------|
| 1 | Migration 0025 (ALTER, nicht CREATE) | `alembic upgrade head` → kein Fehler |
| 2 | `CryptoSignalRecord` Domain Model | Feldnamen matchen bestehende Spalten |
| 3 | `CryptoSignalRepository` (kein internes commit) | save/get_history funktionieren |
| 4 | `/api/v1/crypto/history/{ticker}` + `/history` | GET → JSON |
| 5 | `render.yaml` Cron (Docker-Format) | `prisma-crypto-daily` Entry vorhanden |
| 6 | `crypto_daily_snapshot.py` | Läuft lokal durch, `db.commit()` einmal am Ende |
| 7 | Frontend `SignalSparkline` + `useCryptoHistory` | Rendert in Pro-Tabelle |
| 8 | `CryptoPatternService.detect()` (kein pandas-ta) | 7 Chart- + 2 Candlestick-Muster, Modifier -7.5..7.5 |
| 9 | Pattern-Modifikator in `CryptoScorer` | Score bleibt 0-100, Schwellen unverändert |
| 10 | Bestehender Invarianten-Test angepasst | `clamp(sum(components),0,100) == score` |
| 11 | `CryptoAgentService` (mit Prompt-Caching) | DE-Text, Fixture-Tests grün |
| 12 | `/api/v1/crypto/analyze/{ticker}` SSE | POST → Stream kommt an |
| 13 | `CryptoAgentPanel` + `useCryptoAgentAnalysis` | Stream rendert im Frontend |
| 14 | `get_ohlcv()` mit `asyncio.to_thread` | Gibt DataFrame zurück |
| 15 | Schema `CryptoSignalResponse` erweitert | Neue Felder vorhanden |
| 16 | Unit + Integration Tests | pattern_service, scorer, agent_service (fixtures), repository, endpoints |
| 17 | E2E (Playwright) | Crypto-Spec erweitert um History/Sparkline/Agent-Panel |

## Commit-/PR-Strategie (kleinere PRs, laut CLAUDE.md-Workflow)

1. `feat(crypto): native pattern detection (chart formations + engulfing/star) + scorer modifier`
2. `feat(crypto): CryptoChartAgent streaming analysis (haiku, SSE, prompt caching)`
3. `feat(crypto): historical signal persistence (migration 0025, repository, history endpoints, cron)`
4. `feat(frontend): crypto sparkline trend + agent panel (pro mode)`
5. `test(crypto): unit/integration tests for pattern service, scorer, agent service, repository`
