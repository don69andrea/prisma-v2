"""Unit-Tests für das SHA256-Pinning der ML-Artefakte (W2-C-01)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import joblib
import pytest

from backend.infrastructure.security import model_integrity
from backend.infrastructure.security.model_integrity import (
    ModelIntegrityError,
    load_pinned_hashes,
    sha256_file,
    verified_load,
    verify_file,
)

pytestmark = pytest.mark.unit


def _write(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _manifest(path: Path, entries: dict[str, str]) -> Path:
    manifest = path / "SHA256SUMS"
    manifest.write_text("\n".join(f"{h}  {name}" for name, h in entries.items()) + "\n")
    return manifest


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    f = tmp_path / "m.joblib"
    expected = _write(f, b"hello-model-bytes")
    assert sha256_file(f) == expected


def test_load_pinned_hashes_parses_manifest(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, {"a.joblib": "aa" * 32, "b.joblib": "bb" * 32})
    pinned = load_pinned_hashes(manifest)
    assert pinned == {"a.joblib": "aa" * 32, "b.joblib": "bb" * 32}


def test_load_pinned_hashes_missing_manifest_is_empty(tmp_path: Path) -> None:
    assert load_pinned_hashes(tmp_path / "nope") == {}


def test_verify_file_passes_on_match(tmp_path: Path) -> None:
    f = tmp_path / "m.joblib"
    h = _write(f, b"good")
    manifest = _manifest(tmp_path, {"m.joblib": h})
    verify_file(f, manifest)  # kein Raise


def test_verify_file_raises_on_hash_mismatch(tmp_path: Path) -> None:
    f = tmp_path / "m.joblib"
    _write(f, b"tampered-content")
    manifest = _manifest(tmp_path, {"m.joblib": "00" * 32})
    with pytest.raises(ModelIntegrityError, match="Mismatch"):
        verify_file(f, manifest)


def test_verify_file_raises_when_not_pinned_and_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MODEL_INTEGRITY_ENFORCE", raising=False)
    f = tmp_path / "unknown.joblib"
    _write(f, b"x")
    manifest = _manifest(tmp_path, {"other.joblib": "11" * 32})
    with pytest.raises(ModelIntegrityError, match="nicht im Manifest"):
        verify_file(f, manifest)


def test_verify_file_warns_when_not_pinned_and_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_INTEGRITY_ENFORCE", "0")
    f = tmp_path / "unknown.joblib"
    _write(f, b"x")
    manifest = _manifest(tmp_path, {"other.joblib": "11" * 32})
    verify_file(f, manifest)  # kein Raise, nur Warnung


def test_verified_load_calls_joblib_only_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded: list[Path] = []

    def _fake_load(path: object) -> str:
        loaded.append(Path(str(path)))
        return "MODEL"

    monkeypatch.setattr(joblib, "load", _fake_load)

    f = tmp_path / "m.joblib"
    h = _write(f, b"payload")
    manifest = _manifest(tmp_path, {"m.joblib": h})

    result = verified_load(f, manifest)
    assert result == "MODEL"
    assert loaded == [f]


def test_verified_load_does_not_load_on_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(path: object) -> object:
        raise AssertionError("joblib.load darf bei Hash-Mismatch nicht aufgerufen werden")

    monkeypatch.setattr(joblib, "load", _boom)

    f = tmp_path / "m.joblib"
    _write(f, b"tampered")
    manifest = _manifest(tmp_path, {"m.joblib": "00" * 32})
    with pytest.raises(ModelIntegrityError):
        verified_load(f, manifest)


def test_committed_models_match_manifest() -> None:
    """Drift-/Tamper-Guard: jedes getrackte .joblib ist gepinnt und stimmt überein."""
    models_dir = model_integrity._MODELS_DIR
    manifest = model_integrity._MANIFEST
    if not models_dir.exists() or not manifest.exists():
        pytest.skip("models/ oder SHA256SUMS nicht vorhanden")

    pinned = load_pinned_hashes(manifest)
    joblibs = sorted(models_dir.glob("*.joblib"))
    assert joblibs, "keine .joblib-Artefakte gefunden"
    for path in joblibs:
        assert path.name in pinned, f"{path.name} fehlt im Manifest SHA256SUMS"
        assert sha256_file(path) == pinned[path.name], f"Hash-Drift für {path.name}"
