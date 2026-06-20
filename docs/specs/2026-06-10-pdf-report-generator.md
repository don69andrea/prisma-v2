# Spec: PDF Institutional Report Generator

**Issue:** #73 (to be created)
**Date:** 2026-06-10
**Author:** Andrea Petretta
**Status:** Planned

---

## Ziel

Ein-Klick-Export eines professionellen Investment-Reports (PDF) direkt vom Factsheet — aggregiert alle PRISMA-Daten zu einem institutionellen One-Pager. Demo-Artefakt: *"Das ist das Ergebnis einer vollständigen PRISMA-Analyse."*

---

## Nicht-Ziele

- Portfolio-Report über mehrere Tickers (v1: nur Single-Ticker)
- Real-time Pricing im PDF (Snapshot zum Zeitpunkt der Generierung)
- Branded White-Label für VIAC (v1: PRISMA-Brand)
- Anhänge / Multi-Page Report (max 2 Seiten)

---

## Architektur

### Backend — `ReportService`

**Neue Datei:** `backend/application/services/report_service.py`

**Dependencies:**
- `weasyprint>=62.0` (HTML→PDF, bereits mit CSS-Support)
- Jinja2 (bereits im Stack via FastAPI)

**Report-Inhalt (aggregiert aus bestehenden Services):**

```python
@dataclass(frozen=True)
class ReportData:
    ticker: str
    company_name: str
    exchange: str
    generated_at: datetime

    # Quant
    quant_scores: dict[str, float]      # 5 Modelle: name → score
    quant_signals: dict[str, str]       # name → BUY/HOLD/SELL
    weighted_avg_score: float

    # ML
    ml_signal: str                      # OUTPERFORM/NEUTRAL/UNDERPERFORM
    ml_confidence: float
    shap_top5: list[SHAPEntry]          # aus Feature #70

    # Swiss / Fundamentals
    price_chf: Optional[float]
    market_cap_chf: Optional[float]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    dividend_yield: Optional[float]
    eligible_3a: bool

    # Narrative
    narrative_summary: str              # Max 300 Zeichen (Kurzfassung des Memos)
```

**Service-Methode:**
```python
async def generate_pdf(ticker: str) -> bytes:
    data = await _aggregate_report_data(ticker)  # parallel fetches
    html = jinja_env.render("report.html.j2", data=data)
    return weasyprint.HTML(string=html).write_pdf()
```

**Caching:** `f"report:{ticker}"` in Redis, TTL 6h (Report-Daten ändern sich selten).

### Jinja2-Template `report.html.j2`

**Seite 1 (A4):**
- **Header:** PRISMA-Logo links, Ticker + Company rechts, Datum unten rechts. Gradient-Bar als Separator (Prisma-Spektrum-Farben).
- **Signal-Banner:** Grosses ML-Signal (OUTPERFORM/NEUTRAL/UNDERPERFORM) mit Farb-Hintergrund + Konfidenz-Balken.
- **Quant-Scores Radar:** SVG-Pentagramm (5 Achsen = 5 Modelle), direkt im Template als inline SVG gerendert.
- **SHAP Top-5:** Mini-Waterfall als horizontale Balken (SVG inline).
- **Fundamentaldaten-Tabelle:** KGV / KBV / Dividendenrendite / Market Cap in 2×2 Grid.
- **3a-Eligibility Badge:** Grün/Rot mit Icon.
- **Narrative:** Kursiv-Block, max 3 Sätze.
- **Footer:** *"Generiert von PRISMA V2 — Keine Anlageberatung. Stand: {date}"*

**CSS:**
- Dark Theme: `background: #0a0a14`, Text weiss
- Neon-Akzente: Signal-Farben (`#00ff88` BUY, `#ffaa00` HOLD, `#ff4466` SELL)
- WeasyPrint-kompatibles CSS (kein `backdrop-filter`, kein `transform`)
- Print-optimiert: feste Seitenränder, keine Hover-States

### API

```
GET /api/v1/stocks/{ticker}/report.pdf
Response: application/pdf
Headers: Content-Disposition: attachment; filename="PRISMA_{ticker}_{date}.pdf"
```

Redis-Cache-Check vor Generierung. Cache-Miss: generiere, speichere, returne.

### Frontend (Factsheet)

**Export-Button:**
- Position: top-right im Factsheet-Header, neben dem Ticker
- Design: Glassmorphism-Button, Download-Icon + *"Export Report"*
- Hover: Neon-Glow (`box-shadow: 0 0 20px rgba(100,50,255,0.6)`)

**Loading-State (futuristisch):**
- Button deaktiviert, Text wechselt zu *"Generating..."*
- Unter dem Button erscheint eine animated Progress-Row:
  ```
  ✓ Quant Scores  →  ✓ ML Prediction  →  ⟳ Rendering PDF...
  ```
  (Schritte erscheinen sequentiell mit 400ms Delay via CSS transition)

**Preview-Modal:**
- Nach Generierung: Modal mit `<iframe src="blob:...">` — 3s Preview
- Darunter: *"Download startet automatisch..."* Countdown
- Manuell: *"Download jetzt"* Button

---

## Tests

- Unit: `test_report_service.py` — `generate_pdf()` gibt `bytes` zurück, PDF-Header `%PDF` validieren
- Unit: Template rendert ohne Fehler mit Mock-`ReportData`
- Unit: Cache-Hit überspringt WeasyPrint-Call
- Integration: `GET /api/v1/stocks/NESN.SW/report.pdf` → 200, Content-Type `application/pdf`

---

## Akademischer + VIAC Impact

Zeigt End-to-End-Fähigkeit der Plattform: alle Daten-Schichten (Quant, ML, Narrative, Swiss) in einem professionellen Output. In der Demo physisch ausdruckbar — *"Das ist das Ergebnis einer vollständigen PRISMA-Analyse"* — wirkt wie echtes Fintech-Produkt.
