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

## 2026-04-21 · Initial Scaffold (#0)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: Komplettes Repo-Scaffolding: Clean-Architecture-Ordnerstruktur, AGENTS.md/CLAUDE.md, CONTRIBUTING.md, .gitignore, ADR-0001 (Tech-Stack), Design-Spec (681 Zeilen) via documentation-engineer Sub-Agent, GitHub-Repo-Erstellung, Branch-Protection, Scrum-Setup.
- **Was gut lief**: Parallele Ausführung von Schreibvorgängen und Git-Operationen sparte merklich Zeit. Sub-Agent für die Design-Spec hat sauber strukturiert und alle Scope-Entscheidungen aus dem Brainstorming festgehalten. Conventional-Commits und Co-Authored-By-Footer konsistent gesetzt.
- **Was nicht klappte**: Erster `gh api`-Call für Branch Protection schlug an Type-Coercion fehl; JSON-Body via stdin war der saubere Workaround. Kein inhaltlicher Fehler, nur API-Syntax-Stolperer.
- **Nachbearbeitung nötig bei**: Noch keine.
- **Autor**: Sheyla Sampietro (mit Claude Code)

<!-- Neue Einträge oben an die Liste anfügen. -->
