# ADR 0002: LLM-Provider-Wahl

- **Status**: Accepted
- **Datum**: 2026-04-21
- **Kontext**: Entscheidung aus Phase 1 / Vorbereitung Phase 2
- **Supersedes**: —

## Kontext

PRISMA hat drei AI-Layer, die alle auf einen LLM-Provider angewiesen sind:

- **Layer 1 (Narrative Engine)**: Structured-Output-Generierung pro Aktie
- **Layer 2 (Multi-Agent Pipeline)**: Tool-Use, RAG-Integration, 3 zusammenwirkende Agenten
- **Layer 3 (MCP-Server)**: Model Context Protocol, damit die App aus Claude Desktop nutzbar wird

Die Provider-Wahl beeinflusst: API-Kosten, Feature-Verfügbarkeit (Prompt Caching, Structured Output, MCP), Qualität der Ausgaben, Lehrstoff-Passung des Moduls und den Lock-in.

## Evaluierte Optionen

### Option 1: Anthropic Claude (Sonnet 4.6 + Haiku 4.5)

- ➕ **Modul-Fit**: Curriculum referenziert Claude explizit (MCP ist ein Anthropic-Standard)
- ➕ **MCP nativ**: keine Adapter, keine Proxy-Lösung
- ➕ **Prompt Caching**: ~90% Kostenersparnis auf System-Prompts, Default-Feature
- ➕ **Structured Output**: Sonnet liefert Pydantic-Schema-konforme JSON-Outputs zuverlässig
- ➕ **Halbe Capstone-Team nutzt Claude Code bereits** (Claude-Geläufigkeit)
- ➖ Vendor Lock-in
- ➖ Nur US-Inference (keine EU-Datenresidenz)

### Option 2: OpenAI GPT-4o (+ GPT-4o-mini)

- ➕ Strong-Structured-Output (JSON-Mode, Function Calling)
- ➕ Prompt Caching seit 2024 verfügbar
- ➕ Breites Ecosystem (LangChain, LlamaIndex bevorzugen OpenAI)
- ➖ **Kein natives MCP** — müssten via Adapter wrappen (Wartungslast)
- ➖ Modul lehrt primär Claude, OpenAI-Migration wäre Abweichung vom Lehrplan
- ➖ Leicht teurer pro Output-Token als Claude Sonnet

### Option 3: Open-Weight-Modelle (Llama 3, Mistral, lokal via Ollama)

- ➕ Keine API-Kosten
- ➕ Datenschutz (alles lokal)
- ➕ Modul thematisiert Open-Weight-Modelle
- ➖ Hardware-Requirement (>=16 GB VRAM für 70B-Modelle) — niemand im Team hat das
- ➖ Kein MCP-Server-Äquivalent → Layer 3 bricht weg
- ➖ Structured-Output-Qualität deutlich niedriger, Pydantic-Validation failt häufiger
- ➖ Betriebs-Overhead (Inference-Server aufsetzen + warten) passt nicht in 4 Wochen

### Option 4: Azure OpenAI Service

- ➕ Enterprise-Features (EU-Datenresidenz via Azure Europe-Regionen)
- ➕ Potenziell Academic Credits über Microsoft
- ➖ Zusätzliche Azure-Komplexität (Deployments pro Modell, Subscription, RBAC)
- ➖ Kein MCP, keine direkten Anthropic-Features
- ➖ Out-of-scope für ein BSc-Capstone mit 4 Wochen Zeit

## Entscheidung

**Anthropic Claude** wird als primärer LLM-Provider für PRISMA verwendet.

- **Primäres Modell**: `claude-sonnet-4-6` für Narrative Engine, Synthesizer-Agent, Fundamentals-Agent
- **Sekundäres Modell**: `claude-haiku-4-5` als Fallback-Option bei Hochvolumen-Szenarien (nicht im MVP produktiv)
- **Opus** wird nicht verwendet — zu teuer für Batch-Volume, kein messbarer Qualitäts-Zuwachs für unser strukturierte Output-Workload

## Konsequenzen

### Positiv

- **Curriculum-Passung**: der Capstone spiegelt den Modul-Lehrstoff direkt wieder (wichtig für 40%-Achse)
- **MCP-Server** (Layer 3) wird trivial — keine Provider-Abstraktion nötig
- **Prompt-Caching** default aktiv — reduziert Kosten merklich (~60% bei Batch-Memos)
- **Single Provider** = ein API-Key, ein Billing-Dashboard, ein Rate-Limit-System

### Negativ

- **Vendor Lock-in**: Code-Pfade (`backend/infrastructure/llm/`) rufen Anthropic-SDK direkt auf
- **Single-Provider-Risk**: bei einem Anthropic-Outage steht PRISMA still; kein Fallback-Provider aktiviert

### Mitigationen

- Der LLM-Client-Adapter wird hinter einer `LLMClient`-**Schnittstelle** (Protocol/ABC) versteckt, damit ein späterer Provider-Wechsel auf die Infrastruktur-Schicht beschränkt bliebe
- Kosten-Cap im Anthropic-Dashboard verhindert versehentliche Runaway-Kosten

### Follow-up-Entscheidungen

- ADR-0003: Narrative Engine Operational Decisions (Sprache, Sync/Async, Trigger, etc.)
- ADR-0004: Multi-Agent Pipeline Framework & Operations

## Referenzen

- Claude Sonnet 4.6: https://www.anthropic.com/claude
- Prompt Caching Doku: https://docs.anthropic.com/en/docs/prompt-caching
- MCP Spezifikation: https://modelcontextprotocol.io/
- FHNW Modulbrief "AI-assisted Software Development", FS 2026
