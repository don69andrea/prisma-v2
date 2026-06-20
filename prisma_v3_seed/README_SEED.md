# PRISMA V3 — Datensatz & Seed-Pipeline (Liefer-Paket)

Dieses Paket implementiert **Kapitel 15** des annotierten Master-Specs:
Datenquellen-verifizierung, Migrationen, eine idempotente Seed-Pipeline und die GitHub-Action.

> **Die Dateien hier spiegeln die Ziel-Pfade im Repo `prisma-v2`.**
> Vor dem Commit: in den passenden Repo-Ordner kopieren (Mapping unten), Feature-Branch, PR, CI grün, merge.

---

## 0 · Entscheidungen (begründet)

| Datenart | Quelle (Bootstrap, einmalig) | Quelle (inkrementell, Cron) | Warum |
|---|---|---|---|
| CH-Aktien Kurse | yfinance Bulk | yfinance | Gratis, `.SW`-Titel laufen, GH-Action-IPs nicht von Yahoo geblockt |
| Krypto Kurse | CryptoDataDownload CSV | CoinGecko (bereits verdrahtet) | CSV ohne Rate-Limit für Tiefe; CoinGecko für täglich |
| **Aktien Fundamentals** | **datengetrieben** — `verify_dataset_coverage.py` testet FMP + EODHD + SimFin-US und empfiehlt den Gewinner | gewählter Provider | CH-Fundamentals sind bei allen Free-Tiers wackelig → **nicht raten, messen** |

**Primär-Empfehlung Fundamentals:** EODHD (echte SIX-Coverage). **Garantierter Fallback:** SimFin-US als
methodischer ML-Datensatz (exzellente US-Coverage, reproduzierbar), falls CH-Coverage rot ist.

**Trainingstiefe:** Aktien ab 2015 (~11 J., enthält CS-Kollaps 2023), Krypto daily ab 2017, Krypto 1h ab 2020.

---

## 1 · Datei-Mapping (hier → Repo)

```
prisma_v3_seed/                                  →  prisma-v2/
├── alembic/0031..0035_*.py                      →  backend/alembic/versions/
├── persistence/models/*.py                      →  backend/infrastructure/persistence/models/
├── persistence/repositories/timeseries_repository.py
│                                                →  backend/infrastructure/persistence/repositories/
├── adapters/eodhd_fundamentals_adapter.py       →  backend/infrastructure/adapters/
├── pipeline/{extract,normalize,validate,load}.py→  backend/application/pipeline/
├── scripts/verify_dataset_coverage.py           →  scripts/
├── scripts/seed_historical_prices.py            →  scripts/
├── scripts/seed_crypto_history.py               →  scripts/
├── scripts/seed_fundamentals.py                 →  scripts/
├── config_additions.py                          →  in backend/config.py einarbeiten
└── workflows/historical-seed.yml                →  .github/workflows/
```

## 2 · Reihenfolge (Phase 0 → Seed)

```bash
# 0) GATE — entscheidet die Fundamentals-Quelle. MUSS zuerst grün sein.
uv run python scripts/verify_dataset_coverage.py        # schreibt docs/dataset_coverage.md

# 1) Migrationen
uv run alembic upgrade head

# 2) Bootstrap-Seed (einmalig, Reihenfolge egal)
uv run python scripts/seed_historical_prices.py --from 2015-01-01
uv run python scripts/seed_crypto_history.py    --from 2017-01-01
uv run python scripts/seed_fundamentals.py      --provider auto --from 2015-01-01
```

## 3 · Konventionen, an die sich der Code hält

- Migrationen: `String(36)`-PK (app-generierte UUID), `revision`/`down_revision` — wie 0001–0030.
- Repos: raw SQL via `text()`, eigene Session via `get_session_factory()` — wie `cost_log_repository`.
- Settings: pydantic `Settings`-Felder (kein nacktes `os.getenv`) — siehe `config_additions.py`.
- Idempotenz: alle Writes sind `INSERT ... ON CONFLICT DO NOTHING` über die `UNIQUE`-Constraints.
- Fehler werden **geloggt, nicht still verschluckt** (kein Stub-Fallback im Trainingspfad).
