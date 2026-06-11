# Spec: Conversational Discovery Engine — R2.4-1

**Task:** R2.4-1
**Date:** 2026-06-11
**Author:** Andrea Petretta
**Branch:** `feature/andrea-discovery-engine`
**Status:** Draft — awaiting approval before implementation

---

## Ziel

Der `/start`-Flow ist PRISMA V2's erster Touchpoint für neue Nutzer. In maximal 5 Konversationsrunden wird ein vollständiges `InvestorProfile` ermittelt, das anschliessend die personalisierten Aktienempfehlungen (Discovery Engine) steuert.

Der Flow ersetzt den bestehenden "direkten Profil-Speicher"-Ansatz (`POST /api/v1/profile`) mit einem geführten, konversationellen Onboarding. Das Ergebnis ist ein ausgefülltes `InvestorProfile` mit `confidence_score >= 0.6` und `onboarding_complete = True`.

**Demo-Story:** *"PRISMA fragt dich, wer du bist — und zeigt dir dann genau die Aktien, die zu dir passen."*

---

## Kontext & Abhängigkeiten

### Was Aurelius bereits gebaut hat

**Branch `feature/aurelius-investorprofile` (R2.3-5 + R2.3-6, DONE):**
- `backend/domain/entities/investor_profile.py` — `InvestorProfile` Pydantic-Entity (Turns 1–4, `confidence_score`, `onboarding_complete`)
- `backend/application/services/discovery_service.py` — `get_personalized_universe()` gibt gefilterte `SwissStock`-Liste zurück
- `backend/infrastructure/persistence/` — SQLAlchemy-Model + Repository für `InvestorProfile`
- `backend/alembic/versions/0019_create_investor_profiles.py` — DB-Migration
- REST-Endpunkte: `POST /api/v1/discovery/session`, `POST /api/v1/discovery/answer`, `POST /api/v1/discovery/complete`
- Schemas: `SessionResponse`, `AnswerRequest`, `AnswerResponse`, `CompleteRequest`, `CompleteResponse`

**Branch `feature/aurelius-discovery-agent` (R2.4-3, DONE):**
- `backend/application/services/profile_classifier.py` — `ProfileClassifier` mit Haiku-Klassifikation für Turn 1 (Beruf → `financial_knowledge` + `sector_hint`), regelbasiert für Turns 2–4
- `backend/application/agents/macro_agent.py` — `MacroIntelligenceAgent` mit `MacroScore` Pydantic-Output
- `backend/tests/unit/application/test_profile_classifier.py` — Unit-Tests für Klassifikation
- Konfidenz-Berechnung: `calculate_confidence(profile)` gibt `float` 0.0–1.0

### Was R2.4-1 (Andrea) liefert

R2.4-1 schliesst die **Backend-Brücke** zwischen den Turn-Definitionen (Aurelius) und dem **Frontend-Chat-UI** (Helin, R2.4-2) und ergänzt:

1. **Turn-5 Definition** — der fünfte und letzte Onboarding-Turn (Makro-Kontext-Präferenz), der bei Aurelius' Turns 1–4 noch fehlt
2. **Session-Management-Erweiterung** — `GET /api/v1/discovery/question/{turn}` liefert die nächste Frage im Klartext inkl. Antwort-Optionen
3. **Next-Question-Engine** — Backend-Logik, die basierend auf Konfidenz-Score und aktuellem Turn die nächste Frage selektiert (oder Completion triggert)
4. **Frontend: Next.js 14 Chat-Dialog** — `/start`-Page mit stufenweisem Chat-UI, das die 5 Turns als Chat-Nachrichten darstellt

---

## Entitäten / Schema-Änderungen

### Keine DB-Schema-Änderung erforderlich

`InvestorProfile` in `0019_create_investor_profiles.py` ist bereits vollständig. R2.4-1 erweitert nur das bestehende Schema um Turn-5-Felder via **optionale Pydantic-Felder** (keine neue Migration).

### InvestorProfile — Turn-5-Erweiterung (Pydantic-only)

Ergänzung in `backend/domain/entities/investor_profile.py`:

```python
# Turn 5 — Makro-Sensitivität (neu, optional)
macro_sensitivity: Literal["snb_focus", "global_macro", "ignore"] | None = None
```

Dieses Feld wird von Aurelius' `ProfileClassifier.calculate_confidence()` bereits berücksichtigt, sobald es gesetzt ist — kein Interface-Break.

### Neue Pydantic-Schemas (in `backend/interfaces/rest/schemas/investor_profile.py`)

```python
class QuestionOption(BaseModel):
    value: str       # Maschinenlesbar (z.B. "conservative")
    label: str       # Anzeigetext auf Deutsch (z.B. "Sicherheit über Rendite")
    emoji: str | None = None  # Optionales Icon für Frontend

class QuestionResponse(BaseModel):
    turn: int                           # 1–5
    question: str                       # Fragetext auf Deutsch
    input_type: Literal["text", "single_choice", "multi_choice"]
    options: list[QuestionOption] | None = None  # None bei input_type="text"
    hint: str | None = None             # Optionaler Hilfstext unter der Frage

class AnswerRequest(BaseModel):         # Erweitert bestehende AnswerRequest um Turn 5
    session_id: str
    turn: int = Field(ge=1, le=5)       # NEU: max Turn von 4 auf 5 erhöht
    answer: str | list[str]
```

---

## API-Endpunkte

Alle neuen Endpunkte liegen im bestehenden Router `backend/interfaces/rest/routers/discovery.py`.

### Bestehende Endpunkte (von Aurelius, unverändert)

| Method | Path | Zweck |
|--------|------|-------|
| `POST` | `/api/v1/discovery/session` | Neue Session starten, `session_id` zurückgeben |
| `POST` | `/api/v1/discovery/answer` | Antwort für Turn 1–4 einreichen |
| `POST` | `/api/v1/discovery/complete` | Profil abschliessen, Empfehlungen abrufen |

### Neue Endpunkte (R2.4-1)

#### `GET /api/v1/discovery/question/{turn}`

Gibt die Frage und Antwortoptionen für einen Turn zurück. Vom Frontend aufgerufen, bevor der Nutzer antwortet.

**Response: `QuestionResponse`**

| Turn | Frage | input_type | Optionen |
|------|-------|------------|----------|
| 1 | "Was ist dein Beruf oder Tätigkeitsbereich?" | `text` | — |
| 2 | "Was ist dein primäres Investitionsziel?" | `single_choice` | housing, retirement, freedom, beat_savings, other |
| 3 | "Wie gehst du mit Risiko um?" | `single_choice` | conservative, moderate, aggressive |
| 4 | "Welche dieser Branchen interessieren dich?" (Multi-Select) | `multi_choice` | pharma, tech, finance, industrial, consumer, energy |
| 5 | "Wie wichtig sind dir aktuelle Wirtschaftsnachrichten?" | `single_choice` | snb_focus, global_macro, ignore |

**Fehler:** `404` wenn `turn < 1` oder `turn > 5`

#### `POST /api/v1/discovery/answer` (erweitert für Turn 5)

Bestehender Endpunkt wird erweitert: Turn 5 wird von `NextQuestionService` verarbeitet und setzt `macro_sensitivity` im Profil. Konfidenz-Berechnung wird mit dem neuen Feld neu ermittelt.

Wenn nach Turn 5 `confidence_score >= 0.6` oder `turn == 5` (Max), wird `next_turn = null` zurückgegeben — Frontend leitet zur Completion.

#### `GET /api/v1/discovery/status/{session_id}`

Gibt aktuellen Stand der Session zurück (für Frontend-Recovery nach Page-Reload).

**Response:**
```python
class SessionStatusResponse(BaseModel):
    session_id: str
    current_turn: int           # Nächster noch nicht beantworteter Turn (1–5)
    confidence: float
    onboarding_complete: bool
    partial_profile: InvestorProfileResponse
```

---

## Frontend-Komponenten (Next.js 14)

### `/start` Page — `frontend/app/start/page.tsx`

Neue Seite für den gesamten Discovery-Flow. Mounted bei erstem Besuch oder auf direktem Aufruf von `/start`.

**Ablauf:**
1. `POST /api/v1/discovery/session` → `session_id` in `sessionStorage`
2. `GET /api/v1/discovery/question/1` → erste Frage anzeigen
3. Nutzer antwortet → `POST /api/v1/discovery/answer`
4. `AnswerResponse.next_turn` bestimmt ob weiter (`GET /question/{next_turn}`) oder fertig (`POST /complete`)
5. Nach Completion: Redirect zu `/dashboard?session_id={id}` mit Profil-Reveal-Animation (R2.4-2/Helin)

### Chat-Dialog-Komponenten

| Datei | Zweck |
|-------|-------|
| `frontend/app/start/page.tsx` | Page-Wrapper, Session-Init, Turn-Orchestration |
| `frontend/components/discovery/DiscoveryChat.tsx` | Chat-Container, Turn-State, Message-Liste |
| `frontend/components/discovery/DiscoveryMessage.tsx` | Einzelne Nachricht (PRISMA oder Nutzer) |
| `frontend/components/discovery/DiscoveryInput.tsx` | Text-Input oder Choice-Buttons, je nach `input_type` |
| `frontend/components/discovery/ChoiceButton.tsx` | Einzelner Antwort-Button für `single_choice`/`multi_choice` |
| `frontend/lib/api/discovery.ts` | API-Client: `createSession()`, `getQuestion()`, `submitAnswer()`, `complete()` |

**Design-Referenz:** Folgt PRISMA Glassmorphism-Design-Tokens aus `feature/helin-ux-components`.

**Animationen:**
- PRISMA-Nachrichten erscheinen mit Typewriter-Effekt (CSS: `@keyframes typing`)
- Nutzer-Antworten wechseln in "gesendeten" Bubble-Stil nach Submit
- Konfidenz-Balken unter dem Chat zeigt progressiv Fortschritt (Turn 1 = 20%, Turn 5 = 100%)

---

## Test-Cases

### Unit-Tests (Backend)

**Datei:** `backend/tests/unit/application/test_next_question_service.py`

| Test | Beschreibung |
|------|-------------|
| `test_get_question_turn_1_returns_text_input` | Turn 1 liefert `input_type="text"`, keine Optionen |
| `test_get_question_turn_3_returns_risk_options` | Turn 3 liefert 3 Risiko-Optionen |
| `test_get_question_turn_5_returns_macro_options` | Turn 5 liefert 3 Makro-Optionen |
| `test_get_question_invalid_turn_raises` | Turn 0 und Turn 6 werfen `ValueError` |
| `test_answer_turn_5_sets_macro_sensitivity` | Turn-5-Antwort `"snb_focus"` setzt `macro_sensitivity` korrekt |
| `test_answer_turn_5_triggers_completion` | Nach Turn 5 ist `next_turn = None` |
| `test_confidence_increases_per_turn` | Konfidenz steigt von Turn 1 zu Turn 5 monoton |

**Datei:** `backend/tests/unit/interfaces/test_discovery_router_question.py`

| Test | Beschreibung |
|------|-------------|
| `test_get_question_200_for_valid_turns` | HTTP 200 für Turns 1–5 |
| `test_get_question_404_for_invalid_turn` | HTTP 404 für Turn 0 und Turn 6 |
| `test_answer_turn_5_accepted` | `POST /answer` mit `turn=5` gibt `200` |

### E2E-Tests (Playwright)

**Datei:** `frontend/e2e/discovery-flow.spec.ts`

| Test | Beschreibung |
|------|-------------|
| `test_full_5_turn_flow_completes` | Alle 5 Turns durchlaufen, Redirect zu `/dashboard` |
| `test_choice_buttons_render_for_turn_2` | Turn 2 zeigt 5 Choice-Buttons |
| `test_text_input_renders_for_turn_1` | Turn 1 zeigt Text-Eingabefeld |
| `test_confidence_bar_increments` | Fortschrittsbalken wächst nach jedem Turn |
| `test_page_reload_recovers_session` | Nach Reload: `GET /status/{session_id}` stellt Turn wieder her |

---

## Nicht-Ziele

- **Kein Voice-Input** — nur Text und Choice-Buttons
- **Kein anonymes A/B-Testing** der Fragen-Reihenfolge
- **Keine Persistenz über Browser-Schliessen hinaus** — `session_id` lebt in `sessionStorage` (nicht `localStorage`)
- **Kein Multi-Language-Support** — Fragen und Labels sind Deutsch; Backend-Enum-Values bleiben Englisch
- **Kein direktes Profil-Editieren nach Completion** — Nutzer muss `/start` neu durchlaufen
- **Keine Real-Time-Kollaboration** — eine Session = ein Nutzer
- **Kein Haiku-Call in Turn 2–5** — Turns 2–5 sind regelbasiert (wie Aurelius implementiert); nur Turn 1 nutzt Haiku (bereits fertig)
- **Keine Änderung an bestehenden Endpunkten** von Aurelius — nur additive Erweiterungen

---

## Abhängigkeiten & Merge-Reihenfolge

```
feature/aurelius-investorprofile  ─┐
                                    ├─► develop ─► feature/andrea-discovery-engine
feature/aurelius-discovery-agent  ─┘
```

**Voraussetzung:** Beide Aurelius-Branches müssen auf `develop` gemergt sein, bevor R2.4-1 implementiert wird. Die Endpunkte aus `discovery.py` und `ProfileClassifier` werden direkt genutzt.

**Blockiert:** R2.4-2 (Helin — Brand Logo Grid + ProfileReveal) wartet auf die `/start`-Page und die `GET /question/{turn}`-API aus diesem Task.

---

## Offene Fragen (vor Implementierungsstart klären)

1. **Alembic-Migration:** Braucht das `macro_sensitivity`-Feld eine neue Migration (0020), oder reicht `ALTER TABLE ... ADD COLUMN ... DEFAULT NULL` via Inline-Migration? (Empfehlung: neue Migration für Sauberkeit)
2. **Turn-5-Positionierung:** Soll Turn 5 (Makro) immer als letzter Turn erscheinen, oder kann er bei hohem Konfidenz-Score nach Turn 3 übersprungen werden?
3. **`sessionStorage` vs. Cookie:** Für Mobile-Nutzung könnte ein HttpOnly-Cookie robuster sein als `sessionStorage`. Entscheid vor Frontend-Implementierung.
