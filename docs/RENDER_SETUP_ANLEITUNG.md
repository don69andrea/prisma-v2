# PRISMA V2 — Render Setup Anleitung

> **Für wen:** Alle, die PRISMA V2 auf Render deployen oder den "Deploy fehlgeschlagen"-Fehler beheben wollen.  
> **Warum jetzt:** PR #267 (JWT-Auth) hat drei neue Pflicht-Variablen eingeführt, die nie im Render-Dashboard gesetzt wurden. Jeder Deploy crasht seitdem.

---

## Überblick: Was passiert beim Deploy

Wenn Code auf `main` gepusht wird, läuft folgende Kette:

```
GitHub Push auf main
  → CI (GitHub Actions): Tests laufen
    → CD (GitHub Actions): Render Deploy Hook wird ausgelöst
      → Render: Docker Image wird gebaut
        → Container startet: backend-start.sh läuft
            1. alembic upgrade head   ← Datenbank-Migrationen
            2. python seed_admin.py   ← Admin-User anlegen
            3. uvicorn starten        ← Server hochfahren
          → /health antwortet 200
            → Deploy erfolgreich ✅
```

**Was jetzt passiert (und warum es fehlschlägt):**

```
Container startet: backend-start.sh läuft
  1. alembic upgrade head ✅
  2. python seed_admin.py
       → JWT_SECRET nicht gesetzt → ValueError wird geworfen
       → ODER: ADMIN_EMAIL/ADMIN_PASSWORD fehlen → sys.exit(1)
     → set -e: Shell beendet sich sofort
  → Container crasht
  → /health antwortet nie
  → Render: "Deploy fehlgeschlagen" ❌
```

---

## Teil 1: Render Dashboard — Umgebungsvariablen setzen

Das ist der wichtigste Schritt. Ohne diesen nützen alle Code-Fixes nichts.

### Schritt 1: Render Dashboard öffnen

1. Geh auf **https://dashboard.render.com**
2. Melde dich an
3. Du siehst deine Services: `prisma-v2-backend`, `prisma-v2-frontend`, die Cron-Jobs

---

### Schritt 2: Backend — fehlende Env-Vars setzen

Klicke auf **`prisma-v2-backend`** → linkes Menü → **"Environment"**

Du siehst eine Liste von Umgebungsvariablen. Folgende müssen gesetzt sein:

#### 2a. `JWT_SECRET` generieren und setzen

Dieses Secret signiert alle Login-Tokens. Es muss zufällig und geheim sein.

**Im Terminal auf deinem Mac generieren:**
```bash
openssl rand -hex 32
```

Das gibt dir z.B.: `a3f8c2d1e4b5...` (64 Zeichen hex)

**Im Render-Dashboard:**
- Klick auf **"+ Add Environment Variable"**
- Key: `JWT_SECRET`
- Value: Den generierten Wert einfügen
- Klick **"Save Changes"**

> ⚠️ Diesen Wert nirgends committen oder teilen. Wer ihn hat, kann sich als beliebiger User einloggen.

---

#### 2b. `ADMIN_EMAIL` setzen

Das ist die E-Mail-Adresse des ersten Admin-Users, der beim Start automatisch angelegt wird.

- Key: `ADMIN_EMAIL`
- Value: z.B. `andrea.petretta@students.fhnw.ch`

---

#### 2c. `ADMIN_PASSWORD` setzen

Das Passwort für den Admin-User. Mindestens 12 Zeichen empfohlen.

**Tipp — sicheres Passwort generieren:**
```bash
openssl rand -base64 16
```

- Key: `ADMIN_PASSWORD`
- Value: Das gewählte/generierte Passwort

> Merk dir dieses Passwort — du brauchst es zum Einloggen ins Frontend.

---

#### 2d. Prüfen: Sind diese Variablen bereits gesetzt?

Checke gleichzeitig, ob diese ebenfalls vorhanden sind (sollten schon da sein, aber sicher ist sicher):

| Variable | Muss gesetzt sein? | Typischer Wert |
|---|---|---|
| `API_KEY` | ✅ Ja | `openssl rand -hex 32` |
| `ANTHROPIC_API_KEY` | ✅ Ja | Dein Anthropic API Key |
| `DATABASE_URL` | ✅ Ja | Wird von Render auto-gesetzt (fromDatabase) |
| `ENVIRONMENT` | ✅ Ja | `production` |

Wenn `API_KEY` oder `ANTHROPIC_API_KEY` fehlen, startet der Backend-Container ebenfalls nicht (separate Validator im Code).

---

### Schritt 3: Frontend — `NEXT_PUBLIC_API_KEY` setzen

Klicke auf **`prisma-v2-frontend`** → **"Environment"**

- Key: `NEXT_PUBLIC_API_KEY`
- Value: **Exakt denselben Wert wie `API_KEY` im Backend**

> Wenn diese beiden Werte nicht identisch sind, antwortet das Backend auf jeden Frontend-Request mit HTTP 401 (Unauthorized). Chat, Stocks, Crypto — alles bricht.

---

### Schritt 4: Manuellen Deploy triggern

Nachdem alle Variablen gesetzt sind:

1. Klick auf **`prisma-v2-backend`**
2. Oben rechts: **"Manual Deploy"** → **"Deploy latest commit"**
3. Logs beobachten — du solltest sehen:
   ```
   ==> Running alembic migrations...
   INFO  [alembic.runtime.migration] Running upgrade ...
   ==> Seeding admin user...
   Admin created: 'deine@email.com' (id=1)
   ==> Starting uvicorn on 0.0.0.0:8000 ...
   Application startup complete.
   ```
4. Status wechselt zu **"Live"** ✅

---

## Teil 2: Code-Fixes (einmalig, werden per PR gemergt)

Diese Fixes sorgen dafür, dass zukünftige Deploys robuster sind, auch wenn mal eine Variable fehlt.

### Fix 1: `backend-start.sh` — seed_admin nicht mehr fatal

**Datei:** `scripts/backend-start.sh`

**Problem:** `set -e` + `sys.exit(1)` in `seed_admin.py` = Container crasht sofort.  
**Fix:** Fehler loggen, aber weitermachen.

```sh
# VORHER (bricht den Container):
python scripts/seed_admin.py

# NACHHER (loggt den Fehler, startet trotzdem):
if ! python scripts/seed_admin.py; then
    echo "WARNING: seed_admin.py fehlgeschlagen."
    echo "Prüfe ADMIN_EMAIL, ADMIN_PASSWORD, JWT_SECRET im Render-Dashboard."
    echo "Container startet trotzdem — seed kann via Render Shell nachgeholt werden."
fi
```

**Warum das sinnvoll ist:** Alembic-Migrationen (Datenbank-Schema) sollen bei Fehler stoppen — das ist korrekt, ein kaputtes Schema ist ein Show-Stopper. Aber der Admin-User-Seed ist kein Show-Stopper. Der Server kann laufen ohne Admin-User. Du kannst den Seed dann via Render Shell manuell nachholen.

---

### Fix 2: `render.yaml` — Cron-Jobs nur bei Backend-Änderungen rebuilden

**Datei:** `render.yaml`

**Problem:** Alle 4 Cron-Jobs haben keinen `buildFilter`. Das bedeutet: Jeder Push auf `main` — auch wenn nur CSS geändert wurde — rebuildet alle 4 Cron-Docker-Images neu (je ~3–5 Minuten).

**Fix:** Denselben `buildFilter` wie beim Backend-Service hinzufügen:

```yaml
# Bei jedem Cron-Service einfügen (zwischen schedule: und dockerCommand:):
buildFilter:
  paths:
    - backend/**
    - alembic.ini
    - pyproject.toml
    - uv.lock
    - Dockerfile.backend
```

**Betrifft:**
- `prisma-news-ingestion`
- `prisma-crypto-daily`
- `prisma-smi-market-caps`
- `prisma-stock-daily`

---

## Teil 3: Verifikation — So weisst du, dass alles funktioniert

### 3a. Health Check (Backend)

```bash
curl https://prisma-v2-backend.onrender.com/health
```

Erwartete Antwort:
```json
{"status": "ok", "version": "2.1.0"}
```

### 3b. Database-Ready Check

```bash
curl https://prisma-v2-backend.onrender.com/health/ready
```

Erwartete Antwort:
```json
{"ready": true, "database": "ok"}
```

### 3c. Login testen

```bash
curl -X POST https://prisma-v2-backend.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "deine@email.com", "password": "dein-passwort"}'
```

Erwartete Antwort:
```json
{"access_token": "eyJ...", "token_type": "bearer"}
```

### 3d. Frontend öffnen

Geh auf **https://prisma-v2-frontend.onrender.com**

- Login-Seite erscheint ✅
- Mit ADMIN_EMAIL + ADMIN_PASSWORD einloggen ✅
- Dashboard lädt ohne 401-Fehler ✅

---

## Teil 4: Troubleshooting

### "Deploy fehlgeschlagen" — was tun?

1. **Render Dashboard → `prisma-v2-backend` → "Logs"** öffnen
2. Nach dem Fehler suchen:

| Log-Meldung | Ursache | Fix |
|---|---|---|
| `ValueError: JWT_SECRET muss in der Production-Umgebung gesetzt sein` | `JWT_SECRET` nicht gesetzt | Schritt 2a |
| `ERROR: ADMIN_EMAIL and ADMIN_PASSWORD must be set` | Env-Vars fehlen | Schritt 2b/2c |
| `ValueError: API_KEY muss in der Production-Umgebung gesetzt sein` | `API_KEY` nicht gesetzt | Schritt 2d |
| `ERROR: ANTHROPIC_API_KEY muss in der Production-Umgebung gesetzt sein` | Anthropic Key fehlt | Schritt 2d |
| `ERROR: Alembic-Migration fehlgeschlagen` | DB-Schema-Problem | Code-Bug, PR nötig |

### Frontend zeigt 401 auf allen Seiten

`NEXT_PUBLIC_API_KEY` im Frontend stimmt nicht mit `API_KEY` im Backend überein.
→ Schritt 3: Beide Werte exakt angleichen, dann Frontend manuell deployen.

### Admin-User kann sich nicht einloggen

`seed_admin.py` hat den User vielleicht nie angelegt. Prüfen:
```bash
# In der Render Shell (prisma-v2-backend → "Shell"):
python scripts/seed_admin.py
```

### Render Free Tier: Cold Start (erster Request nach Inaktivität langsam)

Render Free Tier suspendiert Web-Services nach 15 Minuten ohne Traffic. Der erste Request nach Inaktivität kann 30–60 Sekunden dauern. Das ist normal und kein Bug.

---

## Checkliste: Deploy-Ready

```
[ ] JWT_SECRET im Render-Dashboard gesetzt (Backend)
[ ] ADMIN_EMAIL im Render-Dashboard gesetzt (Backend)
[ ] ADMIN_PASSWORD im Render-Dashboard gesetzt (Backend)
[ ] API_KEY im Render-Dashboard gesetzt (Backend)
[ ] ANTHROPIC_API_KEY im Render-Dashboard gesetzt (Backend)
[ ] NEXT_PUBLIC_API_KEY == API_KEY (Frontend, exakt gleich)
[ ] Manueller Deploy gestartet nach Env-Var-Änderungen
[ ] /health gibt {"status": "ok"} zurück
[ ] /health/ready gibt {"ready": true, "database": "ok"} zurück
[ ] Login mit ADMIN_EMAIL + ADMIN_PASSWORD funktioniert
```

---

*Letzte Aktualisierung: 2026-06-18 — Befund: RENDER_DEPLOY_BEFUND_2026-06-18.md*
