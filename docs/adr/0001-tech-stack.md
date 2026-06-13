# ADR 0001: Tech-Stack

- **Status**: Accepted
- **Datum**: 2026-04-21
- **Kontext**: Projekt-Initialisierung PRISMA V2

## Kontext

Wir bauen PRISMA von 0 auf. Entscheidungen zu Sprache, Framework, DB, Frontend, LLM-Provider, Deployment müssen früh getroffen werden, weil spätere Wechsel teuer sind. Das Bewertungsraster des Moduls priorisiert AI-assisted Development (40%), Testing (15%), CI/CD (15%), Dokumentation (15%) — der Stack muss diese Achsen unterstützen.

## Optionen pro Entscheidung

### Backend-Sprache
- **Python** (gewählt): Ökosystem für Quant (pandas, numpy, scikit-learn) + LLM-SDKs (anthropic, mcp) beide erstklassig. FastAPI liefert OpenAPI gratis.
- TypeScript/Node: Starkes Frontend-Matching, aber Quant-Libraries schwächer.
- Go: Performance top, aber LLM- und Quant-Ecosystem dünn.

### Web-Framework
- **FastAPI** (gewählt): Native Pydantic-Integration, automatische OpenAPI/Swagger, async-first, populär.
- Django: Mehr "batteries included", aber schwergewichtig für API-only.
- Flask: Leichtgewichtig, aber keine nativen async/OpenAPI-Features.

### ORM
- **SQLAlchemy 2.0** + Alembic (gewählt): Industriestandard, volle Kontrolle, gute Migrations.
- SQLModel: Pydantic-Integration nett, aber jünger, weniger Doku.
- Django ORM: ausgeschlossen mit FastAPI-Entscheidung.

### Datenbank
- **PostgreSQL 16** (gewählt): Modul verlangt relationales ORM. Render bietet managed Postgres gratis. pgvector-Extension für optionales RAG verfügbar.
- SQLite: zu eingeschränkt für Production-Deploy.
- MySQL: funktioniert, aber Postgres ist fortgeschrittener und Render-nativ.

### LLM-Provider
- **Anthropic Claude** (gewählt): Modul-Fit (Curriculum referenziert Claude explizit), starke Structured-Output-Qualität, Prompt-Caching senkt Kosten deutlich, MCP ist Anthropic-Standard.
- OpenAI: valide Alternative, aber MCP-Integration ist Anthropic-nativ.
- Open-Weight (Llama, Mistral): interessant für Privacy, aber Betriebs-Overhead für das Projekt zu hoch.

### Frontend
- **Next.js 14 (App Router)** + shadcn/ui + Recharts (gewählt): Enterprise-Look, gute DX mit Coding-Agents, shadcn ist flexibel und nicht überladen.
- Streamlit: extrem schnell zu bauen, aber wirkt wie Prototyp in der Präsi.
- React ohne Framework: mehr Boilerplate, weniger Agent-freundlich.

### Testing
- **pytest + Playwright** (gewählt): de-facto Standard Python, Playwright ist moderner als Cypress.
- unittest: zu verbose.
- Selenium: veraltet gegenüber Playwright.

### CI/CD
- **GitHub Actions** (gewählt): Modul-Erwartung, nativ integriert mit GitHub-Repo.
- GitLab CI / CircleCI: würde zusätzlichen Setup-Overhead bedeuten.

### Deployment
- **Render** (Web Service + Postgres managed, gewählt): Modul-Empfehlung, niedriger Ops-Overhead, Free-Tier verfügbar, Auto-Deploy bei Push.
- Fly.io, Railway: valide Alternativen, aber Render ist explizit im Modul-Text erwähnt.
- Eigener Kubernetes-Cluster: ausgeschlossen, Over-Engineering für das Projekt.

### Container
- **Docker + docker-compose** (gewählt): Modul-Pflicht.

## Entscheidung

Python 3.12, FastAPI, SQLAlchemy 2.0 + Alembic, PostgreSQL 16, Anthropic Claude API, MCP SDK, Next.js 14 mit shadcn/ui + Recharts, pytest + Playwright, GitHub Actions, Render, Docker.

## Konsequenzen

### Positiv
- Alle Modul-Pflichtkriterien (OpenAPI, relationales ORM, Docker, Cloud-Deploy) werden nativ erfüllt.
- Ecosystem-Fit für Quant + LLM ist optimal.
- Coding-Agents (Claude Code, Copilot) sind in allen Stack-Teilen hochkompetent.

### Negativ
- Python-only-Backend limitiert bei Latenz-kritischem Code — für PRISMA-Scope irrelevant.
- Next.js hat Bundle-Size-Kosten gegenüber Streamlit — durch Enterprise-Präsentations-Wert kompensiert.
- Render Free-Tier hat Cold-Starts — für Demo akzeptabel, Upgrade auf Starter Plan (~7 $/Monat) bei Bedarf.

### Folge-Entscheidungen (werden separate ADRs)
- ADR-0002: Monorepo vs. getrennte Repos für Backend/Frontend
- ADR-0003: Vector-Store-Wahl (pgvector vs. dedicated) — erst relevant bei RAG-Phase
- ADR-0004: LLM-Modell-Routing (Haiku vs. Sonnet je Use Case)
