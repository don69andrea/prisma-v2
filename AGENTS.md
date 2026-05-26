# AGENTS.md

Konventionen für KI-Coding-Agents (Claude Code, Cursor, Copilot, Codex) in diesem Repository. Dieses Dokument ist die **Quelle der Wahrheit** für Agent-Verhalten — `CLAUDE.md`, `.cursorrules` etc. verweisen darauf.

## Projekt-Kontext

**PRISMA** ist ein quantitatives Stock-Selection-Tool mit drei AI-Layern (Narrative Engine, Multi-Agent Research, MCP-Server). Capstone-Projekt im Modul *AI-assisted Software Development* der FHNW (BSc Business AI, FS 2026). Volle Kontext: `docs/specs/2026-04-21-prisma-capstone-design.md`.

## Grundregeln

### 1. Spec-Driven Development ist Pflicht
Bevor Code für ein neues Feature entsteht, **muss eine Spec unter `docs/specs/YYYY-MM-DD-<feature>.md` existieren und committet sein**. Die Spec erklärt: Problem, Scope, gewählter Ansatz, betroffene Schichten, Testbarkeit. Feature-Branches beginnen erst nach Spec-Merge.

### 2. Clean Architecture respektieren
Abhängigkeitsrichtung: `domain ← application ← interfaces`, `domain ← application ← infrastructure`. Domain-Layer kennt keine äusseren Schichten. Application kennt keine Frameworks. **Verletzungen werden in Code-Review blockiert.**

### 3. Test vor Implementierung
Neue Domain-Services und Quant-Modelle werden **test-first** entwickelt. Unit-Tests mit Golden-Datasets. LLM-Code zusätzlich mit Fixture-Mode (aufgenommene Responses).

### 4. Keine direkten Pushes auf `main`
Jede Änderung via Pull Request. PR braucht: CI grün, 1 Review, verlinkte Spec. Details in `CONTRIBUTING.md`.

## Tech-Stack

| Layer | Tool | Version |
|---|---|---|
| Backend | Python + FastAPI | 3.12 / ≥0.110 |
| ORM | SQLAlchemy + Alembic | 2.0 |
| DB | PostgreSQL | 16 |
| Validation | Pydantic | v2 |
| Quant | pandas, numpy, scikit-learn | stable |
| LLM | anthropic SDK | latest |
| MCP | mcp-sdk (Python) | latest |
| Frontend | Next.js + shadcn/ui + Recharts | 14 |
| Tests | pytest, Playwright | stable |
| CI | GitHub Actions | - |
| Deploy | Render | - |

**Kein Framework-Wechsel ohne ADR** in `docs/adr/`.

## Repository-Layout

```
backend/
  domain/          # Entities, VOs, Domain-Events — keine externen Imports
  application/     # Services/Use Cases — nutzt Domain + abstrakte Ports
  interfaces/      # REST (FastAPI), MCP-Server
  infrastructure/  # Persistence (SQLAlchemy), Market-Data, LLM-Adapter
frontend/          # Next.js App Router
tests/             # unit/ integration/ e2e/ fixtures/
docs/              # specs/ adr/ agents/
```

## Standard-Kommandos

```bash
# Setup lokal (nach git clone)
docker compose up -d
cd backend && pip install -e ".[dev]" && alembic upgrade head
cd ../frontend && npm install

# Pre-Commit-Hooks aktivieren (einmal pro Klon)
pipx install pre-commit    # oder: brew install pre-commit
pre-commit install         # aktiviert automatische Checks bei jedem commit

# Entwickeln
uvicorn interfaces.rest.app:app --reload        # Backend
npm run dev                                      # Frontend
python -m interfaces.mcp.server                  # MCP-Server lokal

# Testen
pytest                                           # alle Python-Tests
pytest --cov=backend --cov-report=term-missing  # mit Coverage
pytest tests/unit -k quality_classic            # gezielt
npx playwright test                              # E2E

# Lint / Typecheck
ruff check backend/
mypy backend/
npx eslint frontend/ --fix
```

## Agent-Aufgabenmuster

### Wenn ein neues Quant-Modell implementiert werden soll
1. Spec unter `docs/specs/` erstellen (Problem, Formel, Input, Output, Tests).
2. Unit-Tests zuerst: Golden-Dataset in `tests/fixtures/`, erwartete Ränge verifiziert.
3. Modell in `backend/domain/models/` als reine Funktion/Klasse implementieren.
4. `RankingService` erweitern, Integration-Test schreiben.
5. ADR bei Design-Entscheidungen (z.B. "Warum Ledoit-Wolf statt OAS-Shrinkage").

### Wenn ein LLM-Feature implementiert werden soll
1. Pydantic-Schema für Input/Output definieren — **kein Freitext-Output**.
2. Prompt-Caching aktivieren (`cache_control: ephemeral`).
3. Fixture aufnehmen in `tests/fixtures/llm/`, Test gegen Fixture in CI.
4. Golden-Prompt-Smoke-Test gegen echte API nur nightly.
5. Token-Kosten in Commit-Message vermerken.

### Wenn ein MCP-Tool hinzugefügt wird
1. Tool-Schema in `backend/interfaces/mcp/tools.py`.
2. Tool ruft Application-Service — keine DB-Queries direkt im MCP-Handler.
3. `claude_desktop_config.json`-Snippet im `docs/` ergänzen.
4. Manuell in Claude Desktop getestet + Screenshot in PR.

## Persistence-Konventionen

### Session-Lifecycle — zwei Patterns

**1. Request-Session** (Normalfall): `get_async_session()` in `infrastructure/persistence/session.py` öffnet eine Session pro Request, committet am Ende automatisch und rollt bei Exception zurück. Router-Handler und ihre Services nutzen dieses Pattern via `Depends(get_session)`.

**2. Self-managed Side-Channel-Session** (Audit/Logging): Repos, deren Schreiboperationen *unabhängig* von der laufenden Business-Transaktion persistiert werden müssen, erhalten eine `session_factory` im Konstruktor und managen Commit/Rollback selbst. Beispiele: `SQLACostLogRepository`, `SQLAResearchMemoRepository`. Begründung: ein Audit-Insert soll nicht mit einer fehlgeschlagenen Business-Operation zurückgerollt werden.

**Regel für Agents**: Neue Repos bekommen `Depends(get_session)`, es sei denn, sie sind explizit Audit-/Logging-Repos — dann `session_factory` (analog `SQLACostLogRepository`). Den `async for`-Wrapper in `get_session()` nicht anfassen; er durchreicht die Generator-Cleanup-Semantik von `get_async_session()` (PR #88).

## Was Agents NICHT tun sollen

- Keine Geheimnisse (.env, API-Keys) committen.
- Keine breiten Refactorings ohne expliziten Auftrag — PRs mit Scope >200 geänderten Zeilen brauchen ADR.
- Keine Direktzugriffe auf externe APIs aus Domain/Application — immer via Port/Adapter in Infrastructure.
- Keine `git push --force` auf shared Branches.
- Kein `--no-verify` bei Commits (Husky/pre-commit-Hooks sind Pflicht).
- Keine Financial-Advice-Sprache im User-Facing-Text ("Kauf Aktie X") — alles ist Educational/Research.

## Anti-Pattern: Subagent-Pfad-Ambiguität bei Worktrees

**Problem (aufgetreten 2026-05-17, PR #120):** Ein Subagent schrieb Dateien ins Haupt-Repo-Verzeichnis statt in den aktiven Worktree, weil der Worktree-Pfad im Prompt fehlte.

**Regel:** Jeder Subagent-Prompt bei aktiver Worktree-Session muss enthalten:
1. Den absoluten Worktree-Pfad (z.B. `/path/to/repo/.claude/worktrees/<branch>/`)
2. Die Anweisung, nach jedem Commit `git show --stat HEAD` auszuführen und den Output zu melden

**Keine hardcoded Datumsgrenzen in Tests gegen `StubMarketDataProvider`:** Der Provider liefert ~504 Handelstage ab `today`. Tests mit fixen Jahreszahlen (z.B. `2025-01-01`) werden Zeitbomben. Stattdessen relative Daten verwenden:
```python
_today = date.today()
_START = date(_today.year - 1, 1, 1)
_END = date(_today.year - 1, 12, 31)
```

## Reflexions-Pflicht

Jede PR, die substantiell mit einem Coding-Agent entstanden ist, bekommt in `docs/AI-USAGE.md` einen Eintrag:

```markdown
## YYYY-MM-DD · <PR-Titel>
- **Agent**: Claude Code / Cursor / Copilot
- **Scope**: <1 Satz>
- **Was gut lief**: <1 Satz>
- **Was nicht klappte**: <1 Satz>
- **Nachbearbeitung nötig bei**: <1 Satz>
```

Diese Reflexion ist **direkt notenrelevant** für die 40%-Achse.

## Häufige CI-Fallstricke

Drei wiederkehrende Probleme aus PR-History (aufgetreten in PR #126 / Issue #128). Checklisten vor dem PR-Öffnen durchgehen.

### 1. jsdom implementiert `URL.createObjectURL` nicht

Vitest/jsdom wirft einen Fehler bei `vi.spyOn(URL, 'createObjectURL')`, weil die Methode schlicht nicht existiert.

**Checkliste:**
- [ ] Vor `spyOn` prüfen: `typeof URL.createObjectURL !== 'undefined'`?
- [ ] Für nicht implementierte Browser-APIs: direkte Zuweisung `global.URL.createObjectURL = vi.fn()` statt `spyOn`
- [ ] Cleanup nach dem Test: `Reflect.deleteProperty(global.URL, 'createObjectURL')`

### 2. Doppelte Alembic-Revision (Multiple Heads)

Wenn `main` zwischen Branch-Abspaltung und PR-Merge eine eigene Migration mit derselben Revisionsnummer bekommt, meldet Alembic `Multiple head revisions are present` und die Backend-CI schlägt fehl.

**Checkliste vor jedem PR mit Alembic-Migrationen:**
- [ ] `git fetch origin && git log --oneline origin/main -- backend/alembic/versions/` ausführen
- [ ] Prüfen ob die eigene Revision-ID bereits auf `main` vergeben ist
- [ ] Bei Kollision: eigene Migration umbenennen (nächste freie ID) und `down_revision` anpassen
- [ ] `alembic heads` lokal ausführen — genau ein Head darf erscheinen

### 3. `# type: ignore` wird nach echtem Fix zu `unused-ignore`

Wenn ein Ruff/mypy-Fehler durch den eigentlichen Fix verschwindet, meldet mypy die alten Suppressor-Kommentare als `[unused-ignore]` — ein zweiter Fix-Commit wird nötig.

**Checkliste nach type-ignore-relevanten Fixes:**
- [ ] Nach dem Fix `mypy` lokal laufen lassen (oder `pre-commit run mypy`)
- [ ] Alle `# type: ignore` in der geänderten Datei auf Aktualität prüfen
- [ ] Überflüssige Kommentare im selben Commit entfernen, nicht als Nachzügler

## Bewertungs-Kontext

Das Capstone-Modul bewertet:
- **40% AI-assisted Development & Tooling**: sichtbarer Agent-Einsatz, AGENTS.md, Spec-Driven, AI-USAGE.md, AI-Features im Produkt.
- **15% Testing**: Unit + Integration + E2E, ≥80% Coverage.
- **15% CI/CD**: GitHub Actions, Docker, Cloud-Deploy.
- **15% Doku & Präsentation**: README, ADRs, Reflexion.
- **3 × 5%**: Use Case, Architektur, Business-Logik.

Handle danach.
