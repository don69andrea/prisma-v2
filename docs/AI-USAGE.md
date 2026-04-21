# AI-Usage Log

Reflexions-Tagebuch über den Einsatz von Coding-Agents (Claude Code, Cursor, Copilot, Codex) in diesem Projekt. **Direkt notenrelevant für die 40%-Achse** des Capstone-Bewertungsrasters.

## Format

Pro PR mit substantieller Agent-Beteiligung ein Eintrag:

```markdown
## YYYY-MM-DD · <PR-Titel> (#<PR-Nummer>)
- **Agent**: Claude Code / Cursor / Copilot / Codex
- **Scope**: <1 Satz, was der Agent gemacht hat>
- **Was gut lief**: <1-2 Sätze>
- **Was nicht klappte**: <1-2 Sätze>
- **Nachbearbeitung nötig bei**: <Dateien oder Logik>
- **Autor**: <Teammitglied>
```

## Einträge

## 2026-04-21 · Phase-1 Foundation Scaffold (#1–#7)
- **Agents**: 2 Sub-Agents parallel (voltagent-core-dev:backend-developer + voltagent-lang:nextjs-developer), beide Sonnet. Orchestriert von Claude Code Opus 4.7.
- **Scope**: In einer Session 70 Files (2243 Zeilen) geschrieben: komplettes FastAPI-Backend mit Clean Architecture + async SQLAlchemy + Alembic + Tests, Next.js-14-Frontend mit shadcn/ui + React Query, docker-compose, GitHub Actions CI, Render-Blueprint. End-to-End auf Docker verifiziert (alle Container healthy, Endpoints liefern).
- **Was gut lief**:
  - Parallelisierung war sauber — beide Agents arbeiteten auf disjunkten Directories, kein Konflikt.
  - Strukturell sehr sauberer Code: Clean-Architecture-Schichten eingehalten, Type-Hints durchgängig, strukturierte Outputs, gute Test-Abdeckung im Scaffold.
  - Direktes Abbilden der Spec-Sektionen (Abschnitt 4, 5, 9, 10, 11, 12) in konkrete Dateien ging zuverlässig.
- **Was nicht klappte** (4 Bugs in agent-generiertem Code, alle beim ersten Docker-Build entdeckt):
  1. `pyproject.toml` hatte `build-backend = "setuptools.backends.legacy:build"` — dieses Backend existiert nicht in setuptools. Korrekt: `setuptools.build_meta`. Klassische Halluzination.
  2. `Dockerfile.frontend` nutzte `npm install --frozen-lockfile` — das ist ein Yarn-Flag, npm kennt es nicht. Korrekt: `npm install`.
  3. `Dockerfile.frontend` hatte `COPY --from=builder /app/public ./public 2>/dev/null || true` — Shell-Syntax (Redirects, `||`) funktioniert NICHT in Dockerfile-COPY-Instruktionen. Docker interpretierte `2>/dev/null` und `||` als Quell-Pfade, daher der kryptische Fehler `"/||": not found`. Fix: einfaches `COPY` + leeres `frontend/public/.gitkeep`.
  4. `Dockerfile.backend` fehlte `ENV PYTHONPATH=/app` — ohne das findet Python das `backend`-Package nicht (da es via WORKDIR/app referenziert, aber nicht als installiertes Package).
  5. `backend/config.py` hatte `cors_origins: list[str]` — pydantic-settings v2 versucht für `list[str]` JSON-Decoding des Env-Values BEVOR der field_validator läuft; `http://localhost:3000` ist kein valides JSON. Fix: `Annotated[list[str], NoDecode]` damit pydantic-settings das Raw-String an den Validator durchreicht.
- **Nachbearbeitung nötig bei**: `pyproject.toml` (build-backend), `Dockerfile.frontend` (2 Stellen), `Dockerfile.backend` (PYTHONPATH), `backend/config.py` (NoDecode). Insgesamt ca. 15 Minuten Debugging.
- **Lektion**: Agents produzieren syntaktisch plausiblen, aber real nicht funktionalen Code wenn es um seltene Infrastruktur-Detail-APIs geht (Dockerfile-vs-Shell-Unterschied, pydantic-settings v2 quirks, obscure Build-Backend-Namen). TDD-Prinzip gilt auch für Infrastruktur: **erstmal bauen + hochfahren + anfragen, bevor man den nächsten Layer draufsetzt**. Alles grün erst nach Verifikation.
- **Autor**: Sheyla Sampietro (mit Claude Code + Sub-Agents)

## 2026-04-21 · Initial Scaffold (#0)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: Komplettes Repo-Scaffolding: Clean-Architecture-Ordnerstruktur, AGENTS.md/CLAUDE.md, CONTRIBUTING.md, .gitignore, ADR-0001 (Tech-Stack), Design-Spec (681 Zeilen) via documentation-engineer Sub-Agent, GitHub-Repo-Erstellung, Branch-Protection, Scrum-Setup.
- **Was gut lief**: Parallele Ausführung von Schreibvorgängen und Git-Operationen sparte merklich Zeit. Sub-Agent für die Design-Spec hat sauber strukturiert und alle Scope-Entscheidungen aus dem Brainstorming festgehalten. Conventional-Commits und Co-Authored-By-Footer konsistent gesetzt.
- **Was nicht klappte**: Erster `gh api`-Call für Branch Protection schlug an Type-Coercion fehl; JSON-Body via stdin war der saubere Workaround. Kein inhaltlicher Fehler, nur API-Syntax-Stolperer.
- **Nachbearbeitung nötig bei**: Noch keine.
- **Autor**: Sheyla Sampietro (mit Claude Code)

<!-- Neue Einträge oben an die Liste anfügen. -->
