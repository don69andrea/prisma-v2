# Spec: Universe-REST-Endpoints + Frontend-Seiten

**Status:** Implementiert — 2026-05-13
**Issue:** [#47 feat(frontend): /universes Page mit Form](https://github.com/don69andrea/prisma-v2/issues/47)
**Haupt-Spec:** `docs/specs/2026-04-21-prisma-v2-design.md` §11 (Frontend)
**Assignee:** Nicolas Lardinois

---

## Kontext

Der CTA-Button auf der Homepage zeigt auf `/universes`, die Route existierte bisher nicht. Issue #20 (Dashboard/Run starten) benötigt ein Universum — ohne UI kann kein Universum angelegt werden. Die Domain-Schicht (Entity, Repository-Port, SQLAlchemy-Adapter, ORM-Modell, Migration) ist vollständig vorhanden. Fehlend: REST-Layer und Frontend.

---

## Scope

### Backend (thin REST-Layer, keine neue Geschäftslogik)

| Endpoint | Methode | Status |
|---|---|---|
| `/api/v1/universes` | GET | Liste aller Universen |
| `/api/v1/universes/{id}` | GET | Einzelnes Universum |
| `/api/v1/universes` | POST | Neues Universum anlegen |

Kein DELETE/PUT im MVP (nicht für Issue #47 benötigt).

**Neue Dateien:**
- `backend/interfaces/rest/schemas/universe.py` — `UniverseCreateRequest`, `UniverseRead`, `UniverseListResponse`
- `backend/application/services/universe_service.py` — `UniverseService` mit `list_universes`, `get_universe`, `create_universe`
- `backend/interfaces/rest/routers/universes.py` — FastAPI Router

**Modifizierte Dateien:**
- `backend/interfaces/rest/dependencies.py` — `get_universe_service` DI-Funktion
- `backend/interfaces/rest/app.py` — Router registrieren

### Frontend

| Route | Komponente | Funktion |
|---|---|---|
| `/universes` | UniverseList (`page.tsx`) | Liste aller Universen, CTA zu `/universes/new` |
| `/universes/new` | UniverseForm (`new/page.tsx`) | Formular: Name, Region, Ticker (kommagetrennt) |

Beide Seiten: Loading-Skeleton + Error-State (TanStack Query).

**Vitest-Setup** (Issue-AC: Mind. 1 Komponenten-Test):
- `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
- `frontend/vitest.config.ts` + `frontend/vitest.setup.ts`
- Test: `frontend/app/universes/__tests__/universe-list.test.tsx`

---

## Datenmodell (bereits in Domain)

```
Universe
  id: UUID
  name: str          (nicht leer)
  region: str
  tickers: tuple[str, ...]  (uppercase)
```

---

## Nicht in Scope

- Universe bearbeiten / löschen (kein PUT/DELETE)
- Ticker-Validierung gegen Live-Daten (nur Format)
- Authentifizierung / Authorization
- Pagination auf Universum-Liste (MVP: alle laden)
