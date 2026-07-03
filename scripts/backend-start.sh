#!/bin/sh
# Start-Script für den Backend-Container.
# Einziger Ort, an dem die Start-Sequenz lebt — wird von Dockerfile-CMD
# (Default) und render.yaml (dockerCommand) gleichermaßen aufgerufen.
#
# 1. Alembic-Migrationen anwenden — geguardet: destruktive Migrationen
#    (TRUNCATE/DROP/DELETE) werden auf bestehender DB NICHT automatisch
#    angewandt (C-06/H-12); Serialisierung via pg_advisory_lock (W2-H-06).
#    Bewusste Freigabe: ALLOW_DESTRUCTIVE_MIGRATIONS=1 (nach pg_dump-Backup).
# 2. Uvicorn im Foreground starten — exec ersetzt den Shell-Prozess, damit
#    Signals (SIGTERM von Docker/Render) direkt an uvicorn gehen.

set -e

echo "==> Running guarded migrations..."
if ! python -m backend.infrastructure.persistence.migration_guard; then
    echo "ERROR: Migration fehlgeschlagen oder wegen destruktiver Operation blockiert — Container stoppt (kein Restart-Loop)"
    echo "Action: Bei Blockade Migration prüfen; nach Backup mit ALLOW_DESTRUCTIVE_MIGRATIONS=1 erneut anwenden."
    exit 1
fi

echo "==> Seeding admin user..."
if ! python scripts/seed_admin.py; then
    echo "WARNING: seed_admin.py fehlgeschlagen — ADMIN_EMAIL/ADMIN_PASSWORD/JWT_SECRET im Render-Dashboard prüfen."
    echo "Der Container startet trotzdem — seed kann via Render Shell nachgeholt werden."
fi

echo "==> Starting uvicorn on 0.0.0.0:${PORT:-8000} ..."
exec uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port "${PORT:-8000}"
