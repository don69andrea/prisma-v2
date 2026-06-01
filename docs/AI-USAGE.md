# AI-Usage Log

Reflexions-Tagebuch über den Einsatz von Coding-Agents (Claude Code, Cursor, Copilot, Codex) in diesem Projekt.

## Überblick

PRISMA wurde durchgehend AI-assistiert entwickelt — primär mit **Claude Code** (Modell-Routing: Opus für Architektur/Reasoning, Sonnet für Implementierung, Haiku für schnelle Strukturierung), ergänzt um Cursor/Codex und externe AI-Peer-Reviews. Dieses Log dokumentiert **52 substantiell agent-assistierte Arbeitsschritte** mit je einer konkreten Lehre.

**Unser Workflow** verdichtete sich über das Projekt zu: Spec-Driven (Spec vor Code) → Plan-as-Contract → Ausführung (Subagent-Driven bei großen Features, inline bei TDD-Tight-Loops) → Two-Stage- bzw. Self-Review → Reflexion im selben PR.

**Wiederkehrende Lehren** (Details + Evidenz unten):
- Spec-/Plan-Qualität bestimmt das Implementations-Tempo nicht-linear (P1, P4, Q1).
- Agent-Outputs gegenprüfen statt vertrauen — Subagent-Reports und CI sind die Wahrheit, nicht Behauptungen (A1, A5, Q4).
- Konstanten/Plattform-Quirks gegen die Live-Quelle verifizieren, nicht aus dem Modell-Gedächtnis (A3, A4).

Die folgenden **Patterns** sind aus den Einträgen destilliert und je auf Evidenz verlinkt.

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

## Patterns (extrahiert aus 52 Einträgen, Stand 2026-06-01)

Diese Sektion kondensiert wiederkehrende Lehren aus den Einträgen unten. Jeder Pattern verlinkt auf die Einträge mit konkreter Evidenz, damit der Pattern-Claim verifizierbar bleibt — nicht aus dem Bauch, sondern aus tatsächlich gemachten Erfahrungen.

**Lesehinweis**: P = Positives (gezielt einsetzen), A = Anti-Patterns (aktiv vermeiden), Q = Quer-Patterns (übergreifende Heuristiken).

### Positives — was wiederholt funktioniert hat

#### P1. Q-by-Q-Brainstorming vor Spec
**Eine Architektur-Frage pro Turn, Optionen + Empfehlung, User entscheidet.** Brainstorming-Skill explizit nutzen; nicht „Wall of Decisions" auf einmal.
- **Evidenz**: PR #24 (5 Architektur-Entscheidungen Budget-Cap einzeln), PR #54 (4 Foundation-Decisions: Scope, UNIQUE-Constraint, Sprach-Spalte, Schema-vs-Entity), PR #26 (4 Iterationen Daten-Feasibility vor Modell-Mix-Entscheidung).
- **Wirkung**: In PR #54 musste **kein einziger** der 7 Build-Steps mid-flight architektonisch neu gedacht werden.
- **How to apply**: Vor `superpowers:writing-plans` 3-6 Architektur-Entscheidungen identifizieren, einzeln durchspielen, dann erst schreiben. Wenn man dem Subagent keinen klaren Auftrag formulieren kann, ist das eigene Denken noch nicht fertig.

#### P2. Reality-Check vor Plan-Schreiben
**Spec gegen reale Codebase grep'en bevor der Plan steht** — referenzierte Repo-Methoden, Tabellen, Pfade müssen tatsächlich existieren.
- **Evidenz**: PR #54 (3 nicht-existente Repo-Methoden in Spec v1.0 → v1.1-Korrektur: `stock_repo.get`, `ranking_repo.get_for_stock`, `ranking_repo.get_universe_context`). Issue #60 (Master-Spec referenzierte `ClaudeLLMClient`/`llm_usage_log`/`/admin/llm-usage`, alle drei heissen im Code anders). PR #34 (Subagent claimte stale Facts).
- **How to apply**: Vor jedem Plan-Schreiben jeden Class-/Method-/Tabellen-Namen via `grep -r` verifizieren. Nicht-existente Referenzen ersetzen oder als TBD markieren.

#### P3. Two-Stage Review (Spec-Compliance + Code-Quality)
**Spec-Reviewer prüft *was* gebaut wurde, Code-Quality-Reviewer prüft *wie*.** Fängt unterschiedliche Bug-Klassen.
- **Evidenz**: PR #54 (Spec-Reviewer fand `Constraint-Naming-Bug` via psql gegen Live-DB, Code-Reviewer fand model_config-Style-Drifts). 7 Build-Steps × 2 Reviewer = 14 Review-Runs → 1 Production-Bug abgefangen, der einer einzelnen Mega-Review entgangen wäre.
- **How to apply**: Ab ≥30 Zeilen Code-Änderung. Bei trivialen 1-Zeilen-Fixes reicht Spec-Re-Review.

#### P4. Plan-as-Contract zwischen Subagents
**1000-1500-Zeilen-Plan mit verbatim Test-Code, Bash-Commands und Commit-Messages pro Step erlaubt sequentielle Subagents ohne Controller-Roundtrips.**
- **Evidenz**: PR #54 (1405-Zeilen-Plan → 7 Subagents in ~30 min Wallclock, jeder Task ~3 min Implementation + ~3 min Review-Loop). PR #70 (12 Build-Steps mit gleicher Disziplin).
- **ROI**: ~60 min Plan-Schreiben → ~3× Implementations-Speed + ~10 Bugs durch Two-Stage-Review früh gefangen.
- **How to apply**: Plan ist nicht „Vorschlag", sondern Vertrag. Jeder Build-Step muss ohne Rückfragen ausführbar sein.

#### P5. Per-Task + Final-Review (kombiniert, nicht entweder-oder)
**Per-Task-Reviews fangen Detail-Bugs, Final-Review fängt System-Bugs.** Bei 8+ Build-Steps nicht skip-bar.
- **Evidenz**: PR #70 (12 Build-Steps mit Per-Task-Reviews — alles grün — plus Final-Review der **3 weitere Critical-Bugs** fand: `r["stock_id"]` KeyError, `asyncio.create_task` GC-Risk, `BudgetCapExceeded` mid-batch uncaught).
- **How to apply**: Nach allen Build-Steps + vor PR-Erstellung einen separaten Final-Review-Pass machen, der das ganze Bild sieht — nicht nur die einzelnen Diffs.

#### P6. Strict-Scope-Reviews (B addressen, W als Folge-Issues)
**B-Findings im PR fixen, W-Findings als Folge-Issues.** Schützt vor Scope-Creep im Review-Loop.
- **Evidenz**: PR #64 (3 Blocker fixed im Strict-Scope-Bundle, W1/W3/W4/W6 → Issues #66-#69). PR #62-Review (W1/W2/W3 als Folge-PR markiert, Approve trotzdem gegeben).
- **Wirkung**: PR-Diff bleibt fokussiert, Review-Iteration kürzer, Reviewer-Vertrauen steigt.
- **How to apply**: Nach Review-Eingang sofort Findings als B / W / N taggen. Nur B im selben PR fixen, W in `gh issue create`.

#### P7. Subagent-Deviations transparent fordern
**Trust-but-Verify**: Subagent muss Deviations vom Prompt mit Begründung melden. Stille Deviations sind gefährlicher als Failures.
- **Evidenz**: PR #25 Wave 8 (Subagent meldete 2 defensive Deviations selbst: `Header(default=None)` für 401-statt-422, Python-side-Sortierung für Test-Robustheit). PR #54 Build-Step 7 (4 Plan-Deviations transparent dokumentiert). PR #70 (7 Drift-Einträge in Spec §11.1).
- **How to apply**: Jeder Subagent-Prompt endet mit „Any deviations from this prompt? List with reasoning."

#### P8. Routing — Main-Context vs Subagent
**Main-Context für TDD-Tight-Loops** (iterative Entwicklung mit Run-Feedback). **Subagent für Multi-File-Bauarbeit nach klarer Vorgabe** (≥9 Files, kein Mid-Step-Run-Feedback nötig).
- **Evidenz**: PR #25 (Wave 6-7 Main-Context für TDD-Tight-Loop, Wave 8 Subagent für 9-Files-Admin-Endpoint). PR #54 (7 sequentielle Subagents nach 1400-Zeilen-Plan). PR #70 (Voltagent-Implementer + Code-Reviewer-Subagents pro Build-Step).
- **Heuristik**: Wenn der nächste Schritt von einem Run-Output abhängt (Test-, Mypy-, Browser-Output) → Main-Context. Wenn gut-definierte File-Änderungen die zusammen committed werden → Subagent.

#### P9. Model-Routing (Opus vs Sonnet vs Haiku)
**Reasoning-dichte Arbeit → Opus. Template-gehorsame Schreibarbeit → Sonnet/Haiku.** Nicht primär Kosten — Kontext-Hygiene.
- **Evidenz**: ADR-0005 (Opus für Trade-off-Analyse, Sonnet-Subagent für ADR-Schreibarbeit nach Vorbild). PR #24 (Opus-Brainstorming, Sonnet-Subagent für 643-Zeilen-Spec-Schreibarbeit).
- **Wirkung**: Opus-Hauptkontext bleibt frei für Entscheidungen, die Urteil brauchen. Spiegelt PRISMAs eigenes Multi-Agent-Pattern (AnalystAgent vs SynthesizerAgent).

#### P10. Null-Object statt Mock für persistente Infrastruktur in Tests
**Test-Infrastruktur (Repositories, Clients) via Null-Object-Pattern implementieren statt via `MagicMock`.** Null-Objekte sind explizit, typsicher und dokumentieren die erlaubten Operationen.
- **Evidenz**: PR #135 (`_NullCostLogRepository` für `FixtureLLMClient` — implementiert das `CostLogRepository`-Interface vollständig, alle Operationen als No-Op. Kein `AsyncMock(return_value=...)` pro Methode nötig). `InMemoryUniverseRepository` in Integration-Tests.
- **Wirkung**: Null-Objekte fangen Breaking Changes an der Schnittstelle (mypy schlägt an wenn Interface sich ändert), Mocks tun das nicht. Testcode ist weniger fragil.
- **How to apply**: Wenn ein Mock mehr als 2 `return_value`-Konfigurationen braucht → Null-Object schreiben. Für einfache Single-Call-Verifikation bleibt `AsyncMock` sinnvoll.

---

### Anti-Patterns — was wiederholt schiefging

#### A1. Plan-Code-Drift: Plan-Templates sind Vorschlag, nicht Ground-Truth
**Plans extrapolieren oft falsch aus der Spec.** Class-Names, Method-Signatures, Imports müssen gegen die Codebase verifiziert werden.
- **Evidenz**: PR #54 (5 echte Plan-Bugs: `model_config = ConfigDict(...)` vs `{...}`-Konvention, `dict` vs `dict[str, Any]`, `Base`-Import-Pfad falsch, Constraint-Naming-Doubling, `async_session_factory` existiert nicht). PR #64 (3 Blocker durch Plan-Code-Drift: `asyncio.gather` mit shared Session, EN-Template-Token-Verbrauch, ID-Drift). PR #70 (7 Drift-Einträge in Spec §11.1).
- **Mitigation**: P2 (Reality-Check vor Plan).

#### A2. AI-generierte Config-Files sind kontextblind für Subdirectories
**`.gitignore`/`.dockerignore`-Regeln werden generisch generiert.** Bei Multi-Language-Repos können sie unbeabsichtigt matchen.
- **Evidenz**: CI-Stabilisierung 2026-04-21 (`lib/`-Regel matched silent `frontend/lib/utils.ts` etc. → 3 Files fehlten in Git, lokal grün, CI rot, ~30 min Fehldiagnose).
- **Mitigation**: Bei Multi-Language-Repos `.gitignore`-Regeln explizit scopen (`/lib/` für Root-only, oder mit explizitem Pfadpräfix).

#### A3. PaaS-Plattform-Quirks aus Trainingswissen falsch
**Render/Vercel/Cloudflare-Specifics** (Tier-Limits, argv-parsing, primitive-typed bindings) sind nicht zuverlässig in Training-Daten.
- **Evidenz**: Render-Deployment 2026-04-21 (3 Stolpersteine: `preDeployCommand` Paid-only; `dockerCommand: "sh -c '...'"` exit 127 weil YAML-String als single-argv; `fromService.host` liefert URL ohne `https://`-Scheme).
- **Mitigation**: Bei jedem Deploy-Config-Field aktiv prüfen „was passiert wenn die Plattform das wörtlich interpretiert?" und „welche Tier-Stufe brauche ich?". Inline-Shell-Strings in YAML immer als Array oder Script-Datei.

#### A4. Constants aus Erinnerung (Pricing, Limits, API-Schemas)
**Pricing-Werte, Token-Limits, API-Quotas aus Trainings-Daten** stimmen oft nicht mehr — müssen gegen Live-Quelle verifiziert werden.
- **Evidenz**: PR #25 (Sonnet 4.6/Haiku 4.5/Voyage-3-large Pricing als Best-Estimate, Verifikation pflichtig vor Production-Deploy). PR #64 (Schema `max_length=600` aus Spec geraten, Sonnet schreibt 700-1000 Zeichen → Bonus-Fix nach W5-Smoke).
- **Mitigation**: Jeden numerischen Constant in Code/Spec mit „verifiziert gegen [Quelle, Datum]" annotieren — oder als TBD markieren. Schema-Constraints für LLM-Output empirisch kalibrieren (siehe A7).

#### A5. Subagent-Reports sind Snapshots, keine Live-Wahrheit
**Subagent-Findings können bei Eintreffen schon stale sein** — gegenchecken vor Weitergabe an User oder Folge-Subagents.
- **Evidenz**: PR #34 (Roadmap-Subagent claimte „pytest-asyncio fehlt" — war 30 min vorher via PR #34 selbst gefixt — und „PR #25/#26 wartend" — beide gemerged).
- **Mitigation**: Vor dem Weitergeben jedes Subagent-Output kritische Claims schnell gegen Live-State verifizieren (`gh pr view`, `git log`, Tool-Output).

#### A6. Branch-Strategie nach gut Glück
**„Spec-First UND Branch-First"** muss als gemeinsamer Reflex sitzen.
- **Evidenz**: PR #26 (erster Spec-Commit auf `main` — Verstoss gegen AGENTS.md §4 PR-only innerhalb 5 min nach Spec-Commit, dann `git reset --soft HEAD~1` + Verlagerung auf Feature-Branch).
- **Mitigation**: Vor jedem ersten Commit aktiv `git status && git branch --show-current` prüfen.

#### A7. Schema-Constraints aus dem Spec geraten
**LLM-Output-Constraints (`max_length`, `min_length`, Pattern)** müssen empirisch gegen das Production-Modell kalibriert werden, nicht aus dem Spec geraten.
- **Evidenz**: PR #64 (Pydantic `string_too_long` auf `ranking_interpretation` mit `max_length=600`, Sonnet schreibt typisch 700-1000 Zeichen für 5-Modell-Interpretation. In Production wäre alles in Error-Memo-Pfad gewandert).
- **Mitigation**: Vor dem ersten Production-Smoke einmal mit echten Inputs gegen das Modell laufen lassen, dann Schema-Constraints kalibrieren. Real-API-Smoke ist Acceptance, nicht Polish (Q4).

#### A8. Required kwargs ohne Default in internen APIs unbemerkt vergessen
**Interne Hilfsfunktionen mit required kwargs (kein Default)** werden beim ersten Aufrufer korrekt gesetzt, aber bei neuen Aufrufern oft vergessen — besonders wenn die Funktion viele optionale Kwargs hat.
- **Evidenz**: PR #136 / Nacharbeit 2026-05-19 (`LLMClient.embed(feature=)` ist required, aber `RetrievalService.retrieve()` rief `embed()` ohne `feature=` auf — stiller TypeError zur Laufzeit, kein mypy-Fehler weil der Service selbst nicht vollständig getypt war).
- **Mitigation**: (1) Neuen Aufrufer immer gegen die vollständige Methodensignatur der aufgerufenen Funktion gegenchecken. (2) Bei `mypy strict` wäre das sofort gefangen worden — Strict-Mypy zahlt sich aus. (3) Required kwargs in internen APIs als Code-Review-Checkliste aufnehmen.

#### A9. session.merge() mit transientem Objekt hat dasselbe Identity-Map-Problem wie flush()+get()
**`AsyncSession.merge(new_ORM_instance)` emittiert ein SELECT gegen die DB — pending (noch nicht committete) Rows werden nicht gesehen.** Ein zweiter `merge()` mit derselben PK erstellt ein zweites Pending-Objekt → `UniqueViolationError` beim Commit.
- **Evidenz**: PR #131 Follow-up 2026-05-19 (zwei `test_save_twice_updates_instead_of_insert`-Tests, `test_ranking_run_repository` + `test_universe_repository`, knallten mit `asyncpg.UniqueViolationError` — beide Pending-Inserts hatten dieselbe UUID). Das Original-PR-Entry („nichts klappte") war voreilig — CI lief erst nach dem Merge.
- **Mitigation**: PostgreSQL-nativer Upsert via `pg_insert(...).on_conflict_do_update(index_elements=["id"], set_={...})`. Atomic, session-state-unabhängig, kein SELECT nötig. Kostet eine explizite `set_`-Dict-Pflege (welche Felder bei Update geschrieben werden), schützt aber vor allen Identity-Map-Quirks.

#### A10. Jinja2 {% if %}/{% endif %} Leerzeilen bei trim_blocks=False
**Mit `trim_blocks=False` (Default) bleibt der Zeilenumbruch nach `{% endif %}` im Output.** Wird der Block nie betreten (falsy condition), kommt trotzdem ein `\n` aus dem `{% endif %}`-Tag. Ein Blank-Line vor dem `{% if %}`-Tag addiert sich — Ergebnis: 2 statt 1 Leerzeilen.
- **Evidenz**: PR #139 2026-05-19 (`test_prompt_loader.py` snapshot-Tests: `AssertionError` weil Template mit `{% if rag_context %}` Block + Leerzeile davor 2 Leerzeilen produzierte, Snapshot erwartete 1).
- **Mitigation**: (1) Blank-Line vor `{% if %}` entfernen — die `\n` aus dem `{% endif %}`-Tag gibt die einzige Trennzeile wenn Block falsy. (2) Oder `trim_blocks=True` in der Jinja2-Environment setzen. (3) Snapshot-Tests immer mit dem leeren Zustand (`rag_context=""`) verifizieren, nicht nur mit Inhalt.

---

### Quer-Patterns — übergreifende Heuristiken

#### Q1. Spec-Qualität bestimmt Implementations-Tempo nicht-linear
~60 min Plan-Schreiben → ~3× Implementations-Speed (PR #54). Wenn die Spec den nächsten Wave nicht in 3 Sätzen klar macht, ist die Spec **nicht fertig** — schreib sie zuerst zu Ende, sonst zahlst du den Preis 5× während der Implementation.

#### Q2. Memory-Hygiene zählt
Stale Memories kosten 5 min pro Session × n Sessions; Memory-Updates kosten einmalig 30 Sekunden. Memory-Updates sind eine lohnende Praxis (PR #34: alte Memory „Nicolas-Handle pending" hätte zu Best-Guess-Fehlern geführt).

#### Q3. AI-USAGE-Reflexion in Echtzeit, nicht retroaktiv
AI-USAGE.md-Einträge **während** der Arbeit pflegen, nicht „nach dem PR". Lerner-Schleife wirkt sofort (CI-Stabilisierung-Eintrag entstand parallel zum Debug, nicht danach — und half bei der nächsten Iteration).

#### Q4. Real-API-Smoke ist Acceptance, nicht Polish
LLM-Code mit StubClient grün ≠ production-ready. Mindestens 1× gegen echte API laufen lassen vor Merge.
- **Evidenz**: PR #64 W5 (Real-API-Smoke fand Schema-Calibration-Bug, der in Production silent in Error-Memo-Pfad gewandert wäre — kein Test hätte ihn lokal gefangen). Cache-Hit-Rate verifiziert: Call 1 cache_create=3259 / cache_read=0 → Call 2 cache_create=676 / cache_read=3259, 42% Kostenersparnis ab Call 2.

---

## Einträge

## 2026-06-01 · UX-Polish — Nav-Highlight, Deutsche Labels, Spinner, URL-Preselect (PR #161)
- **Agent**: Claude Code (Sonnet 4.6) — superpowers:brainstorming + writing-plans + subagent-driven-development
- **Scope**: 5 kleine UX-Verbesserungen in 4 Subagent-Tasks: (1) `NavLinks`-Client-Component mit `usePathname()` + `aria-current="page"` für aktiven Tab; (2) Deutsche Status-Labels in `RunHistoryList` ("Abgeschlossen", "Ausstehend", "Läuft…", "Fehlgeschlagen") + "Date"→"Datum"; (3) `Loader2`-Spinner bei laufendem Run + "Neuer Run"→"Zurück zu Rankings" in Detail-Page; (4) `RankingsForm` liest `?universeId=` aus URL + `<Suspense>`-Grenze in `rankings/page.tsx`. 6 neue Tests.
- **Was gut lief**: Alle 5 Punkte berührten komplett verschiedene Dateien → keine Task-Konflikte, Subagent-Driven-Execution lief ohne Blocker durch. `useSearchParams()`-Suspense-Anforderung in Next.js 14 war im Plan bereits antizipiert — Subagent musste nichts nachrecherchieren. PR #161 war sofort grün (alle CI-Gates inkl. E2E).
- **Was nicht klappte**: Nichts Kritisches. Der `layout.tsx`-Server-Component-Split (NavLinks als Client-Component extrahieren) hätte auch durch eine falsche `'use client'`-Platzierung auf dem falschen Level scheitern können — im Plan explizit als Anforderung formuliert, kein Problem.
- **Nachbearbeitung nötig bei**: Keine.
- **Lektion**: **UX-Kleinkram akkumuliert sich zu echter Qualität wenn man ihn gezielt sammelt und en-bloc angeht.** 5 Punkte einzeln als separate Mini-Sessions wäre Overhead — als brainstormte Liste in einem Plan zusammengefasst und per Subagent-Driven-Development mit Two-Stage-Review durchgezogen war es sauber und schnell. **`useSearchParams()` in Next.js 14 immer mit `<Suspense>` planen** — bei Server-Component-Wrapping ist das nicht optional und wird von tsc nicht gefangen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-06-01 · Universe → Ranking CTA mit Post-Creation-Dialog (PR #160)
- **Agent**: Claude Code (Sonnet 4.6) — superpowers:brainstorming + writing-plans + subagent-driven-development
- **Scope**: 5 Subagent-Tasks. (1) Radix Dialog UI-Primitive (`components/ui/dialog.tsx`, `@radix-ui/react-dialog` war bereits installiert). (2) `StartRankingDialog`-Component: erscheint nach Universe-Erstellung, fragt "Ranking starten?", "Ja" → `createRun()` + Navigation zu `/rankings/<id>`, "Nein" → onClose + Redirect zu `/universes`. (3+4) Beide Erstellungs-Pages (`new/page.tsx`, `wizard/page.tsx`) nutzen Dialog statt direktem Redirect. (5) `UniverseList` wird Client-Component + "Ranking starten"-Button pro Zeile öffnet denselben Dialog. 7 neue Tests (5 für Dialog, 2 für List).
- **Was gut lief**: Radix Dialog bereits im Projekt vorhanden (`@radix-ui/react-dialog` in package.json) → Task 1 war reines Scaffolding ohne Dependency-Risiko. `StartRankingDialog` als wiederverwendbarer Component (genutzt in 3 Stellen) statt 3× inline-Implementation. Two-Stage-Review fing keine kritischen Issues — Plan-Code-Qualität war hoch genug für direkten PASS.
- **Was nicht klappte**: **2 E2E-Tests schlugen fehl** (`01-universe.spec.ts` + `rankings.spec.ts` Test 2): beide erwarteten nach dem Formular-Submit einen direkten Redirect zu `/universes`, aber der neue Dialog hält die Page auf `/universes/new`. Fix: je eine Zeile `await page.getByRole('button', { name: /Nein/i }).click()` vor der `toHaveURL`-Assertion. Die Unit-/Integrationstests (Vitest) hatten diesen Fall nicht abgedeckt, weil E2E der einzige Ort ist, wo der volle Browser-Flow getestet wird.
- **Nachbearbeitung nötig bei**: E2E-Fix in eigenem Commit (`ca76a2e`) im gleichen PR nachgeliefert, CI läuft durch.
- **Lektion**: **Bei Änderungen am Post-Submit-Flow immer die E2E-Tests mitlesen.** Unit-Tests mocken die Navigation weg (`mockPush`), E2E-Tests testen den echten Browser-Zustand. Ein neues UI-Element (Dialog) das die URL-Navigation verzögert ist für Unit-Tests unsichtbar, für E2E sofort ein Blocker. **E2E-Tests als Dokumentation des erwarteten User-Flows lesen** — sie hätten den Dialog-Schritt eigentlich schon im Plan-Review auffallen lassen sollen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-06-01 · Abgabe-Absicherung — Demo-DB-Diagnose, Anthropic-Key-Fix, Katalog-Parität-Migration (chore/abgabe-final)
- **Agent**: Claude Code (Opus 4.8, inline ohne Subagent-Split)
- **Scope**: Post-Demo-Submission-Polish. (1) Live-Render-Deployment verifiziert → Demo-DB war leer (0 Universen/Runs) → via Live-API neu geseedet (Universum + 2 Runs mit divergierenden Gewichten für Compare-Story). (2) Memo-Generierung auf Prod gab blanken 500 → per **lokaler Reproduktion + Ausschlussverfahren** als fehlender `ANTHROPIC_API_KEY` auf Render diagnostiziert (nicht Code/Daten). (3) Nach Key-Fix: 10 Memos generiert, kompletter Demo-Pfad (Rankings → Memo-Drilldown → Compare) per Playwright auf der Live-URL E2E-verifiziert. (4) Migration `0012` für 13-Stock-Katalog-Parität lokal↔deployed. (5) README-Setup-Bugs + Doku-Konsistenz gefixt.
- **Was gut lief**: **Diagnose per lokaler Reproduktion schlug Raten.** Statt den 500 auf Prod zu interpretieren, denselben Memo-Call lokal mit echtem Key gegen lokale DB gefahren → lief grün (200). Damit war Code+Daten als Ursache ausgeschlossen und nur die Prod-Env-Config blieb übrig. Code-Lesen bestätigte: RAG/Voyage-Fehler ist env-unabhängig abgefangen (`narrative_service.py:549`), nur `anthropic.AuthenticationError` ist uncaught → blanker 500. Lückenlose Beweiskette ohne Render-Log-Zugriff. **Migration statt Seed-Skript für Katalog-Parität**: idempotente Daten-Migration (Pattern aus 0009b) bringt lokal+deployed auf denselben Stand UND regeneriert nach jedem Free-Tier-DB-Reset — löst die wiederkehrende „Demo-DB plötzlich leer"-Klasse dauerhaft.
- **Was nicht klappte**: Erste lokale Verifikation gab 11 statt 13 Stocks — meine Test-DB war durch einen früheren `seed_demo_universe.py`-Lauf (NVDA/JPM statt AMZN/TSLA) verunreinigt, `ON CONFLICT DO NOTHING` übersprang die Überlappung. Kein Migrations-Bug — mit frischer DB von Null (= exakter Prod-Deploy-Pfad) korrekt 13. Lehre: Daten-Migrationen immer gegen eine **frisch von Null migrierte** DB verifizieren, nicht gegen eine über die Session gewachsene lokale DB.
- **Nachbearbeitung nötig bei**: Optionales Code-Hardening offen — `anthropic.AuthenticationError` im Memo-Pfad abfangen → strukturierter 502 statt blanker 500 (nur relevant falls Key erneut ausfällt). Universen/Runs/Memos auf Prod bleiben via-API-geseedet und damit nicht reset-resistent (nur der Stock-Katalog ist via Migration permanent).
- **Lektion**: **Bei Env-spezifischen Prod-Fehlern ist lokale Reproduktion mit Ausschlussverfahren schneller und sicherer als Log-Archäologie.** Ein blanker 500 ohne Log-Zugriff ist trotzdem präzise diagnostizierbar, wenn man systematisch Code+Daten lokal ausschließt, bis nur die Env-Config übrig bleibt. **Ephemere PaaS-DBs gehören in Migrationen, nicht in manuelle Seeds** — was reproduzierbar in der DB sein muss, gehört in eine idempotente Migration (läuft bei jedem Deploy), nicht in ein Skript, das jemand manuell ausführen muss und nach dem nächsten Reset vergisst.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-06-01 · Futuristic Loading Screen (PR #158) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: 6.5s animierter Splash-Screen der beim ersten App-Load erscheint. Ein Laserstrahl trifft einen Diamanten (= Unternehmen), bricht sich in 5 Spektralfarben und visualisiert PRISMA's Core-Concept "See through every company." `sessionStorage`-Guard verhindert Wiederholung, CSS-Keyframe-Animation, kein externes Framework.
- **Was gut lief**: Rein visueller, isolierter Feature-Scope — keine Backend-Abhängigkeit, kein State-Impakt auf andere Teile der App. CSS-only Animation blieb im Bundle-Size-Budget.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar (keine Session-Notes vorhanden).
- **Nachbearbeitung nötig bei**: Keine — PR #158 grün gemerged.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-26 · POST /api/v1/universes/{id}/sync — Ticker-Stocks-Sync (Issue #114, PR #133)
- **Agent**: Claude Code (Sonnet 4.6) — superpowers:writing-plans + subagent-driven-development
- **Scope**: `UniverseService.sync_universe()` + REST-Endpoint + 8 Integration-Tests. Service prüft Verfügbarkeit via FundamentalsProvider + MarketDataProvider, liefert `UniverseSyncResult(synced_count, failed_tickers)`.
- **Was gut lief**: Clean-Architecture-Schichten sauber eingehalten (kein REST-Leak ins Application-Layer). DI-Pattern konsequent: Providers via `__init__`, Exception-Logging vorhanden.
- **Was nicht klappte**: Test `test_sync_universe_synced_count_equals_ticker_count` verwendete SMI-Tickers (NESN/NOVN/ROG), die im `StubFundamentalsProvider` nicht existieren — `synced_count=0` war garantiert, aber der Test-Kommentar behauptete das Gegenteil. Reviewer-Feedback (SheylaSam + itsFabia) deckte auf, dass kein Test `synced_count > 0` verifiziierte. Fix: Test auf `_SP500_ID` (AAPL/MSFT, im Stub vorhanden) umgestellt + separaten Test für SMI-Fehlerpfad ergänzt.
- **Nachbearbeitung nötig bei**: `test_universes_endpoint.py` (Sync-Tests), `universe_service.py` (Docstring).
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-29 · Run-History — Liste auf /rankings + Compare-Page (Frontend-Backlog Priorität 6, PR #153)
- **Agent**: Claude Code (Opus 4.7 als Orchestrator + Sonnet 4.6 für Implementer-Subagents)
- **Scope**: Spec → Plan → 7-Task-Subagent-Driven-Execution mit Orchestrator-Self-Review-Variante. Backend: `RunResponse.universe_name` ergänzt (Router joint `UniverseRepository` mit `"(deleted)"`-Fallback). Frontend: `<RunHistoryList/>` mit Checkbox-FIFO (max 2 ausgewählt), `/rankings/compare?a=&b=` Page mit `<CompareBanner/>` (Same/Cross-Universe-Auto-Detection) + `<CompareTable/>` mit Δ-Visuals (grün ↑ / rot ↓ / grau ·). 23 neue Vitest + 6 neue Backend-Tests + 1 Playwright-E2E.
- **Was gut lief**: Die Orchestrator-Self-Review-Variante (Claude dispatcht 1 Implementer, ich prüfe die Ergebnisse selbst statt eines 3-Reviewer-Loops) sparte massiv Token/Zeit ohne Qualitätsverlust — Pre-Discovered-Context im Plan und ein sauberer TDD-Plan reichten als Quality-Gate. Spec-Hotfix während Task-2-Dispatch (Implementer flagged: `stock_id`-Feld existiert nicht auf origin/main, weil Memo-Drilldown-PR #148 noch nicht gemerged) wurde sofort als separater Plan-Hotfix-Commit gefixt — `feedback_spec_hotfix_during_planning`-Pattern bewährt sich.
- **Was nicht klappte**: Subagent in Task 5 hat einen `sameUniverse`-Check zu großzügig gefasst (`id===id || name===name`) damit der Test grün wird — Production-Risk, weil zwei verschiedene Universes denselben Namen tragen könnten. Im Self-Review entdeckt + per Hotfix-Commit korrigiert (strict universe_id-Vergleich + Test-Fixture nutzt shared id für same-universe-Case). Lehre: wenn Tests einen Production-Constraint nicht erlauben, ist meistens der Test falsch konzipiert, nicht die Production-Logic.
- **Nachbearbeitung nötig bei**: keine — alle CI-Gates grün (ruff + mypy + pytest backend; lint + tsc + vitest + e2e frontend). PR #153 offen für Review.
- **Lektion**: **Orchestrator-Self-Review-Variante ist optimal für mechanische Tasks mit engem Plan.** Ein voller 3-Reviewer-Loop ist Overhead, wenn (a) der Plan verbatim Code enthält und (b) ich zwischen den Tasks Zeit habe, den Output selbst zu lesen und die Commits (SHA) zu verifizieren. **Sanity-Check Subagent-Deviations im Self-Review:** wenn ein Subagent von der Spec abweicht "um den Test grün zu bekommen", fast immer ist der Test der Bug, nicht die Production-Logic — separater Hotfix-Commit dokumentiert die Korrektur sauber.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-31 · max_drawdown-Vorzeichen korrigieren (PR #145) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: Formel-Bug in `_compute_metrics`: `max_drawdown` wurde mit falschem Vorzeichen berechnet (`(rolling_max - portfolio) / rolling_max + .max()` → positiv). Spec §6-konforme Formel `(portfolio - cummax) / cummax + .min()` → korrekt negativ. 2 Tests angepasst.
- **Was gut lief**: Root-Cause war durch Spec-Vergleich sofort klar — kein langer Debug-Prozess. Einzeiliger Formel-Fix mit direkter Test-Verifikation.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar. Der Bug war seit der ursprünglichen Backtest-Implementation (#120) vorhanden ohne aufzufallen — kein Vorzeichen-Test existierte.
- **Nachbearbeitung nötig bei**: Keine.
- **Lektion**: **Quant-Formeln brauchen Vorzeichen-Tests.** `max_drawdown` semantisch negativ — ein Test `assert max_drawdown < 0` hätte den Bug beim ersten Merge gefangen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-28 · LLM-Universe-Wizard — Claude Haiku für Universe-Vorschläge (PR #152)
- **Agent**: Claude Code (Opus 4.7 als Orchestrator + Sonnet 4.6 für Implementer-Subagents)
- **Scope**: 4-Task-Plan. Backend: `UniverseSuggestionService` (wrapt `LLMClient.messages_create()` mit Tool-use + Pydantic-Output-Schema, analog Narrative-Engine), neuer Endpoint `POST /api/v1/universes/suggest` (422 bei Empty, 502 bei Invalid LLM Output), zwei Jinja2-Prompts. Frontend: `/universes/wizard` Single-Turn-Page mit Freitext-Eingabe → LLM-Vorschlag → pre-filled Form zum Editieren → Erstellen via existing endpoint. Killer-Feature-Story für Demo: "PRISMA hilft auch das Universum zu definieren."
- **Was gut lief**: Tool-use-Pattern + Pydantic-Schema-Validation (analog Narrative-Engine) gab strukturierten Output ohne Freitext-Parsing-Risiko. Stock-Katalog-Whitelist im System-Prompt verhinderte LLM-Halluzination von nicht-existenten Tickers — wenn LLM erfindet, Schema-Validation catched es als 502.
- **Was nicht klappte**: Initial-Spec hatte Multi-Turn-Dialog ("erst Region, dann Sektor, dann Anzahl") — beim Discuss-Phase-Schritt verworfen zugunsten Single-Turn-Freitext (einfacher UX, weniger State, Demo-tauglicher). Lieber später erweitern wenn Multi-Turn wirklich gebraucht wird.
- **Nachbearbeitung nötig bei**: UX-Lücke: Wizard war nur via direkter URL erreichbar — nach Demo-Polish-Run (2026-05-29) "Mit KI generieren"-Button auf /universes-Page ergänzt.
- **Lektion**: **Discuss-Phase fängt YAGNI-Features.** Multi-Turn-Wizard sah in Spec spannend aus, aber im Discuss-Schritt zeigte sich: Single-Turn deckt 90% der Demo-Use-Cases, Multi-Turn würde Demo-Story komplizieren. **LLM-Output-Validation via Pydantic + Whitelist** ist robusterer als Prompt-Engineering allein — Whitelist garantiert keine Halluzinationen, Schema garantiert kein Format-Drift.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · Tech-Heavy-Demo-Katalog erweitert + Tech-Big-12-Universe (PR #151)
- **Agent**: Claude Code (Sonnet 4.6, inline ohne Subagent-Split)
- **Scope**: 6 neue Tech-Ticker (META, NFLX, AMD, INTC, ORCL, CRM) mit plausiblen Demo-Fundamentals in `StubFundamentalsProvider`. AMZN+TSLA waren via Migration 0009b in DB, aber Provider-Fundamentals fehlten → ergänzt. Idempotentes `scripts/seed_tech_catalog.py` legt die 6 neuen Stocks + Tech-Big-12-Universe (12 Tickers) an. Demo-Pool wächst von 5 auf 12 Tech-Stocks pro Run.
- **Was gut lief**: Idempotenz im Seed-Script (Upsert-Pattern via `merge()`-Calls) erlaubt mehrfaches Ausführen ohne UniqueConstraint-Violations — wichtig wenn DB lokal mal teilweise restored wird. Plausible Demo-Fundamentals (P/E, ROE, FCF-Yield etc.) statt Random-Zahlen damit die Rankings realistisch aussehen.
- **Was nicht klappte**: Keine größeren Issues — kleiner mechanischer Task. Drittes Universum "Semiconductor Leaders" wurde via separates Manual-Seeding nachträglich angelegt, statt im Script.
- **Nachbearbeitung nötig bei**: keine — Seed-Script ist optional vor Demo-Probe ausführbar.
- **Lektion**: **Demo-Daten sind eigener Engineering-Task, kein "schnell mal einfügen".** Plausible Fundamentals + Idempotenz machen Demos reproduzierbar. Stub-Provider muss alle DB-Stocks abdecken, sonst kommt es zu silent Ranking-Lücken.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · Dashboard-Stats — 4 Karten über Runs-Tabelle (Frontend-Backlog Priorität 5, PR #150)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `/dashboard` um 4 Stats-Karten erweitert: Letzter Run (Datum + Status, Link zur Detail), # Universen (Link zu /universes), # Stocks, Top-Pick (Ticker des Rang-1 aus jüngstem completed Run, Sweet-Spot-Sparkles wenn anwendbar, Link zur Factsheet). Frontend-only — Aggregation aus existing APIs (`listRuns`, `listUniverses`, `listStocks`, `getRankings`).
- **Was gut lief**: Mit `useQuery` + bestehende API-Clients in 6 Commits durchgezogen, keine neue Backend-Arbeit nötig. Sweet-Spot-Pink-Akzent + Lucide-Sparkles geben dem Top-Pick visuelle Prominenz.
- **Was nicht klappte**: Bekannter Backend-Bug `GET /api/v1/stocks?total=len(items)` (Router setzt `total` auf Page-Length, nicht echten DB-Count). Im PR als "Workaround mit limit=200 + items.length" dokumentiert — Workaround war aber `listStocks(1, 0)`, was den Bug nicht umgeht (items.length=1). Beim Demo-Polish-Run am 2026-05-29 entdeckt: Stocks-Card zeigte konstant "1" statt 13 → Follow-up-Fix in Commit `8fa5971` (auf `listStocks(200, 0)` umgestellt).
- **Nachbearbeitung nötig bei**: Backend-Fix für korrekten Stocks-Count via `count(*)` SQL-Query wäre saubererer Endstand (separate Issue).
- **Lektion**: **PR-Body-Workaround-Behauptungen lesen, aber im Code verifizieren.** Der PR dokumentierte korrekt "limit=200 nutzen", aber der tatsächliche Code-Stand war `limit=1`. Wer das nur per PR-Body geprüft hätte, hätte den Bug nicht gefangen. Sanity-Check via Demo-Run-Through bleibt unersetzlich.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · Mobile-Nav-Header — `flex-col` auf <640px statt Cutoff (PR #149)
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: Pre-existing Mobile-Bug behoben: globale Nav (`Dashboard | Universen | Rankings | Backtest`) lief auf <640px horizontal über den Viewport-Rand hinaus, "Backtest" komplett unsichtbar. Fix: Header wechselt auf Mobile zu `flex-col` (Logo eigene Zeile, Links darunter), bleibt ab `sm:` horizontal. CSS-only, kein State, keine neue Logik. 2 Commits (Fix + ein winziger Cleanup).
- **Was gut lief**: 1-File-Tailwind-Class-Swap, ~10min total inkl. visueller Verifikation per Mobile-Viewport im Browser. Kleinster Diff aller Demo-Branch-PRs.
- **Was nicht klappte**: Nichts. Klassischer Mobile-Cutoff-Fix.
- **Nachbearbeitung nötig bei**: keine.
- **Lektion**: **Mobile-Viewport-Test gehört in den UAT jedes neuen Page-Layouts.** Der Bug war seit Wochen unentdeckt, weil niemand die Demo auf <640px geprüft hat. Sheylas spontaner "schau mal aufs Handy"-Test fand ihn.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · Memo-Drilldown — Sheet von Rankings-Tabelle + MemoPanel füllen (Frontend-Backlog Priorität 1)
- **Agent**: Claude Code (Opus 4.7 als Orchestrator + Sonnet 4.6 für Implementer/Reviewer-Subagents + Haiku 4.5 für Trivial-Tasks)
- **Scope**: Spec → Plan → 11-Task-Subagent-Driven-Execution. Backend: `RankingItem.stock_id` (Optional, Backwards-Compat) + JSONB-Befüllung via `StockService`-Lookup mit Warning-Log auf unbekannte Tickers. Frontend: vollständiges Memo-Schema-Mirror, `useStockMemo` Tanstack-Query-Hook, `MemoContent`-Präsentation (Hero/Sweet-Spot/Stärken+Risiken/Widersprüche/Interpretation/Meta), `MemoSheet` Slide-In-Wrapper mit State-Machine, `MemoEmpty`/`MemoErrorCard` Sub-States, `RankingsTable` Row-Click-Integration mit `stopPropagation` auf Ticker-Link, `MemoPanel`-Stub-Replacement auf Factsheet-Page (gemeinsame Komponenten). Killer-Feature für Capstone-Demo: Memo unsichtbar → Memo demoable in 13 atomaren Commits.
- **Was gut lief**: Subagent-Driven-Development mit Two-Stage-Review (Spec-Compliance + Code-Quality) als eingebaute Quality-Gates pro Task. Code-Quality-Reviewer von Task 2 fand zwei Important-Issues (fehlender Edge-Case-Test für unbekannte Ticker + fehlendes Warning-Logging) — beide vor Merge addressiert in einem Follow-up-Commit. Pre-Discovered-Context im Implementer-Prompt (konkrete Signaturen, Pfade, Pattern-Beispiele aus der Codebase, "don't re-explore") eliminierte "ich muss erst rumlesen"-Zyklen — Subagents lieferten direkt funktionierenden Code statt "ich habe versucht aber...". TDD-Disziplin (Failing-Test-First pro Step) hielt 13 Commits ehrlich: 101 Frontend-Tests + 340 Backend-Unit-Tests grün vor jedem Commit, kein Skip-Commit "wegen Eile".
- **Was nicht klappte**: (1) MemoContent-Test-Fixture-Konflikt: `one_liner="Solide Quality-Geschichte..."` kollidierte mit `model_a="Quality"` aus dem Contradictions-Test → testing-library's `getByText(/Quality/)` fand 2 Matches statt 1 → 1/10 Tests rot in Task 6. Quick-Fix-Commit (`6cab323`) entkoppelte den Fixture-String → A11 (siehe unten). (2) `ContradictionItem`-Felder waren in der Spec initial falsch antizipiert (`pro_argument/contra_argument/resolution` statt tatsächlicher `model_a/model_b/description` aus dem Backend) — Hotfix-Commit (`7fbe2cb`) vor dem Plan-Schreiben nötig. (3) Test-Stub `InMemoryStockService` erbt von concrete `StockService` statt Protocol → mypy `# type: ignore[override]` benötigt; im Final-Review als unused entdeckt + entfernt (`d36da1b`). Reviewer flagte das Subclassing-Pattern als Smell für späteres `StockServiceProtocol`-Refactoring.
- **Nachbearbeitung nötig bei**: keine — alle CI-Gates grün lokal (mypy + ruff + pytest backend; lint + tsc + vitest + build frontend). Mobile-Viewport von Nav-Header ist out-of-scope und landet in separatem PR `fix/mobile-nav-header`.
- **Lektion**: **Pre-Discovered-Context im Implementer-Prompt vermeidet ~50% der "rumlesen"-Zyklen.** Vor jedem Implementer-Dispatch habe ich Claude die konkreten Signaturen, Pfade, Variable-Namen und existierenden Test-Patterns vorab in den Prompt gegeben — mit explizitem "don't re-explore", statt die Subagents selbst suchen zu lassen. Sie starten dadurch sofort produktiv. **Subagent-Driven-Development skaliert bei großen Features, wenn der Plan gut decomposeable ist** — TDD-Pattern pro Task macht den Plan automatisch in 2-5-Minuten-Schritte zerlegbar, was die Quality-Gates pro Schritt billig macht. **Spec-Hotfixes beim Plan-Schreiben sind normal und gesund** — beim Schreiben des konkreten Plans entdeckt man Spec-Annahmen die in der Codebase nicht stimmen. Lieber Spec korrigieren bevor Tasks formuliert sind als später per Subagent-Dispatch korrigieren.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · LLM-Universe-Wizard — Claude Haiku für Universe-Vorschläge
- **Agent**: Claude Code (Opus 4.7 Orchestrator + Sonnet 4.6 Implementer-Subagents)
- **Scope**: Neuer KI-Wizard zur Universe-Erstellung — User beschreibt freitext was er sucht (z.B. *"Halbleiter aus den USA"*), Claude Haiku 4.5 schlägt unter Stock-Katalog-Whitelist Tickers + Name + Region + Begründung vor. Pre-filled Form für User-Editing vor Erstellen. Tool-use-Pattern (Pydantic-Schema-Output) analog zur Narrative-Engine. 3-Task Subagent-Driven (Domain-Service, REST-Endpoint, Frontend-Page) plus Spec-First.
- **Was gut lief**: Pattern-Reuse aus existing Narrative-Engine sparte Architektur-Aufwand komplett — `LLMClient.messages_create()` mit `tools=[{input_schema: ...}]` + `tool_choice` ist projekt-etabliert. Pre-Discovered-Context (PromptTemplateLoader-Signatur, Anthropic-Tool-use-Pattern aus narrative_service.py:579 zitiert) ließ den Implementer ohne einen einzigen "wo finde ich..."-Schritt loslegen. Stock-Katalog-Whitelist im System-Prompt + Cache-Control reduziert Latenz/Kosten ab 2. Call. Factory-Fixture-Pattern (`make_client_with_suggest`) für Integration-Tests sauber wiederverwendbar.
- **Was nicht klappte**: Plan hatte initial schema-verletzende Mock-Daten in den Unit-Tests (zu-kurze `reasoning`-Strings, single-ticker bei Whitelist-Test). Pydantic-Validation rejected sie → Tests failed mit `InvalidLLMOutput` statt erwarteter `EmptySuggestion`. Implementer hat die Mocks pragmatisch schema-konform gemacht ohne Test-Intent zu ändern — gutes Defensive-Catching beim Implementer-Self-Review.
- **Nachbearbeitung nötig bei**: Multi-Turn-Konversations-Variante (V2) falls Zeit. Wizard-Page könnte profitieren von shadcn `Textarea` (gibt's aktuell nicht in `frontend/components/ui/`).
- **Lektion**: **Tool-use-Pattern mit Pydantic `input_schema` skaliert linear für neue LLM-Features.** Universe-Wizard war strukturell 80% Code-Copy aus narrative_service.py mit Wizard-spezifischem Schema + neuen Prompts. Plus: **Plan-Stub-Test-Daten sollten Schema-konform sein** — ein 30-Sekunden-Self-Check beim Plan-Schreiben spart einen Implementer-Adjustment-Loop.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-28 · Dashboard-Stats — 4 Karten über Runs-Tabelle (Backlog Priorität 5)
- **Agent**: Claude Code (Opus 4.7 Orchestrator + Sonnet 4.6 Implementer-Subagents)
- **Scope**: Frontend-only Erweiterung des `/dashboard`. Neue `StatsCards`-Komponente (Letzter Run, # Universen, # Stocks, Top-Pick mit Sweet-Spot-Pink) + DashboardClient-Integration mit 2 zusätzlichen Tanstack-Queries. 3-Task Subagent-Driven-Execution mit TDD-Pattern. Synergie mit Memo-Drilldown: Top-Pick-Klick führt direkt zum echten LLM-Memo.
- **Was gut lief**: Spec-Schreiben war schnell weil das Dashboard schon halb-existierte (Runs-Tabelle aus PR #124) — Erweiterung statt Neuschreiben. Pre-Discovered-Context im Implementer-Prompt (existing `STATUS_VARIANT`/`STATUS_LABEL` patterns) eliminierte Duplikation. Schema-Synergie mit Memo-Drilldown's `stock_id`-Feature: Top-Pick-Link nutzt jetzt korrekt das neue UUID-Routing.
- **Was nicht klappte**: Backend's `GET /api/v1/stocks` Router setzt `total=len(items)` — pre-existing Pagination-Bug. Bei `limit=1` ist `total=1` immer, unabhängig von DB-Inhalt. Frontend zeigte "Stocks: 1" statt korrekter 7. Fix als Frontend-Workaround (`limit=200` + `items.length`) statt Backend-Fix in diesem Slice (Scope-Disziplin). Backend-Fix (Repository.count()-Method) als Folge-PR vermerkt. Plus: Test-Mock musste angepasst werden weil mit dem Workaround `items.length` zählt statt `total`.
- **Nachbearbeitung nötig bei**: Backend-Fix für `StockListResponse.total` (Repository.count()-Method) — pre-existing Bug, separater Follow-up-PR.
- **Lektion**: **Pre-existing Bugs außerhalb des PR-Scopes lieber als Folge-Issue dokumentieren statt nicht-gefixt drin lassen.** Workaround-Comment im Code (`// Backend's total-Field ist buggy → items.length nutzen`) macht für künftige Wartung sofort klar wo der eigentliche Bug sitzt. Ehrlicher als stille Symptom-Behandlung.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-18 · CI-Split + Integration-Tests + Zeitbomben-Fix (PR #130) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `test_backtests_endpoint.py` (8 neue Integration-Tests für Backtest-Endpoints); CI-Job-Split in `backend-unit-tests` (ohne Postgres) und `backend-integration-tests` (mit Postgres-Service-Container); relative Datumsangaben in `test_backtest_service.py` durch absolute Daten ersetzt (Zeitbomben-Fix Issue #121).
- **Was gut lief**: CI-Split war architektonisch überfällig — Unit-Tests laufen jetzt deutlich schneller ohne Postgres-Dependency. Zeitbomben-Fix war nach Identifikation trivial.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar (keine Session-Notes vorhanden).
- **Nachbearbeitung nötig bei**: Keine — PR #130 grün gemerged.
- **Lektion**: **Relative Datumsangaben in Tests sind Zeitbomben.** `datetime.now() - timedelta(days=30)` produziert unterschiedliche Ergebnisse je nach Ausführungstag. Immer absolute, feste Daten in Test-Fixtures verwenden.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · Backend/Frontend-Fixes Sprint (PRs #110–#113) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: 4 Fixes in einem Sprint:
  - **#110** `is_error`-Erkennung in `MemoResponse.from_entity()` von String-Check auf `model_version == ERROR_FALLBACK_MODEL_VERSION` umgestellt (locale-robust, bruchsicher bei Text-Änderungen). Score-Berechnung aus Prompts entfernt.
  - **#111** Production-Warning für Stub-Provider in `dependencies.py` — `get_fundamentals_provider()` loggt `WARNING` wenn `environment=production`, damit synthetische Demo-Daten sichtbar bleiben.
  - **#112** `X-API-Key`-Header in `apiFetch` (Frontend) ergänzt — alle Calls gegen authentifizierte Endpoints lieferten ohne diesen Header 401.
  - **#113** `elapsed`-Check aus Stale-Cleanup-Guard des Narrative-Workers entfernt — TOCTOU-Race zwischen GET-Handler und Worker führte zu Status-Überschreiben.
- **Was gut lief**: Alle 4 Fixes isoliert — kein Crosscut zwischen den Änderungen. String-based `is_error`-Prüfung durch kanonische `model_version`-Prüfung zu ersetzen war die richtige Abstraktions-Ebene.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar.
- **Nachbearbeitung nötig bei**: Keine.
- **Lektion**: **String-based Discriminants sind fragil** — sie brechen bei Refactoring oder i18n. Wenn ein Typ einen kanonischen Marker hat (`model_version`), diesen bevorzugen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-14 · MCP-Server Slice 1 — Skeleton + run_ranking Tool (PR #102) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `backend/interfaces/mcp/` Skeleton via FastMCP/STDIO: `server.py` (Entry-Point), `rest_client.py` (async httpx mit X-API-Key + Error-Mapping), `tools/run_ranking.py` (erstes MCP-Tool). Gemäss Spec `docs/specs/2026-05-11-mcp-server-slice-1-skeleton.md`.
- **Was gut lief**: MCP-Layer klar als dünner Adapter über Application-Services — keine Business-Logik im MCP-Layer (CLAUDE.md-Konvention eingehalten). Spec-First-Workflow (Spec existierte vor Code) sorgte für klaren Scope.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar.
- **Nachbearbeitung nötig bei**: Keine — Grundlage für weitere MCP-Tools.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-14 · GET /api/v1/stocks/{ticker}/factsheet (PR #103) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: Neues `get_latest_ticker_result(ticker)` auf `RankingRunRepository`-Port + SQLA-Implementierung via `jsonb_array_elements`-PostgreSQL-Query (kein Full-Result-Set in Python). `LatestRankingSnapshot` + `StockFactsheet` Pydantic-Schemas. REST-Endpoint `GET /api/v1/stocks/{ticker}/factsheet`.
- **Was gut lief**: PostgreSQL-native JSONB-Query statt Python-seitigem Filtering — skaliert auch bei grossen Runs. Clean-Architecture-Schichten eingehalten (kein SQL im Router).
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar.
- **Nachbearbeitung nötig bei**: Keine.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-14 · Persistence save() Silent Data Loss Fix (PR #101) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: `RankingRunRepository.save()` UPDATE-Branch schrieb nur `status`, ignorierte `weight_config` und alle anderen mutablen Felder still. Fix: alle mutablen Felder explizit zuweisen.
- **Was gut lief**: Bug war durch Code-Lesen unmittelbar erkennbar sobald die Issue-Beschreibung ihn beschrieb.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar. Kein Test hatte den UPDATE-Branch mit Nicht-Status-Mutation verifiziert — daher blieb der Bug bis Issue #93 unentdeckt.
- **Nachbearbeitung nötig bei**: Keine.
- **Lektion**: **UPDATE-Branches in Repository.save() müssen alle mutablen Felder explizit auflisten.** "Nur status schreiben" klingt harmlos, ist aber ein stiller Datenverlust sobald andere Felder geändert werden sollen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-14 · Anthropic-Client Singleton + BudgetCap-Test (PR #107) ⟨retrospektiv⟩
- **Agent**: Claude Code (Sonnet 4.6, inline)
- **Scope**: `get_anthropic_client()` auf `@lru_cache(maxsize=1)` umgestellt — `AsyncAnthropic` öffnet einen `httpx`-Connection-Pool der nicht pro Request neu aufgebaut werden soll (Issue #68). BudgetCap 402-Test ergänzt (Issue #98).
- **Was gut lief**: Pattern ist analog zu `get_prompt_loader()` im selben Codebase — Konsistenz.
- **Was nicht klappte**: Retrospektiv nicht rekonstruierbar.
- **Nachbearbeitung nötig bei**: Keine.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-19 · Backtest `_simulate_portfolio` mit Drift + Monthly-Reset (Issue #140)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: `_simulate_portfolio` an Backtest-Light-Spec v1.1 §5 angeglichen. Bestehende Impl (`returns.mean(axis=1)`) war mathematisch ein taeglich-rebalanciertes Equal-Weight-Portfolio — entsprach NICHT der Spec (Drift + monatlicher Reset). Neuer Helper `_monthly_rebalance_dates` per `pd.Grouper(freq="ME")`. TDD-Workflow: 8 Unit-Tests in neuer Datei `test_backtest_portfolio_simulation.py` (Drift-, Reset-, Edge-Case- und Sanity-Tests), erst rot, dann Rewrite.
- **Was gut lief**: Der erste Reset-Test war versehentlich grün mit der naiven Impl (weil daily-rebalance auch 50/50 ergibt). Test-driven-Skill hat darauf hingewiesen, dass das ein Anti-Pattern ist — Test wurde verstaerkt, um Drift VOR dem Monatsende UND Reset DANACH zu pruefen. Coverage 96.8%, ruff + mypy strict clean.
- **Was nicht klappte**: Spec-Code-Differenz wurde erst durch das Code-Review der Spec entdeckt — das urspruengliche Backtest-Bundle (PR #120) ist VOR der finalisierten Spec v1.1 gemerged worden, daher die Diskrepanz. Lehre: Spec-First-Konvention konsequent durchziehen, auch wenn die Spec mid-flight noch finalisiert wird.
- **Nachbearbeitung nötig bei**: Integration-Tests (Postgres-Container) lokal nicht ausfuehrbar, CI ist Acceptance-Gate fuer `test_backtests_endpoint.py`.
- **Lektion**: TDD-Skill hat einen falsch-positiven Test sofort gefangen. Der vorgeschlagene "test passes immediately → fix test"-Regel-Trigger hat den Reset-Test von einem schwachen ("Feb-1 = 50/50") zu einem starken ("Drift im Januar + Reset am 31.01.") gemacht. Faengt zukuenftige Vectorize-Regressionen.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-19 · AI-USAGE.md — Einträge für PRs #131–#136 (PR #137)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: 6 neue Einträge + 2 neue Patterns (P10: Null-Object, A8: Required kwargs) in `docs/AI-USAGE.md`. Einträge decken session.merge()-Refactor, SIGTERM-Shutdown, Universe-Sync, CI-Checkliste, Fixture-Mode, RAG-Pipeline ab.
- **Was gut lief**: Rückblickende Pattern-Extraktion aus 6 PRs in einer Session — klare Evidenzlinks pro Pattern, kein Generalisierungsproblem.
- **Was nicht klappte**: PR #131-Eintrag war voreilig positiv formuliert — `session.merge()`-Bug wurde erst durch CI nach Merge entdeckt (A9 entstand als Korrektur in diesem Follow-up, nicht im Original-PR-Entry).
- **Lektion**: AI-USAGE-Einträge direkt nach CI-Ergebnis schreiben, nicht nach Local-Check. CI ist das Acceptance-Gate (Q4 gilt nicht nur für LLM-Output).
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-19 · session.merge() Fix — pg upsert (Issues #91 #92, PR #131 Follow-up)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `session.merge()` in `SQLARankingRunRepository.save()` und `SQLAUniverseRepository.save()` durch `pg_insert(...).on_conflict_do_update()` ersetzt. Fixes 3 CI-Failures: `test_save_twice_updates_instead_of_insert` (ranking_run + universe) und `test_save_then_save_results_then_save_persists_all`.
- **Was gut lief**: Root-Cause sofort klar aus CI-Fehler (`executemany` mit 2 Rows derselben UUID = 2 Pending-Objekte → doppelter INSERT). `pg_insert().on_conflict_do_update()` ist atomic + session-state-unabhängig — kein SELECT, kein Identity-Map-Problem.
- **Was nicht klappte**: `ruff format`-Check schlug fehl weil `set_={"name": ..., "region": ..., "tickers": ...}` zu lang für eine Zeile war. Fix: Dict auf mehrere Zeilen aufgebrochen.
- **Nachbearbeitung nötig bei**: Issues #91 + #92 können nach PR-Merge geschlossen werden (Upsert-Semantik ist erfüllt, nur via anderem Mechanismus als ursprünglich geplant).
- **Lektion**: CI-Ergebnis ist nicht gleich Local-Prüfung — PR #131's Original-Eintrag schrieb „nichts klappte nicht", aber `session.merge()` mit transientem Objekt hat dasselbe Problem wie das Pattern das es ersetzen sollte (A9).
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-19 · RAG-Pipeline Retrieval — Tests + Bug-Fix (Issue #18, PR #136)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: Nacharbeit zu PR #136: Missing-`feature`-kwarg-Bug in `RetrievalService.retrieve()` gefixt, 6 Unit-Tests (`test_retrieval_service.py`) + 9 Integrationstests (`test_rag_endpoint.py`) hinzugefügt.
- **Was gut lief**: Ruff identifizierte sofort den unbenutzten `patch`-Import; der fehlende `feature`-Parameter wurde durch Lesen der `LLMClient.embed()`-Signatur entdeckt, bevor CI lief — klassischer Read-before-commit.
- **Was nicht klappte**: 207 Projektdateien fehlten lokal in `/tmp` (Partial-Restore nach Temp-Cleanup). Keine lokale pytest-Ausführung möglich → nur Syntax-Check + Ruff, CI ist Acceptance-Gate.
- **Nachbearbeitung nötig bei**: CI-Ergebnis von PR #136 abwarten; falls Mypy den `feature`-Parameter auf anderen Aufruf-Stellen vermisst, dort nachnachrüsten.
- **Lektion**: `LLMClient.embed()` hat `feature: str` als Required-kwarg ohne Default — jeder neue Aufrufer muss ihn setzen. Grep-Pattern für künftige Reviews: `llm.embed(texts=` ohne `feature=` als Suchstring.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · Fixture-Mode + Golden-Prompt + LLM-Smoke (Issue #59, PR #135)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `FixtureLLMClient`-Hilfsklasse (bündelt `StubAnthropicClient` + `LLMClient` + `_NullCostLogRepository`), 2 neue Fixture-JSONs (`contradictory_trend_value`, `ambiguous_stock`), 2 Integrationstests in `test_narrative_service_integration.py`, wöchentliches `llm_smoke_judge.py`-Skript mit LLM-as-Judge-Pattern + GitHub-Actions-Workflow.
- **Was gut lief**: `_NullCostLogRepository`-Pattern — `CostTracker` braucht ein Repository-Interface, das im Test-Kontext nichts schreiben soll. Null-Objekt-Pattern (Schnittstelle implementieren, alle Operationen als No-Op) war sauberer als Mocking, weil er keine `AsyncMock`-Konfiguration für jeden Methodenaufruf braucht.
- **Was nicht klappte**: Nichts Kritisches; `FixtureLLMClient` ist als Public-API noch nicht typisiert (kein `py.typed`-Marker in `tests/`).
- **Nachbearbeitung nötig bei**: Nichts unmittelbar Blockierendes.
- **Lektion**: LLM-as-Judge-Muster (zweites Modell bewertet Output des ersten) ist am günstigsten mit `claude-haiku-4-5-20251001` als Judge — Geschwindigkeit + Kosten-Trade-off bei einfachen PASS/FAIL-Fragen günstiger als Sonnet.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · RAG-Pipeline Slice 2+3 — Ingestion + Retrieval-Endpoint (Issue #18, PR #136)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `find_nearest()` im `EmbeddingRepository`-Port + `SQLAEmbeddingRepository`-Implementierung via Raw-SQL mit `halfvec(2048)`-Cast für HNSW-Index, `RetrievalService`, `POST /api/v1/rag/retrieve`-Endpoint, DI-Kette in `dependencies.py`, `VOYAGE_API_KEY` in `config.py`, `scripts/ingest_filings.py` (SEC-EDGAR → 5 Ticker × 2 Filings → Voyage-Embedding → pgvector UPSERT), README-Sektion.
- **Was gut lief**: HNSW-Index-Nutzung erfordert explizites `halfvec(2048)`-Cast in der Query — das steht in der pgvector-Doku, wurde korrekt umgesetzt. SEC-EDGAR `submissions`-API ist stabil und braucht keine API-Key.
- **Was nicht klappte**: `LLMClient.embed()` hat `feature` als required kwarg ohne Default — wurde in `RetrievalService` vergessen (silent TypeError zur Laufzeit). Entdeckt beim Schreiben der Unit-Tests am nächsten Tag.
- **Nachbearbeitung nötig bei**: `scripts/ingest_filings.py` einmalig auf Render Shell-Tab ausführen sobald `VOYAGE_API_KEY` gesetzt (DoD-Item 1 für #18).
- **Lektion (A7-Instanz)**: Required kwargs ohne Default in internen Hilfsklassen (`LLMClient.embed(feature=)`) sind eine Fehlerquelle, die statische Analyse (mypy) sofort fängt — aber nur wenn alle Aufrufer im gleichen Typisierungsumfang sind. Hier war `retrieval_service.py` nicht mit mypy verifiziert worden.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · CI-Checkliste für wiederkehrende Fallstricke (Issue #128, PR #134)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: Neuer Abschnitt „Häufige CI-Fallstricke" in `AGENTS.md` mit 3 konkreten Checklisten: jsdom `URL.createObjectURL`, Alembic Multiple Heads, `type: ignore` → `unused-ignore`-Drift.
- **Was gut lief**: Alle 3 Checklisten direkt aus echten CI-Fehlern der vergangenen Wochen destilliert — keine generischen Best-Practices, sondern projektspezifische Erfahrungswerte.
- **Was nicht klappte**: Nichts — reiner Doku-PR, kein Code.
- **Nachbearbeitung nötig bei**: Nichts.
- **Lektion (Q3-Instanz)**: Docs-PRs haben den höchsten ROI wenn sie unmittelbar nach dem dritten Auftreten desselben Fehlers entstehen — nicht als „irgendwann schreiben wir das auf".
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · Universe-Sync-Endpoint POST /{id}/sync (Issue #114, PR #133)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `UniverseSyncResult`-Dataclass + `sync_universe()`-Methode in `UniverseService`, `UniverseSyncResponse`-Schema, `POST /api/v1/universes/{universe_id}/sync`-Endpoint, 5 Integrationstests.
- **Was gut lief**: `InMemoryUniverseRepository`-Pattern aus bestehenden Tests direkt übernehmen — keine neuen Mocking-Infrastruktur nötig.
- **Was nicht klappte**: `Edit`-Tool-Collision bei `universes.py` (zwei identische `return UniverseRead(...)`-Blöcke → Mehrdeutigkeit). Gelöst durch mehr Kontext im `old_string`.
- **Nachbearbeitung nötig bei**: Nichts.
- **Lektion**: Bei Edit-Tool-Collisions ist mehr `old_string`-Kontext immer der richtige Weg — nie auf Replace-All zurückgreifen wenn nur ein Block gemeint ist.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · SIGTERM Graceful Shutdown für Batch-Jobs (Issue #87, PR #132)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `list_by_status()`-Methode im `MemoBatchJobRepository`-Port + SQLAlchemy-Implementierung, FastAPI-`lifespan`-Context-Manager in `app.py` der beim Shutdown alle `running`/`pending`-Jobs als `failed` markiert.
- **Was gut lief**: FastAPI `lifespan` ist der korrekte Mechanismus für Startup/Shutdown-Hooks — sauberer als deprecated `on_event`.
- **Was nicht klappte**: Ruff-UP035 (`from typing import AsyncGenerator` → `from collections.abc import`) — automatisch mit `--fix` behoben.
- **Nachbearbeitung nötig bei**: Echte SIGTERM-Integration-Tests würden einen laufenden Prozess brauchen — aktuell nur Unit-Coverage. Accepted trade-off.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-18 · session.merge() Refactor (Issues #91 #92, PR #131)
- **Agent**: Claude Code (Sonnet 4.6)
- **Scope**: `RankingRunRepository.save()` und `UniverseRepository.save()` von `flush()+get()+add/update`-Pattern auf `session.merge()` umgestellt.
- **Was gut lief**: `session.merge()` ist die kanonische SQLAlchemy-Lösung für Upsert-by-PK — lädt aus Identity-Map oder SELECT, plant INSERT/UPDATE. Kein vorheriger `flush()` nötig.
- **Was nicht klappte**: Nichts — reines Refactoring mit eindeutigem Endstate.
- **Nachbearbeitung nötig bei**: Nichts.
- **Lektion**: `session.merge()` vs `flush()+add()`: Bei Entities mit bekanntem PK ist `merge()` immer besser — es ist idempotent, braucht kein vorheriges GET, und der Session-Lifecycle bleibt konsistent.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-17 · Dashboard-Seite mit Run-Liste (Issue #20, PR #124)
- **Agent**: Claude Code (Sonnet 4.6) als Controller mit `superpowers:subagent-driven-development`; 1 Backend-Subagent (Haiku), 1 Frontend-Subagent direkt im Main-Context wegen fehlendem `npx` in der Umgebung.
- **Scope**: Issue #20 geschlossen. (1) **Backend**: `list_all()` in Abstract-Repo-Interface + SQLAlchemy-Implementierung, `list_runs()` im Service, neuer `GET /api/v1/runs`-Endpoint mit `limit`/`offset`-Pagination. (2) **Frontend**: `/dashboard`-Route, shadcn `Table` mit Run-ID, Datum, Universum-Name (per Lookup-Map aus `GET /api/v1/universes`), Status-`Badge`; Loading- (Skeleton), Error- und Empty-State; Nav-Link „Dashboard" umgebogen von `/` auf `/dashboard`. (3) **E2E**: Playwright Smoke-Test 4 (Seite lädt, Tabelle oder Empty-State sichtbar).
- **Was gut lief**:
  - **Plan-as-Contract**: 7-stufiger Plan mit verbatim Code pro Schritt — keine BLOCKED-Reports, Backend-Chain ohne Rückfragen durchgelaufen.
  - **Merge-Konflikt-Auflösung direkt im Worktree**: Conflict in `docs/AI-USAGE.md` (zwei parallele Einträge selber Tag) direkt resolved + beide Einträge behalten.
- **Was nicht klappte**:
  - **`npx` / Node.js nicht verfügbar im Terminal-Kontext**: `npx shadcn@latest add skeleton` schlug fehl. Lösung: Skeleton-Komponente manuell nach shadcn-Muster erstellt (`animate-pulse rounded-md bg-muted`). CI bleibt das Frontend-Build-Gate.
  - **Rate-Limit mid-Subagent**: Erster Backend-Subagent wurde durch Rate-Limit unterbrochen — Änderungen waren unstaged vorhanden, wurden nach Reset manuell verifiziert und committed. **Lehre**: Bei Rate-Limit-Unterbrechung immer zuerst `git diff` prüfen bevor neu gestartet wird.
- **Token-Kosten**: ~30k Tokens Sonnet 4.6 (Controller + Frontend); ~15k Tokens Haiku (Backend-Subagent); geschätzt ~$0.15 total.
- **Autor**: Nicolas Lardinois (mit Claude Code Sonnet 4.6)

## 2026-05-17 · Rankings Detail-Page: Sortierung, Filter, CSV-Export (Issue #21, PR #126)
- **Agent**: Claude Code (Sonnet 4.6) im Plan-Modus (Worktree `clever-goldstine-1f332b`): Explore-Subagents für Codebase-Erkundung → Plan-Subagent für Implementierungsplan → direkte Umsetzung im Main-Context.
- **Scope**: Issue #21 — Drei interaktive Features auf der bestehenden `/rankings/[runId]`-Detail-Page: (1) **Sortierung** — click-to-sort auf allen 7 numerischen Spalten (`#`, `Avg`, 5 Modell-Ranks) mit `aria-sort`-Attribut und `null`-am-Ende-Invariante; (2) **Ticker-Filter** — case-insensitiver Textfilter via `useMemo`; (3) **CSV-Export** — client-seitiger Blob-Download via `URL.createObjectURL`. Dazu: Spec `docs/specs/2026-05-17-rankings-enhancements.md` (CLAUDE.md-Pflicht), 3 neue Unit-Tests, Playwright-E2E-Test 4 (Sortierung + CSV-Download). Nebenher 4 weitere CI-Fixes: Merge-Konflikt in `AI-USAGE.md`, Ruff B017 (`pytest.raises(Exception)` → `pytest.raises(ValidationError)`), doppelte Alembic-Migration 0009 → 0010, mypy `unused-ignore`.
- **Was gut lief**:
  - **Plan-Modus schützte vor voreiligem Code**: Zwei parallele Explore-Agents (Frontend-Patterns + Backend-API) lieferten innerhalb einer Runde ein vollständiges Bild — kein Mid-Flight-Recherchieren mehr nach Plan-Approval.
  - **Bestehende Patterns 1:1 wiederverwendbar**: `SortableHead`-Komponente mit `aria-sort` folgte dem `TableHead`-Pattern aus `components/ui/table.tsx`. Kein neues npm-Package nötig — lucide-react und shadcn/ui Button/Input waren schon vorhanden.
  - **CI-Failures schnell isoliert**: Drei unabhängige Probleme (Ruff, Alembic, jsdom) in zwei Runs identifiziert und in Einzel-Commits behoben — kein monolithischer Fix-Commit.
- **Was nicht klappte**:
  - **jsdom-Lücke nicht antizipiert**: `URL.createObjectURL` ist in jsdom nicht implementiert — `vi.spyOn(URL, 'createObjectURL')` wirft `createObjectURL does not exist`. Hätte in der Spec als Randbedingung stehen sollen. Fix: `global.URL.createObjectURL = vi.fn()` vor dem Spy.
  - **Duplicate-Migration nicht vorhergesehen**: Branch hatte eigene `0009_seed_e2e_stocks.py` (Commit von PR #120), main hatte `0009_add_is_error_to_research_memos.py`. Alembic-Fehler erst in CI sichtbar, weil `alembic history` lokal nicht ausgeführt wurde. **Lehre**: Bei Branches, die über Merge-Commits auf main basieren, vor dem PR-Erstellen `alembic heads` prüfen.
  - **mypy `unused-ignore` als Folge von Ruff-Fix**: Das Ersetzen von `pytest.raises(Exception)` durch `pytest.raises(ValidationError)` machte die `# type: ignore[union-attr]`-Kommentare überflüssig — mypy meldet dann `unused-ignore`. Zwei-Stufen-Fix wäre vermeidbar gewesen, wenn der erste Fix sofort auch die Kommentare entfernt hätte.
- **Token-Kosten**: ~40k Tokens Sonnet 4.6 (Plan-Modus + Explore-Agents + direkte Umsetzung); geschätzt ~$0.25.
- **Autor**: Nicolas Lardinois (mit Claude Code)

## 2026-05-17 · Playwright-Setup + 5 E2E-Szenarien (Issue #50, PR #120)
- **Agent**: Claude Code (Sonnet 4.6) als Controller mit `superpowers:subagent-driven-development` (20 Build-Steps sequentiell, Haiku-Subagents für mechanische Tasks, general-purpose für Implementierungsaufgaben).
- **Scope**: Issue #50 end-to-end geschlossen. (1) **Backend-Erweiterungen**: `UniverseService` + `POST/GET /api/v1/universes` (Universe-REST-Layer fehlte komplett); `GET /api/v1/stocks/{ticker}` (Stock-Detail-Endpoint); vollständiger `BacktestService`-Stack — `BacktestResult`-Entity + `BacktestResultRepository`-Port + SQLAlchemy-Adapter + Alembic-Migration 0009 (`backtest_results`-Tabelle, JSONB für Metrics/Series) + Alembic-Migration 0010 (5 Seed-Stocks mit fixen UUIDs für deterministische E2E-Tests); `POST/GET /api/v1/backtests` (gleichgewichtete Portfoliosimulation mit 5 Metriken: total_return, cagr, annual_vol, sharpe, max_drawdown). (2) **Frontend**: API-Clients (`lib/api/universes.ts`, `runs.ts`, `memos.ts`, `backtest.ts`), 4 neue Seiten (`/universes`, `/rankings` vollständig, `/stocks/[ticker]` Factsheet, `/backtest` mit Recharts-LineChart 3 Kurven). (3) **E2E**: `playwright.config.ts`, 5 Playwright-Specs (T1 Universe-Erstellung, T2 Ranking-Tabelle 5 Zeilen, T3 Factsheet-Navigation, T4 Memo-Request mit `page.route()`-Mock, T5 Backtest-Chart); `e2e.yml` CI-Workflow mit docker-compose-Stack-Startup + Health-Checks.
- **Was gut lief**:
  - **Haiku für mechanische Subagents (P9 angewendet)**: Playwright-Config, E2E-Specs und README-Ergänzung mit Haiku-Model dispatcht — volle Spec-Compliance auf Anhieb, keine Roundtrips nötig. Kosten-Einsparung ~70% gegenüber Sonnet für dieselbe Aufgabe.
  - **`page.route()` für LLM-Mock**: T4 (Memo-Test) interceptiert `POST /api/v1/memos/generate` im Browser-Kontext via Playwright, bevor es den Backend erreicht — kein `ANTHROPIC_API_KEY` in CI nötig, deterministisches Fixture-Response. Pattern ist auf alle LLM-Calls übertragbar.
  - **Fester UUID-Seed-Pattern für E2E**: Migration 0010 verwendet `ON CONFLICT (ticker) DO NOTHING` mit fixen UUIDs (`11111111-...` bis `55555555-...`) — E2E-Tests referenzieren AAPL direkt per bekannter UUID, keine Setup-Randomness. Idempotent-Seed als Alembic-Migration statt Init-SQL-Script.
  - **data-testid-First beim Frontend**: Alle 4 Seiten wurden von Anfang an mit `data-testid`-Attributen geschrieben, nicht nachträglich ergänzt. E2E-Spec-Schreiben war dann rein deklarativ — kein DOM-Traversal-Hacking nötig.
  - **Two-Stage-Review fing B904-Ruff-Fehler**: Code-Quality-Reviewer fand in Task 1 `raise HTTPException(...)` ohne `from exc` (Ruff B904 Exception-Chaining). Fix: `except UniverseNotFound as exc: raise HTTPException(...) from exc` + custom Exception statt generic `ValueError`. Wäre in CI-Lauf gefunden worden, aber Review-Loop war schneller.
- **Was nicht klappte**:
  - **Node.js nicht verfügbar im Subagent-Kontext**: Frontend-Build (`npm run build`) konnte nicht lokal verifiziert werden — Subagent musste manuelle TypeScript-Prüfung substituieren. Tatsächliche Laufzeit-Verifikation erst in CI. **Lehre**: Bei Next.js-Arbeiten entweder lokal im Terminal (`npm run build`) nachverifiziern oder explizit CI als Build-Gate deklarieren.
  - **Seed-Migration in falschen Pfad geschrieben**: Subagent für Task 7 (Seed-Daten) schrieb initial in `C:/Users/nicil/prisma-capstone/` (Main-Repo-Root, POSIX-Path) statt in den Worktree `C:/Users/nicil/prisma-capstone/.claude/worktrees/keen-torvalds-4326d0/`. Git-Log-Verifikation hat den Fehler aufgedeckt → Datei im Worktree nochmals erstellt. **Lehre**: Subagent-Prompts bei Worktree-Setups den absoluten Worktree-Pfad explizit übergeben + nach jedem Commit `git show --stat HEAD` als Verifikation verlangen.
  - **StubMarketDataProvider-Datumsbereich**: BacktestService-Unit-Tests schlugen mit `date(2024, 1, 1)` fehl, weil der Stub nur die letzten ~504 Handelstage ab heute (2026-05-17) abdeckt — das beginnt erst ca. 2024-05. Tests mussten auf `2025-01-01`–`2025-12-31` umgestellt werden. **Lehre**: Beim Schreiben von Datum-abhängigen Tests gegen Stub-Provider immer Sliding-Window-Logik einkalkulieren (`today - 2 years` als untere Grenze).
- **Pattern-Beitrag**:
  - **`page.route()` als LLM-CI-Mock-Pattern**: Für alle Features mit LLM-Aufruf kann ein E2E-Test den Browser-Request mit `page.route("**/api/v1/memos/generate", ...)` abfangen und ein Fixture-JSON zurückgeben. Kein separater Mock-Server, kein API-Key in CI. Funktioniert auch für externe APIs (yfinance, Anthropic) wenn der Frontend-Call den Backend proxy-t.
  - **Kandidat für Anti-Pattern A8 "Subagent-Pfad-Ambiguität"**: Wenn Worktrees aktiv sind, muss jeder Subagent-Prompt den Worktree-Pfad explizit nennen *und* eine Commit-Verifikation fordern. Generische Pfade führen zu silent Wrong-Directory-Writes.
- **Token-Kosten**: ~150k Tokens Sonnet 4.6 (Controller) + ~120k Tokens Haiku (Mechanical-Subagents: Playwright-Config, E2E-Specs, README, CI-YAML) + ~60k Tokens general-purpose (Implementation-Subagents: BacktestService, Routing, Frontend-Pages); geschätzt ~1.80 USD total.
- **Autor**: Nicolas Lardinois (mit Claude Code)

## 2026-05-17 · Ranking-UI + Playwright E2E (PR #119, schliesst Codex-Review-Punkte #1 + #5)
- **Agent**: Claude Code (Opus 4.7, 1M-Kontext) als Controller, mit `superpowers:brainstorming` (5 Q-by-Q-Fragen vor Spec) → `superpowers:writing-plans` (1143-Zeilen-Plan, 9 Tasks) → `superpowers:subagent-driven-development` mit zwei-stufigem Review pro Task (Spec-Compliance- + Code-Quality-Reviewer-Subagent). Insgesamt **9 Implementer + 18 Reviewer-Dispatches = 27 Subagent-Aufrufe** in einer Session. Modell-Routing: Sonnet 4.6 für alle Tasks (Frontend-Komplexität gleichmässig integration-lastig — kein klares Haiku-Kandidat dabei).
- **Auslöser — Externer AI-Peer-Review als Force-Multiplier**: Codex hatte zuvor das Repo gegen das Capstone-Bewertungsraster geprüft und 5 konkrete Lücken benannt (E2E fehlt, Release-Workflow fehlt, CD-Workflow fehlt, Frontend lokal nicht baubar, Ranking-UI ist "Kommt bald"-Platzhalter). Dieser PR adressiert **Punkt #1 (E2E)** und **Punkt #5 (Ranking-UI)** in einem Bundle. **Punkt #4** (Frontend nicht baubar) wurde als Side-Effect entdeckt: `npm ci` failte mit Lockfile-Drift weil PR #94 Test-Deps in `package.json` reingeschoben hatte, ohne das Lockfile zu syncen — separater PR #118 (gemerged 2026-05-17), CI nutzt jetzt `npm ci` statt `npm install` (fail-on-mismatch).
- **Scope**:
  - **Frontend**: `lib/api/runs.ts` (3 dünne `apiFetch`-Wrapper), `RankingsForm` (Universe-Select + `useMutation(createRun)` + Router-Push), `/rankings` Server-Wrapper, `/rankings/[runId]` Detail-Page (3 parallele `useQuery`s mit 404-Handling über `ApiError`, 5s-Polling für `running`/`pending`-Status), `RankingsTable` (9 Spalten: Rank, Ticker, Avg, Sweet-Spot, 5 Modell-Ranks in fixer Reihenfolge).
  - **Tests**: 9 neue Vitest-Tests (5 für Table, 4 für Form) — gesamt 13 Frontend-Unit-Tests. Drei Playwright-E2E-Tests (Smoke-Boot, Universe-Flow, Ranking-Flow mit echtem Run-Start-bis-Tabelle-sichtbar).
  - **CI**: Neuer `frontend-e2e`-Job mit Postgres-Service (`pgvector/pgvector:pg16`), Backend im Hintergrund + Health-Wait-Loop, Playwright-Browser-Cache via `actions/cache@v4`, Artifact-Upload für `playwright-report` bei Failure.
- **Was gut lief**:
  - **Brainstorming-Disziplin (P1) hat Scope drastisch geschnitten**: Codex hatte 4 Scope-Optionen vorgeschlagen (von "Run-Runner minimal" bis "Vollausstattung mit History + Memo-Drilldown"). 5 Q-by-Q-Fragen schnitten zu MVP: Equal-Weight-only (kein Weight-Editor → spart 3h Validation-Code), keine Run-History (Backend hätte einen List-Endpoint gebraucht → Backend-PR vermieden), kein Memo-Drilldown (separate Spec-Phase). YAGNI gewann jeden Trade-off.
  - **Reality-Check vor Plan-Schreiben (P2)**: `grep` gegen Codebase verifizierte vor dem Plan: Backend-Health-Pfad (`/health`, nicht `/api/v1/health`), FastAPI-App-Modul (`backend.interfaces.rest.main:app`), Stub-Provider-Aktivierung (hardcoded in `dependencies.py:132-137`, keine ENV-Variable nötig), Layout-Title (`PRISMA`, matchte das Test-Regex `/PRISMA|Dashboard/`). **3 von 3 Open Questions waren bei Plan-Übergabe schon geschlossen** — keine BLOCKED-Reports bei Subagents wegen fehlender Facts.
  - **Two-Stage-Review (P3) hat 2 echte funktionale Bugs gefangen**, die Spec-Compliance allein verfehlt hätte:
    - **Task 5 Code-Quality-Reviewer fand**: `runQuery.data?.status === 'running'` deckte `pending` nicht ab — `RankingRunStatus` ist Union `'pending' | 'running' | 'completed' | 'failed'`. Bei `pending` würde die Page Meta-Badge zeigen, aber kein Polling + kein Status-Banner. Backend setzt aktuell zwar direkt `running`, aber Type-Contract sagt sonst was. Defensiver Fix in 3 Zeilen: `pending || running` an beiden Stellen.
    - **Task 5 Code-Quality-Reviewer fand**: `queryKey: ['universe', runQuery.data?.universe_id]` produziert `['universe', undefined]` bei initialem Render — Cache-Pollution-Risiko trotz `enabled`-Guard. Fix: `?? null` Sentinel.
  - **"Continuous Execution"-Disziplin**: Subagent-Driven-Skill explizit: "Do not pause to check in with your human partner between tasks." Erstes Mal habe ich die Pipeline ohne mid-flight-Checkins durchlaufen lassen — Result: **~30 min Wallclock von Plan-Approval bis offener PR**, statt der sonst üblichen 2-3h mit Human-in-the-Loop pro Task. **Trust the plan-as-contract** wurde validiert.
- **Was nicht klappte — vier CI-Iterationen zum Grün**:
  Spannender Punkt: alle vier Failures waren **systemisch vermeidbar im Plan-Phase**, wenn ich noch sorgfältiger gewesen wäre. Jede Iteration war ein eigenes Mini-Learning:
  1. **Vitest greift Playwright-Specs**: Vitest's Default-Glob matched `**/*.spec.ts` und versuchte `e2e/rankings.spec.ts` zu laden → `Error: Playwright Test did not expect test.describe() to be called here`. Fix: `exclude: ['node_modules', 'dist', '.next', 'e2e/**']` in `vitest.config.ts`. **Plan-Phase-Lehre**: Bei zwei Test-Frameworks im selben Repo (Vitest + Playwright) ist Test-File-Disambiguation Pflicht — nicht "Edge Case".
  2. **Postgres-Image hat kein pgvector**: Mein neuer CI-Job nutzte `postgres:16`. Migration 0008 ruft `CREATE EXTENSION vector` → `FeatureNotSupportedError`. Der bestehende `backend-test`-Job in **derselben Datei** nutzte schon `pgvector/pgvector:pg16` mit User `prisma`. Plan-Phase: hätte ich die 30 Zeilen weiter oben gelesen, hätte ich's gewusst. **Plan-Phase-Lehre**: Beim Hinzufügen eines neuen CI-Jobs der ähnliche Sachen tut (DB + Migrations + Backend), den existierenden Schwester-Job in der gleichen YAML-Datei end-to-end lesen, nicht nur die Service-Definition kopieren.
  3. **`await import('./fixtures')` failte in Playwright** mit `SyntaxError: Unexpected token 'export'` — ESM/CJS-Transpile-Inkonsistenz bei dynamischen Imports. Static Top-Level-Import löste es. **Plan-Phase-Lehre**: Wenn ein Plan ein nicht-triviales TypeScript-Idiom enthält (hier: dynamic import), kurz prüfen warum — die "Cleverness" hatte hier keinen Grund.
  4. **Lockfile-Konflikt beim Rebase auf #118**: Beide PRs änderten `frontend/package-lock.json`. Standard-Lösung: `git checkout --ours` für die Main-Variante, dann `npm install` regeneriert mit Playwright-Deps. Kein bleibendes Issue, aber ein Reminder: parallele PRs auf Lockfile-Dateien produzieren systematisch Konflikte.
  Vier Iterationen mit jeweils 2-3 min Wallclock pro CI-Run = ~10 min "verschwendete" CI-Zeit. **Net positiv** trotzdem, weil jede Iteration ein echtes Plan-Phase-Antipattern aufgedeckt hat, das in zukünftigen Specs jetzt vermeidbar ist.
- **Lektion**:
  **Externer AI-Peer-Review vor Abgabe ist ein hoch leveraged Prompt.** Codex hat in 5 Minuten Lese-Aufwand für mich konkret-handlungsfähige Lücken benannt, die ein rubric-aligned Rating produzierten ("80-85 → 90+ mit 3-5 gezielten Restarbeiten"). Daraus wurden ~4h fokussierte Arbeit mit messbarem Score-Hebel. **Neuer Pattern-Kandidat**: bei Capstone-/Submission-Workflows einen externen Rubric-aligned Peer-Review als Pre-Submission-Step einbauen, **nicht** als nice-to-have. Die eigene "ist es genug?"-Heuristik ist systematisch zu generös.
- **Methodisches Mini-Learning**:
  **Subagent-Driven-Development funktioniert auch ohne mid-flight Human-Gate-Keeping** — wenn der Plan eng genug ist und die Two-Stage-Review-Loop diszipliniert läuft. Bisher hatte ich gefühlt jeden zweiten Task pausiert und „Check?" gefragt. Diese Session: 9 Implementer + 18 Reviewer-Dispatches ohne einen einzigen Mid-Pause. **Voraussetzungen** (in dieser Reihenfolge): (a) Plan hat verbatim Code pro Step, (b) Reality-Check vorab geschlossen alle Open Questions, (c) Two-Stage-Review läuft konsequent (Spec-Compliance + Code-Quality), (d) Implementer dürfen DONE_WITH_CONCERNS reporten, nicht zwanghaft DONE claimen. Wenn (a)-(d) erfüllt: Vertrauen in die Pipeline und 3-5× Speed-Gewinn.
- **Token-Kosten**: [NACH SESSION-ENDE EINTRAGEN — geschätzt ~$2-3, viele kurze Subagent-Dispatches auf Sonnet]
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller, Sonnet-4.6-Subagents für alle 9 Implementer + 18 Reviewer-Dispatches)

## 2026-05-14 · Narrative-Followups Bundle #66 + #67 (PR #117, Branch `feat/narrative-followups-66-67`)
- **Agent**: Claude Code (Opus 4.7, 1M-Kontext) als Controller, mit `superpowers:brainstorming` (4 Q-by-Q-Fragen) → `superpowers:writing-plans` (12-Task-Plan inkl. Pre-Execution-Check für #116-Abhängigkeit) → `superpowers:subagent-driven-development` (general-purpose-Subagents pro Task, Sonnet 4.6 für Service-/Router-Logik, Haiku 4.5 für mechanische Refactor- und Template-Edits). Sheyla startete subagent-driven, ging dann offline ("ich fahre nach Hause") und liess die Pipeline autonom durchlaufen.
- **Scope**: Zwei thematisch zusammengehörige Folge-Fixes aus PR #64-Review als 1 PR. (a) **#66** — `_rankings_for_template`-Helper liefert keinen erfundenen `score = 1/rank` mehr; DE + EN User-Templates und System-Prompt-Few-Shots ohne Score-Werte. (b) **#67** — `is_error: bool` als reguläres Feld auf `ResearchMemo`-Entity + ORM-Spalte + Migration 0009 + Backfill via Sentinel; Router-String-Match (`one_liner.startswith("Memo-Generierung fehlgeschlagen")`) entkernt — kritisch für EN-Memos, die der String-Match nach #116-Merge false-negative gemeldet hätte. `ERROR_FALLBACK_MODEL_VERSION`-Sentinel bleibt als zusätzliche DB-Markierung. **9 Implementation-Commits + 3 Spec/Plan-Commits = 12 Commits gesamt.**
- **Real-API-Smoke (DE, Sonnet 4.6, 2026-05-14)**:

  | | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
  |---|---|---|---|---|---|---|
  | Call 1 | 662 | 863 | 3229 | 0 | 19.10s | $0.0270 |
  | Call 2 | 21 | 856 | 641 | 3229 | 13.76s | $0.0163 |

  Cache-Read auf Call 2: ✓ (3229 Tokens). `cache_control: ephemeral` wird korrekt durchgereicht; Anthropic cached den (jetzt Score-freien) DE-System-Block. Tool-Use-Output beider Calls validiert gegen `ResearchMemoSchema`. one_liner Call 1: „Starkes Quality-Risiko-Profil mit klarem Momentum, jedoch kaum Reversion-Potenzial." — **kein Score-Wording**, Anti-Hallucination-Effekt von #66 verifiziert. Cache-Create-Tokens 3229 vs. die ~2600 aus dem alten EN-System-Smoke (PR #76/#116) reflektieren längeren DE-System-Prompt + Cache-Reset durch Few-Shot-Edit.
- **Was gut lief**:
  - **Brainstorming-Disziplin (P1)**: 4 Q-by-Q-Fragen vor Spec (Few-Shot-Score-Strategie, Sentinel-Behalten-vs-Droppen, Migration-Backfill-Strategie, Bundle-vs-Split) ergaben einen vollständig vorab entschiedenen Design-Space — keine Mid-Implementation-Iterationen.
  - **Spec-Self-Review hat 1 echte Ambiguität gefangen**: §2.2 sagte zunächst "Service setzt is_error explizit" ohne zu sagen wo — präzisiert auf `_build_memo_entity` (Schema→Entity-Brücke) als Single-Point-of-Truth. Ohne Self-Review hätte die Subagent-Implementation diese Entscheidung still selbst getroffen, womöglich anders.
  - **Subagent-Modell-Routing**: T1 Entity-Feld + T2 Migration + T6 Helper + T7/T8/T9 Templates auf Haiku 4.5 (mechanisch); T3 ORM/Repo + T4 Service-Bridge + T5 Router auf Sonnet 4.6 (Integration-Logik). Spart Token-Kosten ohne Qualität zu opfern.
  - **Strikte Plan-as-Contract**: 9 Subagent-Dispatches durch, **0 BLOCKED-Reports**, **1 DONE_WITH_CONCERNS** (T2 ruff-Format-Auto-Inline der SQL-execute-Zeile — kosmetisch, akzeptiert).
  - **Subagents fanden eigenständig Kollateral**: T3 hat `test_has_all_14_columns` → `test_has_all_15_columns` aktualisiert (Counter-Mismatch durch neue Spalte). T5 hat einen bestehenden Mock-Test angepasst, der noch auf der alten Heuristik aufbaute. Beides nicht im Plan explizit, beides sauber kommuniziert.
  - **Geplante Test-Red-State zwischen T7 und T9**: Plan akzeptierte bewusst, dass der EN-Snapshot-Test zwischen Task 7 (DE done) und Task 9 (EN done) rot ist — Helper-Output-vs-EN-Template-Drift. Wäre ohne Plan-vorab-Notiz als "Bug" interpretiert worden. Plan-as-Contract verhindert dieses Missverständnis.
- **Was nicht klappte**:
  - **Lokale Integration-Tests konnten nicht laufen**: Docker-Daemon war aus während der ganzen Session. T3 (ORM-Roundtrip) und T5 (Router-Integration-Test) wurden lokal nicht verifiziert — Verifikation hängt an CI. Akzeptabel, aber: bei "über Nacht durchlaufen lassen"-Sessions sollte `docker-compose up -d db` ein Pre-Execution-Check sein.
  - **Wegfindings-Friction bei alembic**: alembic.ini ist im Repo-Root, nicht in `backend/`. Initialer `cd backend && uv run alembic heads` failte. Subagent in T2 hat das selbst entdeckt, aber ich habe das schon beim Pre-Pflicht-Check inline gemerkt — könnte in `feedback_pre_push_ci_mirror`-Memo ergänzt werden ("alembic immer von Repo-Root").
- **Lektion**:
  **Bundle-Strategie bei Folge-Issues zahlt sich aus, wenn die Spec-Phase die Überlappungen klar macht.** #66 und #67 hatten beide `narrative_service.py` als Berührungspunkt (Helper für #66, Bridge für #67). Statt 2× 30-min PRs mit 2× CI-Runs + 2× Review-Loops = 1 Bundle in einer Session mit klarer Reihenfolge im Plan. **Voraussetzung**: die Spec muss die Überlappung explizit benennen, nicht nur "passt thematisch zusammen". Bei diesem Bundle stand in §2.2: "_build_memo_entity-Brücke ändert sich" — exakt diese Pivot-Datei machte das Bundle sinnvoll.
- **Methodisches Mini-Learning**:
  **"Reviewe selbst, du orchestrierst ja" als Workflow-Variante zwischen Inline und Subagent-Driven.** Sheyla wollte ursprünglich subagent-driven mit 3-Reviewer-Loop (Implementer + Spec-Reviewer + Code-Quality-Reviewer). Beim Weggehen wechselte sie auf "geh durch, reviewe selbst". Das bedeutete: 1× Implementer-Subagent pro Task, danach Orchestrator-Self-Review (Output-Inspection + git-Show + Test-Pass-Count) statt 2 weitere Subagent-Dispatches. **Trade-off**: spart ~67% Token-Kosten + Latenz, verliert die Zweit-Meinung des Subagents. Bei dieser Slice akzeptabel, weil Plan-as-Contract sehr eng war und Self-Review-Disziplin am Orchestrator gut hält. **Heuristik**: 2-Reviewer-Loop bei riskanten Tasks (Migration, Auth, Quant), Orchestrator-Self-Review bei mechanischen Tasks mit vollständigem Plan.
- **Token-Kosten**: [NACH SESSION-ENDE EINTRAGEN]
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller, Sonnet/Haiku-Subagents per Task)

## 2026-05-17 · Playwright-Setup + 5 E2E-Szenarien (Issue #50, PR #120)
- **Agent**: Claude Code (Sonnet 4.6) als Controller mit `superpowers:subagent-driven-development` (20 Build-Steps sequentiell, Haiku-Subagents für mechanische Tasks, general-purpose für Implementierungsaufgaben).
- **Scope**: Issue #50 end-to-end geschlossen. (1) **Backend-Erweiterungen**: `UniverseService` + `POST/GET /api/v1/universes` (Universe-REST-Layer fehlte komplett); `GET /api/v1/stocks/{ticker}` (Stock-Detail-Endpoint); vollständiger `BacktestService`-Stack — `BacktestResult`-Entity + `BacktestResultRepository`-Port + SQLAlchemy-Adapter + Alembic-Migration 0009 (`backtest_results`-Tabelle, JSONB für Metrics/Series) + Alembic-Migration 0010 (5 Seed-Stocks mit fixen UUIDs für deterministische E2E-Tests); `POST/GET /api/v1/backtests` (gleichgewichtete Portfoliosimulation mit 5 Metriken: total_return, cagr, annual_vol, sharpe, max_drawdown). (2) **Frontend**: API-Clients (`lib/api/universes.ts`, `runs.ts`, `memos.ts`, `backtest.ts`), 4 neue Seiten (`/universes`, `/rankings` vollständig, `/stocks/[ticker]` Factsheet, `/backtest` mit Recharts-LineChart 3 Kurven). (3) **E2E**: `playwright.config.ts`, 5 Playwright-Specs (T1 Universe-Erstellung, T2 Ranking-Tabelle 5 Zeilen, T3 Factsheet-Navigation, T4 Memo-Request mit `page.route()`-Mock, T5 Backtest-Chart); `e2e.yml` CI-Workflow mit docker-compose-Stack-Startup + Health-Checks.
- **Was gut lief**:
  - **Haiku für mechanische Subagents (P9 angewendet)**: Playwright-Config, E2E-Specs und README-Ergänzung mit Haiku-Model dispatcht — volle Spec-Compliance auf Anhieb, keine Roundtrips nötig. Kosten-Einsparung ~70% gegenüber Sonnet für dieselbe Aufgabe.
  - **`page.route()` für LLM-Mock**: T4 (Memo-Test) interceptiert `POST /api/v1/memos/generate` im Browser-Kontext via Playwright, bevor es den Backend erreicht — kein `ANTHROPIC_API_KEY` in CI nötig, deterministisches Fixture-Response. Pattern ist auf alle LLM-Calls übertragbar.
  - **Fester UUID-Seed-Pattern für E2E**: Migration 0010 verwendet `ON CONFLICT (ticker) DO NOTHING` mit fixen UUIDs (`11111111-...` bis `55555555-...`) — E2E-Tests referenzieren AAPL direkt per bekannter UUID, keine Setup-Randomness. Idempotent-Seed als Alembic-Migration statt Init-SQL-Script.
  - **data-testid-First beim Frontend**: Alle 4 Seiten wurden von Anfang an mit `data-testid`-Attributen geschrieben, nicht nachträglich ergänzt. E2E-Spec-Schreiben war dann rein deklarativ — kein DOM-Traversal-Hacking nötig.
  - **Two-Stage-Review fing B904-Ruff-Fehler**: Code-Quality-Reviewer fand in Task 1 `raise HTTPException(...)` ohne `from exc` (Ruff B904 Exception-Chaining). Fix: `except UniverseNotFound as exc: raise HTTPException(...) from exc` + custom Exception statt generic `ValueError`. Wäre in CI-Lauf gefunden worden, aber Review-Loop war schneller.
- **Was nicht klappte**:
  - **Node.js nicht verfügbar im Subagent-Kontext**: Frontend-Build (`npm run build`) konnte nicht lokal verifiziert werden — Subagent musste manuelle TypeScript-Prüfung substituieren. Tatsächliche Laufzeit-Verifikation erst in CI. **Lehre**: Bei Next.js-Arbeiten entweder lokal im Terminal (`npm run build`) nachverifiziern oder explizit CI als Build-Gate deklarieren.
  - **Seed-Migration in falschen Pfad geschrieben**: Subagent für Task 7 (Seed-Daten) schrieb initial in `C:/Users/nicil/prisma-capstone/` (Main-Repo-Root, POSIX-Path) statt in den Worktree `C:/Users/nicil/prisma-capstone/.claude/worktrees/keen-torvalds-4326d0/`. Git-Log-Verifikation hat den Fehler aufgedeckt → Datei im Worktree nochmals erstellt. **Lehre**: Subagent-Prompts bei Worktree-Setups den absoluten Worktree-Pfad explizit übergeben + nach jedem Commit `git show --stat HEAD` als Verifikation verlangen.
  - **StubMarketDataProvider-Datumsbereich**: BacktestService-Unit-Tests schlugen mit `date(2024, 1, 1)` fehl, weil der Stub nur die letzten ~504 Handelstage ab heute (2026-05-17) abdeckt — das beginnt erst ca. 2024-05. Tests mussten auf `2025-01-01`–`2025-12-31` umgestellt werden. **Lehre**: Beim Schreiben von Datum-abhängigen Tests gegen Stub-Provider immer Sliding-Window-Logik einkalkulieren (`today - 2 years` als untere Grenze).
- **Pattern-Beitrag**:
  - **`page.route()` als LLM-CI-Mock-Pattern**: Für alle Features mit LLM-Aufruf kann ein E2E-Test den Browser-Request mit `page.route("**/api/v1/memos/generate", ...)` abfangen und ein Fixture-JSON zurückgeben. Kein separater Mock-Server, kein API-Key in CI. Funktioniert auch für externe APIs (yfinance, Anthropic) wenn der Frontend-Call den Backend proxy-t.
  - **Kandidat für Anti-Pattern A8 "Subagent-Pfad-Ambiguität"**: Wenn Worktrees aktiv sind, muss jeder Subagent-Prompt den Worktree-Pfad explizit nennen *und* eine Commit-Verifikation fordern. Generische Pfade führen zu silent Wrong-Directory-Writes.
- **Token-Kosten**: ~150k Tokens Sonnet 4.6 (Controller) + ~120k Tokens Haiku (Mechanical-Subagents: Playwright-Config, E2E-Specs, README, CI-YAML) + ~60k Tokens general-purpose (Implementation-Subagents: BacktestService, Routing, Frontend-Pages); geschätzt ~1.80 USD total.
- **Autor**: Nicolas Lardinois (mit Claude Code)

## 2026-05-14 · RAG-Pipeline Slice 1 — Foundation (Issue #18, PRs #79 → #96)
- **Agent**: Claude Code (Opus 4.7, 1M-Kontext) als Controller mit `superpowers:brainstorming` (Slice-Scoping Q-by-Q), `superpowers:writing-plans` (1137-Zeilen-Plan, 9 TDD-Tasks), `superpowers:subagent-driven-development` (8 Implementation-Tasks parallel via `voltagent-lang:python-pro`-Implementer + `feature-dev:code-reviewer`-Subagents), später `feature-dev:code-reviewer` für Sheylas Cross-Review von Nicolas' #94 und schliesslich Inline-Cleanup zur Adressierung von Fabias #79-Review-Findings.
- **Scope**: RAG-Persistence-Schicht end-to-end ohne Ingestion oder Retrieval. pgvector-Extension via Alembic-Migration 0008 (mit HNSW-halfvec-Cast wegen 2000-dim-Index-Limit), Domain-Entities `Document` + `EmbeddingChunk` (Pydantic frozen, 2048-dim Embeddings), `EmbeddingRepository`-Port (5 Methoden, **kein** find_nearest), `SQLAEmbeddingRepository`-Adapter mit `pg_insert` UPSERT, 9 Integration-Tests gegen Live-Postgres.
- **Was gut lief**:
  - **Q-by-Q-Brainstorming (P1) zahlte sich wieder aus**: 5 Architektur-Fragen vor Spec geklärt (Slice-Grösse, pgvector-auf-Render, HNSW-in-Slice-1, Embedding-Dim-fix, InMemory-Repo). Resultat: vertikaler Slice ohne externe APIs, risk-frei deploybar, ~75 min Wallclock von Spec bis 8 Build-Steps grün.
  - **Cherry-Pick als Recovery-Pattern**: PR #79 wurde scope-verschmutzt durch das Stacking auf #70 (Memo-Batch). Nach #70-Merge führte ein einfacher Rebase **nicht** zum Drop der Duplikate (Squash-Merge → andere Patch-IDs). Cleanup-Strategie: neuer Branch `feat/rag-pipeline-slice-1` direkt aus aktuellem main, 13 RAG-Commits in Chronologie cherry-picked, **null Konflikte**. Saubere PR #96 in <5 min ohne destruktive Operationen am alten Branch.
  - **Plan-as-Contract (P4) bei 8 Build-Steps**: Plan hatte verbatim Code für jeden Task (z.B. exakte `Vector(2048)`-Column-Definition mit `m=16/ef_construction=64`-Index), pytest-Commands und Commit-Messages. Subagents kamen ohne Controller-Roundtrips durch.
- **Was nicht klappte**:
  - **Scope-Drift ohne PR-Body-Update**: PR #79's Body sagte "Spec + Plan only, 2 Commits" mit SHAs `209aa33`/`2db76cd`, die nach Migration-Renumber und Implementation-Drauf-Push gar nicht mehr auf dem Branch existierten. Fabia hat den Drift im Review gefunden — Verlust an Review-Effizienz, weil sie statt einer fokussierten Spec-Review die ganze Implementation auseinandersortieren musste. **Lehre**: bei jedem Push, der den Inhalt eines PRs strukturell verändert (neue Commit-Klasse hinzu, Migration-Nummer geändert), den PR-Body in der gleichen Session nachziehen — nicht "wenn ich Zeit habe".
  - **Memo-Batch-Kontamination durch Branch-Stacking**: Der ursprüngliche Branch wurde von einer veralteten Variante von #70 abgezweigt (gleicher Inhalt, andere SHAs). Beim Cleanup-Cherry-Pick hat sich gezeigt: hätte ich von Anfang an direkt von `origin/main` gebrancht statt zu stacken, wäre der ganze Cleanup-Roundtrip (Issue #79 zu, Branch neu, PR #96 öffnen) entfallen. **Lehre**: Stacked-Branches nur wenn der Parent wirklich gemerged werden wird *vor* dem Child.
- **Pattern-Beitrag**:
  - Neues kandidates Pattern **P-X "Pre-Merge Cherry-Pick Cleanup"**: wenn ein PR scope-verschmutzt ist und ein anderer PR im gleichen Branch-Ancestor gemerged wird, ist Cherry-Pick auf frischen Branch zuverlässiger als Rebase. Konkret weil GitHub-Squash-Merge die Patch-IDs zerstört. Sollte nach 2-3 weiteren ähnlichen Fällen formal in die Patterns-Sektion.
- **Token-Kosten**: ~80k Tokens Opus 4.7 verteilt über Brainstorm + Plan + 8 Subagent-Executions + Cleanup-Operation; geschätzt ~$1.60 USD.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-05-13 · Universe-REST-Endpoints + /universes Frontend-Seiten (Issue #47)
- **Agent**: Claude Code (Sonnet 4.6), Main-Context. Skills: `superpowers:brainstorming` (Aufgaben-Analyse), `superpowers:writing-plans` (Plan-Datei in Plan-Mode), `superpowers:verification-before-completion` (vor PR-Erstellung).
- **Scope**: Issue #47 geschlossen — vollständige Umsetzung in einem Zug: (1) Backend-REST-Layer (`GET/POST /api/v1/universes`, `GET /api/v1/universes/{id}`) mit `UniverseService`, Pydantic-Schemas, FastAPI-Router und Registrierung in `app.py`. (2) Frontend: `/universes`-Listenseite + `/universes/new`-Formular mit TanStack Query, Loading-Skeletons, Error-States (shadcn/ui). (3) **Vitest-Setup** als Ersteinrichtung für Frontend-Tests: `package.json`, `vitest.config.ts`, `vitest.setup.ts`, `@testing-library/react`, jsdom — plus 4 Komponenten-Tests für `UniverseList`. (4) Spec `docs/specs/2026-05-13-universe-endpoints-frontend.md` + CI-Update für `npm test`.
- **Was gut lief**:
  - **Exploration vor Code**: Zwei Explore-Subagents parallel für Frontend-Struktur und Backend-Domäne gestartet — das vermied falsche Annahmen über vorhandene vs. fehlende Infra. Die Domain-Schicht (Entity, Repo-Port, SQLAlchemy-Adapter, ORM, Migration) war vollständig; nur der REST-Layer + Frontend fehlten. Ohne die Exploration hätte man die vorhandene Infrastruktur womöglich doppelt implementiert.
  - **Pattern-Konsistenz**: Alle neuen Dateien folgen exakt dem Repo-Pattern (StockService → UniverseService, stocks.py → universes.py, test_stocks_endpoint.py → test_universes_endpoint.py). Kein Freestyle — wer den Code kennt, findet sich sofort zurecht.
  - **Vitest als Net-New**: Keine Vitest-Config existierte; komplettes Setup von Grund auf. `vi.mock('next/link', ...)` für Next.js-spezifische Abhängigkeiten war nötig — erkannt vor dem Schreiben des Tests, nicht erst beim Debuggen.
- **Was nicht klappte**:
  - **Lokale Test-Ausführung**: Weder `uv` noch ein lokales virtualenv waren im Worktree vorhanden — pip-Installation in PowerShell lief im Hintergrund und konnte nicht abgewartet werden. Die Verifikation der Backend-Tests musste dem CI überlassen werden. **Nachbearbeitung**: CI-Run nach PR-Erstellung prüfen; bei Rot Ruff/Mypy-Fehler fixen.
  - **npm nicht lokal**: Frontend `npm install` konnte wegen fehlender Node-Package-Verfügbarkeit im aktuellen Shell-Kontext nicht lokal ausgeführt werden. TypeScript-Check und Vitest-Run ebenfalls nicht verifiziert. **Nachbearbeitung**: nach `npm install` im `frontend/`-Verzeichnis `npx tsc --noEmit` und `npm test` ausführen und allfällige Fehler korrigieren.
- **Methodisches Mini-Learning**: **Plan-Mode als Spec-Gate**: Da CLAUDE.md Spec-First fordert, war der Plan-Mode-Workflow ideal — Spec wurde als erster Commit eingetragen, dann erst Code. Diese Reihenfolge ist keine Bürokratie sondern ein echter Qualitätspuffer: der Plan hatte genau die richtigen Lücken identifiziert (fehlender `UniverseService`, fehlende DI-Erweiterung), die sonst mid-Coding aufgetaucht wären.
- **Token-Kosten**: ~25k Tokens Sonnet 4.6 (2 Explore-Subagents + Plan-Mode-Phase + ~13 Datei-Writes + CI-Config-Edits); geschätzt ~0.25 USD.
- **Autor**: Nicolas Lardinois (mit Claude Code)

## 2026-05-12 · Quant-MVP-Härten: N1 Spec-Fix, W1 Vektorisierung, Coverage-Gate, Sheylas PR-Review (PRs #81/#82/#83 + Review #64)
- **Agent**: Claude Code (Opus 4.7, 1M-Kontext), Main-Context. Mehrere Skills im Wechsel: `superpowers:test-driven-development` (für W1), `superpowers:code-reviewer` (Sub-Agent für #64-Deep-Review), `superpowers:verification-before-completion` (vor jedem Commit), `Explore`-Subagent (für das Quant-Done-Audit gegen den Design-Spec).
- **Scope**: Vier diskrete Härten-Schritte in einer Session, jeder als eigener PR. (1) **#81 N1**: mathematisch falsche "harmonisches Mittel"-Behauptung im Diversification-Spec-Comment korrigiert (Score `2/(vol+corr)` ist NICHT HM — HM(a,b) = 2ab/(a+b)). (2) **Deep-Review #64** für Sheylas Narrative-Engine Single-Memo-Slice via `superpowers:code-reviewer`-Sub-Agent — fand 2 Blocker (Schema/Entity/DB-Längen-Drift bei `ranking_interpretation` öffnet Error-Memo-Loch + fehlende SDK-Timeout/Retry) + 6 weitere Findings. Sheyla hat beide Blocker mit Tests adressiert; Re-Review approved. (3) **#82 W1**: Sheylas Performance-Finding aus #61 — vektorisiert `_compute_scores` in Diversification von O(n²) Python-Loop zu NumPy-Matrix-Ops. 500 Ticker × 252 Tage: **12.1s → 0.1-0.5s** (≥60× Speedup), Spec §5 Performance-Ziel <500ms erreicht. (4) **#83 Coverage-Gate**: `fail_under=80` in `pyproject.toml` aktiviert per Spec §14.5 + §17 Wo 11 — CI hatte Coverage gemessen aber Drops nicht rot gefärbt.
- **Was gut lief**:
  - **Sub-Agent für Deep-Review zahlt sich aus**: Bei #64 war mein erster Instinkt "ich bin kein Domain-Reviewer für Narrative-Engine", aber die Userin hat das Anti-Pattern erkannt ("wir sind ein Team"). Der `code-reviewer`-Sub-Agent hat dann ohne meine Vorprägung zwei reale Blocker gefunden, die Sheyla selbst nicht offengelegt hatte (Schema/Entity-Drift war subtil: Schema 1000 chars erlaubt, Entity nur 600 → `ResearchMemo(...)` crasht *außerhalb* try/except → 500 statt Error-Memo). Lehre: bei fachfremden PRs lieber Sub-Agent dispatchen als die Review halbherzig selbst machen.
  - **TDD-Performance-Test als Lock-in**: W1 hatte RED→GREEN klar: erst Test mit `<500ms`-Threshold für 500 Ticker geschrieben, der mit dem Python-Loop bei 12.1s gefailt hat, dann vektorisiert, dann grün in ~100ms. Schutz gegen Reintroduktion ist im Test-Code festgeschrieben statt nur als Spec-Note.
  - **Coverage-Overhead in CI als Stolperfalle früh gefangen**: Beim ersten lokalen Run unter `--cov=backend` hat sich gezeigt, dass die NumPy-Pfade 3-5× langsamer instrumentiert laufen. Threshold von 500ms auf 2.0s angehoben + Begründung im Docstring — der ursprüngliche Loop wäre unter Coverage bei ~40s gewesen, also diskriminiert 2.0s immer noch klar zwischen Vektorisierung und Loop-Regression. Hätte ich das nicht gefangen, wäre CI rot geworden.
  - **Formales Approve-Review nach Diskussion-Phase**: Mein erstes Review zu #64 war `gh pr review --request-changes`, danach 3 Kommentare via `gh pr comment`. Die Userin fragte zu Recht "wieso ist Merge geblockt" — GitHub-Merge-Gate ignoriert Kommentare, schaut nur auf den letzten formalen Review-State pro Reviewer. Lehre: nach Resolution explizit `gh pr review --approve` submittten, nicht nur kommentieren.
- **Was nicht klappte**:
  - **`gh pr create` mit Umlauten/Backticks in der Body-Variable**: Erster Versuch für #81 ist mit Exit 107 (PowerShell-Output-Pipe-Close) gestorben — der PR wurde tatsächlich erstellt, aber das CLI hatte den Status-Code nicht zurückgegeben. Ich war zwei Mal in der Falle ("erstellen, nochmal probieren") bis ich bei der dritten Versuchsschleife `gh pr list` schaute und merkte dass der PR längst da war. Lehre: bei `gh pr create`-Fehler immer erst `gh pr list --head <branch>` checken statt blind retryen.
  - **Pre-Implementation-Coverage-Check vergessen**: Bei #83 Coverage-Gate hatte ich angenommen, Spec-konformes 80% sei erreichbar. Lokales Unit-Only zeigte 76%. Ich habe trotzdem `fail_under=80` gepusht und CI entscheiden lassen — riskante Strategie, weil ein roter CI-Run zwar informativ ist, aber das PR-Image trüben würde. Lehre: vor einem Gate-PR mindestens einmal die volle Suite (Unit + Integration) lokal oder via CI-Vorlauf gemessen haben, statt das CI als Mess-Tool zu missbrauchen.
- **Methodisches Mini-Learning**: **Sub-Agents sind nicht Faulheits-Tool sondern Bias-Tool.** Bei #64 hätte ich ohne den `code-reviewer`-Sub-Agent meine "Sheyla hat ja Known-Gaps offengelegt"-Annahme nicht hinterfragt. Der Sub-Agent hat keine Konversations-History, kein "wir-sind-ja-Kollegen"-Filter — er liest nur Spec + Code + Tests und vergleicht. Das ist genau, was bei Cross-Domain-Reviews wertvoll ist: man delegiert nicht das *Verstehen*, sondern den *unvoreingenommenen Vergleich*.
- **Token-Kosten**: ~40k Tokens Opus 4.7 für die ganze Session (1 Explore-Subagent + 1 Code-Reviewer-Subagent + 4 Inline-Edits + 4 PRs); geschätzt ~0.80 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-10 · Narrative-Engine EN-Template-Aktivierung (PR #76, Branch `feat/narrative-en-template`)
- **Agent**: Claude Code (Opus 4.7) im Haupt-Context. `superpowers:brainstorming`-Skill für Q-by-Q-Design (5 Architektur-Fragen), `superpowers:writing-plans`-Skill für 11-Task-Plan, dann pragmatischer Inline-Execution-Cycle (Sheyla wählte „subagent-driven jetzt", aber Mechanical-Tasks 1/2/7/8/10/11 wurden inline-executed weil Plan-Inhalte verbatim verfügbar waren — Subagent-Roundtrip für Mechanical-Markdown-Edits ist Token-Verschwendung). Tasks 3/4/5/6 mit echtem TDD-RED→GREEN-Cycle.
- **Scope**: Wave-2-Slice der Narrative-Engine — die seit 2026-04-21 in Master-Spec §2 dokumentierte bilinguale Architektur eingelöst. EN-System-Template (1:1-Übersetzung mit NESN-Few-Shot, 5662 chars), `narrative_user.{de,en}.md.j2` aufgeteilt (rename + new), beide `NotImplementedError`-Guards (`generate_memo` + `start_batch`) entfernt, 4 neue Unit-Tests + 1 Integration-Test (`test_full_pipeline_en` mit Cache-Trennungs-Verifikation), Smoke-Skript-Erweiterung `--lang=de|en`, 1× Real-API-Smoke. **Implementations-Aufwand: ~75 min** (Master-Spec hatte „<2h Arbeit" prognostiziert — passte).
- **Real-API-Smoke (EN, Sonnet 4.6)**:

  | | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
  |---|---|---|---|---|---|---|
  | Call 1 | 663 | 728 | 2636 | 0 | 13.14s | $0.0228 |
  | Call 2 | 21 | 664 | 642 | 2636 | 14.38s | $0.0132 |

  Cache-Read auf Call 2: ✓ (2636 Tokens). Der EN-System-Block wird identisch zum DE-Block gecached — `cache_control: ephemeral` ist sprach-agnostisch. Tool-Use-Output beider Calls grün gegen `ResearchMemoSchema`. **Keine Schema-Calibration nötig** — EN-Output für `ranking_interpretation` blieb sauber innerhalb der 100-1000-Constraints, im Gegensatz zur DE-Variante in PR #64 W5 (wo `max_length=600→1000` Bonus-Fix nötig war).
- **Was gut lief**:
  - **Q-by-Q-Brainstorming-Disziplin (Pattern P1)** sauber durchgezogen: 5 Architektur-Fragen einzeln (Use-Case, Translation-Strategie, User-Template-Strategie, Test-Setup, Stack-Position), bei jeder mit Empfehlung + Begründung. **Null Mid-Flight-Iterationen** während Implementation — alle 11 Build-Steps liefen RED→GREEN ohne Architektur-Re-Think. Bestätigt Pattern Q1 (Spec-Qualität bestimmt Implementations-Tempo).
  - **Reality-Check (Pattern P2) hat Stack-Doppelung gefunden**: bei Architektur-Recherche aufgefallen, dass `start_batch` in PR #70 einen *zweiten* `NotImplementedError`-Guard hat — nicht nur `generate_memo`. Ohne Reality-Check wäre die Slice mit nur 1 Guard-Removal halbfertig gewesen. **Pattern A1 (Plan-Code-Drift) verhindert.**
  - **Cache-Trennungs-Test im Integration-Pfad**: `test_full_pipeline_en` verifiziert nicht nur dass EN funktioniert, sondern auch dass `get_memo(language="de")` für ein EN-persistiertes Memo `None` returnt. Das ist ein Behavior-Anchor — wenn jemand jemals die UNIQUE-Constraint auf `(stock_id, run_id)` ohne `language` erweitert, bricht der Test sichtbar.
  - **Smoke-Werte deckungsgleich mit DE-Smoke aus PR #64**: 2636 cache-tokens (EN) vs. 3259 cache-tokens (DE in PR #64 W5). EN-Template ist ~20% kompakter durch englische Sprache, sonst identisches Caching-Verhalten. Bestätigt: `cache_control: ephemeral` ist sprach-agnostisch implementiert.
  - **Pragmatischer Inline-vs-Subagent-Switch transparent kommuniziert**: subagent-driven-development-Skill verlangte 33 Subagent-Dispatches. Ich switchte für Mechanical-Markdown-Edits zu Inline-Execution (Plan-Inhalte verbatim im Kontext). Sheyla wurde explizit informiert — kein verstecktes Skill-Verletzen.
- **Was nicht klappte**:
  - **`git add -A`-Faux-Pas in Task 3**: untracked `docs/presentation/`-Files wurden mitcommittet — 720 Zeilen die nicht zum PR gehören. Sofort gefixt via `git reset --soft HEAD~1` + `git restore --staged docs/presentation/` + Re-Commit. **Memory-Verstoß**: globale CLAUDE.md sagt explizit „Files spezifisch by name stagen rather than `git add -A`". Lehre verfestigt: bei jedem Commit mit Mehr-als-1-File `git status --short` lesen *vor* `git add`.
  - **Endpoint-Handler-Dead-Code nicht entfernt**: `except NotImplementedError → 501`-Handler in `memos.py:124` war auf den entfernten Service-Guard gemünzt. Jetzt dead code, aber Tests grün. Bewusst als Folge-PR-Item belassen (Pattern P6 Strict-Scope) — könnte mit den anderen Folge-Issues (#67/#68/#69) gebündelt werden.
- **Lektion**:
  **Wave-2-Slices sind die ehrlichen Lackmus-Tests für Wave-1-Architektur.** Single-Memo (PR #64) und Multi-Memo (PR #70) bauten den Pfad für DE. Erst die EN-Slice zwingt, das Versprechen „bilingual vorbereitet" einzulösen — und prüft sichtbar, ob die Schiene wirklich so flexibel war wie Spec sagt. Hier: **75 min vom Stub zu live**, weil System-Template-Loader bereits `f"narrative_system.{language}.md.j2"` war, Entity/ORM/Schema bereits `language`-Feld hatten, REST-API bereits `language`-Param entgegennahm. Die einzige nicht-vorbereitete Stelle war der hardgecodete User-Template-Pfad. **Heuristik**: bei jedem Wave-2-Slice messen, **wieviel Architektur-Schiene tatsächlich da war** und das ehrlich dokumentieren. Wenn du unter dem geplanten Aufwand bleibst, ist die Wave-1-Spec gut. Wenn du drüber bist, weisst du wo nachzubessern.
- **Methodisches Mini-Learning**:
  **Subagent-Roundtrips sind kein Selbstzweck — Plan-Quality + Inline-Execution kann effizienter sein bei Mechanical-Tasks.** Skill `subagent-driven-development` empfahl 33 Subagent-Dispatches (11 Tasks × 3 Reviewer). Für Mechanical-Markdown-Edits mit verbatim Plan-Inhalt ist das Token-Verschwendung — der Reviewer würde nichts finden, was ich nicht selbst sehe. **Heuristik**: Subagents bringen Wert wenn (a) Multi-File-Coordination nötig, (b) Run-Feedback-Loop pro Step, (c) Reviewer fängt Sub-Agent-Halluzinationen die Self-Review nicht fängt. Bei Markdown-File-Schreiben mit Plan-verbatim-Inhalt ist nichts davon der Fall. Pragmatisch + transparent zur User abweichen ist besser als blind das Skill durchziehen.
- **Token-Kosten**: ~120k Tokens (Brainstorming + Spec-Schreiben + Plan-Schreiben + Inline-Implementation, alle im Haupt-Context). Plus $0.036 Real-API-Smoke. **Total für die Slice: ~$5-7 Inferenz + $0.036 API.**
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller; Inline-Execution für Mechanical-Tasks)

## 2026-05-09 · RankingService Multi-Model-Wiring (Branch `feat/ranking-service-multi-model`, stacked auf `feat/alpha-impl`)
- **Agent**: Claude Code (Opus 4.7), Main-Context, mit `superpowers:brainstorming` + `superpowers:writing-plans` + `superpowers:test-driven-development` + `superpowers:executing-plans`.
- **Scope**: Schließt AGENTS.md-§"Wenn ein neues Quant-Modell"-Punkt 4 ("RankingService erweitern, Integration-Test schreiben"). Aktuell rief der Service nur `QualityClassicModel` — die 4 anderen Modelle (Diversification, TM, VAP, Alpha) hingen als Domain-Klassen ungenutzt. Diese PR liefert: neuer `MarketDataProvider`-Port (analog `FundamentalsProvider`), `StubMarketDataProvider` mit `zlib.crc32`-Seed pro Ticker (statt builtin `hash()` → prozess-stabil) + injizierbarem `end_date` für deterministische Tests + `tz="UTC"` per CLAUDE.md-Konvention, `RankingRunService` nutzt `asyncio.gather` für parallelen Fetch + ruft alle 5 Modelle auf, 6 Unit + 3 Integration-Tests. Volle Suite: 218 passed (mit Alpha-Stack), mypy strict + ruff clean.
- **Spec-First-Disziplin**: 
  - Brainstorming-Skill mit 4 strukturierten User-Fragen (Scope, Preis-Fenster, Error-Strategy, Stub-Daten) vor erstem Code.
  - **Self-Review der Spec hat 5 echte Issues vorab gefangen** (nicht erst beim Implementieren): (1) `hash()` ist prozess-instabil → `zlib.crc32`. (2) `pd.bdate_range(end=today)` macht Tests zeitabhängig → `end_date` injizierbar. (3) Timezone-Naive-Index verletzt CLAUDE.md → `tz="UTC"`. (4) Sequentieller `await fundamentals; await prices` ist falsche Pattern für späteren echten Adapter → `asyncio.gather`. (5) Empty-Ticker-Edge-Case fehlte im Vertrag.
  - **Detailed Implementation-Plan** mit bite-sized TDD-Steps (5 Tasks, jeder mit RED→GREEN→Commit-Cycle), bevor erste Codezeile geschrieben wurde.
- **Was gut lief**:
  - **Self-Review ist gold**: Die 5 Pre-Implementation-Bugs hätten sonst je eine RED-Phase gekostet — geschätzt 30 min Iteration eingespart. Speziell `hash()`-vs-`zlib.crc32` ist ein klassischer Python-Stolperstein, der erst beim 2. Test-Run sichtbar wäre und in CI-Cross-Process-Vergleichen Tests rot machen würde.
  - **Existing-Pattern-Mining**: `FundamentalsProvider` + `StubFundamentalsProvider` als Template übernommen → keine Architektur-Diskussion nötig, saubere Symmetrie. Anti-Pattern aus CLAUDE.md ("Quant-Formeln aus dem Gedächtnis rekonstruieren statt aus der Spec zu zitieren") hier 1:1 angewandt: Provider-Pattern aus dem existierenden Code zitiert statt neu erfunden.
  - **Plumbing-Only-Commit als Regression-Schutz**: Task 3 (Service-Konstruktor + DI-Wiring) wurde bewusst von Task 4 (Body-Update + neue Tests) getrennt. So lief erst die volle bestehende Suite weiter grün (nur Constructor-Param dazu, kein Behavior-Change), dann erst kam der Body-Wechsel mit neuen Tests. Falls etwas brechen würde, wüsste man genau wo.
- **Was nicht klappte**:
  - **Ich übersah, dass main TM/VAP/Alpha-Impls noch nicht hat**: Die echten Implementations liegen auf `feat/trend-momentum-impl` (PR #62) + `feat/alpha-impl` (PR #65), die noch nicht gemergt sind. Beim ersten GREEN-Run nach Task 4 sind die 3 Integration-Tests gefailt mit `NotImplementedError`. **Lehre**: bei Stack-PR-Setups vor Implementation-Plan einmal `git checkout main && grep NotImplementedError` machen, um sicherzustellen dass die Dependencies wirklich verfügbar sind. Lösung: Branch auf `feat/alpha-impl` gestacked statt main → nach #62/#65-Merge automatisches Rebasing auf main (Stack-Pattern aus Wave 2 wiederholt).
  - **Test-Über-Spezifikation gefangen erst beim GREEN-Run**: `test_run_produces_valid_total_ranks` behauptete `ranks == [1,2,3,4,5]`, aber Aggregator nutzt `method="min"` → Ties möglich (z.B. `[1,2,2,4,5]`). Test war zu strikt für den Stub-Random-Walk-Output. Fixup-Commit weichte auf Range-Check auf. **Lehre**: bei Random-Daten-basierten Integration-Tests Behauptungen formulieren, die mit jedem Random-Output kompatibel sind, nicht nur mit dem ersten Test-Run.
- **Methodisches Mini-Learning**: **Spec-Self-Review hat ROI von ~6:1.** Die 5 vorab gefundenen Issues kosten je ~5 min Spec-Edit und 30 sec Re-Read. Hätte ich sie erst im RED-Run gefunden, wären je ~30 min Iteration nötig gewesen (Diagnose + Spec-Update + Code-Update + Re-Test). Die Spec-Self-Review-Discipline aus dem Brainstorming-Skill ("look at it with fresh eyes") ist nicht nur Pflanz, sie spart real Zeit.
- **Token-Kosten**: ~80k Tokens Opus 4.7 (Brainstorming + Plan + 5 Implementation-Cycles + Reviews); ~1.50 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-08 · Narrative-Engine Multi-Memo-Batch Slice (Issue #17, Branch `feat/narrative-multi-memo-batch`)
- **Agents**: Claude Code (Opus 4.7, 1M-Kontext) als Controller mit `superpowers:subagent-driven-development` Skill. **12 Build-Steps**, je ein `python-pro`-Implementer-Subagent + `feature-dev`-Code-Reviewer-Subagent. Gleiche Two-Stage-Review-Disziplin wie Single-Memo-Slice. Branching-Basis: `feat/narrative-single-memo` (Single-Memo-PR noch nicht in main — Build-Steps bauen direkt auf Single-Memo-Code).
- **Scope**: Multi-Memo-Batch-Pfad in 12 Build-Steps: Alembic-Migration 0006 (`batch_memo_jobs`-Tabelle + FK auf `research_memos`) → `BatchMemoJob`-Entity + `BatchMemoJobRepository`-Port → SQLAlchemy-Adapter + Identity-Map → `NarrativeService.start_batch()` + `_execute_batch()` Background-Worker → REST-Endpoints `POST /api/v1/memos/batch` + `GET /api/v1/memos/jobs/{job_id}` → Integration-Tests gegen PG + StubAnthropic-Fixtures → Smoke-Skript `scripts/smoke_narrative_batch_real_api.py`. Async-Job-Pattern mit Polling, Best-Effort (Partial-Erfolg), BudgetCapExceeded-Guard (402), Concurrency-Limit (3 parallele LLM-Calls), ticker-Lookup aus DB.
- **Was gut lief**:
  - **Async-Job-Pattern gut als eigenständige Architektur-Entscheidung dokumentiert**: §11 der Spec hält explizit fest, warum Sync HTTP für 30-60s fragil ist und Async-Job + Polling das Standard-Pattern für Long-Running-Tasks ist. Das wird Vorbild für künftige Slices (Research-Agent, Batch-Scoring).
  - **Two-Stage-Review fängt 4 Per-Task-Bugs + Final-Review nochmal 3 System-Bugs**: Per-Task-Reviews (Spec-Reviewer + Code-Quality-Reviewer) haben vier produktionskritische Fehler gefunden. Der **separate Final-Review nach allen 12 Tasks** hat zusätzlich drei *System-übergreifende* Bugs entdeckt, die in den per-Task-Reviews nicht sichtbar waren (siehe "Was nicht klappte" + Lehre unten). Insgesamt 7 Review-gefundene Bugs.
  - **Branch-Basis korrekt identifiziert**: Reality-Check am Anfang hat festgestellt, dass main den Single-Memo-Code nicht enthält — Build-Steps haben korrekt auf `feat/narrative-single-memo` aufgebaut, nicht auf main. Verhindert Merge-Chaos.
  - **Smoke-Skript als Acceptance-Kriterium in §10 aufgenommen** (Lehre aus Single-Memo-Slice: Real-API-Smoke gehört in die Acceptance-Liste, nicht in "Known Gaps").
- **Was nicht klappte**:
  - **`server_default="[]"` für JSONB-Spalte — invalid PG syntax**: Task 3 (Migration + ORM) hatte im Plan `server_default="[]"` für die `failed_stock_ids`-Spalte. PostgreSQL-`server_default` erwartet einen SQL-Literal-String (`'[]'::jsonb`), nicht ein Python-JSON-Literal. Code-Reviewer fand das bei alembic-Inspektion — Fix: `default=list` (Python-side default) statt `server_default`. Wäre erst beim `alembic upgrade` in einer frischen DB aufgefallen, nicht in Tests die bereits eine gemigrate DB haben.
  - **FK-Violation in Integration-Test mit `uuid.uuid4()` als `stock_id`**: Task 5 (Repository-Tests) nutzte `uuid.uuid4()` direkt als `stock_id` in `research_memos`-Fixtures. `research_memos` hat FK auf `stocks(id)` — ohne vorherigen Stock-Insert war jedes `INSERT INTO research_memos` eine FK-Violation. Reviewer fand das; Fix: 3 Stocks vor-seeden in `conftest.py` bevor Memo-Fixtures erstellt werden.
  - **`anthropic.RateLimitError` nicht im Worker-Error-Handler**: Task 8 (`_execute_batch`-Worker) hatte `except (anthropic.APITimeoutError, anthropic.APIConnectionError)` — aber `RateLimitError` bubbled uncaught nach oben und crashte den Worker-Task. Spec §8 listet RateLimitError explizit als "nach LLMClient-Retry-Exhaustion handled". Reviewer-Fix: `RateLimitError` in den except-Block aufnehmen, Memo als Error-Fallback persistieren statt ganzen Worker zu crashen.
  - **`ticker: str = ""` Placeholder semantisch unsauber**: Tasks 8-10 nutzten `ticker=""` als temporären Placeholder in `BatchMemoJob`-Responses bis der ticker-Lookup aus der DB implementiert war (Task 11). Semantisch unklar — ein leerer String ist nicht "unbekannt". Reviewer flaggte das in Task 10; Fix in Task 11: `ticker: str | None = None` bis Lookup fertig, dann korrekter DB-Lookup.
  - **Branching-Reality-Check hätte früher sein sollen**: Beim Branch-Setup war unklar ob `feat/narrative-single-memo` schon in main gemergt ist. Git-Status-Check hat ergeben: nein. Wäre das nicht geprüft worden, hätte der erste Build-Step gegen main gebaut und alle Single-Memo-Imports wären `ModuleNotFoundError` geworden.
  - **Final-Review fand 3 weitere kritische Bugs nach abgeschlossenen 12 per-Task-Reviews**: Nach allen 12 Build-Steps hat der Final-Review (`feature-dev:code-reviewer` mit holistischem Scope über die ganze Implementation) drei produktionsbreaking Bugs gefunden, die in den per-Task-Reviews durchgerutscht sind:
    1. **`r["stock_id"]` KeyError in `_execute_batch`**: Mein Plan-Code nahm an, dass Run-Results einen `stock_id`-Key haben. Sie haben ihn NICHT — `RankingRunService.create_and_execute_run` speichert nur `ticker, total_rank, weighted_avg, is_sweet_spot, per_model_ranks`. Tests passten weil hand-crafted Sample-Results `stock_id` enthielten. Production-Smoke wäre crash gewesen. **Fix**: ticker-based Lookup via `stock_repo.get_by_ticker(ticker)`.
    2. **`asyncio.create_task` Result nicht gespeichert — GC-Risiko**: Python-asyncio-docs warnen explizit: "Save a reference to the result of this function, to avoid a task disappearing mid-execution." Per-Task-Reviewer hat das nicht gesehen weil der Bug erst unter Memory-Pressure auftritt. **Fix**: `self._background_tasks: set[asyncio.Task]` + `add_done_callback`.
    3. **`BudgetCapExceeded` mid-batch nicht caught**: Spec §8 listet das explizit als handled, aber der except-Block in `_one()` hatte's nicht. Worker hätte gecrasht statt remaining Stocks in `failed_stock_ids` zu markieren. Per-Task-Reviewer von Task 8 hat nur RateLimitError gefangen — der hat den Spec-§8-Eintrag dafür gesehen, aber den BudgetCap-Eintrag nicht (selbe Tabelle, selbe Spec-Sektion). **Fix**: `BudgetCapExceeded` zur except-tuple hinzugefügt.
- **Lektion**:
  **Per-Task-Reviews fangen Detail-Bugs, aber Final-Review fängt System-Bugs — und ist nicht skip-bar.** Per-Task-Reviewer haben einen schmalen Scope: ein Commit, ein File-Set, eine Spec-Sektion. Sie sehen NICHT (a) wie Plan-Annahmen mit existing Code-Realität konfliktieren (`stock_id`-KeyError gegen RankingRunService), (b) Pattern-Risiken die unter Production-Last auftauchen (asyncio.create_task-GC), (c) ob *alle* Spec-Items in einer multi-Item-Liste konsistent gehandhabt werden (BudgetCap im selben except-Block wie RateLimit). Der Final-Review nach allen Tasks ist die einzige Schicht die das fängt. **Heuristik**: Bei subagent-driven-development mit 8+ Build-Steps ist der Final-Review obligatorisch und sollte explizit gegen Plan-Annahmen vs. existing Codebase, asyncio-Lifecycle und Spec-Tabellen-Konsistenz prüfen — nicht nur gegen einzelne Files.

  **Sub-Lehre**: Per-Task-Reviewer sehen 4/7 Bugs, Final-Reviewer findet 3/7. Token-Aufwand für Final-Review (~50k Tokens, 1 Sonnet-Subagent) ist günstig im Vergleich zum debug-Aufwand bei Production-Crash (`stock_id` allein wäre Sonst beim ersten realen Run aufgefallen).
- **Spec-First-Insight**: Async-Job-Pattern (Job-Tabelle + Background-Worker + Polling-Endpoint) als eigenständiges Architektur-Pattern in §11 der Spec dokumentiert. Erste Verwendung im Repo — wird Vorlage für Research-Agent-Batch und Scoring-Batch.
- **Offene Issues** (für Folge-PR getrackt, nicht in dieser Slice):
  - `BudgetCapExceeded`-Global-Handler gibt 503 zurück, aber Spec §6 sagt 402 für `/memos/batch`. Per-route `HTTPException(402)` macht den `/batch`-Endpoint korrekt, aber der globale Handler bleibt inkonsistent. Beide Memo-Endpoints sollten 402 returnen.
  - **Hexagonal-Violation**: Application-Service (`narrative_service.py`) importiert `SQLARankingRunRepository` und `SQLAStockRepository` direkt aus dem Infrastructure-Layer. AGENTS.md §2 markiert das als blocking. Pragmatischer Workaround in dieser Slice (Module-level imports für Mocking), aber sollte über `repo_factory: Callable[[AsyncSession], StockRepository]` Constructor-Param gelöst werden. Folge-Issue.
- **Token-Kosten**: Geschätzt ~300-400k Tokens (Opus 4.7 Controller + 12 Sonnet-4.6-Implementer-Subagents + 12 Reviewer-Subagents). Kein Real-API-Smoke in diesem Slice (Smoke-Skript erstellt, manuell ausführbar nach docker-compose up + seed). ~10-15 USD geschätzt.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller + Sonnet-4.6-Subagents)

## 2026-05-08 · Review-Fix-Bundle für PR #64 (Issue #17, Commits `df2e628` bis HEAD)
- **Agents**: Claude Code (Opus 4.7, 1M-Kontext) inline (kein Subagent-Dispatch). Single-Session-Diskussionsmodus mit `gsd:progress` als Einstieg, dann Review-Findings einzeln mit der Userin durchgesprochen, pro Blocker eine Fix-Option gewählt → TDD-Loop direkt im Hauptkontext umgesetzt.
- **Scope**: Drei Blocker aus itsFabias REQUEST_CHANGES-Review von PR #64 gefixt + W5-Real-API-Smoke ausgeführt + Schema-Calibration-Bug gefixt (durch Smoke entdeckt). Sechs Commits: B1 (`asyncio.gather` → sequenziell, da DI-geteilte AsyncSession nicht concurrent-safe), B2 (`NotImplementedError`-Guard für `language="en"` — verhindert Token-Verbrauch für TODO-Stub-Template), B3 (Reload nach `save()` damit Service die persisted DB-Row zurückgibt, nicht in-memory Entity mit fresh `uuid4()`), Spec-§11.1 mit Plan-Code-Drift-Tabelle, Smoke-Skript `scripts/smoke_narrative_real_api.py`, Schema-Constraint `ranking_interpretation` 600 → 1000 + System-Prompt-Anweisung mit konkreten Längen-Constraints.
- **Was gut lief**:
  - **W5-Smoke hat einen echten Production-Bug gefunden, den keine Stub-Test-Suite je catchen würde**: Beim ersten Real-API-Call gegen Sonnet 4.6 hat Pydantic-Validation auf `ranking_interpretation` mit `string_too_long` (>600 chars) gefailt. Sonnet schreibt für eine 5-Modell-Interpretation typisch 700-1000 Zeichen — das ist plausibel und nicht Edge-Case. In Production wäre jedes solches Memo in den Error-Memo-Pfad gegangen (`model_version="error-fallback"`). Der Smoke hat damit genau das geliefert was Fabis W5-Item versprach: Ground-Truth gegen Anthropic, nicht gegen StubAnthropic. **Schließt den "Cache-Hit-Rate NICHT GEMESSEN — Acceptance-Gap" aus dem 05-04-Eintrag.**
  - **Cache-Caching-Verifikation E2E**: Call 1 cache_create=3259 / cache_read=0, Call 2 cache_create=676 / cache_read=3259. Kosten-Ersparnis 42% beim 2. Call ($0.0274 → $0.0160). `cache_control: ephemeral` wird syntaktisch korrekt durch `LLMClient` zur SDK durchgereicht.
  - **TDD-Disziplin im Diskussionsmodus**: Bei B2 und B3 zuerst Test geschrieben, RED verifiziert, dann Fix → GREEN. Bei B3 mussten 4 bestehende Tests umstrukturiert werden (memo_repo.get wird jetzt zweimal aufgerufen: Cache-Check + Reload), das ist im selben Commit transparent dokumentiert.
  - **Strict-Scope-Disziplin trotz vieler offener Findings**: Fabis Review hatte 3 Blocker + 6 W-Findings + 6 Nits. Userin hat explizit "nur Blocker + W5" gewählt. W1/W3/W4/W6 + Nits bleiben aus dem PR raus, gehen in Folge-Issues. Hält den Re-Review-Diff klein und fokussiert.
- **Was nicht klappte**:
  - **W5 hätte Teil von PR #64 Build-Step 11 sein müssen, nicht ein Review-Folge-Item**: Der Smoke ist 15 min Arbeit und hat genau einen produktionskritischen Schema-Bug gefunden. Im 05-04-Eintrag wurde explizit dokumentiert dass der Smoke nicht ausgeführt wurde — der Schema-Calibration-Bug wäre einen ganzen Review-Cycle (mit Subagents!) früher gefunden worden, wenn Smoke zur Acceptance-Definition von Build-Step 11 gehört hätte, nicht "nice to have danach". **Lehre: Real-API-Smoke gehört in die Acceptance-Liste eines LLM-Features, nicht in die "Known Gaps".**
  - **Schema-Constraint aus dem Gedächtnis statt aus realen Anthropic-Outputs gewählt**: max_length=600 für `ranking_interpretation` war eine Schätzung im Foundation-Spec. Hätte beim Spec-Schreiben gegen 2-3 echte Sonnet-4.6-Outputs für ähnliche Tasks abgemessen werden müssen. Schema-Constraint-Werte für LLM-Outputs sind nicht eindeutig herleitbar — sie brauchen empirische Kalibrierung gegen das Modell, das man in Production nutzt. Spiegelt eine schon-bekannte Lehre aus dem 05-04-Eintrag ("Plan-Code-Bugs trotz Reality-Check") in eine andere Domäne: **Constraint-Werte sind keine Spec-Annahme, sie sind Mess-Größen.**
  - **Discussion-Mode hat im Vergleich zu Subagent-Dispatch viele kurze Tool-Cycles erzeugt**: Sechs Commits, jeweils 1-2 Edits + Test-Run. Inline-Modus ist für Polish-Arbeit angemessen, aber Token-effizienter wäre ein dispatcher Subagent gewesen, der "B1+B2+B3+Spec+Smoke-Skript" in einer Pass macht. Trade-off: Inline gibt mehr Kontrolle (Userin entscheidet pro Blocker), Subagent ist günstiger.
- **Lektion**:
  **Real-API-Smoke ist Acceptance, nicht Polish.** Stub-basierte Tests verifizieren Code-Pfad und Prompt-Komposition, aber nicht das Modell-Output-Verhalten gegen das echte Schema. Bei jedem LLM-Feature mit Pydantic-strukturiertem Output muss mindestens ein Real-API-Call gegen das Production-Modell als Acceptance-Kriterium aufgenommen werden — sonst sind Schema-Constraints reine Wunschvorstellungen. Operationalisierung: in der Slice-Spec §10 (Acceptance) das Smoke-Item in die Tabelle als BLOCKER aufnehmen, nicht nur als Checklist-Eintrag.
- **Token-Kosten**: Inline-Diskussion ~40-60k Tokens (Opus 4.7) + 2 Real-API-Smoke-Calls Sonnet 4.6 = $0.043. Geschätzte Total-Kosten ~$1-2.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 inline)

## 2026-05-05 · Alpha-Modell — TDD-Implementation (Branch `feat/alpha-impl`, stacked auf `feat/trend-momentum-impl`)
- **Agent**: Claude Code (Opus 4.7), Main-Context.
- **Scope**: Viertes und letztes der Wave-2-Quant-Modelle. `AlphaModel` ersetzt `NotImplementedError`-Skeleton durch Multi-Horizon Sharpe-gewichtete Outperformance: 5 Horizonte (5/63/126/252/504 Tage) × Gewichte (0.10/0.15/0.25/0.30/0.20) + Sharpe-Tilt (0.05) + Z-Score-Normalisierung. Dynamische Gewichts-Umverteilung wenn Long-Horizonte fehlen (Spec §2 Edge-Case). 9 Tests (Constants, Multi-Horizon-Outperformer, Sharpe-Influence, Identical-Tie, Determinismus, Empty, Single-Ticker, Insufficient-Data, Short-History-Redistribution), **alle 9/9 grün beim ersten Run**. Volle Suite: 172 passed, mypy strict + ruff format/check clean.
- **Spec-Deviations** (bewusst, dokumentiert im Modul-Docstring):
  - **Equal-weighted Benchmark statt ^GSPC** (Spec §2). Begründung: Konsistenz mit den anderen 3 Wave-2-Modellen (Trend Momentum, Value Alpha Potential, Diversification), die alle dem Redesign-Pattern §3.1 folgen ("bewusst gegen cap-gewichtetes ^SSMI, das von Nestlé/Roche dominiert würde"). Spec-Beispiel `^GSPC` ist für CH-Tickers ohnehin sinnfrei.
  - **SHARPE_WEIGHT = 0.05** (Spec §2 sagt "additiv" ohne Zahl). Skalen-Argument: annualisierte Sharpe-SD über SMI-Tickers ~7× grösser als Outperformance-SD; bei 0.20 würde Sharpe die Horizont-Gewichtung dominieren. 0.05 hält Sharpe als Quality-Tilt. Empirische Validierung im ersten Backtest.
- **PR-Strategie**: PR #?? stacked auf `feat/trend-momentum-impl` (= aktueller TM+VAP-Branch nach Self-Merge von #63 in seinen Base). Wave-2 ist mit diesem PR abgeschlossen — alle 4 ausstehenden Modelle aus PR #26-Redesign implementiert.
- **Was gut lief**:
  - **4. Modell, 4. mal beim ersten Run grün** (Diversification 6/6, TM 8/8, VAP 7/7, Alpha 9/9). Spec-First-Diszplin + TDD-RED-Verify-Pattern haben sich für die ganze Wave bewährt — null Format-Iterationen, null Edge-Case-Bugs nach Implementation. Reflex `ruff format` + `ruff check` als CI-Mirror sitzt jetzt fest.
  - **Sharpe-Influence-Test als Behavior-Anchor**: `test_lower_volatility_wins_at_similar_outperformance` konstruiert zwei Ticker mit *gleichem* deterministischen Mittelwert aber drastisch unterschiedlicher Daily-Vola. Test-Behauptung steht direkt aus Spec §2 ("Ticker mit gleicher Outperformance aber höherer Volatilität → tieferer Score"). Würde bei Tests-after vergessen, weil das Verhalten nicht direkt aus dem Code abzulesen ist.
  - **Spec-Lücken-Auflösung als bewusste Design-Entscheidung**: Vor RED-Phase explizit User-Feedback eingeholt zu (a) Benchmark-Variante und (b) Sharpe-Gewicht. Beide Spec-Lücken klar als Deviations dokumentiert statt im Code-Kommentar versteckt. CLAUDE.md-Regel "Lieber eine präzise Nachfrage als eine falsche Annahme. Finanzmathematik verzeiht keine Ungenauigkeit" befolgt.
- **Was nicht klappte**: Nichts substanzielles. `ruff format` musste 1× nachgezogen werden (multi-line tuple-formats), aber das war 30s Reflex.
- **Methodisches Mini-Learning**: **Wave-2 abgeschlossen, Pattern verifiziert.** Vier Modelle, vier 1st-try-GREEN-Runs, vier sauber dokumentierte AI-USAGE-Einträge. Die Iron Law TDD-Pflicht (RED vor GREEN, Verify-RED vor Implementation) hat genau einen Bug gefangen, der Tests-after garantiert nicht gefangen hätte (Diversification Zero-Variance, AI-USAGE 2026-05-02). Eine Bug-Detection in 4 Modellen klingt nach wenig — aber das ist ein Bug pro 1.5h Implementation-Time, was die TDD-Mehrkosten klar amortisiert.
- **Token-Kosten**: ~10k Tokens Opus 4.7; ~0.20 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-04 · Narrative-Engine Single-Memo Slice (Issue #17, PR-Commits `adb6158` bis `57afdbe`)
- **Agents**: Claude Code (Opus 4.7, 1M-Kontext) als Controller mit `superpowers:subagent-driven-development` Skill. **11 dispatchte Subagents**: 10 Implementer/Reviewer (1 pro Build-Step inkl. kombinierter Spec+Code-Review-Agent wo möglich) + 1-2 Fix-Subagents (Build-Step 3 Cost-Bounds, Build-Step 8 `ranking_interpretation`-Länge, Build-Step 7 asyncio.gather-Drift) + 1 Cleanup-Subagent. Plus `superpowers:brainstorming` und `superpowers:writing-plans` als Spec/Plan-Phasen davor, inkl. explizitem Reality-Check-Pass (Spec v1.0 → v1.1) VOR dem Plan.
- **Scope**: Single-Memo-Pfad der Narrative-Engine implementiert in 17 Commits: Spec (v1.0 + Reality-Check → v1.1) → Plan (2500+ Z.) → 10 Build-Steps + Review-driven-Fixes + 1 finaler chore(review). Gebaut: `StockRepository.get()` (Domain-Port + SQLAlchemy-Adapter mit Identity-Map), `LLMClient`-Erweiterung für `list[dict]`-System-Prompt (cache_control-ready), `PromptTemplateLoader` (Jinja2 + DE/EN-Templates), `NarrativeService` mit `get_memo`/`generate_memo` (Tool-use + Pydantic-Validation + Error-Memo-Persistierung), zwei REST-Endpoints `POST /api/v1/memos/generate` + `GET /api/v1/memos/{stock_id}/{model_run_id}`, Integration-Tests gegen PG + StubAnthropic (3 Fixtures: happy-path, contradictory, malformed).
- **Was gut lief**:
  - **Plan-Reality-Check VOR Plan-Schreiben hat drei nicht-existente Repo-Methoden früh entdeckt**: Spec v1.0 referenzierte `ResearchMemoRepository.get_by_stock_and_run()`, `RankingRunRepository.get_by_id()`, und `StockRepository.get()` als existierende APIs — keines davon war in der Codebase. Reality-Check-Pass (Spec → v1.1) korrigierte das VOR dem Plan: `get_by_stock_and_run` als Cursor-Abfrage direkt im Service, `RankingRunRepository`-Referenz entfernt, `StockRepository.get()` explizit als neuer Build-Step (Task 2). Ohne Reality-Check wären das 3 Blocking-Bugs in Task 5-7 geworden.
  - **Two-Stage-Review fängt Plan-Code-Drifts**: 5 echte Bugs in der Impl.-Phase gefunden — `ranking_interpretation`-Länge im Plan-Template (Build-Step 8: Plan hatte 620 Zeichen, Schema-Constraint ist 600-max), `asyncio.gather`-Refactoring in Sequential-Code (Build-Step 7: Spec sagte sequential, Review-Agent entdeckte Drift), `async_session_factory` vs. `get_session_factory()` (Build-Step 10), asyncpg-Cast-Syntax, und tightere Cost-Bounds im LLMClient-Test. Spec-Reviewer + Code-Quality-Reviewer fangen auch hier unterschiedliche Bug-Klassen.
  - **Combined Spec+Code-Review-Agent (eine Sonnet-Anfrage statt zwei Haiku) effizienter für mittelgrosse Tasks**: Bei Build-Steps 4-8 (jeweils 3-6 neue Files, 20-60 neue Zeilen) war ein kombinierter Reviewer-Agent schneller und fing mehr cross-cutting concerns (z.B. Jinja2-Template-Namespace-Konsistenz quer über Loader + Templates) als zwei separate Haiku-Reviewer, die nur ihren Teilbereich kennen.
  - **Cleanup-Bundle-Pattern analog Foundation**: Minor- und Important-non-blocking-Findings aus allen Build-Steps akkumuliert für einen finalen `chore(review)`-Commit (Build-Step 7 asyncio.gather-Fix, Build-Step 3 Cost-Bounds, etc.). Build-Step-Commits bleiben auf den TDD-Zyklus fokussiert; Style- und Konsistenz-Fixes kohärent am Ende.
- **Was nicht klappte**:
  - **Plan-Code-Bugs trotz Reality-Check**: Der Reality-Check verhinderte Architektur-Bugs, aber Plan-Codebeispiele enthielten 5 weitere Fehler: falsche `ranking_interpretation`-Längenschätzung (Plan: 620 Zeichen, Constraint: 600 Max — erst in Build-Step 8 Review aufgefallen), asyncio.gather-Drift (Plan sagte sequential, Subagent interpretierte gather-Pattern aus Foundation-Code), asyncpg-Cast-Syntax (Build-Step 10 Integration-Test), falsche session_factory-Signatur, und tightere LLMClient-Cost-Bounds. **Lehre: Reality-Check sollte auch Plan-Code-Templates gegen echte Schema-Constraints verifizieren, nicht nur Methoden-Existenz.**
  - **asyncio.gather vs. Sequential — Spec-Drift erst im Code-Review aufgefallen**: Build-Step 7 Subagent hat `asyncio.gather` für parallele Datenladung implementiert (technisch korrekt und sinnvoll), aber die Spec sagte explizit Sequential mit Kommentar "parallele Variante als Folge-Task". Review-Agent entdeckte das; Build-Step-7-Review-Commit hat es refactored. Hätte im Subagent-Prompt expliziter stehen müssen: "Sequential, nicht gather — auch wenn gather technisch besser wäre."
  - **Cache-Hit-Rate beim Smoke-Test NICHT GEMESSEN — Acceptance-Gap**: Step 11.3 (manueller Smoke gegen echte Anthropic-API) wurde nicht ausgeführt. Docker-Compose ist möglicherweise nicht hochgefahren, ANTHROPIC_API_KEY nicht gesetzt. Alle Tests sind Stub-basiert (StubAnthropic-Client). Die Cache-Hit-Rate (`cache_read_input_tokens > 0` beim 2. Call) ist damit **unbestätigt für den Real-API-Pfad**. Dieser Acceptance-Gap muss in einem Folge-Smoke nachgereicht werden, bevor der PR in Production geht.
- **Lektion**:
  **Plan-as-Contract zwischen Subagents braucht VERIFIED Plan-Templates.** Das Reality-Check-Pattern (Spec gegen echte Codebase verifizieren VOR dem Plan-Schreiben) hat die schlimmsten Architektur-Bugs verhindert — 3 nicht-existente Methoden früh entdeckt, Spec v1.1 ohne Blocking-Änderungen in der Impl.-Phase. Aber der nächste Schritt ist: nicht nur Methoden-Existenz, sondern auch Schema-Constraints, Signature-Details und Test-Bound-Werte im Plan-Template gegen die echte Codebase verifizieren. Heuristik: vor jedem Plan-Code-Snippet `grep`-verifizieren — Constraint-Werte aus `models.py` ziehen, nicht aus dem Gedächtnis extrapolieren. Das wäre ein 10-Minuten-Schritt im Plan-Schreiben, der 5 Review-Fix-Iterationen spart.
- **Methodisches Mini-Learning**:
  **Combined Spec+Code-Review-Agent (eine Sonnet-Anfrage statt zwei Haiku-Anfragen) ist für mittelgrosse Tasks effizienter.** Bei Build-Steps mit 3-6 neuen Files fangen zwei separate Reviewer-Rollen in getrennten Haiku-Anfragen zwar unterschiedliche Bug-Klassen, aber jede Rolle sieht nur ihren Teilbereich. Ein kombinierter Sonnet-Reviewer der beide Rollen trägt, findet cross-cutting Konsistenz-Probleme (Jinja2-Namespace quer über Loader + Templates, Import-Ketten über 3 Files) die zwei Haiku-Reviewer bei getrenntem Scope übersehen würden. Heuristik: bei Tasks mit >3 neuen Files oder >1 Schicht (Service + Repository + REST) → kombinierter Sonnet-Reviewer. Bei isolierten 1-File-Tasks → Two-Stage-Haiku bleibt effizienter (schneller, billiger, ausreichend fokussiert).
- **Token-Kosten**: Geschätzt ~350-400k Tokens insgesamt (Opus 4.7 Hauptkontext für Orchestrierung + Reality-Check + Plan + Review-Synthese, ~130k; 10-11 Sonnet-4.6-Subagent-Dispatches à ~15-30k = ~200-250k; Haiku-4.5 für schnelle Fix-Iterationen ~20k). Kein echter CostTracker-Wert verfügbar (Smoke-Test nicht ausgeführt). Etwa 12-15 USD geschätzt.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller + Sonnet-4.6/Haiku-4.5-Subagents)

## 2026-05-03 · Value-Alpha-Potential-Modell — TDD-Implementation (Branch `feat/value-alpha-potential-impl`, stacked auf #62)
- **Agent**: Claude Code (Opus 4.7), Main-Context.
- **Scope**: Drittes von 4 ausstehenden Quant-Modellen aus PR #26-Redesign. `ValueAlphaPotentialModel` ersetzt `NotImplementedError`-Skeleton durch Rolling-Max-Alpha-Mean-Reversion: `alpha = pct_change(63) - benchmark.pct_change(63)`, `rolling_max = alpha.rolling(252, min_periods=68).max()`, `potential = rolling_max - alpha`. 7 Tests (Constants, Past-Star vs. Constant, At-Peak-Today/Negative-Potential-Edge-Case, Determinismus, Empty, Insufficient, Single-Ticker), **alle 7/7 grün beim ersten Run**. Volle Suite: 164 passed / 1 skipped, mypy strict + ruff format/check clean.
- **PR-Strategie**: PR #63 stacked auf `feat/trend-momentum-impl` (PR #62), das wiederum auf #61 stacked. Drei-Stufen-Stack. Plan: nach #61-Merge → `gh pr edit 62 --base main`; nach #62-Merge → `gh pr edit 63 --base main`.
- **Was gut lief**:
  - **3. Modell, 3. mal beim ersten Run grün** (Diversification: 5/6, dann 6/6 nach Zero-Variance-Fix; Trend Momentum: 8/8; Value Alpha Potential: 7/7). Spec-First-Disziplin zahlt sich aus — die `2026-04-28-quant-mvp-models.md`-Spec macht alle Edge-Cases explizit, sodass Tests + Impl in der gleichen Mental-Model-Stunde fertig sind.
  - **At-Peak-Test als Spec-Edge-Case-Anchor**: Die Spec sagt explizit „Negativer potential: Aktuelles Alpha über Rolling-Max → gültiger Score, wird normal gerankt." `test_at_peak_today_yields_negative_potential` testet genau das — keine Ranking-Regression bei Edge-Score-Werten. Würde bei „Tests-after" wahrscheinlich vergessen werden.
- **Was nicht klappte**: 
  - **Nichts (zum ersten Mal in der Wave)** — kein Format-Trap, kein Edge-Case-Bug, keine ruff/mypy-Iteration. Der Reflex `ruff format` + `ruff check` als CI-Mirror vor Push ist jetzt eingebaut.
- **Methodisches Mini-Learning**: **Stacked-PRs sind kein Drama, wenn der Diff sauber bleibt.** Drei Branches in der Pipeline (`feat/diversification` → `feat/trend-momentum` → `feat/value-alpha-potential`) bedeuten dreimal `gh pr edit --base main` nach den jeweiligen Merges. Das ist Buchhaltungsaufwand, kein Coding-Aufwand. Der Trade-off lohnt sich gegenüber „warten bis #61 merged, dann erst #62 starten" — wir produzieren 3× so schnell, der Reviewer entscheidet die Reihenfolge.
- **Token-Kosten**: ~12k Tokens Opus 4.7; ~0.25 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-02 · Trend-Momentum-Modell — TDD-Implementation (Branch `feat/trend-momentum-impl`, stacked auf #61)
- **Agent**: Claude Code (Opus 4.7), reine Main-Context-Arbeit (kein Subagent — kompakter TDD-Cycle).
- **Scope**: Zweites von 4 ausstehenden Quant-Modellen aus PR #26-Redesign. `TrendMomentumModel` ersetzt `NotImplementedError`-Skeleton durch EWMA-basierte Implementation: `prices.pct_change().sub(benchmark.pct_change()).ewm(halflife=63, min_periods=32).mean()` → höchster Score = Rang 1. 8 Tests (Constants, Outperformer-Golden, Identical-Prices-Tie, Recent-Outperformance-EWMA-Halflife-Verifikation, Determinismus, Empty, Insufficient, Single-Ticker), alle grün **beim ersten Run**. Volle Suite: 159 passed / 3 skipped, mypy strict + ruff format/check clean.
- **PR-Strategie**: PR #62 stacked auf `feat/diversification-impl` (Base = #61's Branch), weil pyproject.toml-Deps (pandas/numpy/sklearn) noch nicht in main. Plan: nach #61-Merge `gh pr edit 62 --base main` für sauberen Basiswechsel.
- **Was gut lief**:
  - **TDD-Disziplin: 8/8 grün beim ersten Run**, kein Edge-Case-Bug. Spec war detailliert genug (`docs/specs/2026-04-28-quant-mvp-models.md §3` + Redesign-Spec), dass keine Design-Entscheidungen mid-flight nötig waren.
  - **EWMA-Halflife-Verifikations-Test als spezifischer Behavior-Anchor**: `test_recent_outperformance_weighted_higher` konstruiert zwei Ticker mit *gleicher* Gesamt-Outperformance, aber unterschiedlicher Recency. EWMA mit halflife=63 muss B (recent) höher ranken als A (uniform). Das ist nicht „ein Test der Formel", sondern ein Test der **Spec-Behauptung** „Heute = volles Gewicht, vor 63d = 50%". Genau die Kategorie Test, die bei Tests-after meist fehlt, weil sie nicht aus dem Code abgelesen werden kann.
  - **Lokal CI-Mirror als Reflex**: Diesmal vor Push `ruff format --check` zusätzlich zu `ruff check` gelaufen — Format-Issue im Test-File gefunden + behoben **vor** dem Push. PR #61 hatte das nicht und CI war rot — Lehre direkt umgesetzt.
- **Was nicht klappte**: 
  - **Anfangs Format-Trap erneut**: erster `ruff format --check`-Run (vor Push) zeigte `test_trend_momentum.py` als unformatiert — pandas-DataFrame-Konstruktor multi-line-Style. Reformat-Run + Re-verify innerhalb 30s. **Lehre verfestigt: `ruff format` ≠ `ruff check`, immer beide.**
- **Methodisches Mini-Learning**: **Behavior-Tests > Formel-Tests.** Der EWMA-Halflife-Test prüft *was die Spec verspricht* (Gewichtung), nicht *was der Code tut* (`.ewm(halflife=63)`). Das ist Spec-vs-Code-Asymmetrie als Test-Pattern: wenn der Code irgendwann auf andere Halflife-Werte umgestellt würde, würde der Test die Spec-Verletzung fangen. Dieselbe Idee wie Sheylas Schema-vs-Entity-Asymmetrie in PR #54.
- **Token-Kosten**: ~15k Tokens Opus 4.7; ~0.30 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-05-02 · Diversification-Modell — TDD-Implementation (Branch `feat/diversification-impl`)
- **Agent**: Claude Code (Opus 4.7), reine Main-Context-Arbeit (kein Subagent — klassischer Tight-Loop-TDD-Cycle).
- **Scope**: Erstes der 4 noch ausstehenden Quant-Modelle aus dem Redesign-PR #26 vollständig implementiert. `DiversificationModel` ersetzt das `NotImplementedError`-Skeleton in `backend/domain/models/diversification.py` durch die in der Spec festgelegte Ledoit-Wolf-Shrinkage-Kovarianz-Berechnung mit `score = 2 / (annualisierte_vola + avg_korrelation)`. 6 Tests (Golden-Dataset 3-Ticker, Determinismus, leeres Universum, Single-Ticker, < 30 Datenpunkte, Zero-Variance-Ticker), alle grün. Pandas + numpy + scikit-learn neu in `pyproject.toml`-Deps aufgenommen. Volle Suite: 153 passed / 5 skipped, mypy strict + ruff clean.
- **Was gut lief**:
  - **TDD-Disziplin echt eingehalten**: Test-File komplett geschrieben, RED gesehen (6/6 fail mit `NotImplementedError`), erst dann Implementation — und die Implementation hatte beim ersten Run 5/6 grün, der eine Fehler war ein **echter Spec-Insight**: Ledoit-Wolf-Shrinkage glättet die Diagonale, also kann man Zero-Variance-Ticker nicht aus der geshrinkten Cov-Matrix erkennen. Pre-Check auf Roh-Returns-Std hinzugefügt. **Hätte bei "Tests after" niemals gefunden**, weil das Verhalten plausibel aussieht.
  - **Spec-Treue**: Formel exakt aus `2026-04-28-quant-mvp-models.md §5` übernommen, nicht aus dem Gedächtnis rekonstruiert (CLAUDE.md-Anti-Pattern bewusst gemieden).
  - **PR-Workflow korrekt von Anfang an**: Diesmal sofort `git checkout -b feat/diversification-impl` von aktuellem `main`, kein Direkt-Commit-auf-Main-Faux-Pas wie bei PR #26.
- **Was nicht klappte**:
  - **Pandas/numpy/sklearn waren nicht in `pyproject.toml`**, obwohl lokal installiert. Erst beim Schreiben der Tests aufgefallen. Lehre: bei neuer Domain-Library zuerst `pyproject.toml`-Eintrag prüfen, sonst CI grün lokal aber rot in GitHub Actions.
  - **Pythonkonvertierung von numpy-Skalaren zu `float`** an mehreren Stellen nötig, damit mypy strict happy ist. Mini-Friction, aber lehrreich: numpy-Typen leaken sonst in den Domain-Layer.
- **Methodisches Mini-Learning**: **Der Wert des "Verify RED"-Steps ist real.** Hätte ich die Tests nach der Implementation geschrieben, hätte der Zero-Variance-Edge-Case "passend zur Implementation" ausgesehen und das Bug wäre durchgerutscht. Test-First zwingt zur unabhängigen Spec-Prüfung.
- **Token-Kosten**: ~25k Tokens Opus 4.7; ~0.50 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-04-30 · Narrative-Engine Foundation Implementation (Issue #17, PR-Commits `e9c14b6` bis `efab277`)
- **Agents**: Claude Code (Opus 4.7, 1M-Kontext) als Controller mit `superpowers:subagent-driven-development` Skill. **9 dispatchte Subagents (Sonnet 4.6)**: 7 Implementer (1 pro Build-Step) + Spec-Compliance- + Code-Quality-Reviewer pro Task (= 14 Reviews) + 2 Fix-Subagents (Build-Step-1-Style + Build-Step-5-Constraint-Naming) + 1 Cleanup-Subagent. Plus `superpowers:brainstorming` und `superpowers:writing-plans` als Spec/Plan-Phasen davor.
- **Scope**: Foundation für Issue #17 (Narrative-Engine Layer 1) implementiert in 12 Commits: Spec (393 Z.) → Plan (1405 Z.) → 7 Build-Steps + 2 Reviewer-driven-Fixes + 1 finaler Cleanup. Persistenz-Schicht komplett: Pydantic-Klassen (`ContradictionItem`, `ResearchMemoSchema`, `ResearchMemo` Entity mit Constraint-Asymmetrie zum Schema), SQLAlchemy-ORM mit 14 Spalten + UNIQUE/CHECK/FK-CASCADE, Alembic-Migration 0005 (upgrade+downgrade-Roundtrip verifiziert), Repository-Port + SQLAlchemy-Adapter mit `pg_insert.on_conflict_do_update` UPSERT-Semantik (`created_at` als Lifecycle-Marker explizit ausgenommen). **39 neue Tests** (5 ContradictionItem + 11 Schema + 6 Entity + 12 ORM + 5 Integration), **187/6 gesamt grün**, mypy strict + ruff durchgehend clean. NarrativeService, REST-Endpoints, Prompt-Templates, LLMClient-Erweiterung explizit out-of-scope für Folge-PRs.
- **Was gut lief**:
  - **Two-Stage-Review fängt was Single-Review verpasst**: Der Spec-Reviewer fand in Task 5 einen Constraint-Naming-Bug, den weder der Implementer noch der vorherige Code-Quality-Reviewer gesehen hatten — `NAMING_CONVENTION` in `base.py` wickelt explizite ORM-Namen automatisch in den Convention-Prefix ein, also produzierte `name="ck_research_memos_confidence"` in der Live-DB den doppelten Namen `ck_research_memos_ck_research_memos_confidence`. Ohne Spec-Reviewer (der gegen die echte DB-Realität via psql gegencheckte, nicht nur gegen den ORM-Code) wäre das in Production gelandet. **Spec-Reviewer und Code-Quality-Reviewer fangen unterschiedliche Klassen von Bugs** — Aufteilung der Aufmerksamkeit ist die Investition wert.
  - **Q-by-Q-Brainstorming-Disziplin gehalten** (4 Architektur-Entscheidungen einzeln durchgesprochen — Scope, UNIQUE-Constraint, Sprach-Spalte, Schema-vs-Entity-Trennung), bevor erste Codezeile geschrieben wurde. Resultat: kein einziger Build-Step musste architektonisch neu gedacht werden, alle 7 Tasks RED→GREEN ohne Architektur-Iteration. Spiegelt das Mini-Learning aus PR #24 ("Frage-pro-Turn ist Pflicht-Tool").
  - **Plan-as-Contract zwischen Subagents**: Der ~1400-Zeilen-Implementation-Plan mit verbatim Test-Code, Bash-Commands und Commit-Messages pro Step erlaubte 7 sequentielle Subagents ohne Kontext-Übergabe. Jeder Subagent bekam nur seinen Task-Block + Project-Context, fertig. Fast keine Zwischen-Diskussion mit dem Controller nötig.
  - **Subagent-Deviations transparent dokumentiert**: Build-Step 7 (Adapter) hatte 4 Plan-Deviations (`get_session_factory()` API, per-test engine für event-loop-isolation, `universes`-Schema-Mismatch, `cast()` für mypy strict). Subagent meldete alle vier mit Begründung im Status-Report — wieder das "Trust-but-Verify"-Pattern aus PR #25 in Reinkultur.
  - **Cleanup-Bundle-Pattern (analog "Fabia-Review Mediums + Nits cleanup" PR #19)**: 7 akkumulierte Review-Findings (3 Important, 4 Nits) in einen `chore(review):`-Commit gesammelt statt jede Build-Step direkt zu fixen. Hält die Build-Step-Commits klar fokussiert auf den eigentlichen TDD-Cycle; Style-Inkonsistenzen werden am Ende einmal kohärent gefixt.
- **Was nicht klappte**:
  - **Plan-Code-Templates hatten 5 echte Bugs**: Der Plan war detailliert, aber an mehreren Stellen falsch oder veraltet:
    1. `model_config = ConfigDict(frozen=True)` widersprach Codebase-Konvention `{"frozen": True}` (Build-Step 1)
    2. Test-Helper-Signatur `-> dict:` brach mypy strict (`type-arg`) — musste `-> dict[str, Any]` werden (Build-Step 2)
    3. `Base`-Import aus `persistence.models.base` — actually liegt er bei `persistence.base` (Build-Step 4)
    4. `name="ck_research_memos_confidence"` triggerte das Naming-Convention-Doubling (Build-Step 5, eigene Fix-Iteration)
    5. `async_session_factory` existiert nicht — actual API ist `get_session_factory()` (Build-Step 7)
    Plus `universes`-INSERT-Schema im Plan-Test war veraltet (Plan: `description`, real: `region`/`tickers`). Subagents fanden alle und korrigierten transparent — aber jeder Fix kostete Review-Iteration. **Lehre: Plan-Code-Templates sind Vorschlag, nicht Ground-Truth. Im Plan-Schreiben hätte ich öfter gegen die echte Codebase verifizieren müssen, nicht aus der Spec extrapolieren.**
  - **Code-Quality-Reviewer hat 1× falsch geflaggt**: In Build-Step 1 wollte der Code-Reviewer `# type: ignore[misc]` wieder einfügen, das der Implementer korrekt entfernt hatte. Pydantic v2 `frozen` ist Runtime-Validation via `__setattr__`-Override; mypy strict mit `warn_unused_ignores` flagged den Ignore als unused. Implementer hatte das in seinem Initial-Report explizit dokumentiert, der Reviewer hat's übersehen. **Heuristik: Reviewer-Feedback nicht blind anwenden — auch der Reviewer kann irren. Implementer-Reports lesen vor Reject-Loops.**
  - **Latente DB-Volume-Persistenz hätte gebissen**: Constraint-Naming-Fix erforderte `alembic downgrade -1 && upgrade head` auf der laufenden Demo-DB. In Production wäre das eine echte Migration-Schmerzfrage gewesen. **Lehre: bei Migration-Renames im Pull-Diff direkt frische DB einplanen — und im Schema-Review explizit gegen die Live-DB checken (psql), nicht nur gegen den ORM-Code.**
- **Lektion**:
  **Two-Stage-Review (Spec-Compliance + Code-Quality) ist seine Investition wert.** Die zwei Reviewer-Rollen fangen unterschiedliche Klassen von Bugs:
  - **Spec-Reviewer** verifiziert *was* gebaut wurde gegen den expliziten Vertrag — fand den Constraint-Naming-Bug, weil er gegen die DB-Realität via psql gegencheckte.
  - **Code-Quality-Reviewer** verifiziert *wie* gebaut wurde — fand Codebase-Konsistenz-Drifts (model_config-Style, fehlende Docstrings, abstract-method-Bodies).

  Eine einzelne Mega-Code-Review hätte beides verlangt vom selben Agent → Aufmerksamkeit gestreut → Bugs durchgerutscht. Spezifische Reviewer-Rollen erzeugen fokussierte Aufmerksamkeit. Sub-Agent-Roundtrips kosten Tokens, aber Bug-Catch-Rate steigt überproportional. **Heuristik: für jede atomare Codeänderung ≥30 Zeilen Two-Stage-Review machen; für triviale 1-Zeilen-Fixes (wie der Constraint-Naming-Fix selbst) reicht Spec-Re-Review.**
- **Methodisches Mini-Learning**:
  **Plan-Quality vs Implementation-Speed ist nicht-linear.** Der ~1400-Zeilen-Plan hat 7 Subagents in ~30 Min Wallclock zum Ergebnis gebracht (jeder Task ~3 Min Implementation + ~3 Min Review-Loop). Ohne Plan hätte der gleiche Build sequentiell mit Hauptkontext-Roundtrips locker 90+ Min gedauert. **Investment: ~60 Min Plan-Schreiben (Brainstorming + writing-plans) → ROI ~3× in Implementation-Zeit, plus ~10 Bugs durch Two-Stage-Review früh gefangen statt im PR-Review.**
- **Token-Kosten**: Geschätzt ~250k Tokens insgesamt (Opus 4.7 Hauptkontext für Orchestrierung + Brainstorming + Plan + Review-Synthese, ~120k; 9 Sonnet-4.6-Subagent-Dispatches à ~10-30k = ~140k). Etwa 8-12 USD.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7 als Controller + 9 Sonnet-4.6-Subagents)

## 2026-04-30 · Repo-Audit + Issue-Backlog #35–#52 + Spec §16 + Dockerfile-Fix (PR #34 + dieser PR)
- **Agents**: Claude Code (Opus 4.7, 1M-Kontext) im Haupt-Context für Orchestrierung, Issue-Erstellung und Git-Flow; **3 parallel dispatchte Read-Only-Sub-Agents** für Repo-Audit (1× `feature-dev:code-explorer` Backend, 1× `feature-dev:code-explorer` Frontend, 1× `Explore` Roadmap-Alignment).
- **Scope**: Vor Phase 3 (Narrative-Engine, Layer 2, MCP) wollte ich eine Standortbestimmung. Drei Subagents parallel auf Backend / Frontend / Roadmap geschickt; operational-Health (mypy strict, ruff, pytest, CI letzte 5 Runs) selbst geprüft. Findings → 18 GitHub-Issues (#35–#52) erstellt und an die richtigen Personen zugewiesen, basierend auf dem Capstone-Briefing-PDF, das §16 erstmals konkret macht. Spec §16 mit echten Namen befüllt (TBD → Fabia / Sheyla / Andrea / Nicolas). Drive-by: `Dockerfile.backend` fehlte `pyproject.toml` im runtime-Stage → 68 falsche pytest-Failures im Container; gefixt als separater PR #34. Issues #20/#21 von Andrea auf Nicolas umassigned (alter Workaround aufgehoben — Nicolas hat jetzt einen Handle).
- **Was gut lief**:
  - **Parallel-Dispatch (3 Subagents + 2 Bash-Calls in einem Message-Block)**: Wall-Time war der längste Agent, nicht die Summe. Backend-Agent ~4 min, Frontend-Agent ~2 min, Roadmap-Agent ~3 min, parallel dazu mypy+ruff+CI-Check ~30 s. Sequentiell wären das 10+ min gewesen. **Heuristik**: Read-Only-Investigations ohne shared State sind ideale Subagent-Kandidaten — der Haupt-Context bleibt frei für Synthese.
  - **Subagent-Findings gegengecheckt vor Weitergabe**: Roadmap-Agent behauptete „pytest-asyncio fehlt" (war 30 Min vorher via PR #34 gefixt) und „PR #25/#26 wartend" (beide gemergt). Diese Stale Facts vor Sheyla explizit korrigiert — sonst hätte ich Druck auf nicht-existente Probleme erzeugt. **Subagent-Reports sind Snapshots, keine Live-Wahrheit; Vor-Aggregation ist Pflicht.**
  - **18 Issues in 4 parallelen Bash-Heredocs**: einer pro Person, jeder mit konsistentem Body (Kontext / Acceptance Criteria / Referenzen / Größe). Labels vorher mit `gh label list` verifiziert — Repo verwendet `type:bug` statt `type:fix`, `type:infra` statt `type:chore` — kein einziger Label-Validation-Fail.
  - **Rollen via PDF-Briefing statt Best-Guess aus PR-Aktivität**: Mein erster Best-Guess hatte Andrea als Quant Core eingestuft (er hat Quality-Classic-Modell #30 gebaut). Falsch: Andrea ist Platform (C), er war nur für Fabia eingesprungen, weil sie auf Spec-Arbeit war. **Lektion: bei Personen-Rollen-Zuordnungen niemals aus PR-Aktivität ableiten — sonst zementiert man Aushilfs-Arbeit als Eigen-Scope.** Erst Sheylas Briefing-PDF hat das geklärt.
- **Was nicht klappte**:
  - **Dockerfile-Bug Wochen latent unentdeckt**: `pyproject.toml` fehlte seit Phase-1-Scaffold im runtime-Stage. CI und lokales venv waren beide unsichtbar betroffen (`pyproject.toml` lag dort im PWD). Erst beim Versuch `docker compose exec backend pytest` sichtbar — und das hat vorher offenbar niemand im Team gemacht. **Heuristik**: nach jedem Foundation-Scaffold einmal die obvious-aber-unübliche Trigger durchgehen (pytest *im* Container, mypy *im* Container, alembic *im* Container von clean Checkout aus). Diese Runs decken Container-Spezifika auf, die venv und CI verstecken.
  - **DB-Migration-Mismatch beim Pull**: alte Migration `0002_create_llm_call_log` wurde upstream zu `0003` umbenannt; lokales DB-Volume hatte aber die alte 0002-Reihenfolge applied → `DuplicateTableError` beim Container-Start. Diagnose dank konkreter alembic-Logs in 2 Minuten geklärt; gelöst mit `docker compose down -v` (DB war eh leer). **Heuristik**: bei Migration-Renames im Pull-Diff direkt frische DB einplanen — Volume-Persistenz hilft hier nicht, sie schadet.
- **Lektion**:
  **Read-Only-Audit-Subagents sind unter-genutzt.** Drei parallele Agents mit klarem Cluster-Scope (Backend / Frontend / Roadmap) lieferten in ~4 Minuten Wall-Time einen synthese-fähigen Bericht mit konkreten Datei-Pfaden und Größen-Schätzungen. Seriell mit Tool-Calls im Haupt-Context wären das 30+ Minuten gewesen, und der Context wäre danach voll mit Code-Excerpts statt frei für Synthese. **Heuristik vor jedem grösseren Repo-Check**: gibt es 2–3 unabhängig prüfbare Cluster? Wenn ja, dispatche — und verlange knappe, strukturierte Reports (✅/⚠️/🔴-Markdown), keine Roh-Excerpts.
- **Methodisches Mini-Learning**: **Memories aktualisieren lohnt sich.** Alte Memory sagte „Nicolas-Handle pending"; ein `gh api .../collaborators`-Call zeigte `NicolasLardinois` aktiv. Memory updated, plus neuer Eintrag `team_roles.md` mit der ganzen A/B/C/D-Zuordnung aus dem PDF. Memory-Update kostet einmalig 30 Sekunden; Memory-Stale kostet wiederholt 5 Minuten in jeder zukünftigen Session und führt zu Best-Guess-Fehlern wie dem Andrea-=-Quant-Lapsus oben.
- **Token-Kosten**: ~150k Tokens (Opus 4.7 1M-Kontext, davon ~50k vom Audit selbst durch die drei Subagent-Reports). Geschätzt 5–7 USD.
- **Autor**: Sheyla Sampietro (mit Claude Code Opus 4.7)

## 2026-04-27 · Quant-Models-Redesign (PR #26, Commits `7f93095` bis `d62e719`)
- **Agent**: Claude Code (Opus 4.7) + 1 Recherche-Sub-Agent (claude-code-guide) für Daten-Feasibility-Check
- **Scope**: Quality AI + Anti-Cyclical aus dem MVP entfernen, Trend Momentum + Value Alpha Potential rein. Spec geschrieben (`2026-04-27-quant-models-redesign.md`, 237 Z.), ADR 0006 (90 Z.), Design-Spec/README/Frontend/Narrative-Engine/MCP-Spec konsistent durchpatcht (5 Files, 45 +/− 34), Skeleton-Domain-Code für 5 Modelle + 22 grüne / 7 skipped Tests, env-Migration `FINNHUB_API_KEY` → `FMP_API_KEY` im `.env.example`. Alles auf Feature-Branch, PR #26 für Review offen.
- **Was gut lief**:
  - Spec-First-Disziplin gehalten: nach erstem Plan-Vorschlag mehrfach iteriert (5→4→5 Modelle, FMP-Free vs. Starter, Diversification rein/raus), bevor erste Codezeile geschrieben wurde. Vier Iterationen Daten-Feasibility hatten direkten Einfluss auf den finalen Modell-Mix — Schreiben wäre ohne diese Vorarbeit Nacharbeit gewesen.
  - Sub-Agent für Recherche zu Yahoo/FMP-Tier-Limits, statt Trainingswissen zu erraten — die "FMP Free liefert kein Historical"-Erkenntnis war der entscheidende Punkt, der Quality AI gekippt hat.
  - mypy-strict + ruff im Skeleton ohne Workarounds clean — beim ersten Versuch flaggte mypy ein `# type: ignore[arg-type]`, das durch ein `model_validate({...})` ersetzt wurde (saubere Lösung statt Stummschaltung).
  - PR-Disziplin: nach Initial-Commit auf `main` korrigiert, alles auf Feature-Branch verlagert, PR mit Test-Plan und To-Do-Liste angelegt — User behielt jederzeit Review-Kontrolle.
- **Was nicht klappte**:
  1. **Erster Commit ging direkt auf `main`.** AGENTS.md §4 verlangt PR-only — Verstoss innerhalb 5 Min nach Spec-Commit. User hat's gemerkt, ich habe per `git reset --soft HEAD~1` den Commit aus `main` entfernt und auf `feat/quant-models-redesign` verschoben. Lehre: **Branch-Strategie vor erstem Commit aktiv prüfen, nicht nach gut Glück auf Default-Branch arbeiten.**
  2. **PowerShell-PATH-Falle nach `winget install gh`.** `gh.exe` lag installiert da, aber die laufende PowerShell-Session kannte den PATH-Eintrag nicht — drei Iterationen mit User, bis ich die Diagnose machte.
  3. **Daten-Feasibility-Check kam zu spät.** Die ersten zwei Konversations-Runden hätten direkt klären müssen, dass Quality AI mit FMP Free nicht geht.
  4. **`.env`-Editier-Konflikt.** Beim Migrieren der lokalen `.env` hatte der User das File parallel selbst editiert.
- **Nachbearbeitung**: keine bisher; PR ist offen, hängt an menschlichem Review.
- **Methodisches Mini-Learning**: **Spec-First spart eindeutig — aber Spec-First UND Branch-First muss als gemeinsamer Reflex sitzen.**
- **Token-Kosten**: ~120k Tokens (Opus 4.7 + 1 Sub-Agent-Call à ~12k); etwa 4 USD.
- **Autor**: Fabia Holzer (mit Claude Code)

## 2026-04-26 · #19 Implementation — Build-Steps 6-8 (PR #25, Continuation)
- **Agents**: Claude Code (Opus 4.7) im Haupt-Context für Wave 6 (LLMClient) + Wave 7 (Exception-Handler); 1 Sub-Agent (Sonnet 4.6) für Wave 8 (Admin-Endpoint, weil grösserer Scope mit 9 Files + 11 Tests). Bewusste Routing-Entscheidung: Tight-Loop-TDD bleibt im Haupt-Context, gut-spezifizierte Multi-File-Bauarbeit geht an den Subagent.
- **Scope**: Drei zusätzliche Build-Steps in derselben PR #25 statt Stacked-PR oder Self-Merge nach 2 h Review-Stille. `LLMClient`-Wrapper für Anthropic + Voyage mit chars/4-Estimation und SDK-fan-out, `BudgetCapExceeded`-FastAPI-Handler mit `Retry-After`-Header (Sekunden bis Monatswechsel UTC), `GET /api/v1/admin/costs`-Endpoint mit X-API-Key-Auth (constant-time compare) + Pydantic-Response-Schema + neue Env-Vars (`BUDGET_CAP_USD`, `BUDGET_CAP_THRESHOLD`). 86 Tests gesamt (war 75; +11 neue), Mypy + Ruff clean. PR #25 enthält jetzt Build-Steps 1-8 von 11.
- **Was gut lief**:
  - **PR-Continuation-Entscheidung**: Drei Optionen (PR erweitern / Stacked-PR / Selbst-Merge nach 2 h) explizit gegenübergestellt mit Pros/Cons, **Empfehlung formuliert** (PR erweitern, weil Andrea noch keinen Review gestartet hatte und Stacked-Komplexität bei 3 Folge-Commits nicht gerechtfertigt). Ich bestätigte. **Lektion**: bei jedem Workflow-Bruch nicht stillschweigend Default wählen, sondern Trade-Offs sichtbar machen.
  - **Subagent-Routing-Entscheidung explizit gemacht**: Waves 6-7 blieben im Haupt-Context, weil TDD-Cycles vom Tight-Loop leben (Test schreiben → Docker-Run → Code → Run, in 30-Sekunden-Cycles). Wave 8 ging an Sonnet-Subagent, weil 9 Files + Schema + Auth-Dep + zwei Test-Files in einem Wave die Main-Context-Hygiene gefährdet hätten. **Heuristik**: Main-Context = iterative Entwicklung mit Run-Feedback, Subagent = Multi-File-Bauarbeit nach klarer Vorgabe.
  - **Subagent-Prompt als Vertrag**: Der ~200-Zeilen-Prompt für Wave 8 spezifizierte alle 7 Files (Schema, Router, Dep, Config-Update, .env-Update, Wire-Up, Tests) inklusive Pydantic-Klassen-Felder, SQL-Queries-Wortlaut, Auth-Comparison-Methode, Test-Cases pro File. Subagent lieferte 86/86 Tests grün, Mypy/Ruff clean, **2 explizit dokumentierte Deviations** (von `Header(...)` auf `Header(default=None)` für 401-statt-422-Auth-Fehler; Python-side sortieren zusätzlich zu SQL-ORDER-BY für Test-Robustheit). **Beide Deviations defensiv und sinnvoll**, vom Subagent von sich aus gemeldet — genau das Verhalten, das man bei delegierten Aufgaben sehen will (transparente Abweichungen statt stille Überraschungen).
  - **Trust-but-Verify-Pattern bewährt**: Nach Subagent-Run direkt `git log` + `git diff --stat` + `pytest` + `mypy` + `ruff` als Sanity-Checks; alle grün. Keine Read-back-zu-tief-Verifikation nötig, weil die Quality-Gates objektiv sind.
- **Was nicht klappte**:
  - **Fast über die Tagesgrenze**: Implementations-Session ging deutlich länger als geplant (ursprünglich „erste 5 Build-Steps", dann Continuation auf 8). Ehrlicher: bei Spec-Implementation gibt's Sog-Effekt — wenn alles grün läuft, ist die Versuchung gross, „nur noch eine Wave" zu machen. Das ist normalerweise gut (Momentum), aber bei dichten Tagen muss bewusst gestoppt werden.
- **Lektion**:
  **Routing-Disziplin: Main-Context für TDD-Tight-Loops, Subagent für Multi-File-Bauarbeit nach klarer Vorgabe.** Beide haben einen Sweet-Spot. Wave 8 als Subagent dispatched zu haben war richtig: 9 Files in einem Subagent-Run sind effizienter als 9 sequentielle Edit-Run-Read-Cycles im Haupt-Context. Aber Waves 6-7 als Subagent zu dispatchen wäre falsch gewesen — die TDD-Cycles brauchen sofortige pytest-Run-Feedback, was Subagent-Roundtrips verzerren würde. **Heuristik**: wenn der nächste Schritt von einem Run-Output abhängt (Test-Output, Mypy-Output, Browser-State), bleib im Haupt-Context. Wenn der Schritt eine Reihe gut-definierter File-Änderungen ist die zusammen committed werden, dispatche.
- **Methodisches Mini-Learning**: Subagent-Deviations dokumentieren ist nicht „Nice-to-have", sondern essenziell für Trust-but-Verify. Ein Subagent der stille Deviations einbaut ist gefährlicher als einer der scheitert — Scheitern ist sichtbar, Stille nicht. Bei zukünftigen Subagent-Prompts explizit fordern: "Any deviations from this prompt with reasoning". Hat hier doppelt funktioniert.
- **Autor**: Sheyla Sampietro (mit Claude Code + Sonnet-Subagent für Wave 8)

## 2026-04-26 · #19 Implementation — Build-Steps 1-5 von 11 (PR #25)
- **Agent**: Claude Code (Opus 4.7), reine Main-Context-Arbeit. **Kein Subagent** dieses Mal — die TDD-Schleife (Test schreiben → in Docker laufen lassen → minimal implementieren → wieder laufen) lebt vom Tight-Loop, der Subagent-Roundtrips würde abwürgen.
- **Scope**: Erste Hälfte der Spec-Implementation: `BudgetCapExceeded` (Domain), `pricing.py` mit `ModelPricing`-Dataclass + Registry (Infrastructure), `LLMCallLogORM` SQLAlchemy-Modell + Alembic-Migration (Persistence), `CostTracker` Application-Service mit `check_cap`/`record`. 60 Tests gesamt (24 neue), alle grün, Ruff + Mypy clean, Migration mit upgrade+downgrade-Roundtrip auf Live-DB verifiziert. Folge-PR baut darauf den `LLMClient`-Wrapper, FastAPI-Handler, Admin-Endpoint + Config-Anbindung.
- **Was gut lief**:
  - **Spec-Detailgrad zahlt sich aus**: Weil PR #24 alle fünf Architektur-Entscheidungen explizit gemacht hatte (Wrapper-Pattern, Audit-Log, chars/4, Kalender-Monat UTC, 503-Mapping), gab es während der Implementation **null Design-Entscheidungen mid-flight**. Jeder Wave-Schritt war: Spec lesen → Test schreiben → run → Code → run → commit. Die Spec war Map, nicht nur Konzept.
  - **TDD-Disziplin durchgehalten**: 5 Waves × (RED → GREEN → next Wave). Bei jedem Wave wurde der Test ZUERST geschrieben, ZUERST laufen gelassen (must fail wegen ImportError oder fehlendem Modul), dann Implementation. Keine Versuchung, "schnell den Code zu schreiben, Test kommt nach". CLAUDE.md-Regel ist genau dafür da — sie ist anstrengend in dem Moment, aber das resultierende Vertrauen ist real.
  - **Mock vs Real-DB-Pragmatik**: Boundary-Tests von `check_cap` via Monkey-Patch von `_current_month_usd` waren die richtige Wahl — schnell, präzise, isoliert. Eine echte DB-Test-Fixture wäre für 6 Boundary-Cases Overkill gewesen. Die SUM-SQL-Roundtrip-Verifikation kommt im Folge-PR mit den anderen DB-touching Tests.
  - **Migration smoke-test mit downgrade-Roundtrip**: `alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` — das Drei-Schritt-Muster fängt asymmetrische Migrationen (upgrade funktioniert, downgrade ist kaputt) sofort. Standard-Practice, aber leicht zu vergessen wenn man's eilig hat.
- **Was nicht klappte**:
  - **Pyproject.toml-im-Container-Issue erkannt aber nicht gefixt**: Die Tests im Container müssen mit `-o asyncio_mode=auto` aufgerufen werden, weil die Pytest-Config aus `pyproject.toml` nicht greift (Dockerfile mounted nur `backend/`, nicht den Repo-Root). CI ist davon nicht betroffen (installiert via `pip install -e .[dev]`). **Bewusste Scope-Disziplin**: bug erkannt, in PR-Body geflaggt, aber nicht in dieser PR gefixt — sonst wird's ein PR über zwei Themen.
  - **Pricing-Werte sind Best-Estimate**: Sonnet 4.6 ($3/$15), Haiku 4.5 ($1/$5), Voyage-3-large ($0.18) — aus Training-Daten erinnert, nicht live verifiziert gegen `https://www.anthropic.com/pricing` und `https://docs.voyageai.com/docs/pricing`. Im Modul-Docstring + Commit-Message als verifikations-pflichtig markiert. Die Architektur ist davon unberührt; nur das Single-Source-of-Truth-Constant muss vor Production-Deploy gegengeprüft werden.
- **Lektion**:
  **Spec-Qualität bestimmt Implementations-Tempo direkt.** Die Wave-Geschwindigkeit (5 Waves in einer Session, jede mit RED-GREEN-Zyklus + Tests + Lint + Commit) war nur möglich, weil PR #24 jede Architektur-Entscheidung **vorab** geschlossen hatte. Hätte die Spec irgendwo "TBD" oder vage Optionen offen gelassen, wäre jeder Wave eine Mini-Brainstorming-Session geworden. Heuristik: **wenn die Spec den nächsten Wave nicht in 3 Sätzen klar macht, ist die Spec nicht fertig — schreib sie zuerst zu Ende, sonst zahlst du den Preis 5× während der Implementation**.
- **Methodisches Mini-Learning**: Container-/CI-Asymmetrien explizit notieren statt zu fixen. Das `pyproject.toml`-im-Container-Issue ist ein klassischer Yak-Shaving-Trigger — "ich fix das schnell" wird zu zwei Stunden Dockerfile-Debug. Stattdessen: in PR-Body geflaggt, separater Issue-Kandidat, weiter mit Hauptaufgabe.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-04-25 · Spec für Issue #19 — Budget-Cap & Cost-Tracking (PR #24)
- **Agents**: Claude Code (Opus 4.7) im Haupt-Context für strukturiertes Brainstorming + Verifikation + Git-Flow; 1 Sub-Agent (Sonnet 4.6) für die 643-zeilige Spec-Schreibarbeit. Gleiches Routing-Pattern wie bei ADR-0005, bewährt.
- **Scope**: Implementations-Spec für das Budget-Cap-Feature aus ADR-0004 §7. Q-by-Q-Brainstorming durch fünf Architektur-Entscheidungen: (1) Wrapper-Client vs. expliziter Guard-Block, (2) Audit-Log vs. aggregierter Counter, (3) chars/4-Estimation vs. SDK-`count_tokens`, (4) Kalender-Monat UTC vs. Rolling-30-Days, (5) HTTP-503 vs. 402/429. Pro Frage: Optionen mit +/- gegenübergestellt, Empfehlung markiert, Sheyla wählte. Spec dann an Sonnet-Subagent delegiert mit kompletter Vorab-Spezifikation aller fünf Entscheidungen + Section-Outline + Style-Referenzen.
- **Begleitende Team-Hygiene heute (kein eigener Eintrag)**: PR #9 (Andreas erster PR, 4 Tage offen) reviewed + approved + gemergt; PR #23 (ADR-0005, 3 Tage Review-Stille) selbst gemergt; Issue #16 (CORS-Tightening) selbst im Render-Dashboard erledigt + dokumentiert geschlossen; #22 auto-closed via PR-23-Merge.
- **Was gut lief**:
  - **Ein-Frage-pro-Turn-Disziplin**: keine Wall-of-Decisions. Nach jeder Frage hat Sheyla die Implikation wirklich verstanden und konnte begründet wählen statt zu nicken. Die Disziplin der Brainstorming-Skill — fragmentieren statt batchen — erzwingt gründliches Nachdenken auf beiden Seiten.
  - **Subagent-Prompt-Qualität als Filter für eigenes Denken**: Bevor ich den Sonnet-Subagent dispatchen konnte, musste ich alle fünf Entscheidungen + Section-Outline + Style-Regeln in einen ~80-Zeilen-Prompt packen. Wo der Prompt vage wurde, war meine eigene Architektur-Klarheit unzureichend. Das Schreiben des Prompts war damit selbst die letzte Designschicht — der Subagent musste nichts mehr „designen", nur dokumentieren.
  - **Spec-Output direkt implementierbar**: keine TBDs, keine offenen Fragen, alle Mermaid-Diagramme korrekt, SQL exakt, Decimal-für-Geld durchgehend, Build-Order mit expliziten Abhängigkeiten. Sheyla muss nicht in einer zweiten Iteration nachschärfen.
  - **Datums-Konventions-Korrektur durch Sheyla**: sie hat gemerkt, dass die alten Phase-3-Specs mit Future-Datum (`2026-04-28-*`) falsch benannt waren — Files wurden am 21./22. April geschrieben, nicht am 28. Statt blind weiter mit dem falschen Pattern, hat sie hinterfragt. Resultat: heute → real-date-Konvention etabliert, alte Files unbenannt belassen (Rename = Commit-Noise für 0 Funktionalitäts-Gewinn). Genau die Art „Konvention bewusst dokumentieren statt implizit ererben"-Moment.
- **Was nicht klappte**:
  - **Falsche Datums-Konvention vier Tage durchgerutscht**: hätte beim allerersten Phase-3-Spec auffallen müssen. Der heutige Diskussionsmoment war ein Glücksfall — ohne Sheylas Frage hätten wir den Fehler unbemerkt fortgepflanzt. Heuristik: bei jedem Datei-Naming-Pattern aktiv prüfen, ob das Datum die Erstellung oder eine geplante Zukunft beschreibt; nur Erstellung ist git-konsistent.
- **Lektion**:
  **Strukturiertes Brainstorming dominiert „direkt drauflos schreiben".** Nach den fünf Entscheidungs-Frage-Runden hatte die Spec keine versteckten Annahmen, keine vagen Stellen, keine Design-Holes. Der Subagent musste nicht „kreativ" sein. Das ist der Unterschied zwischen einem Spec-Draft, der noch eine zweite Iteration braucht, und einem, der direkt in einen Implementations-Plan überführbar ist. **Heuristik**: vor jedem Subagent-Dispatch alle Architektur-Entscheidungen explizit gemacht haben. Wenn man dem Agent keinen klaren Auftrag formulieren kann, ist das eigene Denken noch nicht fertig — der Subagent ist hier ein Lackmustest.
- **Methodisches Mini-Learning**: Frage-pro-Turn ist nicht „nett zum User" — sondern Pflicht-Tool gegen die eigene Versuchung, die Spec gleich zu schreiben statt sie erst durchzudenken. Die Geduld zahlt sich exponentiell aus, je grösser die Spec — bei 643 Zeilen wäre eine zweite Iteration teurer gewesen als die fünf Frage-Runden zusammen.
- **Autor**: Sheyla Sampietro (mit Claude Code + Sonnet-Subagent)

## 2026-04-22 · ADR-0005 — Datenquelle für Quant-Fundamentaldaten (PR #23, Closes #22)
- **Agents**: Claude Code (Opus 4.7) im Haupt-Context für Brainstorming, Verifikation und Git-Flow; 1 Sub-Agent (Sonnet 4.6) für die reine ADR-Schreibarbeit.
- **Scope**: Entscheidungsprozess für die Fundamentaldaten-Quelle der 8 Quality-Classic-Metriken. Brainstorming von 4 Optionen (yfinance-live / CSV-only / Hybrid / Alpha-Vantage-oder-Finnhub), Wahl des Hybrid-Ansatzes (committed CSV-Snapshot als Wahrheit + yfinance-Adapter nur für manuellen Pre-Presentation-Refresh). Schreiben von `docs/adr/0005-data-source-quant-fundamentals.md` im bestehenden ADR-Stil, minimale Klarstellung in §13 des Haupt-Design-Dokuments, PR mit Fabia + Andrea als Reviewer. Begleitet von Wechsel von direct-to-main auf PR-Flow (Phase-1-Infra-Firefighting-Modus ist vorbei, jetzt hat das Team Review-Verantwortung).
- **Was gut lief**:
  - **Model-Routing bewusst gesetzt**: Opus 4.7 führte die Trade-off-Analyse und das Spec-Navigieren (Kontext aus 681-Zeilen-Haupt-Spec + Issue-Rationale synthetisieren). Die reine Template-gehorsame Schreibarbeit — ein ADR nach dem exakten Muster von 0001/0002 verfassen — wurde an einen Sonnet-Subagent delegiert. Das senkte den Token-Footprint im Haupt-Context merklich und hielt die Aufmerksamkeit für die Review-Entscheidung frei.
  - **Trust-but-Verify nach Subagent-Run**: Vor dem Commit wurden das generierte ADR und der Diff der §13-Änderung gelesen. Keine Halluzinationen, Format exakt an den Vorbildern, Paragraph-Insertion minimal-invasiv.
  - **Brainstorming-Disziplin**: 4 Optionen wurden mit +/- bewertet bevor eine empfohlen wurde — Benutzerin konnte A/B/C einfach abwägen und C auswählen, kein "hier ist meine Einzellösung, nimm oder lass"-Fallstrick.
- **Was nicht klappte**:
  - **Verdeckte Spec-Inkonsistenz wurde erst beim Lesen sichtbar**: §13 des Haupt-Design-Dokuments setzte `yfinance` als primäre Laufzeit-Quelle voraus, Issue #22 empfahl aber explizit einen CSV-Snapshot. Diese Spannung hätte schon bei der Issue-Erstellung auffallen können. Retroaktive §13-Klarstellung war die Konsequenz — nicht tragisch, aber ein Hinweis, dass Specs und Issues konsistent-gehalten werden müssen, wenn beide Design-Aussagen treffen.
- **Lektion**:
  **Model-Routing ist eine reale AI-Engineering-Disziplin.** Reasoning-dichte Arbeit (Options-Abwägung, Risiko-Analyse, Kontext-Synthese) bleibt beim grösseren Modell. Template-gehorsame Schreibarbeit nach bestehendem Muster wird an ein kleineres Modell delegiert. Der Punkt ist nicht primär Kostenersparnis, sondern **Kontext-Hygiene**: der Haupt-Context behält Platz für die Entscheidungen, die wirklich Urteil brauchen. Dieselbe Split-Logik spiegelt PRISMAs eigenes Narrative-Layer-Design wider (AnalystAgent vs. SynthesizerAgent aus dem Multi-Agent-Spec) — das Werkzeug-Muster matched das Produkt-Muster.
- **Methodisches Mini-Learning**: Beim Wechsel von direct-to-main auf PR-Flow den Trigger-Punkt explizit machen. Hier: sobald das Team zugewiesene Issues hat und der Code-/Design-Change ihre Arbeit beeinflusst, ist der PR-Review-Loop nicht nur Hygiene sondern Team-Dependency-Management. Die Grenze sauber zu benennen schützt davor, aus Bequemlichkeit weiter direkt auf `main` zu schieben.
- **Autor**: Sheyla Sampietro (mit Claude Code + Sonnet-Subagent)

## 2026-04-21 · Render-Deployment Phase 1 — 4 Commits bis End-to-End-grün (Commits `7b2de04` bis `87e2407`)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: Blueprint-basiertes Deployment (DB + Backend + Frontend) auf Render's Free-Tier. Vier aufeinanderfolgende Produktions-Deploy-Versuche, drei davon an Details der Render-Plattform gescheitert bevor der Fourth Green wurde.
- **Was gut lief**:
  - Die Render-Logs waren in jedem Fehlerfall konkret genug, um die Root-Cause nach einmal Lesen zu isolieren — kein rätselhaftes "works on my machine"-Debugging nötig.
  - DATABASE_URL-Scheme-Rewrite via pydantic-Validator (`postgresql://` → `postgresql+asyncpg://`) war proaktiv eingebaut — sonst wäre ein fünfter Deploy-Cycle nötig gewesen.
  - Commit-Disziplin blieb trotz Zeitdruck sauber: ein Fix pro Commit, aussagekräftige Messages, nichts gebündelt.
- **Was nicht klappte — drei Render-spezifische Stolpersteine**:
  1. **`preDeployCommand` ist Paid-Tier-only** — der Agent hat das Field gesetzt um Alembic-Migrationen vor dem App-Start zu triggern, aber Render's Blueprint-Validator hat den Deploy sofort abgelehnt: "preDeployCommand is not supported on free plan". Fix: Migrations inside Container-Start-Sequence.
  2. **`dockerCommand: "sh -c 'alembic upgrade head && exec uvicorn ...'"` exit 127 "not found"** — Render's YAML-Parser übergibt den gesamten String als EINEN argv-Eintrag (nicht wie die Shell `sh -c` + zwei weitere Args). Docker sucht dann nach einem Executable namens `sh -c 'alembic …'` (mit Leerzeichen im Namen) und findet es natürlich nicht. **Fix**: Start-Sequenz in ein `scripts/backend-start.sh` auslagern und nur ein `CMD ["/app/backend-start.sh"]` im Dockerfile — dann ist der argv-Split wieder sauber. Render wollte gar kein `dockerCommand`-Override mehr.
  3. **`NEXT_PUBLIC_API_URL` via `fromService.property: host` liefert nur den Hostname — ohne `https://`** — das Frontend lud, aber der Backend-Badge zeigte HTTP 404. Ursache: Der Client-Code machte `${API_BASE_URL}${path}` = `"prisma-backend-7ai7.onrender.com/health"`. Der Browser interpretiert eine schemelose URL als *relativen Pfad* → Request ging an `https://prisma-frontend-jrto.onrender.com/prisma-backend-7ai7.onrender.com/health` → 404. Render bietet keine "scheme prepend"-Option für `fromService`. **Fix**: Backend-URL hardcoden (`value: https://prisma-backend-7ai7.onrender.com`). Einmalig ungünstig, aber semantisch klar — und `NEXT_PUBLIC_*` wird bei Next.js sowieso Build-Time in das Bundle gebacken, d.h. dynamische Service-Refs helfen hier architektonisch nichts.
- **Nachbearbeitung nötig bei**:
  - `render.yaml` (3 × iteriert)
  - neues `scripts/backend-start.sh` als einziger Start-Sequence-Ort
  - `Dockerfile.backend` auf `CMD ["/app/backend-start.sh"]`
- **Lektion**:
  **PaaS-Plattformen haben viele implizite Einschränkungen, die der Agent aus seinem Trainings-Wissen nicht alle kennt.** Tier-Limits, Argv-Parsing-Quirks, Primitives die nur Teile einer URL liefern — diese sind dokumentiert, aber nicht in "einen typischen `render.yaml`"-Beispielen im Trainingscorpus. **Heuristik**: Bei jedem Deploy-Config-Feld mental fragen "was passiert wenn Render das wörtlich so interpretiert?" und "welche Tier-Stufe brauche ich dafür?". Gerade Shell-Semantik-Illusion in YAML-Strings (`dockerCommand: "sh -c '...'"`) ist ein wiederkehrender Fallstrick — **immer als Array-Form oder Script-Datei schreiben, nie als inline-Shell-String**.
- **Methodisches Mini-Learning**: Bei undurchsichtigen PaaS-Bugs ist die schnellste Diagnose-Frage nicht "was ist falsch?" sondern "was genau reicht Render hier ins Child-Process weiter?". Im Zweifel stdout/stderr direkt lesen statt Hypothesen bauen — die Render-Logs haben in allen drei Fällen den korrekten Hint direkt ausgegeben.
- **Autor**: Sheyla Sampietro (mit Claude Code)

## 2026-04-21 · CI stabilisieren — 5 Commits bis grün (Commits `74c558a` bis `78ee56d`)
- **Agent**: Claude Code (Opus 4.7) mit Sub-Agent-Unterstützung beim initialen Scaffold
- **Scope**: Nach dem Foundation-Commit fiel die GitHub-Actions-CI mehrfach um. Ich arbeitete mich durch 5 aufeinanderfolgende Fix-Commits (Backend-Lint → Backend-Format → Frontend-Pfad-Alias → Mypy-Ignore-Komm. → **eigentliche Root-Cause**: fehlende Files im Git).
- **Was gut lief**: 
  - Jeder Fix wurde lokal verifiziert, bevor gepusht wurde (docker compose exec + `ruff check` + `npm run build`)
  - AI-USAGE.md-Eintrag parallel zur Debug-Arbeit gepflegt → Lernschleife während der Reparatur, nicht erst danach
  - Systematisches Vorgehen: CI-Logs lesen → Fehler isoliert reproduzieren → fix → push → beobachten
- **Was nicht klappte — die eigentliche Lektion**:
  Mehrere CI-Runs zeigten `Module not found: Can't resolve '@/lib/utils'` im Frontend. Der **offensichtlich** wirkende Fix war `baseUrl: "."` in `tsconfig.json` zu ergänzen (Next.js path-alias-Konvention). Das stimmte auch — aber der Bug blieb! Erst beim manuellen Reproduzieren mit `docker run node:20-alpine npm run build` — das lokal GRÜN lief — wurde klar: **die Files existierten gar nicht im Git**. Ursache: Der Agent hatte beim Initial-Scaffold einen Python-Template-`.gitignore` generiert. Die Regel `lib/` matched nicht nur das erwartete Python-Build-Directory, sondern auch `frontend/lib/` — und hat damit `utils.ts`, `api/client.ts`, `api/health.ts` silent aus dem Repo geschluckt. Lokal alles OK (Files auf Disk), CI tot (cloned Repo ohne Files).
- **Nachbearbeitung nötig bei**:
  - `.gitignore`: `lib/` → `/lib/` scopen (Root-only); gleiches für `lib64/`
  - `git add frontend/lib/` um bisher ignorierte Files endlich zu committen
  - 2 unused `# type: ignore` Kommentare in Tests entfernen (mypy-strict flaggt sie)
  - 3 Files mit neuerer Ruff-Version nachformatieren
- **Lektion**:
  **AI-generierte Config-Files (`.gitignore`, `.dockerignore`, `.eslintignore`) sind typischerweise Templates, die kontextblind für Subdirectories sind.** Wenn das Projekt mehrere Sprachen/Stacks hat, prüfe jede Regel: matched sie wirklich nur was gemeint war? Die Kosten der Blindheit waren hier 3 Fehldiagnosen + rund 30 Minuten Debugging, bevor ich aufs wirkliche Problem kam. Gute Heuristik für künftige Reviews: **bei Multi-Language-Repos `.gitignore`-Regeln bewusst scopen** (mit führendem `/` für Root-only, oder mit expliziten Pfadpräfixen).
- **Methodisches Mini-Learning**: *Lokal grün, CI rot* = fast immer eine Environment-Diskrepanz. Statt am Code zu zimmern, zuerst prüfen: (1) ist derselbe Code wirklich committed? (2) wird derselbe Stand geclont? (3) ist dieselbe Tool-Version aktiv? Die Versuchung, "einfach noch einen Fix" zu pushen statt die Diskrepanz zu isolieren, hat mich hier 2 Commits gekostet.
- **Autor**: Sheyla Sampietro (mit Claude Code)

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

## 2026-04-27 · Early Implementation Sprint — Domain, Modelle, REST, Docs (PRs #27–#33) ⟨retrospektiv⟩
- **Agent**: Claude Code (Modell unbekannt, retrospektiv rekonstruiert aus Git-History)
- **Scope**: 7 PRs am selben Tag — das Kern-Fundament des PRISMA-Backends und der ersten Dokumentation:
  - **#27** `docs/getting-started.md` — Schritt-für-Schritt-Setup-Guide (Voraussetzungen, Clone, venv, Docker, Verify)
  - **#28** Domain-Modell: `Universe`, `WeightConfig`, `RankingRun`-Aggregate mit Status-Lifecycle, Repository-Interfaces, SQLAlchemy-Implementierungen, Alembic-Migration
  - **#29** `scripts/seed_demo_universe.py` — idempotentes Seed-Script für "Demo-US-5" (AAPL/MSFT/GOOGL/NVDA/JPM)
  - **#30** `QualityClassicModel.run()` — 8 Kennzahlen, Z-Score-Normalisierung, fehlende Daten robust behandelt
  - **#31** `RankingAggregator` — gewichteter Total-Rank, Sweet-Spot-Detection (Top-25% in ≥3/5 Modellen), Weight-Redistribution bei fehlenden Modellen
  - **#32** Spec für alle 5 MVP-Quant-Modelle (Formeln, yfinance-Fields, Edge-Cases, Test-Approach)
  - **#33** REST-Endpoints: `POST /api/v1/runs`, `GET /api/v1/runs/{id}`, `GET /api/v1/runs/{id}/rankings` + Migration 0004 + `FundamentalsProvider`-Port + Stub
- **Was gut lief**: In einem Tag wurde das komplette Quant-Backend auslieferbar — Domain, Persistence, Berechnung, API. Die Spec (#32) wurde nach Implementierung der ersten Modelle geschrieben (unideal, aber bei frühem Prototyping pragmatisch). `RankingAggregator`-Sweet-Spot-Heuristik (≥3/5 Modelle Top-25%) erwies sich als stabil für die gesamte Projektlaufzeit.
- **Was nicht klappte**: Retrospektiv nicht vollständig rekonstruierbar. Spec-First-Konvention (#32 nach #30/#31) wurde in diesem Sprint nicht eingehalten — Quant-Spec entstand nach der Implementation statt davor. Wurde in späteren PRs konsequenter umgesetzt.
- **Nachbearbeitung nötig bei**: Modelle Alpha, Trend Momentum, Value Alpha Potential, Diversification waren zu diesem Zeitpunkt noch offen (in #32 als "noch offen" markiert).
- **Lektion**: **Spec-First zahlt sich aus, auch wenn es in frühen Sprints verführerisch ist, Code-First zu gehen.** Die nachträglich geschriebene Quant-Spec (#32) korrigierte einige Formeln gegenüber der ersten Implementierung — bei strenger Spec-First-Disziplin wären diese Korrekturen nie als Commits nötig gewesen.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-12 · fix(frontend): Rankings nav-link /universes → /rankings (#51)
- **Agent**: Claude Code (Sonnet 4.6) — superpowers:writing-plans + inline Execution
- **Scope**: Issue #51 behoben: falscher `href='/universes'` im Rankings-Nav-Link korrigiert, Route-Konstanten in `lib/routes.ts` zentralisiert, Placeholder-Seite `/rankings` erstellt.
- **Was gut lief**: Plan + Exploration via parallele Explore-Agents war effizient — Dateipfad und Bug-Zeile wurden sofort identifiziert. AskUserQuestion half, zwei Ansätze (Href-Fix vs. Disabled+Tooltip) strukturiert mit dem User zu klären, bevor Code entstand. Alle 3 Commits + PR in einem Rutsch.
- **Was nicht klappte**: `npx tsc --noEmit` liess sich im Claude-Code-Shell-Kontext nicht ausführen (Node.js nicht im PATH der Git-Bash-Shell). TypeScript-Check muss via CI verifiziert werden.
- **Nachbearbeitung nötig bei**: CI-Ergebnis des PRs abwarten; falls tsc-Fehler auftauchen, `frontend/lib/routes.ts` Import-Pfade prüfen.
- **Autor**: Nicolas Lardinois (mit Claude Code)

## 2026-04-21 · Initial Scaffold (#0)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: Komplettes Repo-Scaffolding: Clean-Architecture-Ordnerstruktur, AGENTS.md/CLAUDE.md, CONTRIBUTING.md, .gitignore, ADR-0001 (Tech-Stack), Design-Spec (681 Zeilen) via documentation-engineer Sub-Agent, GitHub-Repo-Erstellung, Branch-Protection, Scrum-Setup.
- **Was gut lief**: Parallele Ausführung von Schreibvorgängen und Git-Operationen sparte merklich Zeit. Sub-Agent für die Design-Spec hat sauber strukturiert und alle Scope-Entscheidungen aus dem Brainstorming festgehalten. Conventional-Commits und Co-Authored-By-Footer konsistent gesetzt.
- **Was nicht klappte**: Erster `gh api`-Call für Branch Protection schlug an Type-Coercion fehl; JSON-Body via stdin war der saubere Workaround. Kein inhaltlicher Fehler, nur API-Syntax-Stolperer.
- **Nachbearbeitung nötig bei**: Noch keine.
- **Autor**: Sheyla Sampietro (mit Claude Code)

<!-- Neue Einträge oben an die Liste anfügen. -->

## 2026-05-26 · RAG-Kontext in NarrativeService + CI-Debugging (Issues #138, PR #146)
- **Agent**: Claude Code (Sonnet 4.6) — systematic-debugging skill
- **Scope**: Issue #138 DoD: NarrativeService.generate_memo() ruft RetrievalService.retrieve() auf, bettet 3–5 SEC-Filing-Chunks als `rag_context` in den LLM-Prompt ein. DI-Chain verdrahtet RetrievalService wenn VOYAGE_API_KEY gesetzt; graceful degradation bei Fehler. Gleichzeitig: 6 CI-Runs debuggt bis PR #146 grün war.
- **Was gut lief**: NarrativeService-Integration war bereits vollständig implementiert (Konstruktor-Parameter, Prompt-Template-Block, Unit-Tests, DI-Chain) — durch sorgfältiges Code-Reading vor dem Plan-Schreiben entdeckt. systematic-debugging Skill verhinderte blinden 6. Fix-Versuch.
- **Was nicht klappte**: CI hat 5× gefailed (vorherige Session) ohne Root-Cause-Analyse. In dieser Session: Root Cause systematisch isoliert — 3 unabhängige Schichten: (1) Test-Kontamination durch `test_embedding_repository.py` ohne Cleanup-Fixture, (2) pgvector NaN-Similarity bei Zero-Vektor-Mock `[0.0]*2048`, (3) Singleton-Engine hält asyncpg-Connections über pytest-function-Event-Loops → `RuntimeError: Task got Future attached to a different loop`.
- **Lektion**: **Wenn CI 3+ Mal failt: sofort Root-Cause analysieren, nicht weiterfixen.** `systematic-debugging` Skill erzwingt diesen Stop. Konkrete Werkzeuge: `gh run view --log-failed` zeigt exakte Fehlerzeilen; `git log --oneline` im CI-Log zeigt Test-Ausführungsreihenfolge; dann Hypothese → minimaler Fix → verifizieren. NullPool-Pattern für async SQLAlchemy in pytest ist Standard — `asyncio_default_test_loop_scope=function` + Singleton-Engine = cross-loop Bug.
- **Autor**: Andrea Petretta (mit Claude Code)

## 2026-05-26 · RAG-Pipeline Slice 2+3 (Issue #18)

- **Agent**: Claude Code (Haiku 4.5 + Subagent-Driven-Development)
- **Scope**: 17-Task Implementation: Domain-Dataclass → RetrievalService → REST-Endpoint → 15 Tests + Ingestion-Script
- **Was gut lief**: Erkannt dass Slice 1 >50% Infra bereits lieferte. Focused auf fehlende Teile. TDD natural. Subagent-Driven mit fresh context pro Task optimal für unabhängige Tasks.
- **Was nicht klappte**: Anfängliches Code-Reading zu spät. Initial Branch-Organisation (commits auf falschen Branch). Ingestion-Script nur Stub-Level.
- **Nachbearbeitung nötig bei**: Voyage-API-Integrationstests, Postgres halfvec-Casting robustness, E2E-Smoke gegen echtes EDGAR.
