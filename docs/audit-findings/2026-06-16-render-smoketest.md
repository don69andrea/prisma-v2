# Audit-Findings — Render Smoke-Test (2026-06-16)

Read-only Smoke-Test gegen die deployte Render-Production-Instanz. Nur GET-Requests, keine Last, keine Wiederholungsschleifen.

- Backend: https://prisma-v2-backend.onrender.com
- Frontend: https://prisma-v2-frontend.onrender.com

## Getestete Endpoints

| Endpoint | Status | Antwortzeit | Hinweis |
|---|---|---|---|
| `GET /health` (Backend, 1. Aufruf) | 200 | 51.66s | Cold-Start (Render Free Tier) |
| `GET /health` (Backend, 2. Aufruf) | 200 | 0.234s | Warm |
| `GET /` (Frontend, 1. Aufruf) | 307 | 11.90s | Redirect → `/start`, eigener Cold-Start |
| `GET /` (Frontend, 2. Aufruf) | 307 | 0.574s | Warm |
| `GET /api/v1/universes` | 401 | 1.216s | "Invalid API key" — erwartet, kein Bug (Auth-Pflicht) |
| `GET /openapi.json` | 404 | 0.963s | Nicht verfügbar |
| `GET /docs`, `/redoc`, `/api/openapi.json`, `/api/v1/openapi.json`, `/api/v1/health` | 404 | <1s je | Keine Doku-/Alias-Pfade erreichbar |

## Versionsabgleich

- Render `/health` meldet: `version = 2.0.0`
- `pyproject.toml` (Arbeitsverzeichnis): `version = "2.2.0"`
- **Abweichung bestätigt** — Render-Deployment ist nicht auf dem aktuellen Stand.

## Befunde

### F-RENDER-1 — Render-Backend deployed veraltete Version (2.0.0 statt 2.2.0)
- **Bereich:** Deployment
- **Schweregrad:** Wichtig
- **Ort:** Backend `/health`, Vergleich mit `pyproject.toml`
- **Beschreibung:** Die Production-Instanz meldet Version 2.0.0, während der aktuelle Code-Stand im Arbeitsverzeichnis 2.2.0 ist. Render hat demnach nicht den neuesten `main`-Stand deployed.
- **Reproduktion:** `curl -s https://prisma-v2-backend.onrender.com/health` vs. `grep '^version' pyproject.toml`
- **Vorschlag:** Bekanntes mögliches Problem laut früherem PR (fehlende Deploy-Hook-Secrets) — Deploy-Hook-Konfiguration auf Render prüfen/erneut einrichten, kein neuer Bug, aber Re-Deploy notwendig, damit Production den aktuellen Stand widerspiegelt.

### F-RENDER-2 — Cold-Start auf Render Free Tier (~52s Backend, ~12s Frontend)
- **Bereich:** UX / Performance
- **Schweregrad:** Wichtig
- **Ort:** Backend `/health`, Frontend `/`
- **Beschreibung:** Der erste Request nach Inaktivität dauert beim Backend 51.66s und beim Frontend 11.90s, bevor die Instanz "aufgewacht" ist. Nachfolgende Requests sind mit 0.23s (Backend) bzw. 0.57s (Frontend) deutlich schneller. Für Endnutzer fühlt sich das wie ein Hänger/Absturz der App an, nicht wie normales Verhalten.
- **Reproduktion:** Erster `curl`-Call nach einer Phase ohne Traffic auf beide URLs zeigt die hohen Zeiten; ein zweiter Call direkt danach zeigt die warme Zeit.
- **Vorschlag:** Nice-to-have UX-Absicherung: Ladeindikator/Hinweistext im Frontend für den Fall einer langsamen ersten Antwort ("App startet, bitte einen Moment warten") und/oder Health-Check-Ping-Strategie (z. B. externer Uptime-Monitor), falls Cold-Starts in der Praxis stören. Kein Code-Bug, sondern eine Infrastruktur-Eigenschaft des Free Tiers.

### F-RENDER-3 — Kein OpenAPI-Schema in Production erreichbar
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have
- **Ort:** `/openapi.json`, `/docs`, `/redoc`, `/api/openapi.json`, `/api/v1/openapi.json`
- **Beschreibung:** Alle geprüften Doku-/Schema-Pfade liefern 404. Dadurch lässt sich der vollständige Endpoint-Katalog der Production-API nicht read-only über das Schema verifizieren (vermutlich bewusst deaktiviert, z. B. `docs_url=None` in Production-Konfiguration).
- **Reproduktion:** `curl -s -o /dev/null -w "%{http_code}" https://prisma-v2-backend.onrender.com/openapi.json` → 404
- **Vorschlag:** Falls die Deaktivierung in Production gewollt ist (üblich aus Sicherheitsgründen), kein Handlungsbedarf. Falls nicht beabsichtigt, Konfiguration prüfen, damit Audits/Doku-Konsumenten das Schema einsehen können.

### F-RENDER-4 — `/api/v1/universes` verlangt API-Key (erwartetes Verhalten)
- **Bereich:** Funktional
- **Schweregrad:** Nice-to-have
- **Ort:** `GET /api/v1/universes`
- **Beschreibung:** Endpoint liefert korrekt 401 mit `{"detail":"Invalid API key"}`, wenn kein gültiger X-API-Key gesendet wird. Dies ist das erwartete, korrekte Verhalten und kein Bug — wird hier nur als bestätigter Funktionscheck dokumentiert.
- **Reproduktion:** `curl -s https://prisma-v2-backend.onrender.com/api/v1/universes` → 401
- **Vorschlag:** Keine Aktion nötig. Bestätigt, dass Auth-Schutz auf Production aktiv ist.
