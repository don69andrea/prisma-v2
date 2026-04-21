# Pull Request

## Was & Warum

<!-- 1-3 Sätze: Was ändert dieser PR und warum ist die Änderung nötig. -->

## Spec-Link

<!-- Link zur Spec unter docs/specs/ (bei Features Pflicht, bei Fixes/Chores optional) -->
- Spec: `docs/specs/...`

## Scope (bitte ankreuzen)

- [ ] `type:feature` – neue Funktionalität
- [ ] `type:bug` – Bugfix
- [ ] `type:refactor` – Strukturänderung ohne Verhaltenswechsel
- [ ] `type:docs` – Dokumentation
- [ ] `type:test` – Tests
- [ ] `type:infra` – Infrastruktur / CI / Deploy
- [ ] `type:spec` – neue oder geänderte Spec

## Architektur-Compliance

- [ ] Clean-Architecture-Schichten respektiert (`domain ← application ← interfaces/infrastructure`)
- [ ] Keine Framework-Imports in `domain` / `application`
- [ ] Externe API-Calls nur via Port/Adapter in `infrastructure`
- [ ] ADR hinzugefügt, falls strukturelle Entscheidung getroffen

## Tests

- [ ] Unit-Tests für neue Domain-Logik
- [ ] Integration-Tests für API- oder DB-Änderungen
- [ ] E2E-Test bei UI-Flow-Änderungen
- [ ] Coverage nicht verschlechtert
- [ ] Bei LLM-Code: Pydantic-Schema + Fixture-Mode-Test

## AI-Usage

<!-- Wie wurde dieser PR mit Coding-Agents gebaut? Pflicht-Eintrag in docs/AI-USAGE.md. -->
- Agent: Claude Code / Cursor / Copilot / -
- Was gut lief:
- Was nicht klappte:
- Nachbearbeitung nötig bei:

## Screenshots (bei UI-Änderungen)

<!-- Vor/Nach oder einfach der neue Zustand -->

## Checklist

- [ ] CI-Checks grün
- [ ] Mindestens 1 Review-Approval
- [ ] Conversation-Threads resolved
- [ ] Feature-Branch wird beim Merge gelöscht (automatisch)
- [ ] Eintrag in `docs/AI-USAGE.md` ergänzt
