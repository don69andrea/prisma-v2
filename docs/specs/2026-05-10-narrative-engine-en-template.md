# Spec: Narrative Engine — EN-Template aktivieren (AI Layer 1, Folge-Slice)

**Status**: Draft v1.0 — 2026-05-10
**Rolle**: B — AI Engineer (Sheyla)
**Parent-Spec**: `docs/specs/2026-04-28-narrative-engine.md` §2 (Sprach-Architektur-Notiz)
**Vorgänger-Slices**:
- `docs/specs/2026-05-04-narrative-engine-single-memo.md` (Single-Memo, PR #64)
- `docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md` (Multi-Memo Batch, PR #70)

---

## Inhaltsverzeichnis

1. [Zweck & Nutzerwert](#1-zweck--nutzerwert)
2. [Scope](#2-scope)
3. [Architektur-Überblick](#3-architektur-überblick)
4. [Template-Strategie](#4-template-strategie)
5. [Service-Änderungen](#5-service-änderungen)
6. [Test-Strategie](#6-test-strategie)
7. [Real-API-Smoke](#7-real-api-smoke)
8. [Akzeptanz-Kriterien](#8-akzeptanz-kriterien)
9. [Bewusste Abweichungen](#9-bewusste-abweichungen)
10. [Risiken](#10-risiken)
11. [Offene Entscheidungen](#11-offene-entscheidungen)
12. [Änderungshistorie](#12-änderungshistorie)

---

## 1. Zweck & Nutzerwert

> **TL;DR (Reviewer):** Master-Spec sagt seit 2026-04-21 „Architektur ist bilingual vorbereitet, EN-Aktivierung <2h Arbeit". Diese Slice löst das ein. Demonstriert die bilinguale Architektur in Action — gleicher Input, andere Sprache, identische Schema-Struktur.

Die Narrative-Engine ist seit der Foundation-Slice (PR #54) bilingual vorbereitet: `ResearchMemo`-Entity hat ein `language`-Feld, ORM hat eine entsprechende Spalte, der `NarrativeService` nimmt einen `language: Literal["de", "en"]`-Parameter. Single-Memo (PR #64) und Multi-Memo-Batch (PR #70) haben den Pfad gebaut — aber hardgecoded auf `language="de"` via expliziter `NotImplementedError`-Guards, weil das EN-Template ein Stub ist.

Diese Slice füllt den EN-Template-Stub und entfernt die Guards.

**Wert für die 40%-AI-Achse**:
- Disziplin Spec vor Code von Anfang an (bilinguale Architektur seit Master-Spec) wird **eingelöst** — nicht nur dokumentiert, sondern produktiv funktional.
- Demonstriert das Pattern „Architektur-Vorbereitung bezahlt sich aus": <2h von Stub zu live, weil die Schiene bereits liegt.
- Liefert ein konkretes Demo-Szenario: dasselbe Stock (NESN), zwei Sprachen, identisches Schema → die LLM-Schicht ist eine austauschbare Komponente, nicht das Produkt.

**Kein Production-Use-Case**: Diese Slice adressiert *keinen* echten Endnutzer-Bedarf. Es ist eine Architektur-Komplettierung. UI-i18n bleibt Stretch-Goal (Frontend-Track).

---

## 2. Scope

> **TL;DR (Reviewer):** In: 1:1-Übersetzung beider Templates, beide Guards entfernen, Tests + 1× Real-API-Smoke. Out: lokalisierte Few-Shot-Beispiele, Frontend-Sprach-Switcher, EN-spezifische Schema-Constraints.

### In Scope

- **System-Template `narrative_system.en.md.j2`** — 1:1-Übersetzung des DE-Templates: alle 5 Modelle, 4 Kategorien, Sweet Spot, Rang-zu-Sprache-Mapping (englische Begriffe), Confidence-Levels, Ton-Vorgaben, Disclaimer, Output-Format-Hinweise, Few-Shot-Beispiel mit NESN-Daten. Keine Lokalisierung.
- **User-Template-Aufteilung**: `narrative_user.md.j2` per `git mv` umbenannt zu `narrative_user.de.md.j2`, neue Variante `narrative_user.en.md.j2` mit englischen Labels (`STOCK / RANKINGS / AGGREGATION / Total Rank / Quant Sweet Spot / used weights / not specified / unknown`).
- **Service-Änderung**: `NarrativeService.generate_memo` und `NarrativeService.start_batch` — beide `NotImplementedError`-Guards entfernen. User-Prompt-Loader-Aufruf wird sprach-abhängig: `f"narrative_user.{language}.md.j2"`.
- **Tests**: 4 Unit-Tests + 1 Integration-Test + 2 Snapshot-Tests (DE renamed, EN neu) + 1 Stub-Fixture (`top_quality_stock_en.json`).
- **Smoke-Skript-Erweiterung**: `scripts/smoke_narrative_real_api.py` bekommt `--lang=de|en`-Flag (default `de`, backwards-compat).
- **Schema-Constraints identisch zu DE**: keine sprach-spezifischen Anpassungen vorab. Real-API-Smoke validiert empirisch — falls EN-Output außerhalb der Constraints liegt, **inline-Bonus-Fix** im selben PR (analog PR #64 W5-Bonus-Fix für `ranking_interpretation`).

### Out of Scope

- **Lokalisierte Few-Shot-Beispiele** (AAPL/MSFT statt NESN) — würde die Demo-Aussage „gleicher Input, andere Sprache" schwächen. Wenn echter EN-Production-Use-Case kommt, kann lokalisiert werden.
- **EN-spezifische Schema-Constraints** (z.B. kürzere `min_length` für `ranking_interpretation`, weil EN kompakter) — vorab YAGNI; Smoke validiert empirisch.
- **Frontend-Sprach-Switcher / UI-i18n** — orthogonale Frontend-Arbeit.
- **EN-LLM-as-Judge-Test** (analog Issue #59 Golden-Prompt) — Wave-3-Hardening, separater Issue.
- **EN-Output-Tone-Adaption für US-Asset-Mgmt** — Demo-Slice, kein Production-Tone-Tuning.
- **Cost-Math-Differenzierung pro Sprache** — `CostTracker` ist sprach-agnostisch; Token-Verbrauch wird pro Call gemessen, nicht aggregiert pro Sprache.

---

## 3. Architektur-Überblick

> **TL;DR (Reviewer):** Reine Erweiterung der existierenden bilingualen Schiene. Keine neuen Komponenten, keine neuen Ports/Adapter. Nur Templates füllen + Guards entfernen + Tests.

```
backend/infrastructure/llm/prompts/
├── narrative_system.de.md.j2          (UNVERÄNDERT)
├── narrative_system.en.md.j2          (MODIFIED: 1:1-Übersetzung)
├── narrative_user.de.md.j2            (RENAMED von narrative_user.md.j2 via git mv)
└── narrative_user.en.md.j2            (NEU: EN-Variante mit englischen Labels)

backend/application/services/
└── narrative_service.py
    ├── generate_memo:      NotImplementedError-Guard entfernt
    ├── start_batch:        NotImplementedError-Guard entfernt
    └── User-Prompt-Loader: "narrative_user.md.j2" → f"narrative_user.{language}.md.j2"

backend/tests/fixtures/prompts/
├── expected_user_prompt.de.md         (RENAMED von expected_user_prompt.md)
└── expected_user_prompt.en.md         (NEU: Snapshot für EN-User-Prompt)

backend/tests/fixtures/llm/narrative/
└── top_quality_stock_en.json          (NEU: EN-Variante als Stub-Response)

backend/tests/unit/application/test_narrative_service.py
├── ENTFERNT: test_generate_memo_raises_for_en_language
├── ENTFERNT: test_start_batch_raises_for_en_language (Name in PR #70 ggf. abweichend)
├── NEU:      test_generate_memo_renders_en_templates
├── NEU:      test_start_batch_accepts_en_language
├── NEU:      test_user_prompt_snapshot_en
└── BLEIBT:   test_user_prompt_snapshot_de  (renamed-snapshot-Pfad)

backend/tests/integration/test_narrative_service_integration.py
└── NEU: test_full_pipeline_en  (StubAnthropic+EN-Fixture, persistierter Memo, Cache-Trennung)

scripts/
└── smoke_narrative_real_api.py        (MODIFIED: --lang=de|en CLI-Flag, default de)
```

**Cache-Verhalten**: zwei separate Anthropic-Caches automatisch — verschiedene System-Prompt-Prefixes erzeugen verschiedene Cache-Keys. Kein Code-Change nötig. Cache-Hit-Rate bleibt pro Sprache hoch, weil System-Prompts pro Sprache identisch über Calls.

**Hexagonal-Compliance**: keine neuen Domain-Entities, keine neuen Ports, keine neuen Adapter. Nur Templates (Infrastructure) + Service-Logic (Application). Konsistent mit Single-Memo + Multi-Memo-Slices.

---

## 4. Template-Strategie

### 4.1 System-Template (`narrative_system.en.md.j2`)

**Ansatz**: 1:1-Übersetzung des DE-Templates. Nicht „lokalisiert für US-Asset-Mgmt", nicht „idiomatisch englisch umformuliert" — direkte Übersetzung, die die strukturelle Gleichheit beider Templates sichtbar macht.

**Struktur** (gleich wie DE):

```
# Methodisches Framework
## Die 5 Quant-Modelle
## Die 4 Kategorien
## Quant Sweet Spot

# Interpretations-Regeln
## Rang-zu-Sprache-Mapping (englische Begriffe: "very strong" / "strong" / ...)
## Widersprueche (Contradictions)
## Confidence

# Ton-Vorgaben

# Disclaimer

# Output-Format

# Beispiel-Memo (Few-Shot)
   AKTIE → STOCK, mit NESN-Daten unverändert
   Beispiel-Output: ResearchMemoSchema-konform auf Englisch
```

### 4.2 Rang-zu-Sprache-Mapping (Englisch)

| Perzentil | DE-Begriff | EN-Begriff |
|---|---|---|
| Top 10% | sehr stark | very strong |
| Top 25% | stark | strong |
| Top 50% | überdurchschnittlich | above average |
| 50-75% | unterdurchschnittlich | below average |
| Bottom 25% | schwach | weak |
| Bottom 10% | sehr schwach | very weak |

### 4.3 User-Template (`narrative_user.en.md.j2`)

**Labels-Mapping**:

| DE | EN |
|---|---|
| `AKTIE` | `STOCK` |
| `Sektor` | `Sector` |
| `Land` | `Country` |
| `MODEL RUN` | `MODEL RUN` (unverändert — Code-konvention) |
| `Universum` | `Universe` |
| `Aktien` | `stocks` |
| `Benchmark-Median-Rang` | `Benchmark median rank` |
| `Top-20%-Schwelle` | `Top-20% threshold` |
| `RANKINGS (1 = bester)` | `RANKINGS (1 = best)` |
| `Rang` | `Rank` |
| `AGGREGATION` | `AGGREGATION` (unverändert) |
| `Total Rank` | `Total Rank` (unverändert) |
| `Quant Sweet Spot` | `Quant Sweet Spot` (unverändert — Begriff bleibt) |
| `Verwendete Gewichte` | `Used weights` |
| `nicht angegeben` | `not specified` |
| `Unbekannt` | `Unknown` |

**Closing-Statement-Übersetzung**:
- DE: „Produziere das strukturierte JSON-Memo via `submit_memo`-Tool gemaess Systemanweisungen."
- EN: „Produce the structured JSON memo via the `submit_memo` tool per system instructions."

### 4.4 Few-Shot-Beispiel im System-Template

NESN-Daten bleiben unverändert (gleiche Aktie, gleiches Universum, gleiche Rangzahlen). Nur die Beispiel-Output-Felder werden übersetzt:

```
Example output (EN):
{
  "ticker": "NESN",
  "total_rank": 11,
  "one_liner": "Quality and risk profile within sweet spot, modest momentum signals.",
  "ranking_interpretation": "Strong quality (rank 8/80) and excellent diversification (rank 5/80, top 6%) ...",
  "key_strengths": ["Top-decile quality fundamentals", "Lowest universe correlation"],
  "key_risks": ["Below-average value alpha potential (rank 60/80)"],
  ...
}
```

---

## 5. Service-Änderungen

### 5.1 `generate_memo` — Guard entfernen

**Vorher** (in PR #64, Zeile ~150-156):

```python
if language == "en":
    raise NotImplementedError(
        "EN-Memos sind in dieser Slice noch nicht implementiert "
        "(narrative_system.en.md.j2 ist Stub). Bitte language='de' nutzen."
    )
```

**Nachher**: Guard komplett entfernt. Der Pfad läuft durch wie für DE.

### 5.2 `start_batch` — Guard entfernen

**Vorher** (in PR #70, Zeile ~199-201):

```python
if language == "en":
    raise NotImplementedError(...)
```

**Nachher**: Guard komplett entfernt. Batch-Worker ruft `_generate_memo_isolated` mit `language="en"`, was an `generate_memo` weitergegeben wird.

### 5.3 User-Prompt-Loader-Pfad

**Vorher**:

```python
user_prompt = self._prompts.render("narrative_user.md.j2", context)
```

**Nachher**:

```python
user_prompt = self._prompts.render(f"narrative_user.{language}.md.j2", context)
```

System-Prompt-Loader ist bereits sprach-abhängig (`f"narrative_system.{language}.md.j2"`) — keine Änderung.

---

## 6. Test-Strategie

### 6.1 Unit-Tests

Datei: `backend/tests/unit/application/test_narrative_service.py`

| Test | Was er prüft |
|---|---|
| ENTFERNT `test_generate_memo_raises_for_en_language` | Guard ist weg — Test obsolet |
| ENTFERNT `test_start_batch_raises_for_en_language` (Name kann in PR #70 abweichen) | Guard ist weg — Test obsolet |
| NEU `test_generate_memo_renders_en_templates` | Spy auf `prompt_loader.render` — bei `language="en"` wird mit `"narrative_system.en.md.j2"` und `"narrative_user.en.md.j2"` aufgerufen |
| NEU `test_start_batch_accepts_en_language` | `service.start_batch(run_id, language="en")` wirft keine Exception, Job pending erstellt; Worker ruft intern mit `language="en"` auf |
| NEU `test_user_prompt_snapshot_en` | Render `narrative_user.en.md.j2` mit fixem Context, Diff gegen `expected_user_prompt.en.md` |
| BLEIBT `test_user_prompt_snapshot_de` (renamed Snapshot-Pfad) | Drift-Schutz für DE-Template |

### 6.2 Integration-Test

Datei: `backend/tests/integration/test_narrative_service_integration.py`

```
test_full_pipeline_en:
  Setup:    StubAnthropic mit top_quality_stock_en.json-Fixture
            Stock + RankingRun in PG seeded
  Action:   service.generate_memo(stock_id, run_id, language="en")
  Assert:
    - DB hat Memo mit language="en"
    - Schema-Validation grün
    - service.get_memo(..., language="en") returnt Memo
    - service.get_memo(..., language="de") returnt None  ← Cache-Trennung
```

### 6.3 EN-Stub-Fixture

Datei: `backend/tests/fixtures/llm/narrative/top_quality_stock_en.json`

Format: identisch zu `top_quality_stock.json` (DE-Variante), aber alle String-Felder auf Englisch.

```json
{
  "ticker": "NESN",
  "total_rank": 11,
  "one_liner": "Quality and risk profile within sweet spot, modest momentum signals.",
  "ranking_interpretation": "Strong quality fundamentals (rank 8/80) ...",
  "sweet_spot_explanation": "In sweet spot: top 25% on quality, alpha, and diversification.",
  "key_strengths": ["Top-decile quality fundamentals", "Lowest universe correlation"],
  "key_risks": ["Below-average value alpha potential (rank 60/80)"],
  "contradictions": [],
  "confidence": "high"
}
```

### 6.4 Coverage-Ziel

≥90% auf den geänderten Service-Pfaden, analog zur Single-Memo-Slice.

---

## 7. Real-API-Smoke

### 7.1 Skript-Erweiterung

`scripts/smoke_narrative_real_api.py` bekommt `--lang=de|en` CLI-Flag (argparse, default `de`).

```bash
# Backwards-compat (unverändert): default DE
python scripts/smoke_narrative_real_api.py

# Neu: EN-Smoke
python scripts/smoke_narrative_real_api.py --lang=en
```

### 7.2 Smoke-Pattern

Identisch zu PR #64 W5-Smoke:

1. **Call 1** (cache_create): NESN-Sample-Daten, Tool-Use erzwungen, Schema-Validation gegen `ResearchMemoSchema`.
2. **Call 2** (cache_read): identischer Call → muss `cache_read_input_tokens > 0` zeigen, was beweist dass das EN-System-Template gecacht wird.

### 7.3 Manueller Run vor PR-Merge

Vor PR-Erstellung **manuell** ausführen:

```
$ python scripts/smoke_narrative_real_api.py --lang=en
```

Erwartung — Ergebnis-Tabelle in PR-Body:

|  | Input | Output | Cache-Create | Cache-Read | Latenz | Kosten |
|---|---|---|---|---|---|---|
| Call 1 | ~700 | ~700-900 | ~3000 | 0 | ~10-15s | ~$0.025 |
| Call 2 | ~20 | ~700-900 | ~700 | ~3000 | ~10-15s | ~$0.015 |

(Werte sind Erwartung — Ist-Werte kommen aus dem Smoke und werden im PR-Body dokumentiert.)

### 7.4 Schema-Calibration-Strategie

Falls Smoke `string_too_short` oder `string_too_long` wirft (Pattern A7 — Schema-Constraints aus dem Spec geraten):

1. **Inline-Bonus-Fix** im selben PR: `min_length`/`max_length` der betroffenen Felder anpassen.
2. **Spec §11 Plan-Code-Drift** dokumentieren (analog PR #64 W5-Bonus-Fix für DE `ranking_interpretation` 600→1000).
3. **Wenn substantiell** (z.B. EN-Outputs strukturell anders, mehrere Felder betroffen): Slice splitten — Templates in dieser PR, Schema-Calibration als Folge-PR mit eigener Spec.

---

## 8. Akzeptanz-Kriterien

Implementation dieser Slice ist komplett, wenn:

- [ ] `narrative_system.en.md.j2` ist 1:1-Übersetzung des DE-Templates (alle Sektionen: 5 Modelle, 4 Kategorien, Sweet Spot, Rang-Mapping, Confidence, Ton, Disclaimer, Output-Format, Few-Shot mit NESN — alles in flüssigem Englisch)
- [ ] `narrative_user.en.md.j2` mit englischen Labels (siehe §4.3)
- [ ] `narrative_user.md.j2` per `git mv` zu `narrative_user.de.md.j2` umbenannt
- [ ] `expected_user_prompt.md` per `git mv` zu `expected_user_prompt.de.md` umbenannt
- [ ] `expected_user_prompt.en.md` neu (Snapshot für EN-User-Prompt mit fixem Context)
- [ ] Service: beide `NotImplementedError`-Guards (`generate_memo`, `start_batch`) entfernt
- [ ] Service: User-Prompt-Loader-Aufruf nutzt `f"narrative_user.{language}.md.j2"`
- [ ] Unit-Tests: alle 4 NEU-Tests grün (renders_en_templates, start_batch_accepts_en, snapshot_en, snapshot_de)
- [ ] Integration-Test: `test_full_pipeline_en` grün, Cache-Trennung DE/EN verifiziert
- [ ] EN-Stub-Fixture `top_quality_stock_en.json` Schema-konform
- [ ] mypy strict + ruff lint/format clean
- [ ] Real-API-Smoke `python scripts/smoke_narrative_real_api.py --lang=en` ausgeführt: 2-Call-Pattern grün, `cache_read > 0` auf Call 2, Schema-Validation beider Calls grün
- [ ] PR-Body enthält Smoke-Tabelle (Token-Verbrauch, Cache-Hit-Rate, Latenz, Kosten — analog PR #64)
- [ ] AI-USAGE.md-Eintrag mit Reflexion: welche P-Patterns angewandt, welche neuen Lehren entstanden sind
- [ ] Spec §11 Plan-Code-Drift dokumentiert, falls Schema-Calibration während Implementation nötig wurde

---

## 9. Bewusste Abweichungen

### 9.1 Vom Master-Spec (`docs/specs/2026-04-28-narrative-engine.md`)

| Master-Spec-Stelle | Slice-Verhalten | Begründung |
|---|---|---|
| §2 — „Englische Memo-Generierung im MVP: out of scope" | EN wird ausgeliefert | Wave-2-Demonstration der bilingualen Architektur. Master-Spec selbst sagt: „Architektur ist bilingual vorbereitet, nachzulegen <2h Arbeit, sobald UI-i18n verfügbar". Diese Slice ist die <2h-Einlösung — UI-i18n ist orthogonal (Frontend-Track). |
| §10.3 — Golden-Prompt-CI auch für EN | nicht in dieser Slice | Out-of-scope, Issue #59 (Wave-3-Hardening). DE und EN haben Snapshot-Tests, aber keinen nightly-Cron gegen echte API. |

### 9.2 Vom Single-Memo-Slice (`docs/specs/2026-05-04-narrative-engine-single-memo.md`)

Single-Memo-Spec §2 sagt explizit „DE-only, EN ist Stub". Diese Slice setzt diese Einschränkung außer Kraft. Konsistent mit der dort dokumentierten Erwartung „bewusste Slice-Out-Scope-Entscheidung mit zukünftiger Folge-Slice".

### 9.3 Vom Multi-Memo-Slice (`docs/specs/2026-05-08-narrative-engine-multi-memo-batch.md`)

Multi-Memo-Spec §8 hat den `start_batch`-EN-Guard als „Best-Effort-Defensive". Diese Slice entfernt ihn analog zum `generate_memo`-Guard.

---

## 10. Risiken

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|---|---|---|---|
| EN-Output unter `min_length=100` (EN ist kompakter als DE) | mittel | Schema-Validation-Failures → Error-Memo-Pfad statt Memo | Real-API-Smoke validiert vor Merge; Inline-Bonus-Fix `min_length=80` falls nötig (analog PR #64 W5-Pattern) |
| Few-Shot mit NESN macht EN-Output nicht idiomatisch genug | niedrig | Memo-Qualität subjektiv schwächer | Sonnet 4.6 ist bilingual stark; Smoke verifiziert empirisch via Tool-Use-Output |
| Stack-Risiko: EN-Slice braucht #64 + #70 mergebar | mittel | Implementation-Branch kann erst nach #70-Merge erstellt werden | Spec ist heute schreibbar + reviewbar (kein Code-Dependency); Implementation wartet bewusst — keine kritische Pfad-Abhängigkeit |
| Anthropic-Cache muss neu aufgebaut werden bei Template-Edits | niedrig | Erste EN-Smoke-Calls haben höhere Token-Kosten | Cache-Reset nach Edits ist erwartetes Verhalten (5-min TTL); dokumentiert im DE-Template-Header schon |
| User-Template-Rename triggert Test-Coverage-Fall | niedrig | Snapshot-Test-Path stale | git mv erhält Diff-Continuity; Tests werden parallel angepasst |

---

## 11. Offene Entscheidungen

Keine. Alle Architektur-Entscheidungen wurden im Brainstorming (2026-05-10, Q-by-Q-Pattern P1) geklärt:

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| Q1 | Use-Case | Bilinguale Architektur in Action zeigen (40%-AI-Achse) | Nicht Production, nicht UI-i18n-Vorbereitung — pure Demo der existierenden Architektur. |
| Q2 | Translation-Strategie | 1:1 mit NESN-Beispiel | Demo-Aussage „gleicher Input, andere Sprache" am stärksten. Lokalisierung wäre Over-Engineering. |
| Q3 | User-Template-Strategie | Zwei parallele Templates (`.de.` und `.en.`) | Konsistent zur System-Template-Konvention. Niedrige Service-Komplexität (`f"narrative_user.{language}.md.j2"`). |
| Q4 | Test-Setup | Minimal + 1× Real-API-Smoke | Pattern Q4 (Real-API-Smoke ist Acceptance) + A7 (Schema-empirisch kalibrieren). |
| Q5 | Stack-Position | Stacked auf #70 (Multi-Memo) | EN aktiviert beide Pfade (single + batch) gleichzeitig. Konsistenter Mid-State, kein Koordinations-Aufwand mit #70. |

---

## 12. Änderungshistorie

| Version | Datum | Autor | Änderung |
|---|---|---|---|
| Draft v1.0 | 2026-05-10 | Sheyla / Claude Code Opus 4.7 | Initiale Slice-Spec — schneidet EN-Template-Aktivierung aus Master-Spec §2 Sprach-Architektur-Notiz heraus. Q-by-Q-Brainstorming durch 5 Architektur-Entscheidungen (Use-Case, Translation, User-Template, Tests, Stack-Position). |
