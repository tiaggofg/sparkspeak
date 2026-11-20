"""Unit tests for sparkspeak-setup-models and sparkspeak-health CLI."""

import json
from pathlib import Path

import pytest

from sparkspeak.cli import setup_models
from sparkspeak.config import SparkSpeakConfig
from sparkspeak.infrastructure.audio.pipewire_device import DeviceProbeResult

_DATA_DIR = ".data"


def test_health_reports_json_without_crashing_on_missing_devices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """sparkspeak-health outputs valid JSON even when models and PipeWire are missing."""
    cfg = SparkSpeakConfig(
        project_root=tmp_path,
        db_path=tmp_path / _DATA_DIR / "sparkspeak.db",
        backups_dir=tmp_path / _DATA_DIR / "backups",
        models_dir=tmp_path / _DATA_DIR / "models",
    )
    monkeypatch.setattr(setup_models, "load_config", lambda: cfg)
    monkeypatch.setattr(
        setup_models,
        "probe_pipewire_devices",
        lambda: DeviceProbeResult(has_input=False, has_output=False, error="No PortAudio"),
    )

    exit_code = setup_models.health()
    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["piper_model_installed"] is False
    assert data["whisper_cache_present"] is False
    assert data["pipewire_input"] is False
    assert data["pipewire_output"] is False


def test_health_and_setup_models_detect_installed_models(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """setup_models populates .data/models and health reports ready=True."""
    models_dir = tmp_path / _DATA_DIR / "models"
    cfg = SparkSpeakConfig(
        project_root=tmp_path,
        db_path=tmp_path / _DATA_DIR / "sparkspeak.db",
        backups_dir=tmp_path / _DATA_DIR / "backups",
        models_dir=models_dir,
    )

    def _fake_download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"downloaded:" + url.encode("utf-8"))

    def _fake_whisper(model_size: str, download_root: Path) -> None:
        download_root.mkdir(parents=True, exist_ok=True)
        (download_root / f"{model_size}.bin").write_bytes(b"weights")

    result = setup_models.install_models(
        cfg,
        download_fn=_fake_download,
        whisper_prefetch_fn=_fake_whisper,
    )
    assert (models_dir / "piper" / "en_US-lessac-medium.onnx").is_file()
    assert (models_dir / "piper" / "en_US-lessac-medium.onnx.json").is_file()
    assert result["piper_voice"] == "en_US-lessac-medium"
    assert result["whisper_model"] == "base"

    monkeypatch.setattr(setup_models, "load_config", lambda: cfg)
    monkeypatch.setattr(
        setup_models,
        "probe_pipewire_devices",
        lambda: DeviceProbeResult(
            has_input=True,
            has_output=True,
            input_device_name="PipeWire Mic",
            output_device_name="PipeWire Sink",
        ),
    )
    setup_models.health()
    payload = json.loads(capsys.readouterr().out)
    assert payload["piper_model_installed"] is True
    assert payload["whisper_cache_present"] is True
    assert payload["pipewire_input"] is True
    assert payload["pipewire_output"] is True
