#!/bin/sh
# Start-Script für den Backend-Container.
# Einziger Ort, an dem die Start-Sequenz lebt — wird von Dockerfile-CMD
# (Default) und render.yaml (dockerCommand) gleichermaßen aufgerufen.
#
# 1. Alembic-Migrationen anwenden (idempotent)
# 2. Uvicorn im Foreground starten — exec ersetzt den Shell-Prozess, damit
#    Signals (SIGTERM von Docker/Render) direkt an uvicorn gehen.

set -e

echo "==> Running alembic migrations..."
alembic upgrade head

# Refresh market_cap_chf for all SMI stocks from yfinance.
# This runs after every deploy so Render's free-tier DB never starts with
# null market caps after a reset. The script is idempotent and tolerates
# partial failures (individual tickers are skipped on error, not the whole run).
echo "==> Refreshing SMI market caps from yfinance..."
python scripts/update_smi_market_caps.py || echo "WARNING: market cap refresh failed (non-fatal) — will retry on next deploy"

echo "==> Starting uvicorn on 0.0.0.0:${PORT:-8000} ..."
exec uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port "${PORT:-8000}"
