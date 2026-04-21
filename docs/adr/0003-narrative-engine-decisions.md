# ADR 0003: Narrative Engine — Operational Decisions

- **Status**: Accepted
- **Datum**: 2026-04-21
- **Kontext**: Schliesst die 6 "TBD"-Punkte aus der Narrative Engine Spec
- **Referenz-Spec**: `docs/specs/2026-04-28-narrative-engine.md` §13
- **Ergänzt**: ADR-0002 (LLM-Provider-Wahl)

## Kontext

Die Design-Spec der Narrative Engine (Layer 1) markiert 6 operationale Entscheidungen als "TBD". Damit die Implementation startklar ist, werden diese hier einzeln entschieden und begründet.

## Entscheidungen

### 1. Sync vs. Async Batch-Generierung

**Entscheidung**: **Sync** für MVP.

- Bei Top-N=20 und durchschnittlich 2.5 s pro Memo (Sonnet + Caching) ≈ **50 s pro Batch**
- HTTP-Request mit 60–90 s Timeout tolerierbar
- Frontend zeigt einen Progress-Indikator (Polling pro fertigem Memo via optional GET-Endpoint)
- **Async Job-Queue** (Celery/Arq) bleibt als Stretch dokumentiert, kommt wenn Batches zu lang werden oder mehrere parallel laufen

### 2. Auto-Trigger nach Ranking-Run oder manuell?

**Entscheidung**: **Manuell** (User klickt "Memos generieren" im Frontend).

- Verhindert unbeabsichtigte Kosten (jeder Ranking-Run würde sonst automatisch ~$0.20 verbrennen)
- Portfolio-Manager entscheidet bewusst, wann Tiefe gewünscht ist
- In der Präsi lehrreicher: "Wir zeigen den User-Intent explicit, nicht als Magic-Hintergrundverhalten"

### 3. Memo-Sprache: nur DE oder DE+EN

**Entscheidung**: **Nur Deutsch** im MVP, Architektur bleibt bilingual-fähig.

- Parameter `lang: Literal["de", "en"] = "de"` im Service-Interface
- EN-Prompt-Template als Stub (leere Datei) committet
- Aktivierung von EN wäre <2 h Arbeit wenn UI-i18n kommt (Stretch-Goal)

### 4. Default Top-N pro Batch

**Entscheidung**: **20**.

- Passt zum "Top-Quartile-Fokus" der meisten Portfolio-Manager
- Batch-Kosten bei 20: ~$0.19 — vertretbar
- Parameter bleibt einstellbar (5–50) über API-Query-Param

### 5. Memo-Recycling vs. Neu-Generierung

**Entscheidung**: **Neu generieren bei jedem Run**, alte Memos bleiben in DB persistiert.

- Neue Rankings → potenziell andere Story → altes Memo wäre irreführend
- Historie-Erhalt ermöglicht spätere Vergleiche ("Wie hat sich die Memo-Einschätzung dieser Aktie über die letzten 3 ModelRuns entwickelt?")
- Storage-Cost ist trivial (ein Memo ~2 KB JSON)
- **Force-Regenerate**-Endpunkt (`POST /memos/{stock_id}/{run_id}/regenerate`) erlaubt explizit Neuerzeugung für bestehende Runs

### 6. Budget-Kontrolle: hart oder weich

**Entscheidung**: **Zweistufig** — weich (Warning) + hart (Verweigerung).

| Schwelle | Verhalten |
|---|---|
| 80% des Monats-Caps | Log-Warning + Banner im Frontend "vorsichtig mit weiteren Batches" |
| 95% des Monats-Caps | Service verweigert neue Batches (HTTP 429 mit erklärender Message) |
| 100% (Anthropic-Seite) | API lehnt alles ab — letzte Verteidigung |

Check passiert **vor** jedem Batch via `GET /v1/organizations/usage`. Bei API-Ausfall des Usage-Endpoints: Fail-Open (Batch läuft trotzdem, Log-Warning). Alternative wäre Fail-Closed, aber das würde einen Anthropic-Incident zu unserem Incident machen.

## Konsequenzen

### Positiv

- **Klare Implementations-Vorlage**: kein TBD mehr offen → Developer kann direkt nach Spec coden
- **Kostenkontrolle**: zweistufige Budget-Policy macht "Runaway-Batch"-Szenarien unmöglich
- **Historien-Erhalt**: persistierte alte Memos ermöglichen zukünftige Analyse-Features

### Negativ

- **Sync** limitiert Batch-Grösse (bei 50+ Memos könnte Timeout passieren) — bei Bedarf muss auf Async umgestellt werden (dokumentiert als Stretch)
- **Manuelle Triggerung** bedeutet einen Extra-Klick — nutzerfreundlichkeitsmässig minimal, aber intentional

### Follow-up

- Implementation in Phase 2 (Woche 2) gemäss Spec §14 Akzeptanz-Kriterien
- Evaluation nach erstem produktiven Batch: war 20 Memos die richtige Zahl? Sync ausreichend?
- Falls Sync-Timeouts auftreten: Async-Migration-Plan (ADR ergänzen)

## Referenzen

- Narrative Engine Spec: `docs/specs/2026-04-28-narrative-engine.md`
- ADR-0002 (LLM-Provider-Wahl)
