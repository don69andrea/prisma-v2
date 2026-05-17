# Narrative Engine — Follow-up Bundle #66 + #67

**Status**: Design  
**Datum**: 2026-05-14  
**Owner**: Sheyla Sampietro (AI Engineer)  
**Closes**: #66 (Score=1/rank Hallucination), #67 (is_error String-Match)  
**Bezugs-PRs**: #64 (Single-Memo-Slice, Review-Quelle), #70 (Multi-Memo-Batch), #116 (EN-Template, in Review)  
**Spec-Vorgänger**: `docs/specs/2026-05-04-narrative-engine-single-memo.md` (Master-Spec §5/§7)

---

## §1 Motivation

Aus dem PR #64-Review hat itsFabia sechs Folge-Findings dokumentiert (W1–W6). Vier wurden bereits adressiert:

- W3 (#67-zugeordnet, aber als String-Match-Refactor noch offen) — siehe unten
- W4 (#68 Anthropic-Singleton) — gemerged via PR #107
- W6 (#69 Timeout/Retry) — gemerged via PR #107, Issue verifiziert geschlossen 2026-05-14

Verbleibend: **W1 (#66)** und **W3 (#67)**. Beide einzeln klein, thematisch zusammengehörig: Disziplinierung der Narrative-Engine-Schnittstelle gegen Erfindung („Score") und Fragilität (String-Match). Bundle als ein PR, weil Überlappung in `narrative_service.py`.

## §2 Scope

### §2.1 #66 — Score=1/rank Hallucination entfernen

**Problem.** `_rankings_for_template` in `backend/application/services/narrative_service.py:104` berechnet `score = round(1.0/max(rank,1), 4)` als Proxy für einen echten Score-Wert, der in den Run-Results nicht existiert. Dieser erfundene Float wird ins User-Prompt-Template gerendert (`narrative_user.md.j2:14`) und vom System-Prompt-Few-Shot (`narrative_system.de.md.j2:118-122`) durch echte-Score-aussehende Beispiele („Score 0.87") flankiert. Resultat: die LLM hält den Wert für eine quantitative Aussage und referenziert sie in der Memo-Begründung — eine Hallucination-Quelle in einem mit "Educational/Research"-Disclaimer ausgelieferten Output.

**Fix.** Score komplett aus dem Prompt-Pfad entfernen. Rang bleibt — der ist faktisch und stammt aus Run-Results. Sobald echte per-Modell-Scores in Run-Results landen (zukünftige Slice), wird der Slot reaktiviert.

**Geänderte Dateien:**
- `backend/application/services/narrative_service.py` — Helper `_rankings_for_template` returnt `dict[str, dict[str, int]]` mit nur `rank`-Key (vorher `dict[str, dict[str, float | int]]` mit `rank` + `score`)
- `backend/infrastructure/llm/prompts/narrative_user.md.j2` (DE-only bis PR #116 mergt) — Zeile 14 von `Rang {{ ranking.rank }}/{{ n_stocks }}, Score {{ "%.4f"|format(ranking.score) }}` zu `Rang {{ ranking.rank }}/{{ n_stocks }}`
- `backend/infrastructure/llm/prompts/narrative_system.de.md.j2` — Zeilen 118-122 (Few-Shot „Vergleichbare Modelle"-Block): von `Quality Classic: Rang 8/80, Score 0.87` zu `Quality Classic: Rang 8/80`. Analog für die anderen 4 Modelle.
- *(Nach #116-Merge:* `narrative_user.en.md.j2` *+* `narrative_system.en.md.j2` *analog. Wird im selben PR mit-ediert wenn #116 bis dahin gemerged ist; sonst Folge-Slice.)*

**Kosten-Implikation.** System-Prompt-Inhalt ändert sich → Cache-Hash bricht → 1× neuer Cache-Create-Token-Cost (~2600 Tokens für DE, ~2100 für EN bei einmaligem Re-Warmup). Akzeptabel.

### §2.2 #67 — `is_error` als echtes Entity-Feld

**Problem.** `backend/interfaces/rest/routers/memos.py:63-65` leitet `is_error` aus zwei String-Heuristiken ab:

```python
is_error = memo.model_version == ERROR_FALLBACK_MODEL_VERSION or memo.one_liner.startswith(
    "Memo-Generierung fehlgeschlagen"
)
```

Probleme:
1. **Redundanz** — wenn `_build_error_memo_schema` die einzige Quelle ist, sind beide Bedingungen wahr; das `or` ist toter Code.
2. **Brittleness** — der String-Match auf deutschen Fehlertext schlägt fehl, sobald EN-Memos (PR #116) durch dieselbe Pipeline laufen. Der englische `one_liner` startet nicht mit „Memo-Generierung fehlgeschlagen".
3. **Layer-Smell** — Router liest Domain-State per Inferenz aus einem Output-Feld (`one_liner`) statt als explizite Property. Verschiebt Geschäftslogik in den Adapter.

**Fix.** `is_error: bool = False` als reguläres Feld auf `ResearchMemo`-Entity + ORM-Spalte + Migration. Service setzt es explizit in `_build_error_memo_schema` (=True) bzw. überall sonst (=False, via Pydantic-Default). Router liest `memo.is_error` als simple Property.

**Sentinel-Marker `ERROR_FALLBACK_MODEL_VERSION = "error-fallback"` bleibt erhalten.** Begründung: doppelte Signatur in DB-Logs erleichtert Forensik bei ETL-Inspektion ohne is_error-Spalte-Join. Belt-and-suspenders.

**Geänderte Dateien:**
- `backend/alembic/versions/0009_add_is_error_to_research_memos.py` (NEU) — `ADD COLUMN is_error BOOLEAN NOT NULL DEFAULT false` + Backfill-`UPDATE`-Statement
- `backend/domain/entities/research_memo.py` — neues Feld `is_error: bool = False`
- `backend/infrastructure/persistence/orm/research_memo_orm.py` — `is_error: Mapped[bool] = mapped_column(...)` (existing column-list erweitert)
- `backend/infrastructure/persistence/repositories/research_memo_repository.py` — `_to_entity` / `_to_orm`-Mapping erweitern
- `backend/application/services/narrative_service.py` — `_build_memo_entity` (Schema→Entity-Brücke bei `narrative_service.py:641`) leitet `is_error` aus dem Schema ab:
  ```python
  is_error=(schema.model_version == ERROR_FALLBACK_MODEL_VERSION)
  ```
  Damit bleibt die Heuristik **an einer einzigen Stelle** (Persistenz-Brücke), wird auf Write-Time evaluiert und als gespeicherter Fakt persistiert. Router liest danach `memo.is_error` als reine Property. `_build_error_memo_schema` selbst bleibt unverändert (setzt weiter `model_version=ERROR_FALLBACK_MODEL_VERSION`, sonst nichts).
- `backend/interfaces/rest/routers/memos.py` — Zeile 63-65 → `is_error=memo.is_error` (direkter Attribute-Read); Zeile 185 (`get_job` → `BatchMemoSummary`) analog: `is_error=m.is_error`

**Was sich NICHT ändert:**
- `ResearchMemoSchema` (LLM-Output-Schema) bleibt unangetastet. `is_error` ist eine Service-Side-Annotation, kein LLM-Output.
- `BatchMemoSummary.is_error` in `backend/interfaces/rest/schemas/memo_batch.py:29` existiert bereits — nur die Herleitung im Router wird sauber.
- Bestehende Integration-Tests (`test_memos_endpoint.py:185 assert body["is_error"] is True`) bleiben grün.

## §3 Migration-Strategie

```sql
-- 0009_add_is_error_to_research_memos.py upgrade()
ALTER TABLE research_memos ADD COLUMN is_error BOOLEAN NOT NULL DEFAULT false;

-- Backfill historischer Daten anhand des bisherigen Sentinels
UPDATE research_memos
   SET is_error = true
 WHERE model_version = 'error-fallback';

-- downgrade()
ALTER TABLE research_memos DROP COLUMN is_error;
```

**Idempotenz.** Alembic versioniert das Migration-Skript; doppelter Aufruf bricht. Bei manueller Wiederholung außerhalb Alembic-Stamps müsste `ADD COLUMN IF NOT EXISTS` verwendet werden — wir verlassen uns auf Alembic-State.

**Backfill-Sicherheit.** `model_version='error-fallback'` ist die einzige aktuelle Quelle für Error-Memos (siehe `_build_error_memo_schema`-Aufrufer in `narrative_service.py:610` + `:624`). Keine Edge-Cases mit anderen Sentinel-Werten.

**Production-Trigger.** Render-Deployment führt Alembic-Migration automatisch via `prestart.sh` aus. Lokal: `alembic upgrade head` in docker-compose-Stack.

## §4 Test-Strategie (TDD-Reihenfolge)

| Step | Task | Test-Typ | RED-Erwartung |
|------|------|----------|---------------|
| 1 | Entity-Feld | Unit (`test_research_memo.py`) | `ResearchMemo(...)` ohne `is_error` → default False; mit `is_error=True` → True |
| 2 | Migration | Integration (Live-PG) | Alembic-Upgrade + Sample-Daten: Error-Memo-Row hat is_error=True, normale Row is_error=False |
| 3 | ORM-Roundtrip | Integration | Persist Memo(is_error=True) → fetch → is_error=True erhalten |
| 4 | Service-Error-Pfad | Unit (`test_narrative_service.py`) | `_build_error_memo_schema(...)` produziert Schema mit is_error=True; normale Memo-Generation produziert is_error=False |
| 5 | Router-Simplification | Integration (`test_memos_endpoint.py`) | Bestehender Test 185 bleibt grün; neuer Test: ohne `model_version`-Match Heuristik klappt is_error trotzdem (z.B. wenn man manuell eine Row mit is_error=True und model_version='claude-sonnet-4-6' einfügt) |
| 6 | Helper-Score-Removal | Unit (`test_narrative_service.py`) | `_rankings_for_template({"per_model_ranks": {"alpha": 5}})` returnt `{"Alpha": {"rank": 5}}` — kein `score`-Key |
| 7 | Template-Snapshot-DE | Unit (`test_prompt_templates.py`) | Gerenderter User-Prompt enthält `Rang 8/80` aber nicht `Score` |
| 8 | System-Prompt-Snapshot | Unit | DE-System-Prompt enthält keine „Score 0.87"-Few-Shot-Zeile mehr |
| 9 | Real-API-Smoke (manuell) | Smoke | `python -m backend.scripts.smoke_narrative_real_api --lang=de` → Output erwähnt keinen erfundenen Score, Schema-Validation grün, Werte in AI-USAGE.md dokumentieren |

**Coverage-Erwartung.** Bestehende 80%-Gate-Schwelle bleibt; alle neuen Code-Pfade haben dedizierte Tests.

## §5 PR-#116-Interaktion

PR #116 (EN-Template, Draft → Review) splittet `narrative_user.md.j2` in `.de`/`.en` und führt `narrative_system.en.md.j2` ein. Beziehungen zu diesem Bundle:

- **Reihenfolge.** Dieser Bundle wartet auf #116-Merge. Branch von frischem main nach #116-Merge, dann Implementation. Vermeidet Template-Konflikte.
- **EN-Symmetrie.** Wenn #116 gemerged ist, ediert dieser PR auch die EN-Templates (Score-Removal symmetrisch in `narrative_user.en.md.j2` + `narrative_system.en.md.j2`). Wenn #116 unerwartet lange braucht: EN-Symmetrie als Folge-Issue parken, DE-only Slice rausgeben.
- **is_error × EN.** Genau der Use-Case der die `is_error`-Refactor motiviert: ohne dieses Bundle wäre der Router-String-Match für EN-Memos false-negative. PR #116 selbst hat das nicht gefixt — daher hat das Bundle Mehrwert genau im Moment des #116-Merges.

## §6 Akzeptanzkriterien

- [ ] `_rankings_for_template` returnt keine score-Werte mehr (Unit-Test)
- [ ] User-Prompt-Template DE rendert „Rang X/N" ohne „Score" (Snapshot-Test)
- [ ] System-Prompt DE Few-Shot enthält kein „Score 0.XX" mehr (Snapshot-Test)
- [ ] *(Wenn #116 gemerged ist:)* gleiche Bedingungen für EN
- [ ] `ResearchMemo.is_error` als Pflichtfeld auf Entity (default False)
- [ ] Migration 0009 läuft auf Live-PG durch, backfillt historische Error-Memos
- [ ] Router `memos.py:63-65` und `:185` nutzen `memo.is_error` direkt, kein String-Match mehr
- [ ] Bestehende Integration-Tests bleiben grün
- [ ] Real-API-Smoke DE grün: Memo-Output erwähnt keinen erfundenen Score
- [ ] AI-USAGE.md-Eintrag

## §7 Out of Scope (bewusst vertagt)

- **Echte per-Modell-Scores.** Würde Run-Results-Schema erweitern (zusätzliches Feld pro Modell). Aktuell liefern die 5 Quant-Modelle nur Ranks. Future-Slice.
- **`ERROR_FALLBACK_MODEL_VERSION` droppen.** Diskutiert; bewusst behalten (§2.2 Sentinel-Marker).
- **Dead-Code-Cleanup über is_error hinaus.** `memos.py` hat andere Vereinfachungspotenziale (z.B. `from_entity`-Verkürzung) — separat oder gar nicht.
- **EN-Symmetrie als Hard-Dependency.** Wenn #116 stockt, akzeptieren wir kurzfristig asymmetrische Templates und tracken die EN-Lücke als Folge-Issue.

## §8 Risiken & Mitigation

| Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|
| LLM-Output verändert sich qualitativ ohne Score-Hint | Mittel | Real-API-Smoke + Schema-Validation. Wenn Output-Qualität sinkt, Few-Shot mit reinem Rang-Wording verstärken (z.B. „Top-Quintile=Rang 1-16", als Heuristik-Hilfe ohne Erfundenes). |
| Migration-Backfill verfehlt eine Error-Row | Niedrig | `model_version='error-fallback'` ist die einzige aktuelle Quelle; alle Aufrufer von `_build_error_memo_schema` setzen den Sentinel. |
| Cache-Reset durch System-Prompt-Änderung erhöht Inferenz-Kosten | Niedrig | Einmaliger Cache-Create (~2600 Tokens DE, ~2100 EN) — Cents-Bereich. Akzeptabel. |
| Test-Suite-Regression durch entity-Erweiterung | Niedrig | Pydantic-Default macht `is_error` opt-in; Fixtures müssen nicht angepasst werden. |
| PR-Konflikt mit #116 falls noch nicht gemerged | Mittel | Dieser Bundle wartet auf #116-Merge (§5). |

## §9 Open Questions

Keine — alle Macro-Trade-offs sind im Brainstorming entschieden:
- Score-Strategie: Option 1 (komplett raus, auch System-Prompt-Few-Shot)
- is_error-Form: Entity-Feld mit Migration und Backfill
- Sentinel: behalten
- Bundle: ein PR

## §10 Referenzen

- Issue #66 (W1): https://github.com/SheylaSam/prisma-capstone/issues/66
- Issue #67 (W3): https://github.com/SheylaSam/prisma-capstone/issues/67
- PR #64 Review-Kommentar: https://github.com/SheylaSam/prisma-capstone/pull/64#pullrequestreview-4230626614
- Master-Spec §5 (Memo-Generation): `docs/specs/2026-05-04-narrative-engine-single-memo.md`
- AGENTS.md: Branching-/Commit-Konventionen
