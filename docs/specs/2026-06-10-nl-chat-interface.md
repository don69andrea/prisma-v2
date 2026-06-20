# Spec: Conversational NL Interface (PRISMA Chat)

**Issue:** #72 (to be created)
**Date:** 2026-06-10
**Author:** Andrea Petretta
**Status:** Planned

---

## Ziel

Floating Chat-Panel auf allen PRISMA-Pages — Nutzer stellen Fragen in Deutsch/Englisch, Claude antwortet mit echten PRISMA-Daten via Tool Use. Macht Self-Service Analytics per Natursprache möglich.

---

## Nicht-Ziele

- Multi-User Chat / geteilte Sessions
- Chat-History persistiert über Browser-Reload hinaus (nur In-Memory via Redis, 15min TTL)
- Voice Input
- Claude als genereller Finanz-Berater (nur PRISMA-eigene Daten, kein externen Websearch)

---

## Architektur

### Backend — `ChatService`

**Neue Datei:** `backend/application/services/chat_service.py`

**Claude-Konfiguration:**
- Modell: `claude-sonnet-4-6` (Research-Synthese)
- Prompt-Caching: `cache_control: ephemeral` auf System-Prompt (ändert sich selten)
- Streaming: `stream=True`, SSE-Events an Frontend

**Tool-Definitionen (über bestehende Services):**

```python
tools = [
    {
        "name": "search_stocks",
        "description": "Sucht Aktien im PRISMA-Universum nach Name oder Ticker",
        "input_schema": {"query": str, "exchange": Optional[str]}
    },
    {
        "name": "filter_stocks",
        "description": "Filtert Aktien nach Kriterien: Signal, 3a-Eignung, Score-Threshold",
        "input_schema": {
            "signal": Optional[Literal["BUY", "HOLD", "SELL"]],
            "eligible_3a": Optional[bool],
            "min_score": Optional[float],
            "universe": Optional[str]
        }
    },
    {
        "name": "get_factsheet",
        "description": "Detaillierte Quant-Scores, ML-Prediction und Fundamentaldaten für einen Ticker",
        "input_schema": {"ticker": str}
    },
    {
        "name": "get_macro_context",
        "description": "Aktueller SNB-Entscheid, CHF/EUR, Inflation CH",
        "input_schema": {}
    },
    {
        "name": "compare_stocks",
        "description": "Vergleicht zwei Ticker anhand Quant-Scores und ML-Signal",
        "input_schema": {"ticker_a": str, "ticker_b": str}
    },
    {
        "name": "get_ranking",
        "description": "Top-N Aktien aus einem Universum nach gewichtetem Score",
        "input_schema": {"universe": Optional[str], "top_n": int}
    }
]
```

**System-Prompt:**
```
Du bist PRISMA Assistant — ein präziser, datengetriebener Finanz-Assistent.
Du hast Zugriff auf das PRISMA-Universum (SMI/SMIM/SPI + US-Aktien).
Antworte immer auf Basis der Tool-Ergebnisse, nie aus deinem Trainingswissen über Preise.
Sprache: Deutsch bevorzugt, Englisch wenn Nutzer auf Englisch fragt.
Disclaimer: "Keine Anlageberatung" bei konkreten Kauf-/Verkaufsempfehlungen.
```

**Session-Management:**
- `session_id` = UUID, in Redis mit 15min TTL
- Max 10 Turns pro Session (danach: *"Session zurücksetzen?"*)
- `GET /api/v1/chat/session` → neue Session-ID
- `POST /api/v1/chat/{session_id}` → Message senden, SSE streamen

### API — SSE Streaming

```
POST /api/v1/chat/{session_id}
Body: { "message": str }
Response: text/event-stream

Events:
  data: {"type": "token", "content": "Nestlé "}
  data: {"type": "token", "content": "hat ein "}
  data: {"type": "tool_call", "tool": "get_factsheet", "input": {"ticker": "NESN.SW"}}
  data: {"type": "tool_result", "ticker": "NESN.SW", "signal": "BUY"}
  data: {"type": "done"}
```

### Frontend — Floating Chat Drawer

**Trigger:**
- Floating Button bottom-right: `64px` Circle, PRISMA-Prisma-Icon, Neon-Puls-Ring (CSS animation)
- Badge: Zahl wenn ungelesene Antworten (Session-basiert)

**Drawer:**
- Öffnet von rechts: `width: 420px`, `height: 70vh`, `backdrop-blur(20px)`, `background: rgba(10,10,20,0.85)`
- Rand: 1px Gradient-Border (Lila → Blau)
- Header: *"PRISMA Assistant"* + Reset-Button (Mülleimer-Icon)

**Messages:**
- User-Bubbles: rechts, solid `bg-purple-900/50`, rounded
- PRISMA-Bubbles: links, Gradient-Border, `bg-black/60`
- Streaming-Cursor: `█` blinkt am Ende während Claude schreibt
- Tool-Use-Indikator: während Tool läuft — *"Fetching NESN.SW data..."* in Grau italic

**Inline-Ticker-Cards:**
- Wenn Claude einen bekannten Ticker nennt (Regex: `/\b[A-Z]{1,4}\.SW\b|\b[A-Z]{2,5}\b/`), automatisch als klickbarer Chip gerendert
- Hover auf Chip → Mini-Factsheet-Popover (Signal-Badge + Top-Score)
- Klick → navigiert zu `/stocks/{ticker}`

**Suggested Queries (kontextuell):**
- Auf `/rankings`: *"Was sind die Top-5 SMI BUY-Signale?"*, *"Erkläre den Sweet-Spot-Algorithmus"*
- Auf `/stocks/[ticker]`: *"Ist {ticker} für 3a geeignet?"*, *"Vergleich mit Nestlé"*
- Auf `/portfolio/simulator`: *"Welche Allocation maximiert den Sharpe?"*

---

## Fehlerbehandlung

- Tool-Call schlägt fehl → Claude bekommt Error-Message, formuliert Antwort ohne diese Daten
- Stream-Timeout (30s) → Frontend zeigt *"Timeout — bitte nochmals versuchen"*
- Rate-Limit → 429 mit Retry-After Header

---

## Tests

- Unit: `test_chat_service.py` — Tool-Dispatch auf korrekte Services, Session-TTL
- Unit: Tool-Result-Serialisierung (keine internen Objekte im Claude-Kontext)
- E2E (Playwright): Chat öffnen, Query stellen, Antwort erscheint (gemocked)

---

## Akademischer Impact

Self-Service Analytics via Natursprache ist die Zukunft von BI-Tools (Gartner Trend 2025/26). Zeigt die AI-Integration von PRISMA von ihrer intuitivsten Seite — live in der Demo besonders wirkungsvoll.
