# Go-Live-Audit PRISMA V2 — 2026-06-16

## Zusammenfassung

Vollständiger Funktionstest vor Go-Live: Backend-Testsuite (Unit + Integration + mypy +
ruff), Frontend-Testsuite (Unit + Lint + Typecheck + Build) und die komplette
Playwright-E2E-Suite (73 Tests über 16 Spec-Dateien) wurden gegen einen isolierten
lokalen Stack (eigene Postgres-Testdatenbank, Backend auf Port 8001, Frontend-Build auf
Port 3000) ausgeführt. Alle während des Audits gefundenen Bugs wurden sofort behoben und
verifiziert.

**Endstand:**
- Backend: Unit- und Integrationstests grün, `mypy` und `ruff` ohne Befunde.
- Frontend: 234/234 Unit-Tests grün, Lint ohne Fehler (2 vorbestehende, unkritische
  Warnings in nicht verändertem Code), Build erfolgreich.
- E2E: **73/73 Tests grün** (zuletzt: 41 fehlgeschlagen → 6 → 0, über mehrere
  Fix-Iterationen).
- **Ein go-live-relevanter Blocker verbleibt** und kann nicht durch Code behoben werden
  (siehe Abschnitt „Verbleibender Blocker“).

---

## Befunde & Fixes

### 1. [Kritisch] LLM-Budget-Cap-Check war in echter Postgres-Umgebung immer fehlerhaft

**Datei:** `backend/infrastructure/persistence/repositories/cost_log_repository.py`

Die atomare Budget-Cap-Prüfung (`check_cap_atomic`) — der Mechanismus, der verhindert,
dass mehrere Backend-Prozesse gemeinsam das monatliche LLM-Spend-Limit überschreiten —
schlug bei **jedem** Aufruf gegen eine reale Postgres-Datenbank fehl:

```
asyncpg.exceptions.AmbiguousFunctionError: operator is not unique: unknown * unknown
```

Ursache: `cap_usd` und `threshold` wurden als untypisierte `str`-Werte in eine
SQLAlchemy-`text()`-Rohabfrage gereicht; Postgres konnte den `*`-Operator zwischen zwei
„unknown“-typisierten Parametern nicht auflösen. Der Fehler wurde gefangen und auf einen
reinen In-Process-Lock zurückgefallen (Log: „Multi-process Budget-Safety nicht
garantiert“) — die Mehrprozess-Sicherung war damit in der Praxis **nie aktiv**, auch nicht
in der echten Render-Produktionsumgebung.

**Fix:** explizite Typ-Casts via `CAST(:param AS numeric)` in der SQL-Abfrage.
(Ein erster Fix-Versuch mit `:param::numeric` führte zu einem neuen
`PostgresSyntaxError`, da SQLAlchemys Bind-Parameter-Parser `::` direkt nach einem
Parameternamen fehlinterpretiert — `CAST(...)` ist hier die robuste Variante.)

**Verifiziert:** Direkter Aufruf von `check_cap_atomic` gegen die reale Testdatenbank
liefert nun korrekt `True`/`False` ohne Exception.

**Empfehlung für danach (nicht blockierend):** Es existiert kein Integrationstest, der
diese SQL-Abfrage gegen eine echte Postgres-Instanz prüft — nur Unit-Tests mit einem
Fake-Repository. Das ist der Grund, warum der Bug unentdeckt blieb. Ein Integrationstest
für `SQLACostLogRepository.check_cap_atomic` wird empfohlen.

### 2. [Mittel] Doppelte `<h1>`-Überschrift auf `/dashboard` und `/decision`

**Dateien:** `frontend/app/dashboard/page.tsx`, `frontend/app/decision/page.tsx`

Beide Routen rendern eine statische Überschrift in `page.tsx` **und** eine zweite,
mode-abhängige Überschrift im jeweiligen Client-Component (`dashboard-client.tsx`,
`decision-client.tsx`). Im Pro-Modus ist der Text identisch („Dashboard.“ bzw.
„Decision Intelligence.“) — zwei `<h1>`-Elemente mit demselben Text auf einer Seite sind
sowohl ein Accessibility-Defekt (mehrere Top-Level-Headings) als auch die Ursache eines
E2E-Testfehlers (`getByRole('heading', ...)` traf zwei Elemente).

**Fix:** Die redundante statische Überschrift in beiden `page.tsx`-Dateien entfernt;
die Client-Components rendern bereits vollständige, kontextabhängige Header (inkl.
Zeitstempel, Pro/Simple-Badges, Begrüssung).

### 3. [Mittel] Fehlendes `data-testid` auf Fehlermeldung im Pro Mode (Krypto-Seite)

**Datei:** `frontend/app/crypto/crypto-client.tsx`

Die Fehlermeldung „Signale konnten nicht geladen werden.“ wird in Simple Mode und Pro
Mode separat gerendert (Copy-Paste). Nur die Simple-Mode-Variante hatte
`data-testid="signals-error"` — im Pro Mode fehlte das Attribut, wodurch die
Fehlermeldung für Nutzer zwar sichtbar, aber für automatisierte Prüfungen (E2E-Tests,
zukünftiges Monitoring per Test-ID) nicht auffindbar war.

**Fix:** `data-testid="signals-error"` ergänzt.

### 4. [Niedrig] Veraltete `APP_VERSION` in `render.yaml`

**Datei:** `render.yaml`

`APP_VERSION` war auf `"2.0.0"` gepinnt, während der Code-Default in
`health.py` bereits `"2.1.0"` ist — der `/health`-Endpoint hätte nach Deploy eine
falsche Versionsnummer zurückgegeben.

**Fix:** auf `"2.1.0"` korrigiert.

### 5. [Test-Infrastruktur] E2E: Universe-Name-Kollision führte zu 120s-Timeout

**Datei:** `frontend/e2e/01-universe.spec.ts`

Der Test verwendete einen fest kodierten Universum-Namen („E2E Test Universum“). Die
Spalte `name` in der Tabelle `universes` hat einen `UNIQUE`-Constraint; bei jedem
Wiederholungslauf (z. B. nach einem fehlgeschlagenen vorherigen Lauf oder manuellem
Debugging gegen dieselbe DB) schlug die Erstellung mit `500 Internal Server Error`
(`UniqueViolationError`) fehl. Da das Formular daraufhin nur eine Fehlermeldung statt des
erwarteten Bestätigungsdialogs zeigte, lief der Test in einen vollen 120s-Timeout, statt
mit einer aussagekräftigen Fehlermeldung sofort zu scheitern.

Alle anderen E2E-Tests im Suite verwenden bereits einen Zeitstempel-Suffix für genau
diesen Zweck — dieser eine Test war die Ausnahme.

**Fix:** Name auf `` `E2E Test Universum ${Date.now()}` `` umgestellt, konsistent mit der
restlichen Suite.

### 6. [Test-Infrastruktur] Playwright Strict-Mode-Fehler durch Teiltext-Match

**Datei:** `frontend/e2e/15-crypto.spec.ts`

`page.getByText('Sentiment')` traf zwei Elemente: das eigentliche Score-Label **und**
den Seiten-Untertitel („...technisch-sentimentale Prognose...“), da Playwrights
`getByText` standardmässig Teilstrings matcht.

**Fix:** `exact: true` ergänzt.

### 7. [Test-Infrastruktur, bereits vor diesem Audit behoben] `localStorage`-SecurityError
und falscher Backend-Port in E2E-Fixtures

Bereits im Verlauf dieses Audits behoben (vor dem in diesem Bericht dokumentierten
Abschnitt): `page.evaluate()`-Aufrufe vor `page.goto()` schlugen mit `SecurityError`
fehl (Chromiums `about:blank`-Origin-Restriktion) — auf `page.addInitScript()`
umgestellt. Zusätzlich zeigte `frontend/e2e/fixtures.ts` per Default auf den falschen
Backend-Port und verwendete eine andere Umgebungsvariable
(`E2E_API_BASE_URL`) als der Rest der Suite (`PLAYWRIGHT_API_URL`) — beides
vereinheitlicht, inkl. Korrektur in `.github/workflows/ci.yml`.

### 8. Sonstige Code-Hygiene (aus Backend-/Frontend-Testlauf, Tasks #1/#2)

- Mehrere überflüssige `# type: ignore[type-arg]`-Kommentare in
  `portfolio_agent.py`, `ml_prediction_service.py`, `monte_carlo_service.py`,
  `stub_market_data.py` entfernt (durch aktuelle `numpy`/`mypy`-Versionen nicht mehr
  nötig).
- `frontend/vitest.setup.ts`: Node 22+ bringt ein eigenes, unvollständiges globales
  `localStorage` mit, das `window.localStorage` in jsdom verdeckt und Tests zum Absturz
  bringen konnte — durch eine vollständige In-Memory-`Storage`-Implementierung ersetzt.
- `frontend/app/stocks/__tests__/stocks-list.test.tsx`: Test-Fixture um die Felder
  `exchange`/`market_cap_chf` ergänzt (fehlten nach Typ-Erweiterung von `StockRead`).

---

## Verbleibender Blocker (nicht code-seitig behebbar)

### GitHub Actions: Deploy-Secrets fehlen vollständig

`gh secret list -R don69andrea/prisma-v2` liefert eine **leere Liste** — keine Secrets
sind im Repository konfiguriert. `.github/workflows/cd-render.yml` erwartet
`RENDER_V2_DEPLOY_HOOK_BACKEND` und `RENDER_V2_DEPLOY_HOOK_FRONTEND`; der Workflow
validiert dies per Fail-Fast-Check und wird bei jedem Push auf `main` fehlschlagen, bis
diese Secrets gesetzt sind.

**Notwendige manuelle Aktion (durch Repo-Owner):** Deploy-Hook-URLs aus dem Render-
Dashboard (jeweils für Backend- und Frontend-Service) kopieren und als Secrets unter
GitHub → Settings → Secrets and variables → Actions hinterlegen.

---

## Nicht-blockierende Beobachtungen

- `Dockerfile.frontend` enthält keine `HEALTHCHECK`-Direktive (im Gegensatz zu
  `Dockerfile.backend`). Render selbst prüft den Health-Status über den HTTP-Endpoint,
  daher kein Blocker — für Konsistenz und lokales Docker-Debugging trotzdem empfehlenswert.
- `backend/interfaces/rest/rate_limiter.py`: Die LLM-Rate-Limiter-Middleware deckt nicht
  `/api/v1/profile` und `/api/v1/discover` ab — geprüft und bestätigt, dass diese
  Endpunkte reine DB-Operationen ohne LLM-Aufrufe sind, also korrekt ausgenommen.

---

## Testumfang im Detail

| Bereich | Ergebnis |
|---|---|
| Backend Unit + Integration Tests | grün |
| `mypy backend/` | keine Befunde |
| `ruff check backend/` | keine Befunde |
| Frontend Unit Tests | 234/234 grün |
| Frontend Lint | keine Fehler (2 vorbestehende Warnings, nicht in geändertem Code) |
| Frontend Build | erfolgreich |
| E2E (Playwright, 73 Tests / 16 Spec-Dateien) | **73/73 grün** |

## Fazit

Aus rein applikatorischer Sicht (Code, Tests, Konfiguration) ist PRISMA V2 go-live-bereit:
alle automatisierten Tests sind grün, und der gefundene kritische Produktionsbug
(Budget-Cap-Sicherung) ist behoben und verifiziert. Der einzige verbleibende Blocker ist
organisatorisch, nicht technisch: die fehlenden Render-Deploy-Secrets in GitHub Actions
müssen vor dem ersten automatisierten Deploy auf `main` manuell nachgetragen werden.
