# PRISMA Demo-Skript

> **Zweck:** Strukturierter Walk-Through für die Capstone-Live-Demo (~10-15min).
> **Demo-URL:** http://localhost:3000 (lokal) bzw. Live auf Render (siehe README)
> **Stand:** 2026-06-01 — **alle Features sind in `main` gemerged** (PRs #142–#155). Der frühere Integrations-Branch `demo/all-features` ist obsolet.

## 1. Pre-Flight (5min vor Demo)

```bash
# Backend
cd /Users/sheyla/Projects/prisma-capstone
DATABASE_URL=postgresql+asyncpg://prisma:prisma@localhost:5432/prisma \
  .venv/bin/uvicorn backend.interfaces.rest.app:create_app --factory --reload --port 8000

# Frontend (eigenes Terminal)
cd frontend && npm run dev

# Browser: http://localhost:3000
```

**Branch:** `main` (enthält alle Features; `alembic upgrade head` seedet den 13-Stock-Katalog automatisch via Migration 0012).

**Smoke-Check** vor Publikum: http://localhost:3000/dashboard sollte Stocks=13 + ≥1 Run zeigen. Wenn nicht → DB-Container kontrollieren (`docker ps` → `prisma-db`) und Universen/Runs per `scripts/seed_demo_universe.py` + Run-Start anlegen.

## 2. Story-Bogen (30 Sekunden)

> *"PRISMA hilft, Aktien systematisch auszuwählen — wie ein optisches Prisma weisses Licht in seine Spektralfarben zerlegt, zerlegt PRISMA Unternehmen entlang von fünf quantitativen Dimensionen: Quality, Trend, Value, Alpha, Diversification. Zusätzlich generiert die Narrative-Engine via Claude Research-Memos pro Top-Pick. Ich zeige es Ihnen am besten direkt."*

→ **Anker:** Der Spektrum-Strip unter dem Header ist das visuelle Mantra. Während der ganzen Demo bewusst dort hindeuten lassen.

## 3. Walk-Through (3 Akte, je ~3min)

### Akt 1 — Universe (1.5min)

**Startpunkt:** `/dashboard` zeigen.

**Talking Points:**
- "Vordefinierte Universen per Seed-Skript: Demo-US-5, Tech-Big-12 (weitere jederzeit anlegbar)."
- "Jeden Run kann man von hier aus starten — aber zuerst zeige ich, wie ein Universe selbst entsteht."

**Klick:** Nav → "Universen"

**Show:** Liste mit drei Universen. Klick auf "Mit KI generieren" (KI-Wizard, der neue Sparkles-Button).

**Talking Points zum Wizard:**
- "Freitext-Eingabe: 'Halbleiter und KI-Stocks aus den USA'."
- "Claude Haiku schlägt aus unserem 13-Stock-Katalog passende Tickers vor — Whitelist-constrained, keine Halluzinationen."
- "Vorschlag wird in das normale Form pre-filled, User kann editieren bevor er erstellt."

**Pointer:** "Das ist der wichtigste UX-Hebel des Tools — Aktien-Auswahl ist normalerweise die Reibung, die Privatanleger blockiert."

**Skip-Option falls Zeit knapp:** Wizard ist auch demonstrierbar mit nur einem Vorschlag-Beispiel — nicht zwingend bis Universe-Erstellung gehen.

### Akt 2 — Ranking & Drilldown (3min)

**Klick:** Nav → "Rankings"

**Show:** Form "Neuer Run" + "Vergangene Runs"-Liste mit 2 completed Runs.

**Talking Points:**
- "Form: Universe wählen, optional Modell-Gewichte tweaken, dann 'Run starten'."
- "Run läuft asynchron — ca. 5-15 Sekunden auf Stub-Daten, bei Live-API länger."
- "Ich nutze einen vorbereiteten Run für die Demo."

**Klick:** Tech-Big-12-Run → "Öffnen"

**Show:** Detail-Page mit Top-10-Cards, Bar-Chart, Vollständige Tabelle.

**Pointer-Reihenfolge:**
1. **Top-10-Cards oben** — Sterne markieren Sweet-Spots (Top-Quintil in allen 5 Modellen)
2. **Bar-Chart** — Top-10 nach weighted_avg, Gold-Akzent bei Sweet-Spots
3. **Tabelle** — alle 12 Stocks mit Per-Modell-Rängen, Tooltips auf Spalten-Headern erklären jedes Modell

**Talking Point Sweet-Spot:**
> *"NVDA ist Sweet-Spot — das heisst: er ist in Quality UND Trend UND Value UND Alpha UND Diversification im obersten Fünftel. Das ist selten — meistens fehlt eine Dimension."*

**Klick:** NVDA-Ticker → Factsheet öffnet sich

**Show:** Factsheet mit 5 Modell-Karten, Q1-Badges, Kurschart, Research-Memo-Section

**Talking Point Memo:**
- "Wenn ein Memo existiert: strukturierter LLM-Output — Stärken, Risiken, Widersprüche zwischen Modellen, One-Liner."
- "Wenn keins: 'Memo generieren'-Button startet Background-Job mit Claude."
- **Demo-Tipp:** Falls Live-Generation zu langsam ist, vorab für 1 Ticker generieren lassen und in der Demo diesen zeigen.

### Akt 3 — Vergleich & Robustheit (2min)

**Klick:** Nav → "Rankings" zurück

**Show:** Run-History-Liste

**Talking Points:**
- "PRISMA hält jeden Run mit Timestamp + Universe + Status. Ein wichtiger Stress-Test der Methodik ist: Sind die Top-Picks stabil über mehrere Runs?"

**Klick:** Beide Run-Checkboxen → "Vergleichen"-Button

**Show:** Compare-Page mit Banner + Δ-Tabelle.

**Pointer:**
- **Banner:** "Run A: Tech-Big-12, Run B: Demo-US-5. Banner zeigt: 4 gemeinsame Stocks, 8 nur in A, 1 nur in B — cross-universe."
- **Tabelle:** "NVDA hat in beiden Runs Rang 1 — robust. MSFT hat ±1 Rang Bewegung — innerhalb der Methodik. AAPL hat in der kleineren Demo-US-5 sogar Rang 4 statt 5 — kleinere Peer-Group, andere Verteilung."

**Story-Anker:**
> *"Die Stabilität der Top-Picks zwischen Runs ist ein wichtiger Robustheits-Indikator. PRISMA zeigt dir nicht nur eine Antwort, sondern lässt dich auch validieren, ob die Antwort konsistent ist."*

## 4. Optional: Backtest (1min — nur wenn Zeit)

**Klick:** Nav → "Backtest"

**Show:** Form mit Run-ID, Top-N, Datums-Range, Benchmark.

**Talking Points:**
- "Backtest simuliert: 'Hätte man die Top-3 dieses Runs gekauft im Zeitraum X, was wäre rausgekommen?'"
- "Vergleich gegen Benchmark (S&P 500, SMI etc.)."
- **Vorsicht:** Live-Backtest braucht echte Run-ID + Markt-Daten — wenn die nicht da sind, ist's Demo-Skipper. Lieber per Screenshot oder ganz weglassen.

## 5. Q&A — Likely Questions

### "Wie ist die Berechnung der Modelle?"
- Jedes Modell ist eine pure Python-Funktion in `backend/domain/models/`. Spec: `docs/specs/2026-04-21-prisma-capstone-design.md`.
- Quality Classic: P/E, P/B, FCF-Yield, Operating Margin, Div-Yield, D/E, EPS-Growth, Sales-Growth gewichtet.
- Andere ähnlich — verschiedene Faktor-Gruppen.
- Per-Modell-Ranks aggregiert via `weighted_avg`, Default Equal-Weights (jedes Modell 20%).

### "Wo kommen die Daten her?"
- Aktuell `StubFundamentalsProvider` + `StubMarketDataProvider` mit deterministischen Demo-Daten — damit Demo reproduzierbar ist.
- Production-Adapter für `yfinance` + `Finnhub` existieren als Ports/Adapters-Pattern, sind aber nicht im Demo aktiv.

### "Halluziniert die KI Aktien?"
- Nein — der LLM-Wizard hat eine harte Whitelist auf den vorhandenen Stock-Katalog (13 Stocks). Wenn Claude einen nicht existierenden Ticker vorschlägt, schlägt die Pydantic-Validation fehl mit 502.
- Research-Memos sind strukturierter Output via Tool-Use-Pattern — keine Freitext-Parsing-Risiken.

### "Wieso 5 Modelle und nicht 3 oder 7?"
- Empirische Wahl basierend auf Literatur (siehe Spec). Quality + Value sind klassisch Fundamental-Analyse, Trend + Alpha sind Momentum/Markt-Signale, Diversification ist Korrelations-Adjustment.
- Modelle sind plug-in-fähig — neue können hinzugefügt werden via `domain/models/`-Pattern.

### "Was ist die Rolle von Claude im Projekt?"
- Drei Stellen:
  1. **LLM-Wizard** für Universe-Erstellung (Haiku 4.5 — schnell, billig)
  2. **Research-Memos** pro Top-Pick (Sonnet 4.6 für Synthese-Qualität)
  3. **Development-Tool** — Capstone wurde mit Claude Code entwickelt (siehe `docs/AI-USAGE.md`, 40%-Bewertungsachse)
- Klare Trennung: PRISMA als App ist NICHT abhängig von Claude für Kern-Funktion. Quantitative Rankings funktionieren ohne LLM. LLM ist eine Erweiterung, nicht das Fundament.

### "Was würde ich anders machen wenn ich nochmal anfangen würde?"
- (Ehrliche Antwort — Demo-tauglich) Mehr Disziplin am Anfang bei der Hexagonal-Architektur — manche frühen Modelle haben `yfinance` direkt importiert statt über Port → später refactored. Lehre: Ports-and-Adapters-Pattern von Tag 1 strikt durchziehen.

## 6. Demo-Disaster-Recovery

| Problem | Workaround |
|---|---|
| Backend down | `curl http://localhost:8000/api/v1/runs` → wenn 500/connection-refused, `docker ps` checken. Notfalls Frontend mit Stub-Daten (falls vorbereitet) oder Skip auf Slides. |
| Run-Start hängt | Liegt meist am Stub-Provider, nicht an Logic. Vorhandene completed Runs nutzen statt neu starten. |
| Memo-Generation langsam | Vor Demo für 1 Top-Pick vorgenerieren. |
| Browser-Cache | Hard-Reload (Cmd+Shift+R) oder Inkognito-Fenster. |
| Mobile-View kaputt | Header hat `flex-col` für <640px — sollte passen. Sonst Desktop-Viewport nutzen. |

## 7. Was NICHT zeigen (Time-Saver)

- `/backtest` wenn keine echten Markt-Daten geladen sind → Form ohne Resultat ist enttäuschend.
- MCP-Integration — interessant, aber braucht Claude Desktop offen + Tool-Konfiguration. Lieber kurz erwähnen + Slides zeigen.
- Direkte API-Calls (Swagger/OpenAPI) — Bewerter sehen Frontend, nicht REST-API.

## 8. Reihenfolge der Tabs (Browser-Setup vor Demo)

1. `/dashboard` (Startseite der Demo)
2. `/universes` (Akt 1)
3. `/universes/wizard` (Akt 1, falls Live-Generation)
4. `/rankings` (Akt 2)
5. `/rankings/84ce5028-b03a-40ce-9405-9fd2b3d5f61e` (Tech-Big-12 Detail)
6. `/rankings/84ce5028-b03a-40ce-9405-9fd2b3d5f61e/stock/NVDA` (Factsheet mit Memo)
7. `/rankings/compare?a=84ce5028-b03a-40ce-9405-9fd2b3d5f61e&b=2d272e9c-934c-4e5b-97ad-83c091314fdc` (Akt 3)

**Tipp:** Tabs in dieser Reihenfolge öffnen, dann nur Cmd+Option+Pfeil zwischen ihnen springen.
