# ADR 0004: Multi-Agent Pipeline — Framework & Operational Decisions

- **Status**: Accepted
- **Datum**: 2026-04-21
- **Kontext**: Schliesst die 7 "TBD"-Punkte der Multi-Agent-Pipeline-Spec
- **Referenz-Spec**: `docs/specs/2026-04-28-multi-agent-research.md` §15
- **Ergänzt**: ADR-0002 (LLM-Provider), ADR-0003 (Narrative Engine Ops)

## Kontext

Die Multi-Agent-Pipeline ist das komplexeste AI-Feature — 3 Agenten, RAG, News-Integration, Orchestrierung. Die Design-Spec hat 7 operationale TBDs, die vor Implementation entschieden sein müssen.

## Entscheidungen

### 1. Orchestrierungs-Framework

**Entscheidung**: **pure asyncio + Anthropic SDK direkt**. Keine LangGraph, kein CrewAI.

Evaluierte Optionen:

| Framework | Pro | Contra |
|---|---|---|
| **pure asyncio** (unsere Wahl) | transparenter Code (80 Zeilen), keine Extra-Dependency, volle Kontrolle, einfach zu präsentieren | etwas mehr Boilerplate |
| LangGraph | Batterien-inklusive Agent-Graphen, Streaming-Events | Framework-Lernkurve, Python-Wrapper um LangGraph-YAML, zusätzliche Lib-Updates | 
| CrewAI | deklarative Agent-Rollen, erinnert an Team-Metapher | noch jüngeres Ökosystem, Debugging aufwändiger |

**Gründe für asyncio**:
- Unsere Topologie ist simpel (2-fan-out → 1-merge) — Frameworks würden nicht beschleunigen
- In der Präsi können wir konkret durch unsere ~80 Zeilen Python-Orchestrierung führen, ohne Framework-Magie erklären zu müssen
- Weniger Dependencies = weniger Security-Updates, weniger CI-Drift-Risiken
- Die Teammitglieder B (AI-Engineer) kennt asyncio bereits aus FastAPI-Kontext

### 2. Default Top-N für Batch-Deep-Dive

**Entscheidung**: **10**.

- Bei durchschnittlich $0.048 pro Deep-Dive: **~$0.48 pro Batch** — bezahlbar
- 10 × 60 s ÷ Concurrency-3 ≈ **3.5 Minuten** pro Batch (akzeptabel für async Job)
- "Top-10" ist ein etabliertes Investment-Research-Konzept und intuitiv kommunizierbar
- Einstellbar via Query-Param (Range 3–20)

### 3. RAG-Corpus-Scope

**Entscheidung**: **5 US-Ticker initial**: AAPL, MSFT, GOOGL, NVDA, JPM.

Je 2 × 10-K + 2 × 10-Q = **20 Dokumente**, ~200 MB PDFs, ~4 000 Chunks, ~8 MB Embeddings in pgvector.

- Ingestion-Zeit: ~30 Min einmalig (SEC-EDGAR-Download + PDF-Parsing + Chunking + Voyage-Embedding)
- Einmaliger Kosten: ~$0.24 Voyage-Embedding
- Für **CH/EU-Aktien** gibt es keinen SEC-Corpus. Fundamentals-Agent fällt für diese Titel zurück auf "Kein Filing-Corpus für diese Region — nur Ranking-basierte Interpretation". Stretch-Goal: Manuelle Geschäftsbericht-PDF-Upload für Schweizer Titel.

Rationale für genau diese 5: Grosse US-Namen mit breitem News-Coverage, hohe Filing-Qualität, Wahrscheinlichkeit hoch, dass sie in Demo-Universen auftauchen.

### 4. Embedding-Modell

**Entscheidung**: **Voyage AI `voyage-3-large`** (2048 Dimensionen).

Evaluierte Alternativen:

| Modell | Kosten / 1 M Tokens | Dim | Kommentar |
|---|---|---|---|
| **Voyage voyage-3-large** (Wahl) | $0.12 | 2048 | Von Anthropic empfohlen; optimiert für RAG-Retrieval |
| OpenAI text-embedding-3-large | $0.13 | 3072 | Gute Qualität, aber OpenAI-Vendor-Bindung |
| Cohere embed-english-v3 | $0.10 | 1024 | Günstig, aber "english-only" — wir parsen teils mehrsprachige Filings |
| Open-weight (BGE, SentenceTransformers) | $0 | variabel | On-host Embedding; zusätzlicher Infrastruktur-Overhead, MVP-unkritisch |

Voyage-3-large bietet das beste Qualitäts-Kosten-Verhältnis und ist von Anthropic selbst als RAG-Partner empfohlen.

### 5. Job-Queue-Technologie

**Entscheidung**: **In-process asyncio** für MVP.

- Implementation: eigene `JobQueue`-Klasse mit Dict + asyncio.Task-Tracking
- Deep-Dive-Jobs leben im FastAPI-Prozess — bei Server-Restart gehen pending Jobs verloren
- Status-Storage in PostgreSQL, damit Frontend auch nach Page-Reload pollen kann

**Warum nicht Celery/Arq?**
- Extra Infrastruktur (Redis-Broker nötig) = zusätzlicher Render-Service
- Projektzeitraum limitiert — wir haben bessere Stellen zum Investieren
- Stretch-Goal dokumentiert: Migration auf Arq (leichter als Celery), wenn Deep-Dives >100/Tag werden

### 6. Synthesizer-Input: mit oder ohne Layer-1-Memo

**Entscheidung**: **Mit Layer-1-Memo, falls vorhanden**.

- Wenn für die Aktie im aktuellen ModelRun bereits ein Narrative-Memo existiert (Layer 1), wird es als zusätzlicher Input-Kontext an den Synthesizer-Agent gereicht
- Gibt dem Synthesizer einen "groben Rahmen" des Ranking-Narrativs — führt zu konsistenteren Dossiers über die Layers hinweg
- Extra-Tokens: ~500, vernachlässigbar (<$0.01 zusätzlich pro Deep-Dive)
- **Wenn kein Layer-1-Memo**: Synthesizer läuft ohne, kein Problem

### 7. Budget-Kontrolle bei Batch-Deep-Dive

**Entscheidung**: **Hard cap** — Abbruch bei Überschreitung, **keine** pro-Aktie-Granularität.

Konkret:
- Vor jedem Batch: aktueller Monats-Usage vs. Cap prüfen
- Wenn `(current + estimated_batch_cost) > 95% cap`: Batch-Abbruch mit erklärendem Error
- Keine teilweise Ausführung ("mache 5 von 10") — entweder alles oder nichts

**Gegen per-stock-Check**:
- Wäre komplex zu implementieren (Kosten werden erst nach LLM-Response sichtbar)
- Edge-Case: Aktie 7 von 10 sprengt das Budget → was passiert mit Aktie 8–10? Unklare Semantik
- Einfachheit über Granularität im MVP

## Konsequenzen

### Positiv

- **Implementations-ready**: alle 7 TBDs geschlossen → Phase 2 (Woche 3) kann ohne Design-Diskussion starten
- **Keine Framework-Abhängigkeit**: Updates von LangGraph/CrewAI können uns nicht brechen
- **Klares Kostenverhalten**: hard cap + single-Provider-LLM = vorhersagbares Budget

### Negativ

- **RAG-Corpus auf 5 US-Ticker limitiert** → CH/EU-Aktien bekommen nur Partial-Dossiers. Mitigation: Partial-Success ist explizit designed (Spec §11), nicht versteckt als Fehler
- **In-process Job-Queue**: bei Server-Crash gehen laufende Jobs verloren. Mitigation: Jobs sind idempotent, User kann erneut triggern; Status steht in DB, nicht im Prozess-Memory
- **asyncio ohne Framework**: eigene State-Machine-Logik — Testing-Overhead etwas höher, aber Code-Verständnis viel leichter

### Follow-up

- Implementation-Spec-Sektion 7.2 zeigt den exakten Orchestrierungs-Pseudocode — direkter Einstiegspunkt
- Bei wachsendem Interesse an CH-Firmen: Ingestion-Script für Schweizer Jahresberichte als Stretch-Goal
- Nach erstem echten Deep-Dive-Run: Observability-Daten (Cache-Hit-Rate, Real-Kosten, Latenzen) in AI-USAGE.md dokumentieren

## Referenzen

- Multi-Agent Pipeline Spec: `docs/specs/2026-04-28-multi-agent-research.md`
- Voyage AI Pricing: https://docs.voyageai.com/pricing
- pgvector: https://github.com/pgvector/pgvector
- ADR-0002 (LLM-Provider-Wahl), ADR-0003 (Narrative Engine Ops)
