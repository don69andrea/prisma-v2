# Getting Started

Ziel: PRISMA lokal zum Laufen bringen in unter 10 Minuten.

## Voraussetzungen

Stelle sicher, dass folgende Tools installiert sind:

| Tool | Mindestversion | Installieren |
|------|---------------|--------------|
| Git | beliebig | [git-scm.com](https://git-scm.com) |
| Docker Desktop | beliebig | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Python | 3.12+ | [python.org](https://www.python.org) oder `brew install python` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) oder `brew install node` |

Versionen prüfen:
```bash
python3 --version   # Python 3.12+
node --version      # v20+
docker --version    # beliebig
```

> **Mac-Nutzer:** Docker Desktop muss nach der Installation einmal geöffnet und gestartet werden (Wal-Icon in der Menüleiste muss ruhig stehen).

## 1. Repo klonen

```bash
git clone https://github.com/SheylaSam/prisma-capstone.git
cd prisma-capstone
```

## 2. Python-Umgebung einrichten

macOS und neuere Linux-Distributionen erlauben keine systemweiten pip-Installationen. Deshalb arbeiten wir mit einem Virtual Environment — einer isolierten Python-Umgebung nur für dieses Projekt:

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## 3. Node-Pakete installieren

```bash
cd frontend
npm install
cd ..
```

## 4. Environment-Variablen konfigurieren

```bash
cp .env.example .env
```

Öffne `.env` und trage folgende Werte ein:

| Variable | Woher | Pflicht |
|----------|-------|---------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys | Ja |
| `FINNHUB_API_KEY` | [finnhub.io](https://finnhub.io) → kostenlos registrieren | Ja |
| `API_KEY` | Selbst generieren (Befehl unten) | Ja |

`API_KEY` generieren:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 5. Services starten

```bash
docker compose up -d
```

Docker baut und startet drei Container:
- `prisma-db` — PostgreSQL 16 mit pgvector
- `prisma-backend` — FastAPI (führt automatisch Datenbankmigrationen aus)
- `prisma-frontend` — Next.js

Beim ersten Start werden Docker-Images heruntergeladen (~200 MB). Das dauert je nach Verbindung 1–3 Minuten.

## 6. Verify — läuft alles?

Container-Status prüfen (alle drei sollten `healthy` oder `Up` zeigen):
```bash
docker ps
```

Backend-Health-Check:
```bash
curl http://localhost:8000/health
# Erwartete Antwort: {"status":"ok"}
```

Dann im Browser öffnen:
- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **API-Dokumentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

## Troubleshooting

**`docker compose` gibt Fehler "unknown command"**
Docker Desktop läuft nicht. Öffne die App und warte bis das Wal-Icon in der Menüleiste ruhig ist.

**Port 5432 / 8000 / 3000 bereits belegt**
Ein anderer Prozess nutzt diesen Port. Prüfen mit:
```bash
lsof -i :5432    # oder :8000 / :3000
```
Den Prozess beenden oder in `docker-compose.yml` den Port anpassen.

**Backend startet, aber `{"status":"ok"}` kommt nicht**
Logs des Backend-Containers prüfen:
```bash
docker logs prisma-backend
```

**`pip install` schlägt fehl mit "externally-managed-environment"**
Du hast das venv vergessen zu aktivieren:
```bash
source .venv/bin/activate
```

**Änderungen am Backend werden nicht übernommen**
Das Backend läuft mit `--reload`, Dateiänderungen werden automatisch erkannt. Falls nicht:
```bash
docker compose restart backend
```

## Services stoppen

```bash
docker compose down          # Container stoppen (Daten bleiben erhalten)
docker compose down -v       # Container + Datenbank-Volumen löschen (Reset)
```
