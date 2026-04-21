# PRISMA — Frontend

Next.js 14 App Router frontend fur das quantitative Stock-Selection-Tool PRISMA.

## Purpose

Stellt die Web-UI fur PRISMA bereit: Universum-Verwaltung, farbcodierte Ranking-Tabellen,
Factsheets mit Fundamentaldaten und Charts, AI-Research-Memos sowie Backtest-Auswertungen.

## Entwicklung starten

**Empfohlen: via docker-compose (vom Repo-Root)**

```bash
docker compose up -d
```

Das Frontend ist dann unter `http://localhost:3000` erreichbar.

**Alternativ: lokal**

```bash
cp .env.local.example .env.local
npm install
npm run dev
```

## Umgebungsvariablen

| Variable              | Beschreibung                          | Default                   |
|-----------------------|---------------------------------------|---------------------------|
| `NEXT_PUBLIC_API_URL` | Basis-URL des FastAPI-Backends        | `http://localhost:8000`   |

## Projekt-Struktur

```
app/              # Next.js App Router (Seiten, Layouts, Providers)
  globals.css     # Tailwind + shadcn CSS-Variablen
  layout.tsx      # Root-Layout mit Header und QueryClientProvider
  page.tsx        # Landing-Page / Dashboard
  providers.tsx   # React Query Provider (Client Component)
components/
  ui/             # shadcn/ui Basiskomponenten (Button, Card, Table, Badge, Input)
  health-status.tsx  # API-Health-Indikator
lib/
  api/            # Typisierter API-Client
    client.ts     # apiFetch<T> Wrapper
    health.ts     # /health Endpunkt
  utils.ts        # cn() Helper (clsx + tailwind-merge)
```

## Lint / Format

```bash
npm run lint
npm run lint:fix
npm run format
```
