# LLM-Universe-Wizard — Design

**Datum:** 2026-05-28
**Issue:** Backlog (Capstone-Demo-Feature)
**Status:** Draft — Mini-Variante (Single-Turn)

## Ziel

Ein User beschreibt in einem Free-Text-Feld, welches Universe er anlegen möchte (z.B. *"Tech-Heavy mit Fokus Halbleiter"*, *"Banks mit Dividende"*). Das System ruft Claude Haiku, der unter Vorgabe des aktuellen Stock-Katalogs einen passenden Vorschlag (Name + Region + Tickers + Begründung) generiert. Der Vorschlag landet als Pre-Filled Form, der User kann editieren und mit dem existing `POST /api/v1/universes` speichern.

Demo-Story: *"PRISMA generiert dir nicht nur Rankings — es hilft dir auch, das richtige Aktien-Universum zu definieren."*

## Nicht-Ziele

- Multi-Turn-Konversation (LLM stellt Rückfragen) — kommt evtl. als V2 wenn Zeit
- Auto-Seeding von unbekannten Tickers — LLM darf NUR aus dem Stock-Katalog wählen
- DE/EN-Toggle — Wizard akzeptiert User-Input auf Deutsch, LLM antwortet auf Deutsch
- LLM-Cost-Tracking pro Wizard-Call separat — geht in den existing Cost-Logger
- Edit-Funktionalität für bestehende Universen — nur Neuanlage
- Multi-Stock-Lookup über externe Provider — nur lokaler Katalog

## Architektur

### Backend

**Neuer Endpoint:** `POST /api/v1/universes/suggest`

**Request:**
```python
class UniverseSuggestionRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=500)
```

**Response:**
```python
class UniverseSuggestionResponse(BaseModel):
    name: str
    region: str
    tickers: list[str]
    reasoning: str  # 1-2 Sätze, warum diese Auswahl
    available_tickers: list[str]  # gefilterte Liste für transparenz
```

**Implementation Layer:**
- `backend/application/services/universe_suggestion_service.py` — neuer Service
  - Dependencies: `LLMClient`, `StockService` (für Katalog-Lookup)
  - Method: `async def suggest(description: str) -> UniverseSuggestion`
- `backend/domain/entities/universe_suggestion.py` — neue Dataclass (frozen)
- `backend/interfaces/rest/routers/universes.py` — neuer Endpoint dazu
- `backend/interfaces/rest/schemas/universe.py` — Pydantic-Schemas

**Prompt-Design** (Jinja2-Template wie existing Memo-Prompts):

System-Prompt (cached via `cache_control: ephemeral`):
```
Du bist ein quantitativer Analyst, der Aktien-Universen für PRISMA empfiehlt.

VERFÜGBARE TICKERS (NUR DIESE NUTZEN):
{% for ticker in available_tickers %}
- {{ ticker }}: {{ stock_names[ticker] }} ({{ stock_sectors[ticker] }})
{% endfor %}

Regeln:
- Wähle 3-12 Tickers aus der Liste oben
- Tickers MÜSSEN aus der Liste oben kommen (sonst werden sie verworfen)
- Schlage einen prägnanten Universe-Namen vor (max 40 Zeichen)
- Region: "US" wenn US-Stocks, "Global" wenn gemischt
- Begründung: 1-2 Sätze auf Deutsch, fokussiert auf Auswahlkriterien
```

User-Prompt:
```
Anfrage: {{ description }}

Liefere die Empfehlung als JSON.
```

**LLM-Call mit Structured Output** (Pydantic-Schema via `response_format`):
- Modell: `claude-haiku-4-5`
- Max-Tokens: 500
- Feature-Flag: `universe_suggestion` (für Cost-Logging)
- Cache: System-Prompt mit Stock-Katalog (5-min TTL — Standard)

**Validation post-LLM:**
- Tickers werden gegen aktuellen Katalog gefiltert
- Wenn weniger als 2 valide Tickers übrig → 422 mit Fehlermeldung
- Wenn `name` leer → fallback auf `"Auto-Universe-{timestamp}"`

### Frontend

**Neue Page:** `frontend/app/universes/wizard/page.tsx`

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ ← Zurück zu Universen                           │
│                                                 │
│ Universe mit KI generieren                      │
│ Beschreibe, was du suchst — Claude wählt aus    │
│ dem verfügbaren Stock-Katalog passende Tickers. │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Beschreibung:                               │ │
│ │ ┌─────────────────────────────────────────┐ │ │
│ │ │ z.B. "Tech-Stocks aus den USA, Fokus   │ │ │
│ │ │       Halbleiter und Cloud"             │ │ │
│ │ └─────────────────────────────────────────┘ │ │
│ │                                             │ │
│ │ [✨ Vorschlag generieren]                    │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ── nach Generation ──                           │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Begründung (KI-generiert)                   │ │
│ │ "Die Auswahl fokussiert auf US-Halbleiter   │ │
│ │  mit starkem Wachstum..."                   │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ┌─────────────────────────────────────────────┐ │
│ │ Name: [Tech-Halbleiter-US                ]  │ │
│ │ Region: [US                              ]  │ │
│ │ Tickers (komma-separiert):                  │ │
│ │ [NVDA, AMD, INTC, MSFT                   ]  │ │
│ │                                             │ │
│ │ [Erstellen]  [Vorschlag verwerfen]          │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**Komponenten:**

- `frontend/app/universes/wizard/page.tsx` — Top-Level-Page
- `frontend/app/universes/wizard/wizard-form.tsx` — Client-Component mit dem Form
- `frontend/lib/api/universes.ts` — neue Function `suggestUniverse(description: string)`

**States:**
- `idle`: Eingabe-Feld + Generate-Button
- `generating`: Spinner während LLM-Call (1-3s)
- `result`: Begründung + Pre-Filled Form sichtbar
- `error`: Error-Message + Retry-Button
- `submitting`: Form-Submit läuft, Spinner auf Erstellen-Button

**Tanstack Query:** `useMutation` für Suggest-Call (nicht cachen — User will frische Ideen pro Klick).

## Datenfluss

```
User schreibt: "Halbleiter-Stocks"
  ↓
[✨ Vorschlag generieren] click
  ↓
POST /api/v1/universes/suggest { description: "Halbleiter-Stocks" }
  ↓ Backend:
  1. StockService.list_stocks() → 13 Tickers + Names + Sectors
  2. LLMClient.complete(system_prompt + user_prompt) → JSON
  3. Parse + validate against catalog → filtered tickers
  4. Return UniverseSuggestionResponse
  ↓ Frontend:
  Setze form fields: name, region, tickers (joined comma), reasoning
  Render result section
  ↓ User editiert ggf., klickt "Erstellen"
  ↓
POST /api/v1/universes { name, region, tickers } (existing endpoint)
  ↓ Router → /universes (success-page)
```

## Edge Cases

- **Empty description (< 3 chars):** Pydantic-Validation → 422, Form zeigt Fehlermeldung
- **LLM-Fehler (Timeout/Rate-Limit):** Error-Card mit Retry-Button
- **LLM gibt < 2 valide Tickers (alle aus Katalog gefiltert):** 422 mit Hinweis "Bitte konkreter beschreiben oder andere Anfrage"
- **LLM gibt invalid JSON:** Pydantic-Parsing-Fehler → 502 mit Hinweis
- **User-Description in Englisch:** Wir lassen das laufen — Haiku versteht beide Sprachen
- **Vorschlag verwerfen:** Form-State resetten, zurück zu idle
- **Stock-Katalog leer (Edge-Case):** Backend gibt 503 "Kein Stock-Katalog verfügbar" zurück

## Testing

**Backend Unit-Tests:**
- `test_universe_suggestion_service.py`:
  - Happy path: gibt valide Suggestion mit 3+ Tickers zurück
  - Filter: LLM-Response mit nicht-vorhandenen Tickers → werden gefiltert
  - 422-Path: weniger als 2 valide Tickers nach Filter
  - LLM-Fehler: wirft entsprechende Exception

**Backend Integration-Test:**
- `test_universes_endpoint.py` (existing): neuer Test für `POST /api/v1/universes/suggest`
  - 200 mit fake LLM-Client
  - 422 mit zu kurzer Description
  - 422 mit Stub der nur unbekannte Tickers vorschlägt

**Frontend Unit-Tests:**
- `wizard-form.test.tsx`: 
  - State-Übergänge (idle → generating → result)
  - Generate-Button disabled wenn Description < 3 chars
  - "Vorschlag verwerfen" reset's State

**Manual:**
- LLM-Wizard mit verschiedenen Beschreibungen testen
- Vorschlag editieren + erstellen → Universe erscheint in `/universes`
- Run darauf starten → funktioniert

## Build Sequence

1. Backend: Domain-Entity `UniverseSuggestion` + Service + Tests
2. Backend: REST-Schema + Router-Endpoint + Integration-Test
3. Frontend: `suggestUniverse` API-Function + Tests
4. Frontend: Wizard-Page + Form-Component + Tests
5. Manual Verification

## LLM-Cost-Abschätzung

Pro Wizard-Call (Haiku 4.5):
- System-Prompt: ~500 Tokens (cached nach 1. Call)
- User-Prompt: ~50 Tokens
- Response: ~200 Tokens
- Cost: $0.0008 (Haiku) — vernachlässigbar

Bei 100 Demo-Calls = ~$0.08. Cost-Cap im LLMClient greift trotzdem.

## Abgrenzung zu existierenden Specs

- **Narrative-Engine-Specs** (multiple): Nutzen LLMClient.complete(). Wizard nutzt denselben Pattern + Cost-Logger.
- **Memo-Drilldown** (`2026-05-28-memo-drilldown`): Erzeugt KI-Memos für *gerankte Stocks*. Wizard erzeugt KI-Vorschläge für *Universe-Definition*. Beide nutzen Claude, beide gleiches Pattern (Pydantic-Output + Cost-Tracking).
- **Dashboard-Stats**: Zeigt Stock-Count — wenn neue Stocks via Wizard-Universes hinzukommen, wächst der Counter. Demo-Synergie.
