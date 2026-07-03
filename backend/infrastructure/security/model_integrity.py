"""SHA256-Pinning für ML-Artefakte (W2-C-01) — Integritätsprüfung vor ``joblib.load``.

``joblib.load`` ist ``pickle.load`` und führt beim Deserialisieren **beliebigen
Code** aus. Da die Modelle als Binär-Blobs im Repo liegen, ist ein manipuliertes
Artefakt (via PR/Branch) eine RCE-Fläche.

Diese Schicht lädt ein Modell nur, wenn der SHA256 der Datei mit dem im Manifest
``models/SHA256SUMS`` gepinnten Wert übereinstimmt (**fail closed**). Manifest und
Artefakt liegen beide unter Versionskontrolle → jede Änderung ist im Review als
Hash-Diff sichtbar. Für Entwicklungs-/Trainingsflüsse kann die Erzwingung mit
``MODEL_INTEGRITY_ENFORCE=0`` abgeschaltet werden.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
_MANIFEST = _MODELS_DIR / "SHA256SUMS"
_CHUNK = 1 << 20  # 1 MiB


class ModelIntegrityError(RuntimeError):
    """Wird geworfen, wenn ein Modell-Artefakt die SHA256-Prüfung nicht besteht."""


def _enforced() -> bool:
    return os.environ.get("MODEL_INTEGRITY_ENFORCE", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def sha256_file(path: Path) -> str:
    """Streamt die Datei und gibt ihren SHA256-Hex-Digest zurück."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def load_pinned_hashes(manifest_path: Path | None = None) -> dict[str, str]:
    """Parst das ``SHA256SUMS``-Manifest (``<hash>  <dateiname>``) → {name: hash}."""
    path = manifest_path if manifest_path is not None else _MANIFEST
    if not path.exists():
        return {}
    pinned: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        digest, name = parts
        pinned[name] = digest.lower()
    return pinned


def verify_file(path: Path, manifest_path: Path | None = None) -> None:
    """Prüft den SHA256 von ``path`` gegen das Manifest. Raise bei Mismatch/Unbekannt.

    Bei ``MODEL_INTEGRITY_ENFORCE=0`` wird nur gewarnt statt geworfen.
    """
    pinned = load_pinned_hashes(manifest_path)
    expected = pinned.get(path.name)
    actual = sha256_file(path)

    if expected is None:
        msg = f"Modell-Artefakt nicht im Manifest gepinnt: {path.name}"
        if _enforced():
            raise ModelIntegrityError(msg)
        _logger.warning("%s — Integritätsprüfung deaktiviert, wird geladen.", msg)
        return

    if actual != expected:
        raise ModelIntegrityError(
            f"SHA256-Mismatch für {path.name}: erwartet {expected}, tatsächlich {actual}. "
            "Artefakt könnte manipuliert sein — Laden abgebrochen."
        )


def verified_load(path: Path, manifest_path: Path | None = None) -> Any:
    """Prüft die Integrität und lädt erst danach via ``joblib.load``."""
    import joblib

    verify_file(path, manifest_path)
    return joblib.load(path)
