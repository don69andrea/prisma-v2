# Plan: Conversational Discovery Engine — R2.4-1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `AGENTS.md` → `CLAUDE.md` → `docs/specs/2026-06-11-conversational-discovery-engine.md` before starting any task.

**Goal:** Complete the `/start` Conversational Discovery Engine — 5-turn onboarding flow that builds an `InvestorProfile` and routes the user to personalized stock recommendations.

**Preconditions (verify before starting):**
- `feature/aurelius-investorprofile` is merged into `develop` (provides `InvestorProfile`, `DiscoveryService`, DB migration 0019, `POST /discovery/session|answer|complete` endpoints)
- `feature/aurelius-discovery-agent` is merged into `develop` (provides `ProfileClassifier` with Haiku Turn-1 classification and `calculate_confidence()`)
- `git rebase develop` performed on `feature/andrea-discovery-engine`

**Tech Stack:** Python 3.12 · FastAPI · Pydantic v2 · Next.js 14 · TypeScript · Playwright

---

## File Map

| Action | Path |
|--------|------|
| Modify | `backend/domain/entities/investor_profile.py` — add `macro_sensitivity` field |
| Create | `backend/alembic/versions/0020_add_macro_sensitivity.py` — nullable column migration |
| Modify | `backend/interfaces/rest/schemas/investor_profile.py` — add `QuestionOption`, `QuestionResponse`, `SessionStatusResponse`; extend `AnswerRequest` to turn 5 |
| Create | `backend/application/services/next_question_service.py` — `NextQuestionService` with 5 turn definitions |
| Modify | `backend/interfaces/rest/routers/discovery.py` — add `GET /question/{turn}`, `GET /status/{session_id}`; extend answer handler for turn 5 |
| Create | `backend/tests/unit/application/test_next_question_service.py` |
| Create | `backend/tests/unit/interfaces/test_discovery_router_question.py` |
| Create | `frontend/lib/api/discovery.ts` — typed API client |
| Create | `frontend/app/start/page.tsx` — /start page with session orchestration |
| Create | `frontend/components/discovery/DiscoveryChat.tsx` |
| Create | `frontend/components/discovery/DiscoveryMessage.tsx` |
| Create | `frontend/components/discovery/DiscoveryInput.tsx` |
| Create | `frontend/components/discovery/ChoiceButton.tsx` |
| Create | `frontend/e2e/discovery-flow.spec.ts` |
| Modify | `docs/AI-USAGE.md` — add entry for this session |

---

## Task 1: Domain Extension — `macro_sensitivity` field

**Files:**
- Modify: `backend/domain/entities/investor_profile.py`
- Create: `backend/alembic/versions/0020_add_macro_sensitivity.py`

- [ ] **Step 1: Add `macro_sensitivity` field to InvestorProfile entity**

In `backend/domain/entities/investor_profile.py`, add after the `known_tickers` field:

```python
# Turn 5 — Makro-Sensitivität (optional, gesetzt durch R2.4-1)
macro_sensitivity: Literal["snb_focus", "global_macro", "ignore"] | None = None
```

- [ ] **Step 2: Generate Alembic migration**

```bash
cd /Users/helinkoyuncu/prisma-v2
alembic revision --autogenerate -m "add macro_sensitivity to investor_profiles"
# OR create manually if autogenerate unavailable:
```

Manual migration content for `backend/alembic/versions/0020_add_macro_sensitivity.py`:

```python
"""add macro_sensitivity to investor_profiles

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-11
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "investor_profiles",
        sa.Column(
            "macro_sensitivity",
            sa.String(length=20),
            nullable=True,
            default=None,
        ),
    )

def downgrade() -> None:
    op.drop_column("investor_profiles", "macro_sensitivity")
```

- [ ] **Step 3: Update SQLAlchemy ORM model**

In `backend/infrastructure/persistence/models/investor_profile.py`, add:

```python
macro_sensitivity: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

---

## Task 2: Backend Tests (write FIRST — TDD)

**Files:**
- Create: `backend/tests/unit/application/test_next_question_service.py`
- Create: `backend/tests/unit/interfaces/test_discovery_router_question.py`

- [ ] **Step 4: Write failing unit tests for NextQuestionService**

Create `backend/tests/unit/application/test_next_question_service.py`:

```python
"""Unit-Tests für NextQuestionService."""
from __future__ import annotations
import pytest
from backend.application.services.next_question_service import NextQuestionService

pytestmark = pytest.mark.unit


@pytest.fixture()
def service() -> NextQuestionService:
    return NextQuestionService()


def test_get_question_turn_1_returns_text_input(service: NextQuestionService) -> None:
    q = service.get_question(1)
    assert q.turn == 1
    assert q.input_type == "text"
    assert q.options is None


def test_get_question_turn_2_returns_5_goal_options(service: NextQuestionService) -> None:
    q = service.get_question(2)
    assert q.input_type == "single_choice"
    assert q.options is not None
    assert len(q.options) == 5
    values = {o.value for o in q.options}
    assert "retirement" in values
    assert "housing" in values


def test_get_question_turn_3_returns_risk_options(service: NextQuestionService) -> None:
    q = service.get_question(3)
    assert q.input_type == "single_choice"
    assert q.options is not None
    values = [o.value for o in q.options]
    assert values == ["conservative", "moderate", "aggressive"]


def test_get_question_turn_4_returns_multi_choice(service: NextQuestionService) -> None:
    q = service.get_question(4)
    assert q.input_type == "multi_choice"
    assert q.options is not None
    assert len(q.options) >= 5


def test_get_question_turn_5_returns_macro_options(service: NextQuestionService) -> None:
    q = service.get_question(5)
    assert q.input_type == "single_choice"
    assert q.options is not None
    values = {o.value for o in q.options}
    assert values == {"snb_focus", "global_macro", "ignore"}


def test_get_question_invalid_turn_raises(service: NextQuestionService) -> None:
    with pytest.raises(ValueError, match="turn"):
        service.get_question(0)
    with pytest.raises(ValueError, match="turn"):
        service.get_question(6)


def test_process_turn_5_sets_macro_sensitivity(service: NextQuestionService) -> None:
    updates = service.process_turn_5_answer("snb_focus")
    assert updates["macro_sensitivity"] == "snb_focus"


def test_process_turn_5_invalid_value_raises(service: NextQuestionService) -> None:
    with pytest.raises(ValueError, match="macro_sensitivity"):
        service.process_turn_5_answer("invalid_option")
```

- [ ] **Step 5: Write failing router tests**

Create `backend/tests/unit/interfaces/test_discovery_router_question.py`:

```python
"""Unit-Tests für GET /api/v1/discovery/question/{turn}."""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from backend.interfaces.rest.app import create_app

pytestmark = pytest.mark.unit


@pytest.fixture()
async def client() -> AsyncClient:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.parametrize("turn", [1, 2, 3, 4, 5])
async def test_get_question_200_for_valid_turns(client: AsyncClient, turn: int) -> None:
    response = await client.get(f"/api/v1/discovery/question/{turn}")
    assert response.status_code == 200
    body = response.json()
    assert body["turn"] == turn
    assert "question" in body
    assert "input_type" in body


@pytest.mark.parametrize("turn", [0, 6, 99])
async def test_get_question_404_for_invalid_turn(client: AsyncClient, turn: int) -> None:
    response = await client.get(f"/api/v1/discovery/question/{turn}")
    assert response.status_code == 404


async def test_answer_turn_5_accepted(client: AsyncClient) -> None:
    """Turn 5 submit returns 200 (session must exist — use mocked repo)."""
    # Integration-level test lives in tests/integration/; this is a schema test only.
    # Verify the AnswerRequest schema accepts turn=5.
    from backend.interfaces.rest.schemas.investor_profile import AnswerRequest
    req = AnswerRequest(session_id="test-uuid", turn=5, answer="snb_focus")
    assert req.turn == 5
```

---

## Task 3: NextQuestionService (make tests pass)

**File:** `backend/application/services/next_question_service.py`

- [ ] **Step 6: Implement NextQuestionService**

Create `backend/application/services/next_question_service.py`:

```python
"""NextQuestionService — liefert strukturierte Fragen für den 5-Turn Discovery-Flow."""
from __future__ import annotations
from typing import Literal, Any
from backend.interfaces.rest.schemas.investor_profile import (
    QuestionOption,
    QuestionResponse,
)

_VALID_MACRO_VALUES: frozenset[str] = frozenset({"snb_focus", "global_macro", "ignore"})

_QUESTIONS: dict[int, QuestionResponse] = {
    1: QuestionResponse(
        turn=1,
        question="Was ist dein Beruf oder Tätigkeitsbereich?",
        input_type="text",
        hint="Keine Sorge — wir nutzen das nur, um deinen Finanzwissens-Stand einzuschätzen.",
    ),
    2: QuestionResponse(
        turn=2,
        question="Was ist dein primäres Investitionsziel?",
        input_type="single_choice",
        options=[
            QuestionOption(value="housing", label="Eigenheim finanzieren", emoji="🏠"),
            QuestionOption(value="retirement", label="Für die Pension sparen", emoji="🏖️"),
            QuestionOption(value="freedom", label="Finanzielle Unabhängigkeit", emoji="🚀"),
            QuestionOption(value="beat_savings", label="Mehr als Sparkonto", emoji="📈"),
            QuestionOption(value="other", label="Etwas anderes", emoji="💡"),
        ],
    ),
    3: QuestionResponse(
        turn=3,
        question="Wie gehst du mit Risiko um?",
        input_type="single_choice",
        hint="Bei Kursrückgängen — wie würdest du reagieren?",
        options=[
            QuestionOption(value="conservative", label="Sicherheit über Rendite — ich schlafe besser so", emoji="🛡️"),
            QuestionOption(value="moderate", label="Ausgewogen — ich kann moderate Schwankungen tragen", emoji="⚖️"),
            QuestionOption(value="aggressive", label="Wachstum über Sicherheit — Rendite zählt", emoji="⚡"),
        ],
    ),
    4: QuestionResponse(
        turn=4,
        question="Welche dieser Branchen interessieren dich?",
        input_type="multi_choice",
        hint="Wähle so viele wie du möchtest — oder überspring diese Frage.",
        options=[
            QuestionOption(value="pharma", label="Pharma & Gesundheit", emoji="💊"),
            QuestionOption(value="tech", label="Technologie", emoji="💻"),
            QuestionOption(value="finance", label="Banken & Versicherungen", emoji="🏦"),
            QuestionOption(value="industrial", label="Industrie & Maschinenbau", emoji="⚙️"),
            QuestionOption(value="consumer", label="Konsum & Lebensmittel", emoji="🛒"),
            QuestionOption(value="energy", label="Energie & Rohstoffe", emoji="⚡"),
        ],
    ),
    5: QuestionResponse(
        turn=5,
        question="Wie wichtig sind dir aktuelle Wirtschaftsnachrichten für deine Anlageentscheide?",
        input_type="single_choice",
        hint="Das hilft uns, makroökonomische Faktoren in deine Empfehlungen einzubeziehen.",
        options=[
            QuestionOption(value="snb_focus", label="SNB-Entscheide und CHF-Kurs beobachte ich genau", emoji="🇨🇭"),
            QuestionOption(value="global_macro", label="Globale Trends und Fed-Entscheide interessieren mich", emoji="🌍"),
            QuestionOption(value="ignore", label="Makro ignoriere ich — ich halte langfristig", emoji="🧘"),
        ],
    ),
}


class NextQuestionService:
    """Liefert strukturierte Fragen für den 5-Turn Discovery-Onboarding-Flow."""

    def get_question(self, turn: int) -> QuestionResponse:
        """Gibt die Frage für den angegebenen Turn zurück.

        Args:
            turn: Aktueller Onboarding-Turn (1–5).

        Returns:
            QuestionResponse mit Fragetext, input_type und Optionen.

        Raises:
            ValueError: Wenn turn ausserhalb des Bereichs 1–5.
        """
        if turn not in _QUESTIONS:
            raise ValueError(f"Ungültiger turn={turn}. Erlaubt: 1–5.")
        return _QUESTIONS[turn]

    def process_turn_5_answer(self, answer: str) -> dict[str, Any]:
        """Verarbeitet die Antwort für Turn 5 und gibt Update-Dict zurück.

        Args:
            answer: Einer von 'snb_focus', 'global_macro', 'ignore'.

        Returns:
            Dict mit 'macro_sensitivity' Key.

        Raises:
            ValueError: Wenn der Wert nicht in den erlaubten Optionen ist.
        """
        if answer not in _VALID_MACRO_VALUES:
            valid = ", ".join(sorted(_VALID_MACRO_VALUES))
            raise ValueError(f"Ungültiger macro_sensitivity-Wert '{answer}'. Erlaubt: {valid}.")
        return {"macro_sensitivity": answer}
```

---

## Task 4: Schema & Router Extension

**Files:**
- Modify: `backend/interfaces/rest/schemas/investor_profile.py`
- Modify: `backend/interfaces/rest/routers/discovery.py`

- [ ] **Step 7: Add new schemas**

In `backend/interfaces/rest/schemas/investor_profile.py`, add:

```python
class QuestionOption(BaseModel):
    value: str
    label: str
    emoji: str | None = None

class QuestionResponse(BaseModel):
    turn: int
    question: str
    input_type: Literal["text", "single_choice", "multi_choice"]
    options: list[QuestionOption] | None = None
    hint: str | None = None

class SessionStatusResponse(BaseModel):
    session_id: str
    current_turn: int
    confidence: float
    onboarding_complete: bool
    partial_profile: InvestorProfileResponse
```

Also extend existing `AnswerRequest`:
- Change `turn: int = Field(ge=1, le=4)` to `turn: int = Field(ge=1, le=5)`

- [ ] **Step 8: Add router endpoints**

In `backend/interfaces/rest/routers/discovery.py`, add after existing endpoints:

```python
from backend.application.services.next_question_service import NextQuestionService

_next_question_service = NextQuestionService()


@router.get(
    "/discovery/question/{turn}",
    response_model=QuestionResponse,
    summary="Onboarding-Frage für einen Turn abrufen",
)
async def get_discovery_question(turn: int) -> QuestionResponse:
    """Gibt Fragetext und Antwortoptionen für Turn 1–5 zurück."""
    try:
        return _next_question_service.get_question(turn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/discovery/status/{session_id}",
    response_model=SessionStatusResponse,
    summary="Aktuellen Status einer Discovery-Session abrufen",
)
async def get_session_status(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> SessionStatusResponse:
    """Gibt den aktuellen Turn und Konfidenz-Score einer Session zurück (für Page-Reload-Recovery)."""
    repo = SQLAInvestorProfileRepository(session=session)
    profile = await repo.get_by_session_id(session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Session für session_id={session_id!r} gefunden.",
        )
    # Berechne nächsten offenen Turn
    turns_completed = 0
    if profile.profession is not None:
        turns_completed += 1
    if profile.investment_goal != "beat_savings" or turns_completed > 1:
        turns_completed = max(turns_completed, 1 if profile.profession else 0)
    # Einfachere Heuristik: nächster Turn = erstes ungesetztes Pflichtfeld
    current_turn = _calculate_next_turn(profile)
    return SessionStatusResponse(
        session_id=session_id,
        current_turn=current_turn,
        confidence=profile.confidence_score,
        onboarding_complete=profile.onboarding_complete,
        partial_profile=_to_profile_response(profile),
    )
```

Also extend the `submit_answer` handler to handle `turn == 5`:

```python
elif body.turn == 5:
    macro_answer = body.answer if isinstance(body.answer, str) else str(body.answer)
    turn5_updates = _next_question_service.process_turn_5_answer(macro_answer)
    updates.update(turn5_updates)
```

Helper for status endpoint:
```python
def _calculate_next_turn(profile: InvestorProfile) -> int:
    """Ermittelt den nächsten noch nicht beantworteten Turn (1–5)."""
    if profile.profession is None:
        return 1
    if profile.investment_goal == "beat_savings" and profile.confidence_score < 0.2:
        return 2
    if profile.risk_profile == "moderate" and profile.confidence_score < 0.4:
        return 3
    if not profile.sector_affinity:
        return 4
    if getattr(profile, "macro_sensitivity", None) is None:
        return 5
    return 5  # All turns answered
```

---

## Task 5: Frontend API Client

**File:** `frontend/lib/api/discovery.ts`

- [ ] **Step 9: Create typed TypeScript API client**

```typescript
// frontend/lib/api/discovery.ts
const BASE = "/api/v1";

export type InputType = "text" | "single_choice" | "multi_choice";

export interface QuestionOption {
  value: string;
  label: string;
  emoji?: string;
}

export interface DiscoveryQuestion {
  turn: number;
  question: string;
  input_type: InputType;
  options?: QuestionOption[];
  hint?: string;
}

export interface InvestorProfilePartial {
  session_id: string;
  risk_profile: string;
  sector_affinity: string[];
  time_horizon: string;
  investment_goal: string;
  confidence_score: number;
  onboarding_complete: boolean;
}

export interface AnswerResponse {
  session_id: string;
  next_turn: number | null;
  confidence: number;
  partial_profile: InvestorProfilePartial;
}

export interface CompleteResponse {
  profile: InvestorProfilePartial;
  recommended_stocks: {
    ticker: string;
    name: string;
    sector: string | null;
    market_cap_chf: number | null;
    exchange: string;
  }[];
}

export async function createSession(): Promise<string> {
  const res = await fetch(`${BASE}/discovery/session`, { method: "POST" });
  if (!res.ok) throw new Error("Session creation failed");
  const data: { session_id: string } = await res.json();
  return data.session_id;
}

export async function getQuestion(turn: number): Promise<DiscoveryQuestion> {
  const res = await fetch(`${BASE}/discovery/question/${turn}`);
  if (!res.ok) throw new Error(`Failed to fetch question for turn ${turn}`);
  return res.json();
}

export async function submitAnswer(
  sessionId: string,
  turn: number,
  answer: string | string[]
): Promise<AnswerResponse> {
  const res = await fetch(`${BASE}/discovery/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, turn, answer }),
  });
  if (!res.ok) throw new Error(`Answer submit failed for turn ${turn}`);
  return res.json();
}

export async function completeDiscovery(sessionId: string): Promise<CompleteResponse> {
  const res = await fetch(`${BASE}/discovery/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error("Discovery completion failed");
  return res.json();
}
```

---

## Task 6: Frontend Components

**Files:**
- Create: `frontend/components/discovery/ChoiceButton.tsx`
- Create: `frontend/components/discovery/DiscoveryMessage.tsx`
- Create: `frontend/components/discovery/DiscoveryInput.tsx`
- Create: `frontend/components/discovery/DiscoveryChat.tsx`
- Create: `frontend/app/start/page.tsx`

- [ ] **Step 10: ChoiceButton component**

```tsx
// frontend/components/discovery/ChoiceButton.tsx
"use client";
interface Props {
  value: string;
  label: string;
  emoji?: string;
  selected: boolean;
  onClick: (value: string) => void;
}

export function ChoiceButton({ value, label, emoji, selected, onClick }: Props) {
  return (
    <button
      onClick={() => onClick(value)}
      className={[
        "flex items-center gap-2 px-4 py-3 rounded-xl border text-left transition-all",
        "text-sm font-medium w-full",
        selected
          ? "border-purple-500 bg-purple-900/40 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)]"
          : "border-white/10 bg-white/5 text-white/70 hover:border-white/30 hover:bg-white/10",
      ].join(" ")}
    >
      {emoji && <span className="text-lg">{emoji}</span>}
      {label}
    </button>
  );
}
```

- [ ] **Step 11: DiscoveryMessage component**

```tsx
// frontend/components/discovery/DiscoveryMessage.tsx
"use client";
interface Props {
  role: "prisma" | "user";
  content: string;
  isTyping?: boolean;
}

export function DiscoveryMessage({ role, content, isTyping }: Props) {
  const isPrisma = role === "prisma";
  return (
    <div className={`flex ${isPrisma ? "justify-start" : "justify-end"} mb-3`}>
      <div
        className={[
          "max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed",
          isPrisma
            ? "bg-black/60 border border-white/10 text-white rounded-tl-sm"
            : "bg-purple-900/50 text-white rounded-tr-sm",
        ].join(" ")}
      >
        {content}
        {isTyping && (
          <span className="ml-1 inline-block w-2 h-4 bg-purple-400 animate-pulse" />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 12: DiscoveryInput component**

```tsx
// frontend/components/discovery/DiscoveryInput.tsx
"use client";
import { useState } from "react";
import type { DiscoveryQuestion } from "@/lib/api/discovery";
import { ChoiceButton } from "./ChoiceButton";

interface Props {
  question: DiscoveryQuestion;
  onSubmit: (answer: string | string[]) => void;
  disabled?: boolean;
}

export function DiscoveryInput({ question, onSubmit, disabled }: Props) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const handleSingleChoice = (value: string) => {
    onSubmit(value);
  };

  const toggleMultiChoice = (value: string) => {
    setSelected((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  };

  if (question.input_type === "text") {
    return (
      <form
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) onSubmit(text.trim()); }}
        className="flex gap-2 mt-4"
      >
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Deine Antwort..."
          disabled={disabled}
          className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white text-sm placeholder-white/40 focus:outline-none focus:border-purple-500"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="px-5 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 rounded-xl text-white text-sm font-medium transition-colors"
        >
          Weiter
        </button>
      </form>
    );
  }

  if (question.input_type === "multi_choice") {
    return (
      <div className="mt-4 space-y-2">
        {question.options?.map((opt) => (
          <ChoiceButton
            key={opt.value}
            {...opt}
            selected={selected.includes(opt.value)}
            onClick={toggleMultiChoice}
          />
        ))}
        <button
          onClick={() => onSubmit(selected.length > 0 ? selected : ["other"])}
          disabled={disabled}
          className="mt-3 w-full px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:opacity-40 rounded-xl text-white text-sm font-medium transition-colors"
        >
          {selected.length > 0 ? `${selected.length} ausgewählt — Weiter` : "Überspringen"}
        </button>
      </div>
    );
  }

  // single_choice
  return (
    <div className="mt-4 space-y-2">
      {question.options?.map((opt) => (
        <ChoiceButton
          key={opt.value}
          {...opt}
          selected={false}
          onClick={handleSingleChoice}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 13: DiscoveryChat container**

```tsx
// frontend/components/discovery/DiscoveryChat.tsx
"use client";
import { useState } from "react";
import { DiscoveryMessage } from "./DiscoveryMessage";
import { DiscoveryInput } from "./DiscoveryInput";
import type { DiscoveryQuestion } from "@/lib/api/discovery";

export interface ChatMessage {
  role: "prisma" | "user";
  content: string;
}

interface Props {
  sessionId: string;
  question: DiscoveryQuestion | null;
  messages: ChatMessage[];
  confidence: number;
  currentTurn: number;
  onSubmit: (answer: string | string[]) => Promise<void>;
  isLoading: boolean;
}

export function DiscoveryChat({
  question,
  messages,
  confidence,
  currentTurn,
  onSubmit,
  isLoading,
}: Props) {
  const progressPct = Math.round((currentTurn - 1) * 20);

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs text-white/40 mb-1">
          <span>Frage {currentTurn} von 5</span>
          <span>{progressPct}% abgeschlossen</span>
        </div>
        <div className="h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-1 pb-4">
        {messages.map((msg, i) => (
          <DiscoveryMessage key={i} role={msg.role} content={msg.content} />
        ))}
        {isLoading && (
          <DiscoveryMessage role="prisma" content="" isTyping />
        )}
      </div>

      {/* Input */}
      {question && !isLoading && (
        <div className="border-t border-white/10 pt-4">
          {question.hint && (
            <p className="text-xs text-white/40 mb-3">{question.hint}</p>
          )}
          <DiscoveryInput question={question} onSubmit={onSubmit} disabled={isLoading} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 14: /start page**

```tsx
// frontend/app/start/page.tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { DiscoveryChat, ChatMessage } from "@/components/discovery/DiscoveryChat";
import {
  createSession,
  getQuestion,
  submitAnswer,
  completeDiscovery,
  DiscoveryQuestion,
} from "@/lib/api/discovery";

export default function StartPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<DiscoveryQuestion | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentTurn, setCurrentTurn] = useState(1);
  const [confidence, setConfidence] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const pushMessage = useCallback((role: "prisma" | "user", content: string) => {
    setMessages((prev) => [...prev, { role, content }]);
  }, []);

  useEffect(() => {
    async function init() {
      setIsLoading(true);
      try {
        // Recover from sessionStorage or create new
        let sid = sessionStorage.getItem("prisma_discovery_session");
        if (!sid) {
          sid = await createSession();
          sessionStorage.setItem("prisma_discovery_session", sid);
        }
        setSessionId(sid);

        const q = await getQuestion(1);
        setQuestion(q);
        pushMessage("prisma", "Willkommen bei PRISMA! Ich stelle dir 5 kurze Fragen, damit ich die richtigen Aktien für dich finden kann.");
        pushMessage("prisma", q.question);
      } finally {
        setIsLoading(false);
      }
    }
    void init();
  }, [pushMessage]);

  const handleSubmit = useCallback(
    async (answer: string | string[]) => {
      if (!sessionId || !question) return;
      setIsLoading(true);

      const userText = Array.isArray(answer) ? answer.join(", ") : answer;
      pushMessage("user", userText);

      try {
        const res = await submitAnswer(sessionId, currentTurn, answer);
        setConfidence(res.confidence);

        if (res.next_turn === null || currentTurn >= 5) {
          // Flow complete
          pushMessage("prisma", "Perfekt! Ich analysiere jetzt dein Profil...");
          const completion = await completeDiscovery(sessionId);
          sessionStorage.removeItem("prisma_discovery_session");
          router.push(`/dashboard?session_id=${sessionId}`);
        } else {
          const nextQ = await getQuestion(res.next_turn);
          setCurrentTurn(res.next_turn);
          setQuestion(nextQ);
          pushMessage("prisma", nextQ.question);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, question, currentTurn, pushMessage, router]
  );

  return (
    <main className="min-h-screen bg-[#0a0a14] flex flex-col">
      <header className="border-b border-white/5 px-6 py-4">
        <h1 className="text-white font-semibold text-lg">PRISMA Discovery</h1>
        <p className="text-white/40 text-sm">Dein persönliches Investorprofil</p>
      </header>

      <div className="flex-1 px-6 py-8 overflow-hidden">
        {sessionId && (
          <DiscoveryChat
            sessionId={sessionId}
            question={question}
            messages={messages}
            confidence={confidence}
            currentTurn={currentTurn}
            onSubmit={handleSubmit}
            isLoading={isLoading}
          />
        )}
      </div>
    </main>
  );
}
```

---

## Task 7: E2E Tests

**File:** `frontend/e2e/discovery-flow.spec.ts`

- [ ] **Step 15: Write Playwright E2E tests**

```typescript
// frontend/e2e/discovery-flow.spec.ts
import { test, expect, Page } from "@playwright/test";

// Mock discovery API responses
async function setupMocks(page: Page) {
  await page.route("**/api/v1/discovery/session", (route) =>
    route.fulfill({ json: { session_id: "test-session-123" } })
  );
  await page.route("**/api/v1/discovery/question/1", (route) =>
    route.fulfill({
      json: {
        turn: 1,
        question: "Was ist dein Beruf?",
        input_type: "text",
        options: null,
        hint: "Hilfstext",
      },
    })
  );
  await page.route("**/api/v1/discovery/question/2", (route) =>
    route.fulfill({
      json: {
        turn: 2,
        question: "Was ist dein Ziel?",
        input_type: "single_choice",
        options: [
          { value: "retirement", label: "Für die Pension sparen", emoji: "🏖️" },
          { value: "housing", label: "Eigenheim", emoji: "🏠" },
        ],
      },
    })
  );
  // ... similar mocks for turns 3-5
  await page.route("**/api/v1/discovery/answer", (route, request) => {
    const body = JSON.parse(request.postData() ?? "{}");
    const nextTurn = body.turn < 5 ? body.turn + 1 : null;
    route.fulfill({
      json: {
        session_id: "test-session-123",
        next_turn: nextTurn,
        confidence: body.turn * 0.2,
        partial_profile: {
          session_id: "test-session-123",
          risk_profile: "moderate",
          sector_affinity: [],
          time_horizon: "medium",
          investment_goal: "beat_savings",
          confidence_score: body.turn * 0.2,
          onboarding_complete: false,
        },
      },
    });
  });
  await page.route("**/api/v1/discovery/complete", (route) =>
    route.fulfill({
      json: {
        profile: {
          session_id: "test-session-123",
          risk_profile: "moderate",
          sector_affinity: ["tech"],
          time_horizon: "medium",
          investment_goal: "beat_savings",
          confidence_score: 1.0,
          onboarding_complete: true,
        },
        recommended_stocks: [],
      },
    })
  );
}

test.describe("Discovery Flow", () => {
  test("shows text input for turn 1", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/start");
    await expect(page.locator("input[type='text']")).toBeVisible();
  });

  test("shows choice buttons for turn 2", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/start");
    // Submit turn 1
    await page.fill("input[type='text']", "Software Engineer");
    await page.click("button:has-text('Weiter')");
    // Turn 2 should show buttons
    await expect(page.locator("button:has-text('Für die Pension sparen')")).toBeVisible();
  });

  test("progress bar shows turn 1 of 5", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/start");
    await expect(page.locator("text=Frage 1 von 5")).toBeVisible();
  });

  test("welcome message appears on load", async ({ page }) => {
    await setupMocks(page);
    await page.goto("/start");
    await expect(page.locator("text=Willkommen bei PRISMA")).toBeVisible();
  });
});
```

---

## Task 8: AI-USAGE.md entry

- [ ] **Step 16: Add AI-USAGE.md entry**

Append to `docs/AI-USAGE.md`:

```markdown
## 2026-06-11 · Conversational Discovery Engine Spec + Plan — R2.4-1

- **Agent**: Claude Code (Sonnet 4.6) — spec-first workflow, no implementation code
- **Scope**: Spec `docs/specs/2026-06-11-conversational-discovery-engine.md` und Plan `docs/superpowers/plans/2026-06-11-discovery-engine-plan.md` für R2.4-1 `/start` Conversational Discovery Engine (5 Turns). Branch: `feature/andrea-discovery-engine`.
- **Was gut lief**: Aurelius' bestehende Arbeit (InvestorProfile Entity, ProfileClassifier, bestehende REST-Endpoints, DB-Migration) systematisch analysiert bevor Spec geschrieben wurde — ergibt präzise Abgrenzung und vermeidet Dopplungen.
- **Was nicht klappte**: Keine Implementierung in diesem Task — nur Spec + Plan.
- **Nachbearbeitung nötig bei**: Vor Implementierungsstart: offene Fragen aus Spec klären (Alembic-Migration-Strategy für macro_sensitivity, Turn-5-Skip-Logik, sessionStorage vs. Cookie).
- **Autor**: Andrea Petretta (mit Claude Code)
```

---

## Commit Sequence

```bash
# Nach Task 1–2 (Domain + Tests skeleton):
git add backend/domain/entities/investor_profile.py \
        backend/alembic/versions/0020_add_macro_sensitivity.py \
        backend/tests/unit/application/test_next_question_service.py \
        backend/tests/unit/interfaces/test_discovery_router_question.py
git commit -m "test(R2.4-1): add failing unit tests for NextQuestionService + Turn-5 domain field"

# Nach Task 3–4 (Service + Router):
git add backend/application/services/next_question_service.py \
        backend/interfaces/rest/schemas/investor_profile.py \
        backend/interfaces/rest/routers/discovery.py
git commit -m "feat(R2.4-1): NextQuestionService + GET /question/{turn} + GET /status/{session_id}"

# Nach Task 5–6 (Frontend):
git add frontend/lib/api/discovery.ts \
        frontend/app/start/page.tsx \
        frontend/components/discovery/
git commit -m "feat(R2.4-1): /start page + DiscoveryChat UI components (5-turn flow)"

# Nach Task 7–8 (E2E + AI-USAGE):
git add frontend/e2e/discovery-flow.spec.ts docs/AI-USAGE.md
git commit -m "test(R2.4-1): add Playwright E2E discovery flow tests"
```

---

## Definition of Done

- [ ] `GET /api/v1/discovery/question/{turn}` gibt für Turns 1–5 korrekte Fragen zurück
- [ ] `POST /api/v1/discovery/answer` mit `turn=5` setzt `macro_sensitivity` korrekt
- [ ] `GET /api/v1/discovery/status/{session_id}` gibt aktuellen Turn zurück
- [ ] Alle 7 Unit-Tests grün: `pytest backend/tests/unit/application/test_next_question_service.py -v`
- [ ] Router-Tests grün: `pytest backend/tests/unit/interfaces/test_discovery_router_question.py -v`
- [ ] `/start`-Page rendert in Next.js ohne TypeScript-Errors: `npm run build`
- [ ] E2E-Tests grün (mit Mock-API): `npx playwright test discovery-flow.spec.ts`
- [ ] Ruff Format + Mypy grün: `ruff format backend/ && ruff check backend/ && mypy backend/`
- [ ] R2.4-2 (Helin) ist nicht blockiert: `GET /question/{turn}` und `/start`-Page sind accessible
