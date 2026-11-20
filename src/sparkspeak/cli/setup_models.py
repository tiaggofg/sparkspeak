"""Model setup and PipeWire audio healthcheck CLI entrypoints."""

import json
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sparkspeak.config import SparkSpeakConfig, load_config
from sparkspeak.infrastructure.audio.piper_tts import DEFAULT_PIPER_VOICE
from sparkspeak.infrastructure.audio.pipewire_device import probe_pipewire_devices

PIPER_HF_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "en/en_US/lessac/medium"
)
DEFAULT_WHISPER_MODEL = "base"

DownloadFn = Callable[[str, Path], None]
WhisperPrefetchFn = Callable[[str, Path], None]


def _default_download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)  # noqa: S310


def _default_whisper_prefetch(model_size: str, download_root: Path) -> None:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]  # noqa: PLC0415

    download_root.mkdir(parents=True, exist_ok=True)
    WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(download_root))


def install_models(
    cfg: SparkSpeakConfig,
    *,
    voice: str = DEFAULT_PIPER_VOICE,
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    download_fn: DownloadFn | None = None,
    whisper_prefetch_fn: WhisperPrefetchFn | None = None,
) -> dict[str, Any]:
    """Download Piper ONNX + JSON and pre-cache faster-whisper weights."""
    dl = download_fn or _default_download
    prefetch = whisper_prefetch_fn or _default_whisper_prefetch

    piper_dir = cfg.models_dir / "piper"
    onnx_path = piper_dir / f"{voice}.onnx"
    json_path = piper_dir / f"{voice}.onnx.json"

    if not onnx_path.is_file():
        dl(f"{PIPER_HF_BASE}/{voice}.onnx?download=true", onnx_path)
    if not json_path.is_file():
        dl(f"{PIPER_HF_BASE}/{voice}.onnx.json?download=true", json_path)

    whisper_dir = cfg.models_dir / "whisper"
    prefetch(whisper_model, whisper_dir)

    return {
        "piper_voice": voice,
        "piper_model_path": str(onnx_path),
        "whisper_model": whisper_model,
        "whisper_dir": str(whisper_dir),
    }


def check_health(cfg: SparkSpeakConfig) -> dict[str, Any]:
    """Check local model files and PipeWire input/output availability."""
    piper_onnx = cfg.models_dir / "piper" / f"{DEFAULT_PIPER_VOICE}.onnx"
    whisper_dir = cfg.models_dir / "whisper"
    whisper_present = whisper_dir.is_dir() and any(whisper_dir.iterdir())
    probe = probe_pipewire_devices()

    return {
        "models_dir": str(cfg.models_dir),
        "piper_model_installed": piper_onnx.is_file(),
        "whisper_cache_present": whisper_present,
        "pipewire_input": probe.has_input,
        "pipewire_output": probe.has_output,
        "input_device": probe.input_device_name,
        "output_device": probe.output_device_name,
        "probe_error": probe.error,
    }


def main() -> int:
    """Entrypoint for `sparkspeak-setup-models`."""
    cfg = load_config()
    result = install_models(cfg)
    print(json.dumps(result, indent=2))
    return 0


def health() -> int:
    """Entrypoint for `sparkspeak-health`."""
    cfg = load_config()
    status = check_health(cfg)
    print(json.dumps(status, indent=2))
    return 0
