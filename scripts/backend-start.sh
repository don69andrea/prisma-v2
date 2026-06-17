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
if ! alembic upgrade head; then
    echo "ERROR: Alembic-Migration fehlgeschlagen — Container stoppt (kein Restart-Loop)"
    echo "Action: Migration-Fehler beheben, committen und neu deployen."
    exit 1
fi

echo "==> Starting uvicorn on 0.0.0.0:${PORT:-8000} ..."
exec uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port "${PORT:-8000}"
