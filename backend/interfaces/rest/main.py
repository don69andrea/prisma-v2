"""Uvicorn-Einstiegspunkt: exportiert die ASGI-App-Instanz."""

from backend.interfaces.rest.app import create_app

app = create_app()
