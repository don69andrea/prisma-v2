# PRISMA V2 — Market-Ready Overhaul
**Datum:** 2026-06-14  
**Branch:** `feat/market-ready-overhaul-2026-06-14`  
**Autor:** Claude Code (Auftrag: Andrea Petretta)  
**Status:** IN BEARBEITUNG

---

## Kontext & Motivation

PRISMA V2 ist eine quantitative Stock-Intelligence-Plattform für den Schweizer Markt (FHNW BI Modul FS2026, Prof. Manuel Renold). Nach der ersten Implementierungsphase besteht der Eindruck, dass viele Features "einfach irgendwas" sind — vorhanden, aber nicht fertig durchdacht, nicht intuitiv und ohne echten Mehrwert für den User.

Dieses Dokument beschreibt alle identifizierten Probleme und deren Lösung im Rahmen des Overhauls.

---

## 1. Identifizierte Probleme (Ausgangslage)

### 1.1 Onboarding-Wizard (`/start`)

| Problem | Datei | Schwere |
|---------|-------|---------|
| Turn 4: `brand_data` wird nie mitgesendet → `sector_affinity` immer `[]` | `discovery.py:149` | KRITISCH |
| Turns 5–7 (Betrag, ESG, Income) nur als Backend-Logik, kein Frontend | `start-client.tsx` | KRITISCH |
| `confidence_score = 0.0` für konservative User (beat_savings + moderate + low) | `profile_classifier.py:130` | HOCH |
| Async-Bug: `handleContinue` ohne `await` aufgerufen | `start-client.tsx:900` | MITTEL |
| Profil-Badge zeigt nach Wizard kein Feedback was das Profil bedeutet | `start-client.tsx` | MITTEL |

**Geplante Lösung:**
- Turn 4: Frontend sendet `brand_data` Dictionary mit (ticker → {name, sector}) zum Backend
- Turns 5–7: Drei neue Frontend-Schritte:
  - Step `betrag`: "Wie viel möchtest du anlegen?" (3 Cards: <10k / 10k–100k / >100k)
  - Step `esg`: "Nachhaltigkeit — wie wichtig?" (3 Options: Wichtig / Egal / Aktiv vermeiden)
  - Step `income`: "Was soll dein Geld tun?" (3 Cards: Dividenden / Wachstum / Beides)
- Reveal-Screen: zeigt kompaktes Profil-Summary mit allen 7 Dimensionen
- Router auf `le=7` setzen + Handler für Turns 5–7 ergänzen
- Confidence-Score: Basiswert 0.2 wenn alle Turns beantwortet (unabhängig von Wertekombination)

### 1.2 Backtest (`/backtest`)

| Problem | Datei | Schwere |
|---------|-------|---------|
| `list[Decimal]` im Schema → JSON serialisiert als Strings → Charts zeigen NaN | `backtest.py:36–38` | KRITISCH |
| Kein leerer-State wenn kein Run vorhanden | `backtest/page.tsx` | MITTEL |

**Geplante Lösung:**
- Schema: `list[Decimal]` → `list[float]` in allen drei Series-Feldern
- Empty-State: Klarer CTA "Ersten Backtest starten"

### 1.3 Decision / Signale (`/decision`)

| Problem | Datei | Schwere |
|---------|-------|---------|
| ML-Gewicht (0.35) fällt bei ML-Ausfall weg statt umverteilt zu werden | `signal_aggregation_service.py` | HOCH |
| BUY/HOLD/SELL Kriterien für User nicht sichtbar | `decision-client.tsx` | MITTEL |
| Keine Sortierung nach Confidence oder Signal-Stärke als Default | `decision-client.tsx` | MITTEL |

**Geplante Lösung:**
- `signal_aggregation_service.py`: ML-Ausfall → ML-Gewicht 50/50 auf Quant/Makro verteilen
- Decision-Client: Tooltip/Erklärung zu BUY/HOLD/SELL Schwellen (≥70/40–69/<40)
- Default-Sort: nach composite_score descending

### 1.4 Portfolio (`/portfolio`)

| Problem | Datei | Schwere |
|---------|-------|---------|
| Gewichte können >100% gesetzt werden ohne Fehler | `portfolio-client.tsx` | HOCH |
| Keine Anzeige der Gesamtgewichtung in Echtzeit | `portfolio-client.tsx` | MITTEL |

**Geplante Lösung:**
- Totalgewichtungs-Indikator: grün bei 100%, gelb bei <100%, rot bei >100%
- "Analyse starten"-Button disabled wenn total != 100% (oder > 100%)
- Hinweis: "Gewichtung: 87% — bitte auf 100% auffüllen"

### 1.5 Dashboard (`/`)

| Problem | Schwere |
|---------|---------|
| Zeigt nur aggregierte Stats, kein echtes Market-Bild | MITTEL |
| Keine Top-Performer / Top-Signals Übersicht | MITTEL |
| Macro-Widget könnte mehr Context geben | NIEDRIG |

**Geplante Lösung:**
- Top 3 BUY-Signale des letzten Runs prominent anzeigen (wenn vorhanden)
- Schnell-Links zu häufig genutzten Features
- Macro-Widget: SNB-Rate mit Trend anzeigen

### 1.6 Navigation & globale UX

| Problem | Datei | Schwere |
|---------|-------|---------|
| Profil-Badge nutzt Emoji (nicht idiomatic) | `nav-links.tsx:119` | NIEDRIG |
| Leere States bei vielen Seiten fehlen oder sind uninformativ | Diverse | MITTEL |
| Error-States zeigen Stack-Traces statt User-freundliche Messages | Diverse | MITTEL |

**Geplante Lösung:**
- Profil-Badge: Emoji entfernen, SVG-Icon stattdessen
- Konsequente Empty-States: jede Seite hat einen CTA wenn keine Daten
- Error-States: User-freundliche Deutsch-Texte, Retry-Button

### 1.7 Dead Code

Folgende Backend-Methoden/Funktionen existieren aber werden nie aufgerufen:
- `profile_classifier.py`: `classify_turn5()`, `classify_turn6()`, `classify_turn7()` — werden mit Overhaul angebunden
- `discovery_service.py`: `sector_affinity`-Filter (wegen Turn-4-Bug immer leer) — wird mit Overhaul nutzbar
- `discovery.py` Router: Constraint `le=4` blockiert alle höheren Turns — wird erweitert

---

## 2. Überarbeitete Feature-Spezifikation

### 2.1 Wizard — Vollständiger 7-Turn-Flow

```
Turn 1: Beruf (Freitext → Haiku klassifiziert financial_knowledge)
Turn 2: Anlageziel (housing / retirement / freedom / beat_savings)
Turn 3: Risiko-Reaktion (conservative / moderate / aggressive)
Turn 4: Brand-Auswahl (24 CH-Titel, 6 Kategorien → sector_affinity + known_tickers)
Turn 5: Anlagebetrag (under_10k / 10k_100k / over_100k)
Turn 6: Nachhaltigkeit (yes / indifferent / no)
Turn 7: Rendite-Präferenz (dividends / balanced / growth)
→ Reveal: Kompaktes Profil-Summary + empfohlene Titel
```

**Datentransfer Turn 4 (Fix):**
```typescript
// Statt {} muss brand_data mitgeschickt werden:
const brandData = Object.fromEntries(
  BRANDS.map(b => [b.ticker, { name: b.name, sector: b.category }])
);
await submitAnswer(sessionId, 4, selectedBrands, brandData);
```

**Backend-Erweiterung:**
```python
# discovery.py: AnswerRequest
turn: int = Field(ge=1, le=7)  # war: le=4

# Neue Handler-Cases für Turns 5–7:
elif turn == 5:
    profile = classifier.classify_turn5(body.answer)
elif turn == 6:
    profile = classifier.classify_turn6(body.answer)
elif turn == 7:
    profile = classifier.classify_turn7(body.answer)
```

### 2.2 Signal-Aggregation Fallback

```python
# signal_aggregation_service.py
if ml_score is None:
    # ML-Gewicht (0.35) auf Quant und Makro verteilen
    total_fallback = _QUANT_WEIGHT + _MACRO_WEIGHT  # 0.65
    effective_quant = _QUANT_WEIGHT / total_fallback  # ~0.69
    effective_macro = _MACRO_WEIGHT / total_fallback  # ~0.31
    composite = quant_score * effective_quant + macro_score * effective_macro
else:
    composite = quant_score * _QUANT_WEIGHT + ml_score * _ML_WEIGHT + macro_score * _MACRO_WEIGHT
```

### 2.3 Backtest Schema Fix

```python
# backtest.py
class BacktestSeriesResponse(BaseModel):
    prisma: list[float]    # war: list[Decimal]
    universe: list[float]  # war: list[Decimal]
    benchmark: list[float] # war: list[Decimal]
```

### 2.4 Portfolio Gewichts-Validierung

```typescript
// portfolio-client.tsx
const totalWeight = positions.reduce((sum, p) => sum + p.weight, 0);
const weightStatus = totalWeight === 100 ? 'ok' : totalWeight > 100 ? 'over' : 'under';
```

---

## 3. Implementierungsplan

### Phase A: Kritische Fixes (kein optionaler Code — alles broken ohne dies)
1. `discovery.py`: Turn-Constraint auf `le=7` + Turn 5-7 Handler
2. `start-client.tsx`: brand_data Fix + Turns 5-7 UI-Steps
3. `backtest.py`: Decimal → float

### Phase B: Wichtige Logik-Fixes
4. `signal_aggregation_service.py`: ML-Fallback Gewichtsnormierung
5. `portfolio-client.tsx`: Gewichts-Validierung

### Phase C: UX-Verbesserungen
6. `dashboard-client.tsx`: Top-Signale + Schnell-Links
7. `discover-client.tsx`: Bessere Stock-Erklärungen
8. `decision-client.tsx`: Default-Sort + BUY/HOLD/SELL Tooltip

### Phase D: Cleanup
9. Tote Branches archivieren (Referenz in CLAUDE.md)
10. Dokumentation aktualisieren

---

## 4. Dateien-Matrix (was welcher Agent ändert)

| Agent | Bereich | Dateien |
|-------|---------|---------|
| A | Wizard | `discovery.py`, `profile_classifier.py`, `start-client.tsx` |
| B | Signal + Backtest | `signal_aggregation_service.py`, `backtest.py` |
| C | Dashboard + Discover | `dashboard-client.tsx`, `discover-client.tsx`, `StatsCards.tsx` |
| D | Portfolio + UX | `portfolio-client.tsx`, `decision-client.tsx` |

---

## 5. Nicht im Scope dieses Overhauls

- `NEXT_PUBLIC_API_KEY` Security-Lücke (separates Security-Ticket)
- ML-1/ML-2 Feature-Mismatch (Training vs. Inference) — separate Analyse nötig
- Vollständige Test-Coverage (separate TDD-Session)
- PDF-Report Generator (bereits implementiert, kein Bedarf)

---

## 6. Erfolgskriterien

Nach Abschluss des Overhauls soll gelten:

1. **Wizard**: Alle 7 Turns erreichbar und funktional, brand_data wird korrekt verarbeitet, Profil-Reveal zeigt alle Dimensionen
2. **Backtest**: Charts zeigen echte Zahlen (kein NaN)
3. **Signale**: ML-Ausfall wird korrekt aufgefangen, Signale sind erklärbar
4. **Portfolio**: Gewichtungs-Fehler werden dem User klar kommuniziert
5. **Dashboard**: Zeigt sofort nützliche Information ohne Klick
6. **Jede Seite**: Hat einen Empty-State und einen Error-State

---

## 7. Offene Fragen (für nächste Session)

- Soll der Wizard-Flow bei Step 4 eine "Weiter ohne Auswahl"-Option anbieten?
- Sollen Turns 5–7 übersprungen werden können (Optional-Flow)?
- Wie soll das Profil nach Browser-Reload wiederhergestellt werden? (GET /discovery/status/{session_id} fehlt noch)
