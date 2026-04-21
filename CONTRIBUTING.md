# Contributing to PRISMA

## Branching & PR-Workflow

`main` ist geschützt. **Kein direkter Push.** Alle Änderungen via Pull Request.

### Branch-Naming

```
<typ>/<kurzbeschrieb-kebab-case>
```

Typen:
- `feat/` — neues Feature
- `fix/` — Bugfix
- `refactor/` — Strukturänderung ohne Verhaltenswechsel
- `docs/` — reine Doku
- `test/` — Test-Ergänzungen
- `chore/` — Infrastruktur, Dependencies, Config
- `spec/` — neue/geänderte Spec

Beispiele: `feat/quality-classic-model`, `fix/ranking-edge-case-empty-universe`, `docs/adr-llm-provider-choice`.

### Commit-Messages (Conventional Commits)

```
<typ>(<scope>): <beschreibung>

[body]

[footer]
```

Beispiele:
```
feat(ranking): add Quality Classic model with 8-factor scoring
fix(narrative): handle empty Top-N edge case
test(quality-ai): add golden dataset for Lasso regression
docs(spec): add design spec for multi-agent research pipeline
```

Bei agent-assistiertem Code: Footer `Co-Authored-By: Claude <noreply@anthropic.com>`.

### PR-Checkliste

Jeder PR muss:

- [ ] verlinkte Spec unter `docs/specs/` haben (falls Feature)
- [ ] alle CI-Checks grün (Lint, Typecheck, Unit, Integration)
- [ ] Coverage nicht verschlechtern (ideal: verbessern)
- [ ] mindestens 1 Review von einem anderen Teammitglied
- [ ] Eintrag in `docs/AI-USAGE.md` (wenn Agent-assistiert)
- [ ] ADR bei architekturrelevanten Entscheidungen

### PR-Template

Das Template unter `.github/pull_request_template.md` wird automatisch eingefügt. Es verlangt:
- Beschreibung (Was & Warum)
- Spec-Link
- Test-Strategie
- Agent-Usage-Summary
- Screenshots bei UI-Änderungen

### Review-Regeln

- Reviewer prüft: Spec-Abgleich, Architektur-Konformität, Testabdeckung, Lesbarkeit
- Author reagiert auf alle Kommentare (fix oder begründete Ablehnung)
- Neue Commits nach Review → Re-Review erforderlich (stale reviews werden automatisch dismissed)

### Merge

- **Squash-Merge** ist default
- PR-Titel wird Squash-Commit-Message — also aussagekräftig formulieren
- PR-Author klickt Merge-Button nach grüner CI + Approval
- Branch wird automatisch gelöscht

### Team-Konventionen

- **Review-Rotation**: Jeder reviewt jeden, kein festes Pairing
- **Response-Zeit**: Reviews innerhalb von 24h (Wochentagen)
- **Kleine PRs**: idealerweise <400 Zeilen, grössere brauchen ADR
- **Draft-PRs** gerne früh öffnen für Diskussion

## Spec-Driven Development

Die wichtigste Team-Regel: **Code nur nach Spec**.

1. Feature-Idee → Diskussion → Konsens
2. Spec schreiben (`docs/specs/YYYY-MM-DD-<feature>.md`)
3. Spec-PR öffnen, Review, Merge
4. **Erst dann** Feature-Branch + Implementierung
5. Implementation-PR verlinkt die Spec

Ausnahme: Trivial-Fixes (Typos, offensichtliche Bugs) dürfen direkt als PR ohne Spec.

## Architecture Decision Records (ADR)

Jede nicht-triviale Architekturentscheidung bekommt einen ADR:

```
docs/adr/NNNN-<kurzer-titel>.md
```

Format: Kontext → Optionen → Entscheidung → Konsequenzen. Status: Proposed / Accepted / Superseded.

## Tests

**Neue Domain-Logik ohne Test = Review-Block.**

- Unit: `tests/unit/` — schnell, deterministisch, keine externen Dependencies
- Integration: `tests/integration/` — DB + API, Docker-compose-up nötig
- E2E: `tests/e2e/` — Playwright, nur bei UI-Flows
- Fixtures: `tests/fixtures/` — Golden-Datasets, LLM-Responses

## Emergencies

Production-Incident, Demo in 30 Minuten, kein Reviewer verfügbar? Repo-Owner darf Branch Protection bypassen. **Bedingung**: Issue dokumentieren, Follow-up-PR innerhalb 48h mit regulärem Review.

## Fragen?

Alles was hier nicht steht: im Team klären, dann als PR gegen dieses File.
