# PDF Institutional Report Generator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One-click PDF export from the Factsheet — aggregates all PRISMA data (Quant, ML+SHAP, Narrative, Swiss) into a professional dark-themed institutional report.

**Architecture:** New `ReportService` aggregates data via existing services in parallel, renders via Jinja2 HTML template → WeasyPrint → PDF bytes. Redis caches rendered PDFs for 6h. New `GET /api/v1/stocks/{ticker}/report.pdf` endpoint. Frontend Factsheet gets an Export button with animated progress steps.

**Tech Stack:** `weasyprint>=62.0` (new dep), Jinja2 (already in deps), existing application services, Next.js.

**Note:** Requires SHAP feature (plan: `2026-06-10-shap-explainability.md`) to be complete for the SHAP Top-5 block.

---

## File Map

| Action | Path |
|--------|------|
| Modify | `pyproject.toml` — add `weasyprint>=62.0` |
| Create | `backend/application/services/report_service.py` |
| Create | `backend/infrastructure/templates/report.html.j2` |
| Create | `backend/interfaces/rest/routers/reports.py` |
| Modify | `backend/interfaces/rest/app.py` — register reports router |
| Create | `backend/tests/unit/application/test_report_service.py` |
| Create | `frontend/components/factsheet/ExportReportButton.tsx` |
| Modify | `frontend/components/factsheet/StockHeader.tsx` — add export button |

---

## Task 1: Add `weasyprint` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add weasyprint to pyproject.toml**

In `pyproject.toml`, in the `dependencies` list, add after `"httpx>=0.27",`:
```toml
    "weasyprint>=62.0",
```

- [ ] **Step 2: Install**

```bash
uv sync
```
Expected: resolves without conflict.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add weasyprint>=62.0 for PDF report generation"
```

---

## Task 2: Jinja2 Report Template

**Files:**
- Create: `backend/infrastructure/templates/report.html.j2`

- [ ] **Step 1: Create template directory if not exists**

```bash
mkdir -p backend/infrastructure/templates
```

- [ ] **Step 2: Create `report.html.j2`**

Create `backend/infrastructure/templates/report.html.j2`:
```html
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4;
    margin: 15mm 18mm 15mm 18mm;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    background: #0a0a14;
    color: #e2e8f0;
    font-size: 10pt;
    line-height: 1.5;
  }

  /* ── Header ── */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 6mm;
    padding-bottom: 4mm;
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg, #7c3aed, #3b82f6, #06b6d4) 1;
  }

  .header-left .brand {
    font-size: 7pt;
    color: #7c3aed;
    letter-spacing: 3px;
    text-transform: uppercase;
    font-weight: 700;
  }

  .header-left .company {
    font-size: 18pt;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
  }

  .header-left .ticker-exchange {
    font-size: 10pt;
    color: #94a3b8;
    font-family: monospace;
  }

  .header-right {
    text-align: right;
    color: #64748b;
    font-size: 8pt;
  }

  /* ── Signal Banner ── */
  .signal-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4mm 6mm;
    border-radius: 3mm;
    margin-bottom: 5mm;
  }

  .signal-banner.OUTPERFORM   { background: #052e16; border: 1px solid #16a34a; }
  .signal-banner.NEUTRAL      { background: #1c1408; border: 1px solid #d97706; }
  .signal-banner.UNDERPERFORM { background: #1a0a0a; border: 1px solid #dc2626; }

  .signal-label {
    font-size: 16pt;
    font-weight: 800;
    letter-spacing: 1px;
  }

  .signal-banner.OUTPERFORM   .signal-label { color: #4ade80; }
  .signal-banner.NEUTRAL      .signal-label { color: #fbbf24; }
  .signal-banner.UNDERPERFORM .signal-label { color: #f87171; }

  .signal-meta {
    text-align: right;
    color: #94a3b8;
    font-size: 9pt;
  }

  .conf-bar-container {
    width: 60mm;
    height: 4px;
    background: #1e293b;
    border-radius: 2px;
    overflow: hidden;
    margin-top: 2mm;
  }

  .conf-bar {
    height: 100%;
    border-radius: 2px;
  }

  .signal-banner.OUTPERFORM   .conf-bar { background: #4ade80; }
  .signal-banner.NEUTRAL      .conf-bar { background: #fbbf24; }
  .signal-banner.UNDERPERFORM .conf-bar { background: #f87171; }

  /* ── Two-column layout ── */
  .two-col {
    display: flex;
    gap: 5mm;
    margin-bottom: 5mm;
  }

  .col-left  { flex: 1; }
  .col-right { flex: 1; }

  /* ── Cards ── */
  .card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 3mm;
    padding: 4mm;
    margin-bottom: 4mm;
  }

  .card-title {
    font-size: 7pt;
    color: #7c3aed;
    letter-spacing: 2px;
    text-transform: uppercase;
    font-weight: 700;
    margin-bottom: 3mm;
  }

  /* ── Radar SVG ── */
  .radar-container {
    text-align: center;
    margin: 2mm 0;
  }

  /* ── Fundamentals table ── */
  .fund-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3mm;
  }

  .fund-item {
    background: #0f172a;
    border-radius: 2mm;
    padding: 2.5mm 3mm;
  }

  .fund-label { font-size: 7pt; color: #64748b; }
  .fund-value { font-size: 11pt; font-weight: 700; color: #e2e8f0; }

  /* ── SHAP bars ── */
  .shap-row {
    display: flex;
    align-items: center;
    gap: 2mm;
    margin-bottom: 1.5mm;
  }

  .shap-label { width: 35mm; font-size: 8pt; color: #94a3b8; text-align: right; }

  .shap-bar-pos {
    height: 5px;
    border-radius: 0 2px 2px 0;
    background: linear-gradient(90deg, #16a34a, #4ade80);
  }

  .shap-bar-neg {
    height: 5px;
    border-radius: 2px 0 0 2px;
    background: linear-gradient(270deg, #dc2626, #f87171);
  }

  .shap-value {
    font-size: 8pt;
    font-family: monospace;
    width: 15mm;
    text-align: left;
    color: #64748b;
  }

  /* ── 3a Badge ── */
  .badge-3a {
    display: inline-block;
    padding: 1mm 3mm;
    border-radius: 2mm;
    font-size: 8pt;
    font-weight: 700;
  }

  .badge-3a.eligible   { background: #052e16; color: #4ade80; border: 1px solid #16a34a; }
  .badge-3a.ineligible { background: #1a0a0a; color: #f87171; border: 1px solid #dc2626; }

  /* ── Narrative ── */
  .narrative {
    font-style: italic;
    color: #cbd5e1;
    font-size: 9pt;
    line-height: 1.6;
    border-left: 2px solid #7c3aed;
    padding-left: 3mm;
  }

  /* ── Footer ── */
  .footer {
    border-top: 1px solid #1e293b;
    padding-top: 3mm;
    font-size: 7pt;
    color: #334155;
    text-align: center;
  }
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <div class="brand">PRISMA V2</div>
    <div class="company">{{ company_name }}</div>
    <div class="ticker-exchange">{{ ticker }} · {{ exchange }}</div>
  </div>
  <div class="header-right">
    <div>Investment Report</div>
    <div>{{ generated_at }}</div>
    <div style="margin-top:1mm; color: #475569">Quantitative Analysis</div>
  </div>
</div>

<!-- SIGNAL BANNER -->
<div class="signal-banner {{ ml_signal }}">
  <div>
    <div style="font-size:8pt; color:#94a3b8; margin-bottom:1mm;">ML-PREDICTION</div>
    <div class="signal-label">{{ ml_signal }}</div>
  </div>
  <div class="signal-meta">
    <div>Konfidenz</div>
    <div style="font-size:12pt; font-weight:700;">{{ (ml_confidence * 100) | round(0) | int }}%</div>
    <div class="conf-bar-container">
      <div class="conf-bar" style="width: {{ (ml_confidence * 100) | round(0) | int }}%"></div>
    </div>
  </div>
</div>

<!-- TWO COLUMNS -->
<div class="two-col">
  <!-- LEFT -->
  <div class="col-left">

    <!-- QUANT RADAR -->
    <div class="card">
      <div class="card-title">Quant Scores</div>
      <div class="radar-container">
        {% set scores = quant_scores %}
        {% set n = scores | length %}
        {% set cx = 70 %}
        {% set cy = 70 %}
        {% set r = 55 %}
        <svg width="140" height="140" viewBox="0 0 140 140">
          <!-- Grid circles -->
          {% for level in [0.25, 0.5, 0.75, 1.0] %}
          <circle cx="{{ cx }}" cy="{{ cy }}" r="{{ r * level }}" fill="none" stroke="#1e293b" stroke-width="0.5"/>
          {% endfor %}
          <!-- Axes -->
          {% for i, (name, score) in enumerate(scores.items()) %}
          {% set angle = (i / n) * 2 * 3.14159 - 3.14159 / 2 %}
          {% set ax = cx + r * [angle | cos] | first %}
          {% set ay = cy + r * [angle | sin] | first %}
          <line x1="{{ cx }}" y1="{{ cy }}" x2="{{ ax | round(1) }}" y2="{{ ay | round(1) }}" stroke="#1e293b" stroke-width="0.5"/>
          {% endfor %}
          <!-- Data polygon -->
          <polygon
            points="{% for i, (name, score) in enumerate(scores.items()) %}{% set angle = (i / n) * 2 * 3.14159 - 3.14159 / 2 %}{% set pct = [score / 100, 0] | max %}{{ (cx + r * pct * (angle | cos)) | round(1) }},{{ (cy + r * pct * (angle | sin)) | round(1) }} {% endfor %}"
            fill="rgba(124,58,237,0.25)"
            stroke="#7c3aed"
            stroke-width="1.5"
          />
          <!-- Labels -->
          {% for i, (name, score) in enumerate(scores.items()) %}
          {% set angle = (i / n) * 2 * 3.14159 - 3.14159 / 2 %}
          {% set lx = cx + (r + 10) * (angle | cos) %}
          {% set ly = cy + (r + 10) * (angle | sin) %}
          <text x="{{ lx | round(1) }}" y="{{ ly | round(1) }}" text-anchor="middle" dominant-baseline="middle" font-size="5.5" fill="#94a3b8">{{ name[:8] }}</text>
          {% endfor %}
        </svg>
      </div>
      <!-- Score list -->
      {% for name, score in quant_scores.items() %}
      <div style="display:flex; justify-content:space-between; font-size:8pt; margin-bottom:1.5mm;">
        <span style="color:#94a3b8;">{{ name }}</span>
        <span style="font-weight:700; color:{% if score >= 70 %}#4ade80{% elif score >= 40 %}#fbbf24{% else %}#f87171{% endif %};">{{ score | round(1) }}</span>
      </div>
      {% endfor %}
    </div>

    <!-- 3a ELIGIBILITY -->
    <div class="card">
      <div class="card-title">3a Eignung (FINMA)</div>
      <span class="badge-3a {% if eligible_3a %}eligible{% else %}ineligible{% endif %}">
        {% if eligible_3a %}✓ 3a-geeignet{% else %}✗ Nicht 3a-geeignet{% endif %}
      </span>
    </div>

  </div>

  <!-- RIGHT -->
  <div class="col-right">

    <!-- FUNDAMENTALS -->
    <div class="card">
      <div class="card-title">Fundamentaldaten</div>
      <div class="fund-grid">
        <div class="fund-item">
          <div class="fund-label">KGV (P/E)</div>
          <div class="fund-value">{% if pe_ratio %}{{ pe_ratio | round(1) }}x{% else %}—{% endif %}</div>
        </div>
        <div class="fund-item">
          <div class="fund-label">KBV (P/B)</div>
          <div class="fund-value">{% if pb_ratio %}{{ pb_ratio | round(1) }}x{% else %}—{% endif %}</div>
        </div>
        <div class="fund-item">
          <div class="fund-label">Dividendenrendite</div>
          <div class="fund-value">{% if dividend_yield %}{{ (dividend_yield * 100) | round(2) }}%{% else %}—{% endif %}</div>
        </div>
        <div class="fund-item">
          <div class="fund-label">Market Cap</div>
          <div class="fund-value">{% if market_cap_chf %}CHF {{ (market_cap_chf / 1e9) | round(1) }}Mrd{% else %}—{% endif %}</div>
        </div>
      </div>
    </div>

    <!-- SHAP TOP-5 -->
    {% if shap_top5 %}
    <div class="card">
      <div class="card-title">Warum {{ ml_signal }}? (SHAP)</div>
      {% set max_abs = shap_top5 | map(attribute='value') | map('abs') | max %}
      {% for entry in shap_top5 %}
      {% set bar_w = ((entry.value | abs) / max_abs * 40) | round(1) %}
      <div class="shap-row">
        <div class="shap-label">{{ entry.label[:18] }}</div>
        {% if entry.value >= 0 %}
          <div style="width:1px; height:8px; background:#334155; margin:0 1mm;"></div>
          <div class="shap-bar-pos" style="width:{{ bar_w }}mm;"></div>
        {% else %}
          <div class="shap-bar-neg" style="width:{{ bar_w }}mm;"></div>
          <div style="width:1px; height:8px; background:#334155; margin:0 1mm;"></div>
        {% endif %}
        <div class="shap-value" style="color:{% if entry.value >= 0 %}#4ade80{% else %}#f87171{% endif %};">
          {% if entry.value >= 0 %}+{% endif %}{{ entry.value | round(3) }}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}

  </div>
</div>

<!-- NARRATIVE -->
{% if narrative_summary %}
<div class="card">
  <div class="card-title">Research-Zusammenfassung</div>
  <div class="narrative">{{ narrative_summary }}</div>
</div>
{% endif %}

<!-- FOOTER -->
<div class="footer">
  Generiert von PRISMA V2 — Quantitative Stock Intelligence Platform · {{ generated_at }} ·
  <strong>Keine Anlageberatung.</strong> Alle Daten ohne Gewähr. FHNW BI Module 2026.
</div>

</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add backend/infrastructure/templates/
git commit -m "feat(infra): Jinja2 HTML template for PDF institutional report"
```

---

## Task 3: `ReportService`

**Files:**
- Create: `backend/application/services/report_service.py`
- Create: `backend/tests/unit/application/test_report_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/application/test_report_service.py`:
```python
"""Unit-Tests für ReportService."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

pytestmark = pytest.mark.unit

from backend.application.services.report_service import ReportService, ReportData
from backend.domain.value_objects.ml_prediction import SHAPEntry


def _make_report_data() -> ReportData:
    return ReportData(
        ticker="NESN.SW",
        company_name="Nestlé S.A.",
        exchange="SIX",
        generated_at=date(2026, 6, 10),
        quant_scores={"Quality": 72.0, "Trend": 55.0, "Value": 60.0, "Alpha": 45.0, "Diversification": 80.0},
        quant_signals={"Quality": "BUY", "Trend": "HOLD", "Value": "HOLD", "Alpha": "WATCH", "Diversification": "BUY"},
        weighted_avg_score=62.4,
        ml_signal="OUTPERFORM",
        ml_confidence=0.72,
        shap_top5=[
            SHAPEntry("roe_zscore", 0.31, 1.2, "Return on Equity"),
            SHAPEntry("vol_30d", -0.18, 0.14, "30-Tage Volatilität"),
        ],
        shap_expected_value=0.12,
        price_chf=89.5,
        market_cap_chf=230_000_000_000.0,
        pe_ratio=22.3,
        pb_ratio=4.1,
        dividend_yield=0.025,
        eligible_3a=True,
        narrative_summary="Nestlé zeigt starke Qualitätskennzahlen mit stabiler Dividende. Diversifikation hervorragend.",
    )


def test_report_data_instantiation() -> None:
    data = _make_report_data()
    assert data.ticker == "NESN.SW"
    assert data.eligible_3a is True
    assert len(data.shap_top5) == 2


@pytest.mark.asyncio
async def test_generate_pdf_returns_bytes() -> None:
    """generate_pdf() gibt nicht-leere bytes zurück die mit %PDF beginnen."""
    svc = ReportService()
    data = _make_report_data()

    with patch.object(svc, "_aggregate_data", new_callable=AsyncMock, return_value=data):
        pdf_bytes = await svc.generate_pdf("NESN.SW")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_generate_pdf_uses_cache(tmp_path) -> None:
    """Zweiter Aufruf nutzt Cache — _aggregate_data wird nur einmal aufgerufen."""
    svc = ReportService()
    data = _make_report_data()
    aggregate_mock = AsyncMock(return_value=data)

    with (
        patch.object(svc, "_aggregate_data", aggregate_mock),
        patch.object(svc, "_cache_get", new_callable=AsyncMock, side_effect=[None, b"%PDF-cached"]),
        patch.object(svc, "_cache_set", new_callable=AsyncMock),
    ):
        await svc.generate_pdf("NESN.SW")  # cache miss
        result2 = await svc.generate_pdf("NESN.SW")  # cache hit

    aggregate_mock.assert_called_once()
    assert result2 == b"%PDF-cached"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest backend/tests/unit/application/test_report_service.py -v
```
Expected: `ImportError` — not yet created.

- [ ] **Step 3: Implement `ReportService`**

Create `backend/application/services/report_service.py`:
```python
"""Application Service: PDF Report Generator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "infrastructure" / "templates"
_CACHE_TTL = 6 * 3600  # 6 hours


@dataclass(frozen=True)
class ReportData:
    ticker: str
    company_name: str
    exchange: str
    generated_at: date
    quant_scores: dict[str, float]
    quant_signals: dict[str, str]
    weighted_avg_score: float
    ml_signal: str
    ml_confidence: float
    shap_top5: list
    shap_expected_value: float
    price_chf: float | None
    market_cap_chf: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    dividend_yield: float | None
    eligible_3a: bool
    narrative_summary: str


class ReportService:
    """Generiert institutionelle PDF-Reports für einen Ticker."""

    async def generate_pdf(self, ticker: str) -> bytes:
        cached = await self._cache_get(ticker)
        if cached:
            return cached

        data = await self._aggregate_data(ticker)
        html = self._render_html(data)
        pdf_bytes = await asyncio.to_thread(self._render_pdf, html)

        await self._cache_set(ticker, pdf_bytes)
        return pdf_bytes

    async def _aggregate_data(self, ticker: str) -> ReportData:
        """Holt alle Report-Daten parallel aus bestehenden Services."""
        from backend.application.services.factsheet_service import FactsheetService
        from backend.application.services.ml_prediction_service import MLPredictionService
        from backend.infrastructure.persistence.session import get_session_factory
        from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
            SQLASwissStockRepository,
        )

        session_factory = get_session_factory()
        swiss_repo = SQLASwissStockRepository(session_factory=session_factory)
        factsheet_svc = FactsheetService(swiss_stock_repo=swiss_repo)
        ml_svc = MLPredictionService()

        factsheet, ml_prediction = await asyncio.gather(
            factsheet_svc.get(ticker),
            ml_svc.predict(ticker),
            return_exceptions=True,
        )

        # Fallbacks für fehlende Daten
        if isinstance(factsheet, Exception) or factsheet is None:
            _logger.warning("Kein Factsheet für %s: %s", ticker, factsheet)
            factsheet = None

        if isinstance(ml_prediction, Exception) or ml_prediction is None:
            _logger.warning("Keine ML-Prediction für %s: %s", ticker, ml_prediction)
            ml_prediction = None

        quant_scores: dict[str, float] = {}
        quant_signals: dict[str, str] = {}
        if factsheet and hasattr(factsheet, "model_scores"):
            for ms in (factsheet.model_scores or []):
                quant_scores[ms.model_name] = ms.score
                quant_signals[ms.model_name] = ms.signal

        return ReportData(
            ticker=ticker.upper(),
            company_name=getattr(factsheet, "company_name", ticker) or ticker,
            exchange=getattr(factsheet, "exchange", "—") or "—",
            generated_at=date.today(),
            quant_scores=quant_scores,
            quant_signals=quant_signals,
            weighted_avg_score=getattr(factsheet, "weighted_avg_score", 0.0) or 0.0,
            ml_signal=getattr(ml_prediction, "signal", "NEUTRAL") if ml_prediction else "NEUTRAL",
            ml_confidence=getattr(ml_prediction, "confidence", 0.0) if ml_prediction else 0.0,
            shap_top5=getattr(ml_prediction, "shap_values", [])[:5] if ml_prediction else [],
            shap_expected_value=getattr(ml_prediction, "shap_expected_value", 0.0) if ml_prediction else 0.0,
            price_chf=getattr(factsheet, "price_chf", None),
            market_cap_chf=getattr(factsheet, "market_cap_chf", None),
            pe_ratio=getattr(factsheet, "pe_ratio", None),
            pb_ratio=getattr(factsheet, "pb_ratio", None),
            dividend_yield=getattr(factsheet, "dividend_yield", None),
            eligible_3a=getattr(factsheet, "eligible_3a", False) or False,
            narrative_summary=_extract_narrative_summary(factsheet),
        )

    def _render_html(self, data: ReportData) -> str:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
        template = env.get_template("report.html.j2")
        return template.render(
            ticker=data.ticker,
            company_name=data.company_name,
            exchange=data.exchange,
            generated_at=data.generated_at.strftime("%d.%m.%Y"),
            quant_scores=data.quant_scores,
            quant_signals=data.quant_signals,
            weighted_avg_score=data.weighted_avg_score,
            ml_signal=data.ml_signal,
            ml_confidence=data.ml_confidence,
            shap_top5=data.shap_top5,
            shap_expected_value=data.shap_expected_value,
            price_chf=data.price_chf,
            market_cap_chf=data.market_cap_chf,
            pe_ratio=data.pe_ratio,
            pb_ratio=data.pb_ratio,
            dividend_yield=data.dividend_yield,
            eligible_3a=data.eligible_3a,
            narrative_summary=data.narrative_summary,
            enumerate=enumerate,
        )

    def _render_pdf(self, html: str) -> bytes:
        import weasyprint

        return weasyprint.HTML(string=html).write_pdf()

    async def _cache_get(self, ticker: str) -> bytes | None:
        try:
            import redis.asyncio as aioredis
            from backend.config import get_settings

            settings = get_settings()
            if not settings.redis_url:
                return None
            client = aioredis.from_url(settings.redis_url)
            raw = await client.get(f"report:{ticker.upper()}")
            await client.aclose()
            return bytes(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(self, ticker: str, data: bytes) -> None:
        try:
            import redis.asyncio as aioredis
            from backend.config import get_settings

            settings = get_settings()
            if not settings.redis_url:
                return
            client = aioredis.from_url(settings.redis_url)
            await client.setex(f"report:{ticker.upper()}", _CACHE_TTL, data)
            await client.aclose()
        except Exception:
            pass


def _extract_narrative_summary(factsheet: object | None) -> str:
    if factsheet is None:
        return ""
    memo = getattr(factsheet, "research_memo", None)
    if not memo:
        return ""
    summary = getattr(memo, "summary", None) or getattr(memo, "content", None) or ""
    return str(summary)[:400]
```

- [ ] **Step 4: Run tests**

```bash
pytest backend/tests/unit/application/test_report_service.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/report_service.py backend/tests/unit/application/test_report_service.py
git commit -m "feat(application): ReportService — PDF generation via WeasyPrint + Redis cache"
```

---

## Task 4: API Endpoint

**Files:**
- Create: `backend/interfaces/rest/routers/reports.py`
- Modify: `backend/interfaces/rest/app.py`

- [ ] **Step 1: Create router**

Create `backend/interfaces/rest/routers/reports.py`:
```python
"""REST Router: PDF Report Generator — GET /api/v1/stocks/{ticker}/report.pdf"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from backend.application.services.report_service import ReportService

router = APIRouter(prefix="/api/v1/stocks", tags=["reports"])
_logger = logging.getLogger(__name__)


@router.get(
    "/{ticker}/report.pdf",
    summary="PDF Institutional Report für einen Ticker",
    description=(
        "Generiert einen professionellen Investment-Report als PDF (A4, Dark Theme). "
        "Aggregiert: Quant-Scores, ML-Prediction + SHAP, Fundamentaldaten, Narrative. "
        "Redis-gecacht für 6h. Keine Anlageberatung."
    ),
    response_class=Response,
)
async def get_report(ticker: str) -> Response:
    svc = ReportService()
    try:
        pdf_bytes = await svc.generate_pdf(ticker.upper())
    except Exception as exc:
        _logger.exception("PDF-Generierung fehlgeschlagen für %s", ticker)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF-Generierung fehlgeschlagen.",
        ) from exc

    filename = f"PRISMA_{ticker.upper()}_{date.today().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 2: Register in `app.py`**

In `backend/interfaces/rest/app.py`, add to imports:
```python
from backend.interfaces.rest.routers import (
    ...
    reports,
    ...
)
```

And in `create_app()`:
```python
app.include_router(reports.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/interfaces/rest/routers/reports.py backend/interfaces/rest/app.py
git commit -m "feat(api): GET /api/v1/stocks/{ticker}/report.pdf endpoint"
```

---

## Task 5: Frontend Export Button

**Files:**
- Create: `frontend/components/factsheet/ExportReportButton.tsx`
- Modify: `frontend/components/factsheet/StockHeader.tsx`

- [ ] **Step 1: Create `ExportReportButton.tsx`**

Create `frontend/components/factsheet/ExportReportButton.tsx`:
```tsx
'use client';

import { useState } from 'react';
import { Download, CheckCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  ticker: string;
}

const STEPS = [
  'Quant Scores',
  'ML Prediction',
  'Swiss-Daten',
  'Rendering PDF',
];

export function ExportReportButton({ ticker }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [step, setStep] = useState(0);

  const handleExport = async () => {
    setState('loading');
    setStep(0);

    // Animate steps
    for (let i = 0; i < STEPS.length - 1; i++) {
      await new Promise((r) => setTimeout(r, 350));
      setStep(i + 1);
    }

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${API_BASE}/api/v1/stocks/${ticker}/report.pdf`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      // Auto-download
      const a = document.createElement('a');
      a.href = url;
      a.download = `PRISMA_${ticker}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setState('done');
      setTimeout(() => setState('idle'), 3000);
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 2000);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1.5">
      <button
        onClick={handleExport}
        disabled={state === 'loading'}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
          'border backdrop-blur-sm',
          state === 'idle' && 'bg-slate-900/60 border-slate-700 text-slate-300 hover:border-purple-500/60 hover:text-white',
          state === 'loading' && 'bg-slate-900/60 border-purple-500/40 text-purple-300 cursor-not-allowed',
          state === 'done' && 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400',
          state === 'error' && 'bg-red-950/60 border-red-500/40 text-red-400',
        )}
        style={
          state === 'idle'
            ? { '--hover-shadow': '0 0 16px rgba(168,85,247,0.4)' } as React.CSSProperties
            : undefined
        }
      >
        {state === 'loading' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {state === 'done' && <CheckCircle className="h-3.5 w-3.5" />}
        {(state === 'idle' || state === 'error') && <Download className="h-3.5 w-3.5" />}
        {state === 'idle' && 'Export Report'}
        {state === 'loading' && 'Generating...'}
        {state === 'done' && 'Downloaded!'}
        {state === 'error' && 'Error — retry'}
      </button>

      {state === 'loading' && (
        <div className="flex items-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              {i > 0 && <span className="text-slate-700 text-[10px]">→</span>}
              <span
                className={cn(
                  'text-[10px] transition-colors duration-300',
                  i < step ? 'text-emerald-500' : i === step ? 'text-purple-400' : 'text-slate-700',
                )}
              >
                {i < step ? '✓' : ''} {s}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add button to `StockHeader.tsx`**

In `frontend/components/factsheet/StockHeader.tsx`, import and add `<ExportReportButton>`:

Find the existing return JSX in `StockHeader.tsx`. Add the import at the top:
```tsx
import { ExportReportButton } from './ExportReportButton';
```

Then in the JSX header, add `<ExportReportButton ticker={ticker} />` in the top-right area alongside existing header actions. (Exact position depends on current StockHeader layout — place it in the header action row.)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/factsheet/ExportReportButton.tsx frontend/components/factsheet/StockHeader.tsx
git commit -m "feat(frontend): ExportReportButton with animated progress steps on Factsheet"
```

---

## Task 6: Lint + Test

- [ ] **Step 1: Lint backend**

```bash
ruff check backend/
ruff format --check backend/
```

- [ ] **Step 2: Full unit tests**

```bash
pytest backend/tests/unit -q
```
Expected: all pass.

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
