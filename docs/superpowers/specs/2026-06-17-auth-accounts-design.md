# Auth & User Accounts — Design Spec
**Datum:** 2026-06-17  
**Status:** Genehmigt  
**Scope:** Feature 1 von 2 (Feature 2: Vollständiges Admin-UI folgt separat)

---

## Ziel

Echtes Login-System mit vollständiger Datenisolation pro User. Testende Personen erhalten jeweils eine isolierte Umgebung mit sauberem Start. Admin erstellt Accounts manuell, kein Self-Registration.

---

## Nicht in diesem Scope

- Vollständiges Admin-UI für alle Backend-Funktionen (→ separates Feature 2)
- OAuth / Magic Links / externe Auth-Provider
- Self-Registration durch Nutzer
- Password-Reset per Email

---

## 1. Datenbankschema

### Neue Tabelle: `users`

| Spalte | Typ | Constraints |
|---|---|---|
| `id` | UUID | PK, default gen_random_uuid() |
| `email` | VARCHAR | UNIQUE, NOT NULL |
| `hashed_password` | VARCHAR | NOT NULL (bcrypt) |
| `role` | ENUM `user_role` | NOT NULL: `"admin"` \| `"viewer"` |
| `is_active` | BOOLEAN | NOT NULL, default true |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() |

### `user_id` FK auf persönliche Entities

Folgende Tabellen erhalten `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`:

- `alert`
- `backtest_result`
- `decision_audit_log`
- `research_memo`
- `ranking_run`
- `llm_call_log`
- `memo_batch_job`
- `investor_profile`

**Migrationsstrategie:** Frischer Start. Bestehende User-Daten werden vor der Migration geleert (TRUNCATE). `user_id` ist von Anfang an NOT NULL.

### Unveränderte Tabellen (geteilte Marktdaten)

`stock`, `news`, `ml_features`, `embedding`, `swiss_filing`, `crypto_signal`, `universe`

---

## 2. Backend Auth-Layer

### Neue Pakete

```
python-jose[cryptography]
passlib[bcrypt]
```

### Neue Dateien (Clean Architecture)

```
backend/
├── domain/
│   └── entities/user.py                          # User-Entity, UserRole-Enum
├── application/
│   └── services/auth_service.py                  # login(), create_user(), reset_user(), hash_password(), verify_token()
├── infrastructure/
│   ├── persistence/models/user.py                # SQLAlchemy-Model
│   └── persistence/repositories/user_repository.py  # get_by_email(), get_by_id(), list_all(), save(), delete_user_data()
└── interfaces/rest/
    ├── routers/auth.py                            # POST /auth/login, GET /auth/me
    └── routers/users.py                           # Admin: CRUD User-Management
```

### Auth-Endpoints

| Method | Path | Auth | Beschreibung |
|---|---|---|---|
| POST | `/auth/login` | — | Email + Passwort → JWT access_token |
| GET | `/auth/me` | User | Aktueller User (id, email, role) |
| GET | `/users` | Admin | Alle User auflisten |
| POST | `/users` | Admin | User erstellen |
| PATCH | `/users/{id}` | Admin | User sperren / Passwort ändern |
| DELETE | `/users/{id}/data` | Admin | User-Daten reset (nicht User selbst) |

### JWT

- Library: `python-jose`
- Payload: `{ sub: user_id, role, exp }`
- Ablauf: 8 Stunden
- Secret: `JWT_SECRET` in `.env`

### Dependencies (ersetzen `require_admin_api_key`)

```python
require_current_user()   # Prüft JWT, gibt User zurück; 401 bei fehlendem/ungültigem Token
require_admin_role()     # Wie oben + prüft role == "admin"; 403 sonst
```

Alle 23 bestehenden Router ersetzen `require_admin_api_key` durch `require_current_user`. Admin-Endpoints (costs, user management) erhalten zusätzlich `require_admin_role`.

### Seed-Script

Beim ersten Start (`scripts/seed_admin.py`) wird ein Admin-User aus Umgebungsvariablen erstellt:

```
ADMIN_EMAIL=...
ADMIN_PASSWORD=...
```

Idempotent: läuft ohne Fehler durch, falls Admin bereits existiert.

---

## 3. Frontend

### Neue Seiten

```
frontend/app/
├── login/
│   └── page.tsx          # Login-Formular: Email + Passwort, Fehlermeldung bei 401
└── admin/
    ├── layout.tsx         # Schutz: nur role="admin", sonst redirect /login
    ├── page.tsx           # Kosten-Dashboard (bestehender /admin/costs Endpoint)
    └── users/
        ├── page.tsx       # User-Liste: Email, Rolle, Status, Erstelldatum
        └── [id]/
            └── page.tsx   # User-Detail: Passwort setzen, sperren/aktivieren, Daten-Reset
```

### Auth-State

`hooks/useAuth.ts` — zentraler Hook:
- JWT im `localStorage` gespeichert
- Stellt `user`, `login()`, `logout()` bereit
- Bei 401-Response vom API: automatisch logout + redirect `/login`

### API-Client

`lib/api.ts` bekommt Interceptor: jeder Request erhält automatisch `Authorization: Bearer <token>`.

### Middleware (`middleware.ts`)

Aktuelle Logik (Cookie `prisma_onboarding`) wird ersetzt:
- Kein JWT vorhanden → redirect `/login`
- JWT vorhanden aber abgelaufen → redirect `/login`
- Pfade `/login`, `/_next`, `/api` bleiben öffentlich

Der `/start`-Onboarding-Flow entfällt als Einstiegspunkt. Die Discovery-Engine (Conversational Investor-Profiling) bleibt als Feature erhalten, wird aber nach dem Login als eigene Seite zugänglich gemacht — nicht mehr als Pre-Login-Gate. Der `/discovery`-Backend-Router bleibt unverändert.

---

## 4. Neue `.env`-Variablen

```env
JWT_SECRET=<random 32+ char string>
JWT_EXPIRE_HOURS=8
ADMIN_EMAIL=andrea@example.com
ADMIN_PASSWORD=<sicheres passwort>
```

---

## 5. Nicht-Ziele (bewusst ausgelassen)

- Refresh Tokens (8h reicht für Testsessions)
- Password-Reset per Email (Admin setzt Passwort manuell)
- Audit-Log für Admin-Aktionen (kann in Feature 2 ergänzt werden)
- Rate-Limiting auf Login-Endpoint (intern, kein öffentliches Risiko)
