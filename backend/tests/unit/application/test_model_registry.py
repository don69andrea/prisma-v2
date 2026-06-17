from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.unit


def test_registry_returns_latest_path(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    (tmp_path / "model_v1.joblib").touch()
    registry_data = {
        "active": "model_v1.joblib",
        "versions": [{"file": "model_v1.joblib", "trained_at": "2026-06-17", "accuracy": 0.61}],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry_data))
    registry = ModelRegistry(models_dir=tmp_path)
    assert registry.get_active_model_path() == tmp_path / "model_v1.joblib"


def test_registry_returns_none_when_no_registry(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    registry = ModelRegistry(models_dir=tmp_path)
    assert registry.get_active_model_path() is None


def test_registry_list_versions(tmp_path):
    from backend.application.services.model_registry import ModelRegistry

    registry_data = {
        "active": "model_v2.joblib",
        "versions": [
            {"file": "model_v1.joblib", "trained_at": "2026-06-10", "accuracy": 0.59},
            {"file": "model_v2.joblib", "trained_at": "2026-06-17", "accuracy": 0.61},
        ],
    }
    (tmp_path / "registry.json").write_text(json.dumps(registry_data))
    registry = ModelRegistry(models_dir=tmp_path)
    versions = registry.list_versions()
    assert len(versions) == 2
    assert versions[1]["file"] == "model_v2.joblib"
