"""Unit tests for configuration path resolution and structured error envelopes."""

import json
from pathlib import Path

import pytest

from sparkspeak.config import SparkSpeakConfig, load_config
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError

_DATA_DIR = ".data"


def test_default_config_resolves_dot_data_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SPARKSPEAK_DB_PATH", raising=False)
    monkeypatch.delenv("SPARKSPEAK_BACKUPS_DIR", raising=False)
    monkeypatch.delenv("SPARKSPEAK_MODELS_DIR", raising=False)

    cfg = load_config(project_root=tmp_path)

    assert isinstance(cfg, SparkSpeakConfig)
    assert cfg.db_path == tmp_path / _DATA_DIR / "sparkspeak.db"
    assert cfg.backups_dir == tmp_path / _DATA_DIR / "backups"
    assert cfg.models_dir == tmp_path / _DATA_DIR / "models"


def test_config_honors_sparkspeak_env_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_db = tmp_path / "custom" / "tutor.db"
    custom_backups = tmp_path / "custom_backups"
    custom_models = tmp_path / "custom_models"
    monkeypatch.setenv("SPARKSPEAK_DB_PATH", str(custom_db))
    monkeypatch.setenv("SPARKSPEAK_BACKUPS_DIR", str(custom_backups))
    monkeypatch.setenv("SPARKSPEAK_MODELS_DIR", str(custom_models))

    cfg = load_config(project_root=tmp_path)

    assert cfg.db_path == custom_db
    assert cfg.backups_dir == custom_backups
    assert cfg.models_dir == custom_models


def test_structured_error_envelope_serializes_required_fields() -> None:
    err = SparkSpeakError(
        error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
        message="No active PipeWire input source detected.",
        recoverable=True,
        fallback_hint="text",
        details={"device": "default"},
    )

    payload = err.to_dict()
    assert payload == {
        "error_code": "MICROPHONE_UNAVAILABLE",
        "message": "No active PipeWire input source detected.",
        "recoverable": True,
        "fallback_hint": "text",
        "details": {"device": "default"},
    }
    parsed = json.loads(err.to_json())
    assert parsed == payload


def test_structured_error_defaults_details_and_fallback_hint() -> None:
    err = SparkSpeakError(
        error_code=ErrorCode.INVALID_RATING,
        message="Rating must be between 1 and 4.",
    )

    payload = err.to_dict()
    assert payload["error_code"] == "INVALID_RATING"
    assert payload["recoverable"] is True
    assert payload["fallback_hint"] is None
    assert payload["details"] == {}
