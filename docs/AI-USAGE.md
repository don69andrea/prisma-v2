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

## 2026-04-25 · Spec für Issue #19 — Budget-Cap & Cost-Tracking (PR #24)
- **Agents**: Claude Code (Opus 4.7) im Haupt-Context für strukturiertes Brainstorming + Verifikation + Git-Flow; 1 Sub-Agent (Sonnet 4.6) für die 643-zeilige Spec-Schreibarbeit. Gleiches Routing-Pattern wie bei ADR-0005, bewährt.
- **Scope**: Implementations-Spec für das Budget-Cap-Feature aus ADR-0004 §7. Q-by-Q-Brainstorming durch fünf Architektur-Entscheidungen: (1) Wrapper-Client vs. expliziter Guard-Block, (2) Audit-Log vs. aggregierter Counter, (3) chars/4-Estimation vs. SDK-`count_tokens`, (4) Kalender-Monat UTC vs. Rolling-30-Days, (5) HTTP-503 vs. 402/429. Pro Frage: Optionen mit +/- gegenübergestellt, Empfehlung markiert, Sheyla wählte. Spec dann an Sonnet-Subagent delegiert mit kompletter Vorab-Spezifikation aller fünf Entscheidungen + Section-Outline + Style-Referenzen.
- **Begleitende Team-Hygiene heute (kein eigener Eintrag)**: PR #9 (Andreas erster PR, 4 Tage offen) reviewed + approved + gemergt; PR #23 (ADR-0005, 3 Tage Review-Stille) selbst gemergt; Issue #16 (CORS-Tightening) selbst im Render-Dashboard erledigt + dokumentiert geschlossen; #22 auto-closed via PR-23-Merge.
- **Was gut lief**:
  - **Ein-Frage-pro-Turn-Disziplin**: keine Wall-of-Decisions. Nach jeder Frage hat Sheyla die Implikation wirklich verstanden und konnte begründet wählen statt zu nicken. Die Disziplin der Brainstorming-Skill — fragmentieren statt batchen — erzwingt gründliches Nachdenken auf beiden Seiten.
  - **Subagent-Prompt-Qualität als Filter für eigenes Denken**: Bevor ich den Sonnet-Subagent dispatchen konnte, musste ich alle fünf Entscheidungen + Section-Outline + Style-Regeln in einen ~80-Zeilen-Prompt packen. Wo der Prompt vage wurde, war meine eigene Architektur-Klarheit unzureichend. Das Schreiben des Prompts war damit selbst die letzte Designschicht — der Subagent musste nichts mehr „designen", nur dokumentieren.
  - **Spec-Output direkt implementierbar**: keine TBDs, keine offenen Fragen, alle Mermaid-Diagramme korrekt, SQL exakt, Decimal-für-Geld durchgehend, Build-Order mit expliziten Abhängigkeiten. Sheyla muss nicht in einer zweiten Iteration nachschärfen.
  - **Datums-Konventions-Korrektur durch Sheyla**: sie hat gemerkt, dass die alten Phase-3-Specs mit Future-Datum (`2026-04-28-*`) falsch benannt waren — Files wurden am 21./22. April geschrieben, nicht am 28. Statt blind weiter mit dem falschen Pattern, hat sie hinterfragt. Resultat: heute → real-date-Konvention etabliert, alte Files unbenannt belassen (Rename = Commit-Noise für 0 Funktionalitäts-Gewinn). Genau die Art „Konvention bewusst dokumentieren statt implizit ererben"-Moment, die in die 40%-Achse einzahlt.
- **Was nicht klappte**:
  - **Falsche Datums-Konvention vier Tage durchgerutscht**: hätte beim allerersten Phase-3-Spec auffallen müssen. Der heutige Diskussionsmoment war ein Glücksfall — ohne Sheylas Frage hätten wir den Fehler unbemerkt fortgepflanzt. Heuristik: bei jedem Datei-Naming-Pattern aktiv prüfen, ob das Datum die Erstellung oder eine geplante Zukunft beschreibt; nur Erstellung ist git-konsistent.
- **Lektion (für die 40%-Achse)**:
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
- **Lektion (für die 40%-Achse)**:
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
- **Lektion (wichtig für die 40%-Achse)**:
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
- **Lektion (wichtig für die 40%-Achse)**:
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

## 2026-04-21 · Initial Scaffold (#0)
- **Agent**: Claude Code (Opus 4.7)
- **Scope**: Komplettes Repo-Scaffolding: Clean-Architecture-Ordnerstruktur, AGENTS.md/CLAUDE.md, CONTRIBUTING.md, .gitignore, ADR-0001 (Tech-Stack), Design-Spec (681 Zeilen) via documentation-engineer Sub-Agent, GitHub-Repo-Erstellung, Branch-Protection, Scrum-Setup.
- **Was gut lief**: Parallele Ausführung von Schreibvorgängen und Git-Operationen sparte merklich Zeit. Sub-Agent für die Design-Spec hat sauber strukturiert und alle Scope-Entscheidungen aus dem Brainstorming festgehalten. Conventional-Commits und Co-Authored-By-Footer konsistent gesetzt.
- **Was nicht klappte**: Erster `gh api`-Call für Branch Protection schlug an Type-Coercion fehl; JSON-Body via stdin war der saubere Workaround. Kein inhaltlicher Fehler, nur API-Syntax-Stolperer.
- **Nachbearbeitung nötig bei**: Noch keine.
- **Autor**: Sheyla Sampietro (mit Claude Code)

<!-- Neue Einträge oben an die Liste anfügen. -->
