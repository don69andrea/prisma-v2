# Render Deploy Befund — 2026-06-18

**Scope:** Vollaudit aller Render-Blueprint- und Deployment-Fehler nach Auth-PR #267  
**Branch:** `fix/render-deploy-crashes-2026-06-18`  
**Status:** Fixes implementiert — PR ausstehend

---

## Zusammenfassung

Seit Merge von PR #267 (`feat/auth): JWT Login + User Management + Admin UI`) schlägt
**jeder** Render-Deploy des Backends fehl. Ursache: drei neue Pflicht-Umgebungsvariablen
wurden im Code hinzugefügt, aber nie im Render-Dashboard gesetzt. Zusätzlich ist
`seed_admin.py` als blocking-fatal in das Startup-Script eingebaut — jeder Fehler
dort crasht den Container.

---

## Befunde

### 🔴 CRIT-1 — `JWT_SECRET` nicht im Render-Dashboard gesetzt

**Datei:** `backend/config.py`

```python
@model_validator(mode="after")
def _jwt_secret_required_in_production(self) -> "Settings":
    if self.environment == "production" and not self.jwt_secret:
        raise ValueError("JWT_SECRET muss in der Production-Umgebung gesetzt sein")
```

`get_settings()` wird beim Import aufgerufen. In Production (Render setzt
`ENVIRONMENT=production`) wirft der Validator sofort `ValueError` wenn `JWT_SECRET`
leer ist. Der Container crasht **bevor alembic oder uvicorn starten**.

`JWT_SECRET` ist in `render.yaml` als `sync: false` definiert → muss manuell im
Render-Dashboard gesetzt werden. Das wurde nach PR #267 nie gemacht.

**Symptom:** Render markiert Deploy als fehlgeschlagen, Health-Check `/health` antwortet nie.

---

### 🔴 CRIT-2 — `ADMIN_EMAIL` / `ADMIN_PASSWORD` fehlen → `seed_admin.py` crasht Container

**Dateien:** `scripts/backend-start.sh`, `scripts/seed_admin.py`

`backend-start.sh` hat `set -e` und ruft `seed_admin.py` auf:

```sh
set -e
...
python scripts/seed_admin.py   # ← fatal wenn env vars leer
```

`seed_admin.py` ruft `sys.exit(1)` wenn `ADMIN_EMAIL` oder `ADMIN_PASSWORD` leer sind:

```python
if not settings.admin_email or not settings.admin_password:
    sys.exit(1)
```

Beide sind `sync: false` in `render.yaml` → nie im Dashboard gesetzt → jeder
Deployment-Versuch crasht den Container nach der Alembic-Migration.

**Fix umgesetzt:** `seed_admin.py`-Aufruf ist jetzt nicht mehr fatal (FIX-1 in diesem PR).

---

### 🟡 WARN-1 — Cron-Services ohne `buildFilter` → unnötige Rebuilds bei jedem Push

**Datei:** `render.yaml`

Die 4 Cron-Services (`prisma-news-ingestion`, `prisma-crypto-daily`,
`prisma-smi-market-caps`, `prisma-stock-daily`) haben keinen `buildFilter`.

**Effekt:** Jeder Push auf `main` — auch reine Frontend-Änderungen — triggert
vollständige Docker-Rebuilds aller 4 Cron-Images (ca. 3–5 Min. each).
Auf Render Free Tier führt das zu:

- Build-Queue-Stau: Backend- und Frontend-Deploy warten hinter 4 Cron-Rebuilds
- Erhöhte Chance auf concurrent-build-Limits
- Unnötige Build-Minuten

**Fix umgesetzt:** Alle 4 Crons haben jetzt denselben `buildFilter` wie der Backend-Service
(FIX-2 in diesem PR).

---

### 🟡 WARN-2 — `NEXT_PUBLIC_API_KEY` muss identisch zu `API_KEY` sein (Dashboard-Check)

**Datei:** `render.yaml` (beide `sync: false`)

Wenn `API_KEY` (Backend) und `NEXT_PUBLIC_API_KEY` (Frontend) nicht denselben Wert
haben, schlägt **jeder** authentifizierte Frontend→Backend-Request mit HTTP 401 fehl.
Chat, Stocks, Crypto — alles.

Kein Code-Fix nötig — reine Dashboard-Konfiguration.

---

### 🟢 INFO — E2E-Failures in CI (behoben)

Playwright-E2E-Tests schlugen zwischen PR #267 und PR #269 fehl:

```
51× waiting for "http://localhost:3000/login" navigation to finish
```

Ursache: Die `prisma_token`-Cookie-Setzung im `global-setup.ts` funktionierte nicht
korrekt während des Auth-Transitions-Zeitfensters. Mit Merge von PR #269
(`feat(users): first_name/last_name`) ist `main` wieder grün (CI 13:05 Uhr).

Latente Warnung: `API_KEY` ist im E2E-Job nicht gesetzt. Das funktioniert weil
`require_admin_api_key` in non-production den leeren Key bypassed (`"" == ""` würde
nicht matchen, aber der Early-Return greift zuerst). Sobald `API_KEY` in CI gesetzt
wird, muss auch `NEXT_PUBLIC_API_KEY` im E2E-Job gesetzt werden.

---

## Fix-Plan

### FIX-1 — `seed_admin.py` non-fatal machen (`backend-start.sh`)

**Problem:** `set -e` + `sys.exit(1)` in `seed_admin.py` crasht Container bei fehlenden Vars  
**Lösung:** `|| true`-Pattern — Fehler geloggt, Container startet trotzdem  
**Status:** ✅ Umgesetzt in diesem PR

```sh
# Vorher:
python scripts/seed_admin.py

# Nachher:
if ! python scripts/seed_admin.py; then
    echo "WARNING: seed_admin.py fehlgeschlagen — ADMIN_EMAIL/ADMIN_PASSWORD/JWT_SECRET im Render-Dashboard prüfen."
    echo "Der Container startet trotzdem — seed kann manuell via Render Shell nachgeholt werden."
fi
```

---

### FIX-2 — `buildFilter` für alle 4 Cron-Services (`render.yaml`)

**Problem:** Crons rebuilden bei jedem Push, unabhängig von geänderten Dateien  
**Lösung:** Gleicher `buildFilter` wie beim Backend-Service  
**Status:** ✅ Umgesetzt in diesem PR

```yaml
buildFilter:
  paths:
    - backend/**
    - alembic.ini
    - pyproject.toml
    - uv.lock
    - Dockerfile.backend
```

---

### FIX-3 — Render Dashboard: 3 fehlende Env-Vars setzen (MANUELL, nicht im Code)

**Status:** ⬜ Muss manuell im Render-Dashboard erledigt werden

| Service | Key | Wert |
|---|---|---|
| prisma-v2-backend | `JWT_SECRET` | `openssl rand -hex 32` (lokal generieren, einfügen) |
| prisma-v2-backend | `ADMIN_EMAIL` | Admin-E-Mail-Adresse |
| prisma-v2-backend | `ADMIN_PASSWORD` | Starkes Passwort |
| prisma-v2-frontend | `NEXT_PUBLIC_API_KEY` | Identisch zu `API_KEY` im Backend |

Render-Dashboard → Service → Environment → "+ Add Environment Variable"

---

## Checkliste nach diesem PR

- [x] FIX-1: `seed_admin.py` non-fatal in `backend-start.sh`
- [x] FIX-2: `buildFilter` auf allen 4 Cron-Services
- [ ] FIX-3: `JWT_SECRET` im Render-Dashboard gesetzt
- [ ] FIX-3: `ADMIN_EMAIL` im Render-Dashboard gesetzt
- [ ] FIX-3: `ADMIN_PASSWORD` im Render-Dashboard gesetzt
- [ ] Verifiziert: `NEXT_PUBLIC_API_KEY` == `API_KEY` im Dashboard
- [ ] Erster Deploy nach PR-Merge: `/health` gibt 200
- [ ] `/health/ready` gibt `{"ready": true, "database": "ok"}`
- [ ] Login-Flow funktioniert im Browser

---

*Erstellt: 2026-06-18 · Branch: `fix/render-deploy-crashes-2026-06-18`*
