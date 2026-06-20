# Dataset Coverage Report

Generiert: 2026-06-20 | Akzeptanz: >= 20 Quartale, < 20% Nulls.

| Quelle | Titel | Quartale | Null-Quote | ok |
|---|---|---|---|---|
| eodhd (CH) | NESN | 0 | 100% | ❌ |
| eodhd (CH) | NOVN | 0 | 100% | ❌ |
| eodhd (CH) | ROG | 0 | 100% | ❌ |
| fmp (CH) | NESN | 0 | 100% | ❌ |
| fmp (CH) | NOVN | 0 | 100% | ❌ |
| fmp (CH) | ROG | 0 | 100% | ❌ |
| simfin_us (US-Proxy) | AAPL | 0 | 100% | ❌ |
| simfin_us (US-Proxy) | MSFT | 0 | 100% | ❌ |
| simfin_us (US-Proxy) | JNJ | 0 | 100% | ❌ |

## Empfehlung: **KEINE Quelle besteht — Plan B (US-Proxy) wählen**

→ `dataset_source_fundamentals = "simfin_us"` als ML-Methodik-Datensatz verwenden.
→ Swiss-Live-Signale nutzen yfinance `.info` für approximierte Fundamentals.

## Entscheidungsregel

1. Wenn FMP >= 20 Quartale mit < 20% Nulls für alle Probe-Titel: `dataset_source_fundamentals = "fmp"`
2. Sonst wenn EODHD Key vorhanden und besteht: `dataset_source_fundamentals = "eodhd"`
3. Sonst: `dataset_source_fundamentals = "simfin_us"` (US-Proxy, akademisch reproduzierbar).

Referenz: PRISMA V3 Spec CHALLENGE 01 / Kap. 15.5.

---

## Entscheidung (2026-06-20)

**Gewählt: `dataset_source_fundamentals = "simfin_us"`**

### Begründung

Kein CH-Fundamentals-Provider war ohne neuen API-Key verfügbar:

- **EODHD**: kein `EODHD_API_KEY` gesetzt — übersprungen. Free-Tier knapp (20 Calls/Tag); ein Paid-Key würde echte SIX-Coverage liefern. Wenn später EODHD_API_KEY in Render Secrets gesetzt wird, erneut ausführen: Skript wählt EODHD automatisch.
- **FMP**: `FMP_API_KEY` ist Platzhalter (`"your-fmp-key"`) — übersprungen. Mit einem echten Key (Free Tier: 250 Calls/Tag, `/key-metrics?period=quarter`) würde FMP als erste Wahl gelten, da der Key bereits in config.py und Render vorhanden ist.
- **SimFin US**: `SIMFIN_API_KEY` nicht gesetzt — übersprungen. SimFin liefert keine brauchbaren CH-Fundamentals (Free Tier), aber exzellente US-Coverage.

### Was `simfin_us` konkret bedeutet

- Das **ML-Modell** wird auf US-Titeln (S&P-Querschnitt) trainiert — methodisch sauber, akademisch reproduzierbar, zitierfähig.
- Die **Schweizer Live-Signale** (Scoring, Dashboard) verwenden `yfinance .info` für approximate Fundamentals (wie V2).
- Diese Trennung ist **explizit und ehrlich** — kein stiller Stub-Fallback (CHALLENGE 01 / FIX-14).
- Wenn ein CH-Provider-Key verfügbar wird: `verify_dataset_coverage.py` erneut laufen lassen → Config automatisch aktualisieren.

### Re-Run-Anleitung

```bash
# FMP-Key setzen:
export FMP_API_KEY=<echter-key>
uv run python scripts/verify_dataset_coverage.py

# EODHD-Key setzen:
export EODHD_API_KEY=<echter-key>
uv run python scripts/verify_dataset_coverage.py

# SimFin-Key + Package:
pip install simfin
export SIMFIN_API_KEY=<echter-key>
uv run python scripts/verify_dataset_coverage.py
```

Das Skript schreibt `docs/dataset_coverage.md` neu und empfiehlt den besten verfügbaren Provider.
