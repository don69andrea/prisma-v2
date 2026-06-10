# PRISMA Chat — NL Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Floating chat panel on all PRISMA pages — users ask questions in natural language, Claude answers using real PRISMA data via Tool Use, streamed token-by-token via SSE.

**Architecture:** New `ChatService` in Application layer orchestrates Claude with 6 tools wired to existing services. SSE endpoint streams tokens. Frontend floating drawer opens from any page, auto-detects tickers in responses and renders inline mini-cards.

**Tech Stack:** `anthropic` SDK (already in deps), Redis for session history (already in infra), FastAPI SSE via `StreamingResponse`, Next.js `EventSource` API.

---

## File Map

| Action | Path |
|--------|------|
| Create | `backend/application/services/chat_service.py` |
| Create | `backend/interfaces/rest/schemas/chat.py` |
| Create | `backend/interfaces/rest/routers/chat.py` |
| Modify | `backend/interfaces/rest/app.py` — register chat router |
| Create | `backend/tests/unit/application/test_chat_service.py` |
| Create | `frontend/lib/api/chat.ts` |
| Create | `frontend/components/chat/ChatDrawer.tsx` |
| Create | `frontend/components/chat/ChatMessage.tsx` |
| Create | `frontend/components/chat/TickerChip.tsx` |
| Modify | `frontend/app/layout.tsx` — mount ChatDrawer |

---

## Task 1: `ChatService` with Tool Use

**Files:**
- Create: `backend/application/services/chat_service.py`
- Create: `backend/tests/unit/application/test_chat_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/application/test_chat_service.py`:
```python
"""Unit-Tests für ChatService."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.unit

from backend.application.services.chat_service import ChatService, ChatMessage, _dispatch_tool


@pytest.mark.asyncio
async def test_dispatch_tool_search_stocks() -> None:
    """_dispatch_tool leitet search_stocks an StockService weiter."""
    mock_stock_service = AsyncMock()
    mock_stock_service.search.return_value = []

    with patch("backend.application.services.chat_service._get_stock_service",
               return_value=mock_stock_service):
        result = await _dispatch_tool("search_stocks", {"query": "Nestlé"})

    mock_stock_service.search.assert_called_once_with("Nestlé")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_dispatch_tool_unknown_returns_error() -> None:
    """Unbekanntes Tool gibt verständliche Fehlermeldung zurück."""
    result = await _dispatch_tool("nonexistent_tool", {})
    assert "unbekannt" in result.lower() or "unknown" in result.lower()


def test_chat_message_dataclass() -> None:
    msg = ChatMessage(role="user", content="Hallo")
    assert msg.role == "user"
    assert msg.content == "Hallo"


@pytest.mark.asyncio
async def test_chat_service_build_tool_definitions() -> None:
    """ChatService liefert genau 6 Tool-Definitionen."""
    svc = ChatService()
    tools = svc._get_tool_definitions()
    assert len(tools) == 6
    names = {t["name"] for t in tools}
    assert "search_stocks" in names
    assert "filter_stocks" in names
    assert "get_factsheet" in names
    assert "get_macro_context" in names
    assert "compare_stocks" in names
    assert "get_ranking" in names
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
pytest backend/tests/unit/application/test_chat_service.py -v
```
Expected: `ImportError` — module not yet created.

- [ ] **Step 3: Implement `ChatService`**

Create `backend/application/services/chat_service.py`:
```python
"""Application Service: PRISMA Chat — Claude Tool Use + SSE Streaming."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

_logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Du bist PRISMA Assistant — ein präziser, datengetriebener Finanz-Assistent.
Du hast Zugriff auf das PRISMA-Universum (SMI/SMIM/SPI + US-Aktien) via Tools.
Antworte IMMER auf Basis der Tool-Ergebnisse — nie aus deinem Trainingswissen über aktuelle Preise.
Sprache: Deutsch bevorzugt. Englisch wenn der Nutzer auf Englisch schreibt.
Bei konkreten Kauf-/Verkaufsempfehlungen: füge immer hinzu "Keine Anlageberatung."
Sei präzise und knapp — maximal 3 Absätze pro Antwort."""

_MODEL = "claude-sonnet-4-6"


@dataclass
class ChatMessage:
    role: str   # "user" | "assistant"
    content: str


class ChatService:
    """Orchestriert Claude mit PRISMA-Tools für Konversations-Interface."""

    def _get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "search_stocks",
                "description": "Sucht Aktien im PRISMA-Universum nach Name oder Ticker-Symbol.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Suchbegriff: Firmenname oder Ticker"},
                        "exchange": {"type": "string", "description": "Optional: 'SW' für Swiss, 'US' für US-Markt"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "filter_stocks",
                "description": (
                    "Filtert Aktien nach quantitativen Kriterien. "
                    "Gibt Liste von Titeln zurück die alle Bedingungen erfüllen."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "signal": {"type": "string", "enum": ["BUY", "HOLD", "WATCH"],
                                   "description": "Swiss Quant Signal"},
                        "eligible_3a": {"type": "boolean", "description": "Nur 3a-geeignete Titel"},
                        "min_score": {"type": "number", "description": "Minimum Quant-Score (0–100)"},
                        "universe": {"type": "string", "description": "SMI | SMIM | SPI"},
                    },
                },
            },
            {
                "name": "get_factsheet",
                "description": "Detaillierte Analyse: Quant-Scores, ML-Prediction, Fundamentaldaten, 3a-Eignung.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Ticker-Symbol, z.B. NESN.SW oder AAPL"},
                    },
                    "required": ["ticker"],
                },
            },
            {
                "name": "get_macro_context",
                "description": "Aktueller SNB-Leitzins, CHF/EUR-Kurs, Schweizer Inflation — makroökonomischer Kontext.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "compare_stocks",
                "description": "Vergleicht zwei Aktien anhand Quant-Scores, ML-Signal und Fundamentaldaten.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker_a": {"type": "string"},
                        "ticker_b": {"type": "string"},
                    },
                    "required": ["ticker_a", "ticker_b"],
                },
            },
            {
                "name": "get_ranking",
                "description": "Top-N Aktien aus einem Universum, sortiert nach gewichtetem Quant-Score.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "universe": {"type": "string", "description": "SMI | SMIM | SPI | US"},
                        "top_n": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                },
            },
        ]

    async def stream(
        self,
        messages: list[ChatMessage],
    ) -> AsyncIterator[str]:
        """Streamt SSE-Events: token | tool_call | tool_result | done."""
        import anthropic

        client = anthropic.AsyncAnthropic()
        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            async with client.messages.stream(
                model=_MODEL,
                max_tokens=1024,
                system=[{"type": "text", "text": _SYSTEM_PROMPT,
                          "cache_control": {"type": "ephemeral"}}],
                tools=self._get_tool_definitions(),
                messages=api_messages,
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield _sse("token", {"content": event.delta.text})
                        elif event.type == "content_block_start":
                            if hasattr(event.content_block, "type") and event.content_block.type == "tool_use":
                                yield _sse("tool_call", {
                                    "tool": event.content_block.name,
                                    "tool_use_id": event.content_block.id,
                                })

                # After streaming: handle tool calls if stop_reason == tool_use
                final = await stream.get_final_message()

            if final.stop_reason == "tool_use":
                # Process tool calls and continue conversation
                tool_results = []
                for block in final.content:
                    if block.type == "tool_use":
                        yield _sse("tool_call", {"tool": block.name, "input": block.input})
                        result_str = await _dispatch_tool(block.name, block.input)
                        yield _sse("tool_result", {"tool": block.name, "result": result_str[:500]})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                # Continue with tool results
                continuation_messages = api_messages + [
                    {"role": "assistant", "content": final.content},
                    {"role": "user", "content": tool_results},
                ]
                async with client.messages.stream(
                    model=_MODEL,
                    max_tokens=1024,
                    system=[{"type": "text", "text": _SYSTEM_PROMPT,
                              "cache_control": {"type": "ephemeral"}}],
                    messages=continuation_messages,
                ) as stream2:
                    async for event in stream2:
                        if hasattr(event, "type") and event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield _sse("token", {"content": event.delta.text})

        except Exception:
            _logger.exception("ChatService stream error")
            yield _sse("error", {"message": "Interner Fehler — bitte nochmals versuchen."})

        yield _sse("done", {})


def _sse(event_type: str, data: dict) -> str:
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def _dispatch_tool(name: str, inputs: dict) -> str:
    """Leitet Tool-Call an entsprechenden Application Service weiter."""
    try:
        if name == "search_stocks":
            svc = _get_stock_service()
            results = await svc.search(inputs.get("query", ""))
            return json.dumps([{"ticker": s.ticker, "name": s.name} for s in results[:10]])

        if name == "filter_stocks":
            from backend.application.services.swiss_market_service import SwissMarketService
            from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
            svc = SwissMarketService(adapter=YFinanceSwissAdapter())
            stocks = await svc.list_stocks(
                signal=inputs.get("signal"),
                eligible_3a=inputs.get("eligible_3a"),
            )
            min_score = inputs.get("min_score", 0)
            filtered = [s for s in stocks if (s.quant_score or 0) >= min_score]
            return json.dumps([
                {"ticker": s.ticker, "signal": s.signal, "score": s.quant_score}
                for s in filtered[:15]
            ])

        if name == "get_factsheet":
            from backend.application.services.factsheet_service import FactsheetService
            from backend.infrastructure.persistence.session import get_session_factory
            from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
                SQLASwissStockRepository,
            )
            repo = SQLASwissStockRepository(session_factory=get_session_factory())
            svc = FactsheetService(swiss_stock_repo=repo)
            data = await svc.get(inputs["ticker"])
            if data is None:
                return f"Keine Daten für {inputs['ticker']} gefunden."
            return json.dumps({
                "ticker": data.ticker,
                "signal": data.signal,
                "quant_score": data.quant_score,
                "eligible_3a": data.eligible_3a,
            })

        if name == "get_macro_context":
            from backend.application.services.macro_service import MacroService
            svc = MacroService()
            ctx = await svc.get_context()
            return json.dumps({
                "snb_rate": ctx.snb_rate,
                "chf_eur": ctx.chf_eur,
                "inflation_ch": ctx.inflation_ch,
            })

        if name == "compare_stocks":
            from backend.application.services.factsheet_service import FactsheetService
            from backend.infrastructure.persistence.session import get_session_factory
            from backend.infrastructure.persistence.repositories.swiss_stock_repository import (
                SQLASwissStockRepository,
            )
            repo = SQLASwissStockRepository(session_factory=get_session_factory())
            svc = FactsheetService(swiss_stock_repo=repo)
            a = await svc.get(inputs["ticker_a"])
            b = await svc.get(inputs["ticker_b"])
            return json.dumps({
                inputs["ticker_a"]: {"signal": a.signal if a else None, "score": a.quant_score if a else None},
                inputs["ticker_b"]: {"signal": b.signal if b else None, "score": b.quant_score if b else None},
            })

        if name == "get_ranking":
            from backend.application.services.swiss_market_service import SwissMarketService
            from backend.infrastructure.adapters.yfinance_swiss import YFinanceSwissAdapter
            svc = SwissMarketService(adapter=YFinanceSwissAdapter())
            stocks = await svc.list_stocks()
            top_n = inputs.get("top_n", 5)
            ranked = sorted(stocks, key=lambda s: s.quant_score or 0, reverse=True)[:top_n]
            return json.dumps([
                {"ticker": s.ticker, "signal": s.signal, "score": s.quant_score}
                for s in ranked
            ])

        return json.dumps({"error": f"Tool '{name}' unbekannt."})

    except Exception as exc:
        _logger.warning("Tool dispatch error: %s — %s", name, exc)
        return json.dumps({"error": str(exc)})


def _get_stock_service():
    from backend.application.services.stock_service import StockService
    from backend.infrastructure.persistence.session import get_session_factory
    from backend.infrastructure.persistence.repositories.stock_repository import SQLAStockRepository

    return StockService(
        stock_repo=SQLAStockRepository(session_factory=get_session_factory())
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest backend/tests/unit/application/test_chat_service.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/chat_service.py backend/tests/unit/application/test_chat_service.py
git commit -m "feat(application): ChatService with Claude Tool Use + SSE streaming"
```

---

## Task 2: API Schema + SSE Router

**Files:**
- Create: `backend/interfaces/rest/schemas/chat.py`
- Create: `backend/interfaces/rest/routers/chat.py`
- Modify: `backend/interfaces/rest/app.py`

- [ ] **Step 1: Create schema**

Create `backend/interfaces/rest/schemas/chat.py`:
```python
"""Pydantic-Schemas für Chat API."""

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    role: str = Field("user", pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessageRequest] = Field(default_factory=list, max_length=20)
```

- [ ] **Step 2: Create chat router**

Create `backend/interfaces/rest/routers/chat.py`:
```python
"""REST Router: PRISMA Chat — SSE Streaming via Claude Tool Use."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.application.services.chat_service import ChatMessage, ChatService
from backend.interfaces.rest.schemas.chat import ChatRequest

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
_logger = logging.getLogger(__name__)


@router.post(
    "",
    summary="PRISMA Chat — Natursprache-Query mit Claude Tool Use",
    description=(
        "Streamt SSE-Events: token | tool_call | tool_result | done | error. "
        "Nutzt Claude mit PRISMA-Tools (search_stocks, filter_stocks, get_factsheet, "
        "get_macro_context, compare_stocks, get_ranking)."
    ),
)
async def chat(req: ChatRequest) -> StreamingResponse:
    svc = ChatService()
    messages = [ChatMessage(role=m.role, content=m.content) for m in req.history]
    messages.append(ChatMessage(role="user", content=req.message))

    return StreamingResponse(
        svc.stream(messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 3: Register router in `app.py`**

In `backend/interfaces/rest/app.py`, add to the imports:
```python
from backend.interfaces.rest.routers import (
    ...
    chat,
    ...
)
```

And in `create_app()`, add:
```python
app.include_router(chat.router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/interfaces/rest/schemas/chat.py backend/interfaces/rest/routers/chat.py backend/interfaces/rest/app.py
git commit -m "feat(api): POST /api/v1/chat SSE streaming endpoint"
```

---

## Task 3: Frontend — Chat API + Components

**Files:**
- Create: `frontend/lib/api/chat.ts`
- Create: `frontend/components/chat/TickerChip.tsx`
- Create: `frontend/components/chat/ChatMessage.tsx`
- Create: `frontend/components/chat/ChatDrawer.tsx`

- [ ] **Step 1: Create `chat.ts`**

Create `frontend/lib/api/chat.ts`:
```typescript
export interface SSEEvent {
  type: 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  content?: string;
  tool?: string;
  result?: string;
  message?: string;
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export function streamChat(
  message: string,
  history: ChatHistoryMessage[],
  onEvent: (event: SSEEvent) => void,
  onDone: () => void,
  onError: (msg: string) => void,
): () => void {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

  const ctrl = new AbortController();

  fetch(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt: SSEEvent = JSON.parse(line.slice(6));
            if (evt.type === 'done') onDone();
            else if (evt.type === 'error') onError(evt.message ?? 'Fehler');
            else onEvent(evt);
          } catch {
            // malformed line — skip
          }
        }
      }
    })
    .catch((e) => {
      if (e.name !== 'AbortError') onError(e.message);
    });

  return () => ctrl.abort();
}
```

- [ ] **Step 2: Create `TickerChip.tsx`**

Create `frontend/components/chat/TickerChip.tsx`:
```tsx
'use client';

import Link from 'next/link';

const TICKER_REGEX = /\b([A-Z]{1,4}\.SW|[A-Z]{2,5})\b/g;

export function parseMessageWithTickers(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  TICKER_REGEX.lastIndex = 0;
  while ((match = TICKER_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const ticker = match[0];
    parts.push(
      <Link
        key={`${ticker}-${match.index}`}
        href={`/stocks/${ticker}`}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono bg-purple-900/60 border border-purple-500/40 text-purple-300 hover:bg-purple-800/60 hover:border-purple-400 transition-colors mx-0.5"
      >
        {ticker}
      </Link>
    );
    lastIndex = match.index + ticker.length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}
```

- [ ] **Step 3: Create `ChatMessage.tsx`**

Create `frontend/components/chat/ChatMessage.tsx`:
```tsx
'use client';

import { parseMessageWithTickers } from './TickerChip';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  isStreaming?: boolean;
  toolHint?: string;
}

export function ChatMessageBubble({ role, content, isStreaming, toolHint }: Props) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
          isUser
            ? 'bg-purple-900/60 text-white'
            : 'bg-slate-900/80 border border-purple-500/20 text-slate-200'
        }`}
        style={isUser ? undefined : { boxShadow: '0 0 12px rgba(168,85,247,0.1)' }}
      >
        {toolHint && (
          <p className="text-[11px] text-slate-500 italic mb-1">{toolHint}</p>
        )}
        <p className="leading-relaxed whitespace-pre-wrap">
          {isUser ? content : parseMessageWithTickers(content)}
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-purple-400 ml-0.5 animate-pulse align-middle" />
          )}
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `ChatDrawer.tsx`**

Create `frontend/components/chat/ChatDrawer.tsx`:
```tsx
'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { MessageSquare, X, RotateCcw, Send } from 'lucide-react';

import { streamChat, type ChatHistoryMessage, type SSEEvent } from '@/lib/api/chat';
import { ChatMessageBubble } from './ChatMessage';
import { cn } from '@/lib/utils';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const SUGGESTED: Record<string, string[]> = {
  default: [
    'Welche SMI-Titel sind 3a-geeignet mit BUY-Signal?',
    'Was ist der aktuelle SNB-Leitzins?',
    'Zeig mir die Top-5 SMI-Aktien',
  ],
};

export function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [toolHint, setToolHint] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, toolHint]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || streaming) return;

      const history: ChatHistoryMessage[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      setMessages((prev) => [...prev, { role: 'user', content: text }]);
      setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
      setStreaming(true);
      setInput('');

      abortRef.current = streamChat(
        text,
        history,
        (evt: SSEEvent) => {
          if (evt.type === 'token' && evt.content) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: updated[updated.length - 1].content + evt.content,
              };
              return updated;
            });
            setToolHint(null);
          } else if (evt.type === 'tool_call' && evt.tool) {
            setToolHint(`Fetching ${evt.tool.replace(/_/g, ' ')}...`);
          }
        },
        () => {
          setStreaming(false);
          setToolHint(null);
        },
        (msg) => {
          setStreaming(false);
          setToolHint(null);
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Fehler: ${msg}`,
            };
            return updated;
          });
        },
      );
    },
    [messages, streaming],
  );

  const reset = () => {
    abortRef.current?.();
    setMessages([]);
    setStreaming(false);
    setToolHint(null);
  };

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center',
          'bg-purple-600 hover:bg-purple-500 text-white shadow-lg transition-all duration-200',
          open && 'rotate-180 bg-purple-800',
        )}
        style={{
          boxShadow: '0 0 0 0 rgba(168,85,247,0.4)',
          animation: open ? undefined : 'pulse-ring 2s infinite',
        }}
        aria-label="PRISMA Chat öffnen"
      >
        {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

      {/* Drawer */}
      <div
        className={cn(
          'fixed bottom-24 right-6 z-50 w-[400px] rounded-2xl overflow-hidden',
          'border border-purple-500/20 shadow-2xl',
          'transition-all duration-300 origin-bottom-right',
          open ? 'scale-100 opacity-100' : 'scale-95 opacity-0 pointer-events-none',
        )}
        style={{
          background: 'rgba(8,8,20,0.92)',
          backdropFilter: 'blur(20px)',
          height: '520px',
          boxShadow: '0 0 40px rgba(168,85,247,0.15), 0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-semibold text-white">PRISMA Assistant</span>
          </div>
          <button onClick={reset} className="text-slate-500 hover:text-slate-300 transition-colors">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-1" style={{ height: '380px' }}>
          {messages.length === 0 && (
            <div className="text-center pt-8 space-y-3">
              <p className="text-xs text-slate-600">Stell mir eine Frage über PRISMA-Daten</p>
              <div className="space-y-2">
                {SUGGESTED.default.map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="block w-full text-left text-xs px-3 py-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-400 hover:border-purple-500/40 hover:text-slate-300 transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <ChatMessageBubble
              key={i}
              role={msg.role}
              content={msg.content}
              isStreaming={streaming && i === messages.length - 1 && msg.role === 'assistant'}
              toolHint={streaming && i === messages.length - 1 && msg.role === 'assistant' ? toolHint ?? undefined : undefined}
            />
          ))}
        </div>

        {/* Input */}
        <div className="px-3 pb-3 border-t border-slate-800 pt-3">
          <div className="flex items-center gap-2 bg-slate-800/60 rounded-xl px-3 py-2 border border-slate-700/60 focus-within:border-purple-500/40 transition-colors">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Frag PRISMA..."
              disabled={streaming}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 outline-none"
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || streaming}
              className="text-purple-400 hover:text-purple-300 disabled:opacity-30 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes pulse-ring {
          0% { box-shadow: 0 0 0 0 rgba(168,85,247,0.4); }
          70% { box-shadow: 0 0 0 12px rgba(168,85,247,0); }
          100% { box-shadow: 0 0 0 0 rgba(168,85,247,0); }
        }
      `}</style>
    </>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/chat.ts frontend/components/chat/
git commit -m "feat(frontend): ChatDrawer with SSE streaming, TickerChip, pulse animation"
```

---

## Task 4: Mount Chat in Layout

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Add `ChatDrawer` to root layout**

In `frontend/app/layout.tsx`, import and add `<ChatDrawer />` just before the closing `</body>`:
```tsx
import { ChatDrawer } from '@/components/chat/ChatDrawer';

// In the JSX, before </body>:
<ChatDrawer />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/layout.tsx
git commit -m "feat(frontend): mount ChatDrawer in root layout — available on all pages"
```

---

## Task 5: Lint + Test

- [ ] **Step 1: Backend lint + tests**

```bash
ruff check backend/ && ruff format --check backend/
pytest backend/tests/unit -q
```
Expected: all pass.

- [ ] **Step 2: TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
