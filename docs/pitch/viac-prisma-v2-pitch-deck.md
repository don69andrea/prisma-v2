# PRISMA V2 für VIAC — Pitch Deck
## Quantitative 3a-Stock-Intelligence für die nächste Generation

---

## Slide 1 — Das Problem

**Schweizer Vorsorgekapital wächst, aber die Tools stagnieren.**

- CHF 1.2 Billionen in der 2. Säule, wachsende 3a-Selfservice-Plattformen
- VIAC-Nutzer wählen zwischen ~30 Aktien — ohne datengetriebene Entscheidungshilfe
- Bestehende Tools zeigen Kennzahlen, aber erklären keine **Signale**
- Anleger entscheiden auf Basis von News und Bauchgefühl statt Quant-Modellen

> **Resultat:** Suboptimale Portfolios, vermeidbare Verluste, fehlende Transparenz.

---

## Slide 2 — PRISMA Solution

**PRISMA = Quantitatives Signal-System für Swiss 3a-Aktien.**

```
Quant-Modelle (45%)  +  ML-Predictor (35%)  +  Makro-Kontext (20%)
              ↓
     BUY / HOLD / WATCH Signal
              ↓
  Erklärung auf Deutsch — kein Fachjargon
```

**Kernprinzip:** Jede Empfehlung ist nachvollziehbar, auditierbar und Pydantic-validiert.  
**Kein Black-Box-LLM.** Alle Signale basieren auf reproduzierbaren Algorithmen.

---

## Slide 3 — Swiss Coverage

**13 SMI-Titel vollständig abgedeckt — erweiterbar auf SMIM/SPI.**

| Ticker | Name              | 3a-eligible |
|--------|-------------------|-------------|
| NESN   | Nestlé            | ✅          |
| NOVN   | Novartis          | ✅          |
| ROG    | Roche             | ✅          |
| UHR    | Swatch Group      | ✅          |
| ABBN   | ABB               | ✅          |
| ZURN   | Zurich Insurance  | ✅          |
| SREN   | Swiss Re          | ✅          |
| CSGN   | CS Group          | ✅          |
| UBSG   | UBS Group         | ✅          |
| LONN   | Lonza Group       | ✅          |
| GIVN   | Givaudan          | ✅          |
| SLHN   | Swiss Life        | ✅          |
| BALN   | Baloise           | ✅          |

**Eligibility-Kriterium (BVV2/FINMA):** XSWX-kotiert + ≥ 100 Mio. CHF Marktkapitalisierung.

---

## Slide 4 — 3a Layer

**PRISMA filtert automatisch 3a-konforme Titel.**

- Regelbasierter `EligibilityFilter` (BVV2 Art. 53)
- Zwei Kriterien: SIX Swiss Exchange + Mindestliquidität 100M CHF
- Ergebnis: `eligible: true/false` mit Begründung (`EXCHANGE_NOT_RECOGNIZED`, `MARKET_CAP_TOO_LOW`)
- Portfolio-Optimierung: `eligible_only=true` → nur 3a-konforme Titel

**Für VIAC:** Alle Einzeltitel-Empfehlungen können gegen 3a-Compliance gefiltert werden —  
direkt in der VIAC-App verwendbar ohne manuelle Prüfung.

---

## Slide 5 — ML Signals

**Dreistufiges Scoring-System mit erklärbaren Komponenten.**

```
┌─────────────────────────────────────────────────────────┐
│  QUANT (45%)     │  ML (35%)         │  MAKRO (20%)     │
│                  │                   │                  │
│ • P/E Ratio      │ XGBoost-Predictor │ SNB-Leitzins     │
│ • P/B Ratio      │ Return Horizon    │ CHF/EUR-Kurs     │
│ • Dividende      │ 12-Monats-Signal  │ Inflations-Klima │
│ • EPS            │ (OUTPERFORM /     │ (EXPANSIV /      │
│ • RSI, Momentum  │  NEUTRAL /        │  NEUTRAL /       │
│                  │  UNDERPERFORM)    │  RESTRIKTIV)     │
└─────────────────────────────────────────────────────────┘
         ↓                   ↓                  ↓
    weighted_score = 0.45×Q + 0.35×ML + 0.20×M
         ↓
    BUY ≥ 65  |  HOLD ≥ 40  |  WATCH < 40
```

**Jedes Signal** wird im Audit-Trail mit vollständiger Begründung gespeichert.

---

## Slide 6 — Demo Path

**5-Schritt-Demo für VIAC-Executive.**

1. **Universe wählen** → SMI 13 Titel laden (`GET /api/v1/universes`)
2. **Ranking starten** → Quant-Scores berechnen (`POST /api/v1/runs`)
3. **Signal Dashboard** → BUY/HOLD/WATCH-Übersicht mit 3a-Filter (`GET /api/v1/decisions`)
4. **Portfolio allozieren** → Score-Weighted oder Risk-Parity (`POST /api/v1/portfolio/allocate`)
5. **Fonds-Vergleich** → PRISMA-Portfolio vs. VIAC Global 100 (`POST /api/v1/fonds/vergleich`)

**Erwartetes Ergebnis:** In < 3 Minuten vom leeren Screen zu einer validierten,  
3a-konformen Aktienauswahl mit Vergleich gegen den VIAC-Strategiefonds.

---

## Slide 7 — Technologie & Sicherheit

**Enterprise-Grade Stack — Production-ready.**

| Layer          | Technologie                          |
|----------------|--------------------------------------|
| Backend        | FastAPI + SQLAlchemy 2.0 async       |
| Datenbank      | PostgreSQL 16 + pgvector             |
| ML             | XGBoost + scikit-learn               |
| LLM            | Claude API (Anthropic) — validiert   |
| Frontend       | Next.js 14 + TypeScript              |
| Deployment     | Render (Docker)                      |
| CI/CD          | GitHub Actions (ruff + mypy + pytest)|

**Security:**
- API-Keys nur über Env-Variables (nie im Code)
- Alle SQL-Queries parameterisiert (kein String-Concatenation)
- LLM-Outputs immer Pydantic-validiert (kein Freetext ans Frontend)
- Audit-Trail für jede Entscheidung

---

## Slide 8 — Alert Engine & Monitoring

**Nutzer bleiben ohne aktives Monitoring informiert.**

- **Price Alerts:** Benachrichtigung wenn Kurs um X% abweicht
- **Signal Alerts:** Benachrichtigung bei BUY→HOLD→WATCH-Wechsel
- **Kanäle:** E-Mail (SendGrid) oder Webhook
- **Täglicher Worker:** APScheduler prüft automatisch alle aktiven Alerts

**Use Case für VIAC:**  
Ein Nutzer hält NESN. NESN-Signal wechselt von HOLD zu WATCH.  
→ Automatische E-Mail-Benachrichtigung an den Nutzer.

---

## Slide 9 — Team & Status

**FHNW BSc Business Artificial Intelligence — FS 2026.**

| | |
|---|---|
| **Projekt** | PRISMA V2 — Swiss Market Stock Intelligence |
| **Hochschule** | FHNW Hochschule für Wirtschaft |
| **Modul** | AI-assisted Software Development |
| **Status** | v2.0 Swiss Foundation — production-deployed |
| **Tests** | 415+ Unit-Tests, ruff + mypy strict, E2E-Suite |
| **PRs** | 47+ Pull Requests, Gitflow, vollständiger Audit-Trail |

**Inspiration:** PRISMA der Vireos AG — konzeptionell adaptiert für 3a-Vorsorge.

---

## Slide 10 — Next Steps & Roadmap

**Drei konkrete Integrationsszenarien für VIAC.**

### Kurzfristig (Q3 2026)
- [ ] VIAC-API-Integration: Direkte Portfolioübernahme aus VIAC-Konto
- [ ] White-Label-Frontend für VIAC-Branded Experience
- [ ] 30-Jahres-Langfrist-Score für Vorsorgehorizont

### Mittelfristig (Q4 2026)
- [ ] Rebalancing-Engine: automatische Gewichtsanpassung
- [ ] RAG über SIX-Filings und NZZ/SRF-News für fundamentale Analyse
- [ ] Steuer-Implikations-Agent (3a-Säule Optimierung)

### Vision (2027)
- [ ] Echtzeit-Signal-Updates (intraday)
- [ ] Multi-Universe: SMI + SMIM + SPI-Top50 parallel
- [ ] Backtesting: PRISMA vs. VIAC Global 100 über 10 Jahre

---

*⚠️ Disclaimer: PRISMA dient ausschliesslich zu Forschungs- und Bildungszwecken.  
Keine Anlageberatung. Historische Performance ≠ zukünftige Rendite.*

---

**Kontakt:** FHNW BSc Business AI Team FS 2026  
**Repository:** github.com/don69andrea/prisma-v2
