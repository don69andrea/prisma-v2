"""Application Service: ModelRegistry — datei-basierte Modell-Versionierung."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

_logger = logging.getLogger(__name__)
_REGISTRY_FILE = "registry.json"


class ModelRegistry:
    """Datei-basierte Modell-Registry in models/registry.json.

    Ermöglicht Versionstracking und schnellen Rollback ohne DB-Dependency.
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        if models_dir is None:
            models_dir = Path(__file__).resolve().parents[3] / "models"
        self._dir = models_dir
        self._registry_path = self._dir / _REGISTRY_FILE

    def _load(self) -> dict[str, Any]:
        if not self._registry_path.exists():
            return {"active": None, "versions": []}
        with self._registry_path.open() as f:
            return cast(dict[str, Any], json.load(f))

    def get_active_model_path(self) -> Path | None:
        """Gibt den Pfad zum aktiven Modell zurück, oder None wenn kein Registry-File."""
        data = self._load()
        active = data.get("active")
        if not active:
            return None
        path = self._dir / str(active)
        if not path.exists():
            _logger.warning("Registry zeigt auf nicht-existentes Modell: %s", path)
            return None
        return path

    def list_versions(self) -> list[dict[str, Any]]:
        """Gibt alle registrierten Modell-Versionen zurück."""
        return cast(list[dict[str, Any]], self._load().get("versions", []))

    def register(self, filename: str, meta: dict[str, Any], set_active: bool = True) -> None:
        """Registriert eine neue Modell-Version und setzt sie optional als aktiv."""
        data = self._load()
        entry = {"file": filename, **meta}
        data["versions"].append(entry)
        if set_active:
            data["active"] = filename
        self._registry_path.write_text(json.dumps(data, indent=2))
        _logger.info("Modell registriert: %s (active=%s)", filename, set_active)
