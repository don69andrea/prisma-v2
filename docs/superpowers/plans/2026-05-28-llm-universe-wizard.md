# LLM-Universe-Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Single-Turn LLM-Wizard für Universe-Erstellung: User schreibt Beschreibung → Claude Haiku schlägt Universe vor (Name + Region + Tickers + Begründung) unter Whitelist-Constraint des Stock-Katalogs → User editiert Pre-Filled Form → submit via existing endpoint.

**Architecture:** Backend Service + Endpoint via existing LLMClient + StockService. Frontend neue Page `/universes/wizard` mit Form + Result-State. Tool-use-Pattern (wie Narrative-Engine) für Structured-Output.

**Tech Stack:** FastAPI/Python, anthropic SDK + Pydantic (Tool-use für JSON-Output), Jinja2-Templates, Claude Haiku 4.5. Next.js + Tanstack Mutation + shadcn.

**Spec:** `docs/specs/2026-05-28-llm-universe-wizard-design.md`

**Branch:** `feat/llm-universe-wizard`

---

## Task 1: Backend — Domain-Schema + UniverseSuggestionService + Tests

**Files:**
- Create: `backend/domain/schemas/universe_suggestion_schema.py` — Pydantic-Schema für LLM-Output
- Create: `backend/application/services/universe_suggestion_service.py` — Service
- Create: `backend/infrastructure/llm/prompts/universe_suggestion_system.de.md.j2`
- Create: `backend/infrastructure/llm/prompts/universe_suggestion_user.de.md.j2`
- Create: `backend/tests/unit/application/test_universe_suggestion_service.py`

### Step 1: Pydantic-Schema schreiben

`backend/domain/schemas/universe_suggestion_schema.py`:

```python
"""Pydantic-Schema für LLM-Output beim Universe-Wizard."""

from pydantic import BaseModel, Field


class UniverseSuggestionSchema(BaseModel):
    """LLM-Tool-Output. Strikte Validierung — fehlerhafte Outputs verwerfen."""

    name: str = Field(..., min_length=2, max_length=40)
    region: str = Field(..., min_length=2, max_length=20)
    tickers: list[str] = Field(..., min_length=2, max_length=15)
    reasoning: str = Field(..., min_length=10, max_length=400)
```

### Step 2: Jinja2-Templates schreiben

`backend/infrastructure/llm/prompts/universe_suggestion_system.de.md.j2`:

```jinja
Du bist ein quantitativer Analyst, der Aktien-Universen für PRISMA empfiehlt.

VERFÜGBARE TICKERS (NUR DIESE NUTZEN):
{% for stock in available_stocks %}
- {{ stock.ticker }}: {{ stock.name }} ({{ stock.sector or "—" }})
{% endfor %}

Regeln:
- Wähle 3-12 Tickers aus der Liste oben
- Tickers MÜSSEN aus der Liste oben kommen (sonst werden sie verworfen)
- Schlage einen prägnanten Universe-Namen vor (max 40 Zeichen, Deutsch oder Englisch)
- Region: "US" wenn ausschließlich US-Stocks, sonst "Global"
- Begründung: 1-2 Sätze auf Deutsch, fokussiert auf Auswahlkriterien
```

`backend/infrastructure/llm/prompts/universe_suggestion_user.de.md.j2`:

```jinja
Anfrage des Users:

{{ description }}

Bitte schlage ein passendes Universe vor.
```

### Step 3: Failing Test schreiben

`backend/tests/unit/application/test_universe_suggestion_service.py`:

```python
"""Unit-Tests für UniverseSuggestionService."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.services.universe_suggestion_service import (
    EmptySuggestion,
    UniverseSuggestion,
    UniverseSuggestionService,
)
from backend.domain.entities.stock import Stock

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _make_stock(ticker: str, name: str = "Test", sector: str = "Tech") -> Stock:
    import uuid
    return Stock(
        id=uuid.uuid4(),
        ticker=ticker,
        name=f"{name} {ticker}",
        sector=sector,
        currency="USD",
    )


def _fake_llm_response(name: str, region: str, tickers: list[str], reasoning: str) -> MagicMock:
    """Mockt eine Anthropic-Tool-Use-Response."""
    response = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "submit_universe_suggestion"
    tool_block.input = {
        "name": name,
        "region": region,
        "tickers": tickers,
        "reasoning": reasoning,
    }
    response.content = [tool_block]
    return response


class TestUniverseSuggestionService:
    async def test_suggest_returns_valid_universe_with_filtered_tickers(self) -> None:
        """LLM-Output passt zum Katalog — alle Tickers werden zurückgegeben."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT"), _make_stock("NVDA")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Tech-Top-3",
                region="US",
                tickers=["AAPL", "MSFT", "NVDA"],
                reasoning="US-Tech-Schwergewichte mit starker Marge.",
            )
        )

        service = UniverseSuggestionService(
            llm_client=llm_client, stock_service=stock_service
        )
        suggestion = await service.suggest(description="Tech-Heavy USA")

        assert suggestion.name == "Tech-Top-3"
        assert suggestion.region == "US"
        assert suggestion.tickers == ["AAPL", "MSFT", "NVDA"]
        assert "Tech" in suggestion.reasoning
        assert llm_client.messages_create.call_count == 1

    async def test_suggest_filters_unknown_tickers(self) -> None:
        """Tickers außerhalb des Katalogs werden rausgefiltert."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Mix",
                region="US",
                tickers=["AAPL", "FOO", "MSFT", "BAR"],
                reasoning="Test mit unbekannten Tickers.",
            )
        )

        service = UniverseSuggestionService(
            llm_client=llm_client, stock_service=stock_service
        )
        suggestion = await service.suggest(description="Test")

        assert suggestion.tickers == ["AAPL", "MSFT"]  # FOO + BAR gefiltert

    async def test_suggest_raises_empty_when_less_than_two_valid_tickers(self) -> None:
        """Wenn nach Filterung weniger als 2 Tickers übrig → EmptySuggestion."""
        stocks = [_make_stock("AAPL")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Solo",
                region="US",
                tickers=["FOO"],  # alle unknown
                reasoning="Test.",
            )
        )

        service = UniverseSuggestionService(
            llm_client=llm_client, stock_service=stock_service
        )

        with pytest.raises(EmptySuggestion):
            await service.suggest(description="Test")

    async def test_suggest_uses_haiku_model(self) -> None:
        """Service muss claude-haiku-4-5 verwenden."""
        stocks = [_make_stock("AAPL"), _make_stock("MSFT")]
        stock_service = MagicMock()
        stock_service.list_stocks = AsyncMock(return_value=stocks)

        llm_client = MagicMock()
        llm_client.messages_create = AsyncMock(
            return_value=_fake_llm_response(
                name="Test", region="US", tickers=["AAPL", "MSFT"], reasoning="OK xx"
            )
        )

        service = UniverseSuggestionService(
            llm_client=llm_client, stock_service=stock_service
        )
        await service.suggest(description="Test")

        call_kwargs = llm_client.messages_create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"
        assert call_kwargs["feature"] == "universe_suggestion"
```

### Step 4: Run test → FAIL

```bash
cd /Users/sheyla/Projects/prisma-capstone
.venv/bin/pytest backend/tests/unit/application/test_universe_suggestion_service.py -v
```
Expected: FAIL — module not found

### Step 5: Service implementieren

`backend/application/services/universe_suggestion_service.py`:

```python
"""UniverseSuggestionService — LLM-Wizard für Universe-Vorschläge."""

import logging
from dataclasses import dataclass
from pathlib import Path

from backend.application.services.stock_service import StockService
from backend.domain.schemas.universe_suggestion_schema import UniverseSuggestionSchema
from backend.infrastructure.llm.client import LLMClient
from backend.infrastructure.llm.prompts.prompt_loader import PromptTemplateLoader

_logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 500


class EmptySuggestion(Exception):
    """LLM-Output enthielt nach Filterung weniger als 2 valide Tickers."""


class InvalidLLMOutput(Exception):
    """LLM gab nicht-parsbare Antwort (kein tool_use oder Schema-Verletzung)."""


@dataclass(frozen=True)
class UniverseSuggestion:
    name: str
    region: str
    tickers: list[str]
    reasoning: str
    available_tickers: list[str]


class UniverseSuggestionService:
    """Generiert Universe-Vorschläge via Claude Haiku + Stock-Katalog-Whitelist."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        stock_service: StockService,
        prompts_dir: Path | None = None,
    ) -> None:
        self._llm = llm_client
        self._stock_service = stock_service
        if prompts_dir is None:
            prompts_dir = Path(__file__).resolve().parent.parent.parent / (
                "infrastructure/llm/prompts"
            )
        self._loader = PromptTemplateLoader(prompts_dir)

    async def suggest(self, description: str) -> UniverseSuggestion:
        """Holt LLM-Vorschlag und filtert gegen Stock-Katalog."""
        stocks = await self._stock_service.list_stocks(limit=200, offset=0)
        if not stocks:
            raise EmptySuggestion("Stock-Katalog ist leer.")

        catalog_tickers = {s.ticker for s in stocks}

        system_prompt = self._loader.render(
            "universe_suggestion_system.de.md.j2", {"available_stocks": stocks}
        )
        user_prompt = self._loader.render(
            "universe_suggestion_user.de.md.j2", {"description": description}
        )

        response = await self._llm.messages_create(
            model=_MODEL,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": "submit_universe_suggestion",
                    "description": "Submit the universe suggestion.",
                    "input_schema": UniverseSuggestionSchema.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": "submit_universe_suggestion"},
            max_tokens=_MAX_TOKENS,
            feature="universe_suggestion",
        )

        schema = self._extract_schema(response)
        filtered = [t for t in schema.tickers if t in catalog_tickers]
        if len(filtered) < 2:
            raise EmptySuggestion(
                f"Nach Filter gegen Katalog blieben nur {len(filtered)} Tickers übrig."
            )

        return UniverseSuggestion(
            name=schema.name,
            region=schema.region,
            tickers=filtered,
            reasoning=schema.reasoning,
            available_tickers=sorted(catalog_tickers),
        )

    @staticmethod
    def _extract_schema(response: object) -> UniverseSuggestionSchema:
        """Zieht das tool_use-Output aus der Anthropic-Response."""
        from pydantic import ValidationError

        content = getattr(response, "content", [])
        for block in content:
            if getattr(block, "type", None) == "tool_use":
                try:
                    return UniverseSuggestionSchema.model_validate(block.input)
                except ValidationError as exc:
                    _logger.warning("LLM-Output-Schema-Verletzung: %s", exc)
                    raise InvalidLLMOutput(str(exc)) from exc
        raise InvalidLLMOutput("Keine tool_use-Antwort vom LLM erhalten.")
```

**Wichtig:** `PromptTemplateLoader` existiert bereits — check signature:

```bash
grep -A 5 "class PromptTemplateLoader\|def render" backend/infrastructure/llm/prompts/prompt_loader.py | head -15
```

Wenn die Signature anders ist (`render(template_name, context_dict)` vs. anderer Stil), passe den Service entsprechend an.

### Step 6: Tests grün

```bash
.venv/bin/pytest backend/tests/unit/application/test_universe_suggestion_service.py -v
```
Expected: 4 PASS

### Step 7: Pre-Push CI-Mirror

```bash
.venv/bin/mypy backend/application/services/universe_suggestion_service.py backend/domain/schemas/universe_suggestion_schema.py
.venv/bin/ruff check backend/application/services/universe_suggestion_service.py backend/domain/schemas/universe_suggestion_schema.py backend/tests/unit/application/test_universe_suggestion_service.py
.venv/bin/ruff format --check backend/application/services/universe_suggestion_service.py backend/domain/schemas/universe_suggestion_schema.py backend/tests/unit/application/test_universe_suggestion_service.py
```
Expected: clean

### Step 8: Commit

```bash
git add backend/domain/schemas/universe_suggestion_schema.py backend/application/services/universe_suggestion_service.py backend/infrastructure/llm/prompts/universe_suggestion_*.j2 backend/tests/unit/application/test_universe_suggestion_service.py
git commit -m "feat(llm): UniverseSuggestionService — Claude Haiku + Katalog-Whitelist"
```

---

## Task 2: Backend — REST-Schema + Router-Endpoint + Integration-Test

**Files:**
- Modify: `backend/interfaces/rest/schemas/universe.py` — neue Schemas
- Modify: `backend/interfaces/rest/routers/universes.py` — neuer Endpoint
- Modify: `backend/interfaces/rest/dependencies.py` — neue DI-Function
- Modify: `backend/tests/integration/test_universes_endpoint.py` — neue Tests

### Step 1: Schemas ergänzen

In `backend/interfaces/rest/schemas/universe.py` ergänzen:

```python
class UniverseSuggestionRequest(BaseModel):
    description: str = Field(..., min_length=3, max_length=500)


class UniverseSuggestionResponse(BaseModel):
    name: str
    region: str
    tickers: list[str]
    reasoning: str
    available_tickers: list[str]
```

### Step 2: DI ergänzen

In `backend/interfaces/rest/dependencies.py` neue Function:

```python
async def get_universe_suggestion_service(
    llm: LLMClient = Depends(get_llm_client),
    stock_service: StockService = Depends(get_stock_service),
) -> UniverseSuggestionService:
    return UniverseSuggestionService(llm_client=llm, stock_service=stock_service)
```

Import oben ergänzen:
```python
from backend.application.services.universe_suggestion_service import UniverseSuggestionService
```

(Check ob `get_llm_client` schon existiert — bei Memo-Service genutzt, vermutlich vorhanden.)

### Step 3: Integration-Test schreiben

In `backend/tests/integration/test_universes_endpoint.py` ergänzen (am Ende):

```python
# ---------------------------------------------------------------------------
# Tests: POST /api/v1/universes/suggest
# ---------------------------------------------------------------------------

from unittest.mock import AsyncMock, MagicMock


async def test_suggest_returns_200_with_valid_suggestion(http_client: AsyncClient) -> None:
    """Mit Mock-LLM gibt der Endpoint einen Vorschlag zurück."""
    from backend.interfaces.rest.app import create_app
    from backend.interfaces.rest.dependencies import get_universe_suggestion_service
    from backend.application.services.universe_suggestion_service import (
        UniverseSuggestion,
        UniverseSuggestionService,
    )

    # Note: dependency-override-Pattern — siehe test_runs_endpoint.py für Vorlage
    # falls existing fixture nicht direkt passt
    # Hier Skeleton — Implementer adaptiert an existing http_client fixture pattern
    # (möglicherweise schon dependency_overrides verfügbar)

    fake_service = MagicMock(spec=UniverseSuggestionService)
    fake_service.suggest = AsyncMock(
        return_value=UniverseSuggestion(
            name="Mock-Universe",
            region="US",
            tickers=["AAPL", "MSFT"],
            reasoning="Test-Vorschlag.",
            available_tickers=["AAPL", "MSFT", "GOOGL"],
        )
    )

    # Override service via http_client fixture's app.dependency_overrides
    # If fixture provides the app: app.dependency_overrides[get_universe_suggestion_service] = lambda: fake_service
    # Adapt zur tatsächlichen fixture-Struktur

    response = await http_client.post(
        "/api/v1/universes/suggest",
        json={"description": "Tech-Heavy"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Mock-Universe"
    assert body["tickers"] == ["AAPL", "MSFT"]


async def test_suggest_returns_422_for_short_description(http_client: AsyncClient) -> None:
    """Description < 3 chars wird abgelehnt."""
    response = await http_client.post(
        "/api/v1/universes/suggest",
        json={"description": "x"},
    )
    assert response.status_code == 422


async def test_suggest_returns_422_when_no_valid_tickers(http_client: AsyncClient) -> None:
    """Wenn Service EmptySuggestion wirft → 422."""
    from backend.application.services.universe_suggestion_service import (
        EmptySuggestion,
        UniverseSuggestionService,
    )
    from backend.interfaces.rest.dependencies import get_universe_suggestion_service

    fake_service = MagicMock(spec=UniverseSuggestionService)
    fake_service.suggest = AsyncMock(side_effect=EmptySuggestion("Keine validen Tickers"))

    # Override fixture-app's dependency
    # ...

    response = await http_client.post(
        "/api/v1/universes/suggest",
        json={"description": "irgendwas"},
    )
    assert response.status_code == 422
```

**Implementer-Hinweis:** Test ist Skeleton. Schau dir `http_client` Fixture und existing-tests im selben File an, um `dependency_overrides` pattern korrekt zu nutzen. Falls Override schwierig ist, ein Test mit echtem Service + Mock-LLM-Client (auf dem ebenfalls injectable Layer) ist genauso valid.

### Step 4: Endpoint im Router

In `backend/interfaces/rest/routers/universes.py` ergänzen:

```python
@router.post(
    "/suggest",
    response_model=UniverseSuggestionResponse,
    summary="Universe-Vorschlag via Claude generieren",
)
async def suggest_universe(
    request: UniverseSuggestionRequest,
    service: UniverseSuggestionService = Depends(get_universe_suggestion_service),
) -> UniverseSuggestionResponse:
    try:
        suggestion = await service.suggest(description=request.description)
    except EmptySuggestion as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidLLMOutput as exc:
        raise HTTPException(status_code=502, detail=f"LLM-Output ungültig: {exc}") from exc
    return UniverseSuggestionResponse(
        name=suggestion.name,
        region=suggestion.region,
        tickers=suggestion.tickers,
        reasoning=suggestion.reasoning,
        available_tickers=suggestion.available_tickers,
    )
```

Imports oben:
```python
from backend.application.services.universe_suggestion_service import (
    EmptySuggestion,
    InvalidLLMOutput,
    UniverseSuggestionService,
)
from backend.interfaces.rest.dependencies import get_universe_suggestion_service
from backend.interfaces.rest.schemas.universe import (
    # ... existing imports ...
    UniverseSuggestionRequest,
    UniverseSuggestionResponse,
)
```

### Step 5: Tests grün

```bash
.venv/bin/pytest backend/tests/integration/test_universes_endpoint.py -v
```
Expected: alle PASS (alte + neue)

### Step 6: Lint

```bash
.venv/bin/mypy backend/interfaces/rest/
.venv/bin/ruff check backend/interfaces/rest/
.venv/bin/ruff format --check backend/interfaces/rest/
```

### Step 7: Commit

```bash
git add backend/interfaces/rest/schemas/universe.py backend/interfaces/rest/routers/universes.py backend/interfaces/rest/dependencies.py backend/tests/integration/test_universes_endpoint.py
git commit -m "feat(rest): POST /api/v1/universes/suggest — LLM-Wizard-Endpoint"
```

---

## Task 3: Frontend — API-Function + Wizard-Page + Tests

**Files:**
- Modify: `frontend/lib/api/universes.ts` — neue Function `suggestUniverse`
- Create: `frontend/app/universes/wizard/page.tsx` — Wizard-Page
- Create: `frontend/app/universes/wizard/__tests__/wizard-page.test.tsx`

### Step 1: API-Function ergänzen

In `frontend/lib/api/universes.ts` ergänzen:

```ts
export interface UniverseSuggestion {
  name: string;
  region: string;
  tickers: string[];
  reasoning: string;
  available_tickers: string[];
}

export function suggestUniverse(description: string): Promise<UniverseSuggestion> {
  return apiFetch<UniverseSuggestion>('/api/v1/universes/suggest', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}
```

### Step 2: Failing Test schreiben

`frontend/app/universes/wizard/__tests__/wizard-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

import WizardPage from '../page';
import * as universesApi from '@/lib/api/universes';

// next/navigation mock
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function wrap(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('Universe-Wizard Page', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows description input and disabled button initially', () => {
    wrap(<WizardPage />);
    expect(screen.getByPlaceholderText(/Beschreibe/i)).toBeDefined();
    const btn = screen.getByRole('button', { name: /generieren/i });
    expect(btn.hasAttribute('disabled')).toBe(true);
  });

  it('enables generate button when description >= 3 chars', () => {
    wrap(<WizardPage />);
    const input = screen.getByPlaceholderText(/Beschreibe/i) as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: 'Tech' } });
    const btn = screen.getByRole('button', { name: /generieren/i });
    expect(btn.hasAttribute('disabled')).toBe(false);
  });

  it('shows result form with prefilled values after successful suggestion', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockResolvedValue({
      name: 'Tech-3',
      region: 'US',
      tickers: ['AAPL', 'MSFT', 'NVDA'],
      reasoning: 'US-Tech-Schwergewichte.',
      available_tickers: ['AAPL', 'MSFT', 'NVDA', 'GOOGL'],
    });

    wrap(<WizardPage />);
    const input = screen.getByPlaceholderText(/Beschreibe/i);
    fireEvent.change(input, { target: { value: 'Tech-Heavy' } });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => {
      expect(screen.getByDisplayValue('Tech-3')).toBeDefined();
      expect(screen.getByDisplayValue('US')).toBeDefined();
      expect(screen.getByDisplayValue(/AAPL.*MSFT.*NVDA/)).toBeDefined();
      expect(screen.getByText(/US-Tech-Schwergewichte/)).toBeDefined();
    });
  });

  it('shows error state when suggestion fails', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockRejectedValue(
      new Error('LLM-Service nicht erreichbar'),
    );

    wrap(<WizardPage />);
    fireEvent.change(screen.getByPlaceholderText(/Beschreibe/i), {
      target: { value: 'something' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => {
      expect(screen.getByText(/LLM-Service nicht erreichbar/)).toBeDefined();
    });
  });

  it('reset clears the suggestion form', async () => {
    vi.spyOn(universesApi, 'suggestUniverse').mockResolvedValue({
      name: 'Tech-3',
      region: 'US',
      tickers: ['AAPL', 'MSFT'],
      reasoning: 'X.',
      available_tickers: [],
    });

    wrap(<WizardPage />);
    fireEvent.change(screen.getByPlaceholderText(/Beschreibe/i), {
      target: { value: 'Tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generieren/i }));

    await waitFor(() => expect(screen.getByDisplayValue('Tech-3')).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: /verwerfen/i }));
    expect(screen.queryByDisplayValue('Tech-3')).toBeNull();
  });
});
```

### Step 3: Run, verify fail

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx vitest run app/universes/wizard/__tests__/wizard-page.test.tsx
```
Expected: FAIL — module not found

### Step 4: Wizard-Page implementieren

`frontend/app/universes/wizard/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Sparkles, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  createUniverse,
  suggestUniverse,
  type UniverseSuggestion,
} from '@/lib/api/universes';

export default function WizardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [description, setDescription] = useState('');
  const [suggestion, setSuggestion] = useState<UniverseSuggestion | null>(null);
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [tickersRaw, setTickersRaw] = useState('');

  const suggestMutation = useMutation({
    mutationFn: () => suggestUniverse(description),
    onSuccess: (data) => {
      setSuggestion(data);
      setName(data.name);
      setRegion(data.region);
      setTickersRaw(data.tickers.join(', '));
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: name.trim(),
        region: region.trim(),
        tickers: tickersRaw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes'] });
      router.push('/universes');
    },
  });

  function resetSuggestion() {
    setSuggestion(null);
    setName('');
    setRegion('');
    setTickersRaw('');
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Link
        href="/universes"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück zu Universen
      </Link>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Universe mit KI generieren</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Beschreibe, welches Universe du suchst — Claude wählt passende Tickers aus dem
          verfügbaren Stock-Katalog.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Beschreibung</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Beschreibe dein Universe — z.B. 'Tech-Stocks USA mit Fokus Halbleiter'"
            className="w-full min-h-[100px] rounded-md border bg-background px-3 py-2 text-sm"
            disabled={suggestMutation.isPending}
          />
          <Button
            onClick={() => suggestMutation.mutate()}
            disabled={description.trim().length < 3 || suggestMutation.isPending}
            className="gap-2"
          >
            {suggestMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Vorschlag generieren
          </Button>
          {suggestMutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {suggestMutation.error instanceof Error
                ? suggestMutation.error.message
                : 'Vorschlag konnte nicht erstellt werden'}
            </p>
          )}
        </CardContent>
      </Card>

      {suggestion && (
        <>
          <Card className="border-pink-500/40 bg-pink-50/40 dark:bg-pink-950/20">
            <CardContent className="py-4 flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-pink-600 dark:text-pink-400 shrink-0 mt-0.5" />
              <p className="text-sm text-muted-foreground">{suggestion.reasoning}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Vorschlag anpassen</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-sm font-medium">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium">Region</label>
                <Input value={region} onChange={(e) => setRegion(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium">Tickers (komma-separiert)</label>
                <Input
                  value={tickersRaw}
                  onChange={(e) => setTickersRaw(e.target.value)}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={() => createMutation.mutate()}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Erstellt...' : 'Erstellen'}
                </Button>
                <Button variant="outline" onClick={resetSuggestion}>
                  Vorschlag verwerfen
                </Button>
              </div>
              {createMutation.isError && (
                <p className="text-sm text-destructive" role="alert">
                  {createMutation.error instanceof Error
                    ? createMutation.error.message
                    : 'Erstellung fehlgeschlagen'}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
```

### Step 5: Tests grün

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx vitest run app/universes/wizard/__tests__/wizard-page.test.tsx
```
Expected: 5 PASS

### Step 6: Lint + Build

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx tsc --noEmit && npm run lint
```

### Step 7: Commit

```bash
cd /Users/sheyla/Projects/prisma-capstone
git add frontend/lib/api/universes.ts frontend/app/universes/wizard/page.tsx frontend/app/universes/wizard/__tests__/wizard-page.test.tsx
git commit -m "feat(frontend): /universes/wizard — Single-Turn LLM-Wizard mit Pre-Filled Form"
```

---

## Task 4: Manual + Demo-Branch + (Optional) PR

### Step 1: Demo-Branch updaten

Damit Sheyla das Feature im Demo-Kontext testen kann:

```bash
git checkout demo/all-features
git merge --no-edit feat/llm-universe-wizard
```

Konflikt mit `frontend/lib/api/universes.ts`: ggf. trivial mergen (beide Branches könnten dieselbe Datei verändert haben).

### Step 2: Backend reload-check

Backend uvicorn lädt automatisch neu nach Branch-Wechsel. Verify:

```bash
curl -s http://localhost:8000/health
```

### Step 3: Frontend dev-reload

Frontend hot-reload greift. Wenn nicht: `Ctrl+C` + `rm -rf .next && npm run dev`.

### Step 4: Wizard im Browser testen

1. Browser → `http://localhost:3000/universes/wizard`
2. Beschreibung eingeben: *"Halbleiter-Stocks aus den USA"*
3. Klick "✨ Vorschlag generieren"
4. Erwartung: ~2-3s Spinner, dann Begründungs-Card + Form-Felder pre-filled
5. Editieren erlaubt — füge z.B. einen Ticker hinzu/entferne einen
6. "Erstellen" klicken → Redirect zu `/universes`
7. Neue Universe in der Liste sehen
8. Run drauf starten → Rankings funktionieren

### Step 5: PR erstellen (optional, abhängig von Sheylas Sprint-Strategie)

```bash
git checkout feat/llm-universe-wizard
git push -u origin feat/llm-universe-wizard
gh pr create --title "feat: LLM-Universe-Wizard — Claude Haiku für Universe-Vorschläge" --body "..."
```

PR-Body: Spec + Plan verlinken, Test-Plan auflisten, Demo-Story betonen.
