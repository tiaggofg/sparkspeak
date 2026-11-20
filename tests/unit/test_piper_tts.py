"""Unit tests for PipeWire device probing and Piper TTS adapter."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio import pipewire_device
from sparkspeak.infrastructure.audio.piper_tts import PiperTTSAdapter


@dataclass
class _FakeAudioChunk:
    sample_rate: int
    audio_float_array: np.ndarray[Any, np.dtype[np.float32]]


class _FakeVoice:
    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_length_scale: float | None = None

    def synthesize(
        self,
        text: str,
        syn_config: Any = None,
        include_alignments: bool = False,
    ) -> list[_FakeAudioChunk]:
        self.last_text = text
        self.last_length_scale = getattr(syn_config, "length_scale", None)
        samples = np.ones(2205, dtype=np.float32) * 0.25
        return [_FakeAudioChunk(sample_rate=22050, audio_float_array=samples)]


def test_speak_text_plays_pcm_to_device(tmp_path: Path) -> None:
    """C7: speak_text synthesizes English audio via piper-tts and sends PCM to PipeWire sink."""
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir(parents=True)
    model_path = piper_dir / "en_US-lessac-medium.onnx"
    config_path = piper_dir / "en_US-lessac-medium.onnx.json"
    model_path.write_bytes(b"fake-onnx")
    config_path.write_text("{}", encoding="utf-8")

    fake_voice = _FakeVoice()
    played: list[tuple[np.ndarray[Any, Any], int, bool]] = []

    def _fake_loader(m_path: Path, c_path: Path | None) -> _FakeVoice:
        assert m_path == model_path
        assert c_path == config_path
        return fake_voice

    def _fake_play(audio: np.ndarray[Any, Any], sample_rate: int, blocking: bool) -> None:
        played.append((audio, sample_rate, blocking))

    adapter = PiperTTSAdapter(
        models_dir=tmp_path,
        voice_loader=_fake_loader,
        playback_fn=_fake_play,
        output_available_fn=lambda: True,
    )
    assert adapter.is_ready() is True

    result = asyncio.run(adapter.speak("Hello engineer!", speed=1.25, blocking=True))
    assert result.spoken is True
    assert result.voice == "en_US-lessac-medium"
    assert result.duration_ms == 100
    assert fake_voice.last_text == "Hello engineer!"
    assert fake_voice.last_length_scale == pytest.approx(0.8)
    assert len(played) == 1
    assert played[0][1] == 22050
    assert played[0][2] is True
    assert len(played[0][0]) == 2205


def test_missing_onnx_model_raises_tts_model_missing(tmp_path: Path) -> None:
    """Missing .onnx model raises recoverable TTS_MODEL_MISSING with fallback_hint='text'."""
    adapter = PiperTTSAdapter(models_dir=tmp_path)
    assert adapter.is_ready() is False

    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(adapter.speak("Testing missing model"))
    assert exc_info.value.error_code == ErrorCode.TTS_MODEL_MISSING
    assert exc_info.value.recoverable is True
    assert exc_info.value.fallback_hint == "text"
    assert "sparkspeak-setup-models" in exc_info.value.message


def test_unavailable_pipewire_sink_raises_audio_output_unavailable(tmp_path: Path) -> None:
    """Unavailable PipeWire sink raises recoverable AUDIO_OUTPUT_UNAVAILABLE."""
    piper_dir = tmp_path / "piper"
    piper_dir.mkdir(parents=True)
    (piper_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-onnx")
    (piper_dir / "en_US-lessac-medium.onnx.json").write_text("{}", encoding="utf-8")

    def _failing_play(audio: np.ndarray[Any, Any], sample_rate: int, blocking: bool) -> None:
        raise SparkSpeakError(
            error_code=ErrorCode.AUDIO_OUTPUT_UNAVAILABLE,
            message="No PipeWire output sink available.",
            recoverable=True,
            fallback_hint="text",
        )

    adapter = PiperTTSAdapter(
        models_dir=tmp_path,
        voice_loader=lambda _m, _c: _FakeVoice(),
        playback_fn=_failing_play,
        output_available_fn=lambda: True,
    )
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(adapter.speak("Hello"))
    assert exc_info.value.error_code == ErrorCode.AUDIO_OUTPUT_UNAVAILABLE
    assert exc_info.value.recoverable is True
    assert exc_info.value.fallback_hint == "text"


def test_probe_devices_handles_missing_portaudio(monkeypatch: pytest.MonkeyPatch) -> None:
    """PipeWire probe returns False flags instead of crashing when PortAudio is absent."""

    def _raise_oserror() -> Any:
        raise OSError("PortAudio library not found")

    monkeypatch.setattr(pipewire_device, "_import_sounddevice", _raise_oserror)
    probe = pipewire_device.probe_pipewire_devices()
    assert probe.has_input is False
    assert probe.has_output is False

    with pytest.raises(SparkSpeakError) as exc_info:
        pipewire_device.play_pcm(np.zeros(10, dtype=np.float32), 22050, blocking=True)
    assert exc_info.value.error_code == ErrorCode.AUDIO_OUTPUT_UNAVAILABLE
    assert exc_info.value.fallback_hint == "text"
