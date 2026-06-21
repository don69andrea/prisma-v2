# PRISMA V3 — Verlaufs- & Entscheidungsprotokoll (Session 2026-06-21)

**Zweck:** Lückenlose Nachvollziehbarkeit dieser Arbeitssession — welche Entscheidungen getroffen
wurden, wie die ML-Trainings abliefen, welche Datenquellen geprüft/verworfen wurden, **warum wir
nicht weiterkommen**, und was die nächsten Schritte sind.
**Verwendung:** Master-Quelle für das spätere Begleitdokument an den Dozenten + interne Nachvollziehbarkeit.
**Verwandte Docs:** `PRISMA_V3_ANNOTATED_v33.md` (Plan/Spec), `PRISMA_V3_ML_BEFUNDE.md` (Testdetails),
`PRISMA_V3_NEUE_ANSAETZE_UND_DATEN.md` (Ausblick/Datenrecherche).

---

## 1 · Was in dieser Session passiert ist (Überblick)

1. Konzept-Challenge der V3-Spec → annotierte Spec (v33) mit Teil B–G.
2. Daten-Fundament gebaut (Phase 0–1): Migrationen, Seed-Pipeline, Universum, Fixes.
3. ML gebaut & getestet (Phase 2) — mehrere Durchläufe, alle sauber evaluiert.
4. **Zentraler Befund: kein robuster ML-Edge.** Ehrlich dokumentiert.
5. Strategischer Reset: ehrliche Rollen der Komponenten, neue Lösungsansätze recherchiert.
6. Datenquellen erschöpfend geprüft (Gratis + Hochschule + Kauf) — Ergebnis: keine leicht
   erreichbare bessere Fundamental-Quelle.

---

## 2 · Datenquellen — geprüft, entschieden, Sackgassen

**Ausgangsproblem:** Es gibt keine gratis, point-in-time-korrekten *historischen Schweizer
Fundamentaldaten*.

| Quelle | Befund | Entscheidung |
|---|---|---|
| **SimFin** (Free) | CH/EU-Coverage faktisch leer (eigener Adapter dokumentiert es); nur US brauchbar | Aus Hauptpfad raus; ML-Datensatz war kurz `simfin_us`, dann verworfen |
| **FMP** (Free) | US-only; CH erst im teuersten „Ultimate"-Tier | Nicht verwendet (kein Bezahl-Tier) |
| **EODHD** | Hat CH/SIX, aber Fundamentals = kostenpflichtig | Nicht gekauft |
| **yfinance** | Gratis, CH (`.SW`) + Krypto OHLCV; Fundamentals nur aktueller Snapshot (kein PIT) | ✅ Rückgrat für Kurse; Fundamentals nur für Anzeige/Quant-Score |
| **CryptoDataDownload** | Gratis Krypto-OHLCV-CSV seit 2017 | ✅ für Krypto-Seed |
| **Coin Metrics Community** | Gratis On-Chain (MVRV, Realized Cap …), v. a. BTC/ETH | ✅ für Krypto-Features |
| **Glassnode** | API = nur im Professional-Tier (paid); Free nur Web-Charts | Nicht nutzbar |
| **WRDS / CRSP / Compustat** | Akad. Goldstandard (PIT, survivorship-frei) — aber **FHNW hat es NICHT** (geprüft: nicht in der Datenbankliste) | Nicht verfügbar |
| **Orbis** (Bureau van Dijk) | FHNW hat es; CH-Firmenfinanzdaten. ABER: BvD→Moody's-Migration → Zugang leitet ins Moody's-Portal um, klassische Orbis-Suche nicht erreichbar; zudem Export-Limit + schwache Point-in-Time | An FHNW-Bibliothek delegiert; nicht projektkritisch |
| **SEC EDGAR** | Gratis, offiziell, PIT US-Fundamentals (Bulk) | Empfohlen für US-ML (noch nicht genutzt) |
| **FHNW weitere DBs** | ProQuest/ABI/Business Source = News/qualitativ (RAG-tauglich, kein Bulk-Feed); Scopus/WoS/EconLit = für den Bericht | Als Ergänzung notiert |

**Daten kaufen?** Analysiert: lohnt nicht. Kauf verbessert Coverage, nicht die fundamentale
Schwierigkeit (Returns sind effizient). Einzig erwägbar: 1 Monat EODHD (~$20–40) für einen
einmaligen CH-Fundamental-Seed, dann kündigen — aber nur falls die Anzeige-Qualität wirklich
besser sein muss. Aktuell **nicht nötig**.

**Fazit Daten:** Kostenlose Pipeline (yfinance + CryptoDataDownload + Coin Metrics + Makro) ist
das Rückgrat. Keine leicht erreichbare bessere Fundamental-Quelle. **Wichtig:** Das ML nutzt
ohnehin keine Fundamentals (siehe §3), daher ist das kein Blocker.

---

## 3 · ML-Trainings — wie sie liefen und was rauskam

Volldetails inkl. Tabellen in `PRISMA_V3_ML_BEFUNDE.md`. Hier die Essenz aller Durchläufe.

**Methodik (durchgängig):** Features point-in-time aus der DB; Purged & Embargoed CV bzw.
strikter Walk-Forward; Pflicht-Baselines (Mehrheitsklasse/Momentum/Buy-and-Hold/exposure-matched);
Netto nach Transaktionskosten.

| # | Durchlauf | Setup | Ergebnis |
|---|---|---|---|
| 1 | **Aktien Quantil** (30d Excess vs SMI) | 30 Titel, monatlich, N=3654, Purged CV | **Kein Edge** — schlägt konstante Quantil-Baseline nicht |
| 2 | **Krypto v1** (7d direktional + vs BTC) | 6 Coins, wöchentlich, N=2430 | Schlägt Mehrheitsklasse, **verliert gegen Momentum & Buy-and-Hold** |
| 3 | **Krypto v2** (30d, täglich, MVRV) | 6 Coins, N=16.686, Purged CV | Sah gut aus (Calmar 1.81) — **war In-Sample-Optimismus** (siehe #5) |
| 4 | **Krypto strikter Walk-Forward** | täglich, Expanding-Window, exposure-matched | **Kein robuster Timing-Skill** — Calmar 0.35 < Exposure-Matched 0.66; echter Skill nur in 1/4 Folds (2023–24) |
| 5 | **Phase-3 Kombi-Signal** (quant+ml+macro) | monatlich, OOS 2019–26, ml=neutral (Modell nicht auf main) | Aktien Sharpe −0.35 vs SMI 0.43; Krypto Sharpe 0.06 vs BTC 0.61 → **quant+macro allein kein Edge**; N=25 statistisch machtlos |

**Die zentrale wissenschaftliche Lehre — In-Sample-Optimismus:**
Durchlauf 3 (Purged CV) ergab Calmar **1.81** und sah nach echtem Edge aus. Im strikten
Walk-Forward (Durchlauf 4) kollabierte derselbe Mechanismus auf Calmar **0.35** — *unter* der
Exposure-Matched-Baseline. Ursache: Die Purged-CV-Folds hatten über Expanding-Window indirekt
Zugang zu Crash-Daten (2022); das Modell „kannte" Crash-Merkmale, die es OOS nicht gekannt hätte.
**Erst der strikte Walk-Forward zeigt die Wahrheit.** Das ist der eigentliche Befund — und genau
der Fehler, den naive „wir schlagen den Markt"-Projekte machen.

---

## 4 · Warum wir nicht weiterkommen (ehrliche Diagnose)

1. **Das Ziel ist fast unmöglich.** 7–30-Tage-Returns liquider Assets sind auf effizienten Märkten
   kaum vorhersagbar. (7d statt 30d hilft nicht — kürzer = verrauschter + höhere relative Kosten;
   getestet in Durchlauf 2.)
2. **Uns fehlt die richtige Information.** Nur Preis/Technik + Makro + Fear&Greed + MVRV. Echten
   Edge holt man aus Daten, die andere nicht nutzen (echte PIT-Fundamentals, Analystenrevisionen,
   News-Sentiment in der Breite) — die hatten wir nie, und sie sind gratis/leicht nicht beschaffbar.
3. **Zu kleine Stichprobe.** Wenige Assets, überlappende Fenster → wenig unabhängige Beobachtungen.
4. **Falsches Ziel-Framing.** Return-*Höhe* ist die härteste Größe; andere Ziele (Volatilität,
   Ranking, Events) sind lernbarer.

**Kurz:** Wir haben das schwerste Problem mit der dünnsten Information angegriffen. Nicht der
Modell-Code ist schuld, sondern *was* vorhergesagt wird und *womit*.

---

## 5 · Konsequenzen & ehrliche Positionierung des Produkts

- **ml_score in Produktion: aus/minimal.** Keine Alpha-/Timing-Behauptung im UI.
- **Das ML bleibt dokumentierte Forschungskomponente** (saubere Pipeline + ehrliche
  Negativ-Evaluation) → erfüllt die „ML-basiert"-Vorgabe voll und zeigt Methodik-Kompetenz.
- **Produktwert + Note** kommen aus: angereicherter Multi-Source-Datensicht, Agentic AI, RAG,
  fundamentalem Quant-Score (Decision-Support), visueller Chart-Analyse/Explainability.
- **Projektvorgaben (FHNW BI):** weiterhin **voll erfüllt** — Agentic ✓, ML-basiert ✓ (inkl.
  ehrlicher Evaluation), RAG ✓, Datensatz/Historisch+Live ✓. Der Negativbefund ist akademisch eine
  Stärke, kein Mangel.

---

## 6 · Build-Status (Phasen)

| Phase | Inhalt | Status |
|---|---|---|
| 0 | Daten-Fundament, Seed-Pipeline, Migrationen 0031–0035, Coverage-Gate | ✅ gemergt (main) |
| 1 | PIT-Universum (0036, 30 Titel + delistete inkl. CSGN), FIX-01/03/06 | ✅ gemergt (main) |
| 2 | ML-Pipeline (Quantil + Krypto v1/v2/WF), ehrliche Evaluation | ⚠️ teils auf Feature-Branches (nicht alle gemergt) |
| 3 | Kombi-Signal + Backtest-Engine + signal_outcomes | ⚠️ Branch `feature/prisma-v3-phase-3` (nicht gemergt) |
| 4 | Dashboard + Explainability/Chart-Analyse + Compliance | ⬜ offen |

**Prozess-Lehre (dokumentieren):** Es gab eine Migrations-Drift (0036 auf Render-DB angewendet,
aber nicht in main, weil PR #285 versehentlich in einen Feature-Branch statt main gemergt wurde;
zusätzlich ein direkter Push auf main unter Umgehung der Branch Protection). Beides sauber
aufgelöst (PR #287/#288). **Lehre:** Branch Protection „Include administrators" aktivieren; PRs
immer gegen `main` öffnen.

---

## 7 · Nächste Schritte (empfohlen)

1. **Vol-Forecasting-Experiment** — Volatilität ist (anders als Returns) gut vorhersagbar; liefert
   endlich einen *positiven* ML-Befund + den Risiko-/Sizing-Baustein. Gratis, hohe Erfolgschance.
2. **Dashboard** — macht die vorhandene Arbeit sichtbar/benotbar; Chart-Analyse als Explainability.
3. Optionale ML-Hebel (siehe `NEUE_ANSAETZE`): Meta-Labeling, News-RAG-Features, Faktor-Modell.
4. SEC EDGAR für US-Fundamentals, falls ernsthaftes Fundamental-ML gewünscht.

---

## 8 · Was auf GitHub aktualisiert werden muss (Doku-Sync)

- `docs/PRISMA_V3_ANNOTATED_v33.md` → **mit Teil G6** (war auf main veraltet).
- `docs/PRISMA_V3_ML_BEFUNDE.md` → **mit Durchlauf 4 + In-Sample-Optimismus** (war veraltet).
- `docs/PRISMA_V3_NEUE_ANSAETZE_UND_DATEN.md` → **neu hinzufügen**.
- `docs/PRISMA_V3_VERLAUF_UND_ENTSCHEIDUNGEN.md` → **dieses Dokument, neu**.
- Optional: die detaillierten Eval-Dateien von den Feature-Branches (`ml_eval_crypto*.md`,
  `signal_backtest.md`) nach `docs/` konsolidieren für volle Nachvollziehbarkeit.

---

*PRISMA V3 — Verlaufs- & Entscheidungsprotokoll · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
