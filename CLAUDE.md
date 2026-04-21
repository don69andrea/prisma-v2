# CLAUDE.md

Kurzkontext für Claude Code. **Quelle der Wahrheit ist `AGENTS.md`** — dieses File ergänzt nur Claude-spezifische Hinweise.

## Projekt in einem Satz

PRISMA = quantitatives Stock-Selection-Tool (5 Modelle) + Claude-Narrative-Engine + Multi-Agent-Research + MCP-Server. Capstone FHNW FS 2026.

## Vor jeder Aufgabe lesen

1. `AGENTS.md` — verbindliche Konventionen
2. `docs/specs/2026-04-21-prisma-capstone-design.md` — Gesamtdesign
3. Die zum Task passende Spec unter `docs/specs/` (wenn vorhanden)

## Claude-Code-spezifische Regeln

### Spec-First
Wenn der User eine neue Feature-Arbeit verlangt, **schreibe zuerst die Spec**, committe sie, und frage dann nach Freigabe, bevor Code entsteht. Nutze die `superpowers:brainstorming`- und `superpowers:writing-plans`-Skills.

### TDD-Pflicht
Für Domain-Code und Quant-Modelle: erst Tests schreiben, dann Implementierung. Nutze `superpowers:test-driven-development`.

### LLM-Features
- **Immer** Pydantic-Schema für Output. Kein Freitext.
- Prompt-Caching aktivieren (`cache_control: ephemeral`) bei wiederkehrenden System-Prompts.
- Für Tests: Fixture-Mode in `tests/fixtures/llm/` nutzen, nicht gegen Live-API in CI.
- Modell-Wahl: `claude-haiku-4-5` für schnelle Strukturierungs-Tasks, `claude-sonnet-4-6` für Research-Synthese.

### MCP-Server-Arbeit
MCP-Tools in `backend/interfaces/mcp/` liegen dünn über Application-Services. Keine Business-Logik im MCP-Layer.

### Code-Reviews
Beim Review eigener Arbeit: `superpowers:verification-before-completion`-Skill nutzen — nie "done" claimen ohne grüne Tests und Coverage.

## Häufige Claude-Fehler in diesem Projekt (bitte vermeiden)

- Quant-Formeln aus dem Gedächtnis rekonstruieren statt aus der Spec zu zitieren
- `yfinance` / `finnhub` direkt im Application-Service aufrufen (→ muss über Port in Infrastructure)
- LLM-Responses mit `response.content[0].text` ungeparst weiterreichen
- Datumshandling ohne Timezone (→ immer UTC-aware)
- Floats für Geldbeträge statt `Decimal`

## Wenn unsicher: fragen

Lieber eine präzise Nachfrage als eine falsche Annahme. Finanzmathematik verzeiht keine Ungenauigkeit.
