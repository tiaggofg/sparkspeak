"""Unit tests for lightweight 16 kHz mono PCM WavRecorder with RMS endpointing."""

import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.wav_recorder import FRAME_SAMPLES, SAMPLE_RATE, WavRecorder


class _FakeInputStream:
    """Deterministic fake sounddevice.InputStream yielding prebuilt float32 frames."""

    def __init__(self, frames: list[np.ndarray], *, fail_on_open: bool = False) -> None:
        self._frames = list(frames)
        self._idx = 0
        self._fail_on_open = fail_on_open

    def __enter__(self) -> "_FakeInputStream":
        if self._fail_on_open:
            raise RuntimeError("PortAudio device open failed")
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self, n_samples: int) -> tuple[np.ndarray, bool]:
        if self._idx >= len(self._frames):
            return np.zeros((n_samples, 1), dtype=np.float32), False
        frame = self._frames[self._idx]
        self._idx += 1
        return frame.reshape(-1, 1), False


def _silence_frame(amplitude: float = 0.001) -> np.ndarray:
    return np.full(FRAME_SAMPLES, amplitude, dtype=np.float32)


def _speech_frame(amplitude: float = 0.25) -> np.ndarray:
    t = np.arange(FRAME_SAMPLES, dtype=np.float32) / SAMPLE_RATE
    return (amplitude * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)


@pytest.mark.anyio
async def test_wav_recorder_writes_16k_mono_wav_with_preroll_and_silence_cutoff(
    tmp_path: Path,
) -> None:
    # 10 silent frames (~320 ms, last ~192ms kept as pre-roll), 5 speech frames, 20 silent frames
    frames = [_silence_frame(0.001) for _ in range(10)]
    frames.extend(_speech_frame(0.25) for _ in range(5))
    frames.extend(_silence_frame(0.001) for _ in range(25))

    recorder = WavRecorder(
        audio_dir=tmp_path,
        mic_probe=lambda: True,
        stream_factory=lambda _sr, _bs: _FakeInputStream(frames),
    )

    result = await recorder.record_utterance(
        silence_timeout_ms=500,  # ~15 frames
        initial_speech_timeout_ms=2000,
        max_duration_ms=10000,
    )

    assert result.speech_detected is True
    assert result.wav_path == str((tmp_path / "last_utterance.wav").resolve())
    assert result.truncated_at_max_duration is False
    assert result.peak_rms > 0.1
    assert result.duration_ms > 5 * 32  # includes pre-roll + speech + trailing silence

    wav_file_path = Path(result.wav_path)
    assert wav_file_path.exists()
    with wave.open(str(wav_file_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() > 5 * FRAME_SAMPLES


@pytest.mark.anyio
async def test_wav_recorder_returns_no_speech_on_initial_timeout(tmp_path: Path) -> None:
    frames = [_silence_frame(0.002) for _ in range(80)]
    recorder = WavRecorder(
        audio_dir=tmp_path,
        mic_probe=lambda: True,
        stream_factory=lambda _sr, _bs: _FakeInputStream(frames),
    )

    result = await recorder.record_utterance(
        silence_timeout_ms=500,
        initial_speech_timeout_ms=1000,
        max_duration_ms=10000,
    )

    assert result.speech_detected is False
    assert result.wav_path is None
    assert result.duration_ms == 0
    assert result.truncated_at_max_duration is False
    assert not (tmp_path / "last_utterance.wav").exists()


@pytest.mark.anyio
async def test_wav_recorder_caps_at_max_duration_and_sets_truncated(tmp_path: Path) -> None:
    # Continuous speech exceeding max_duration_ms=300ms (~9 frames)
    frames = [_speech_frame(0.2) for _ in range(30)]
    recorder = WavRecorder(
        audio_dir=tmp_path,
        mic_probe=lambda: True,
        stream_factory=lambda _sr, _bs: _FakeInputStream(frames),
    )

    result = await recorder.record_utterance(
        silence_timeout_ms=1000,
        initial_speech_timeout_ms=2000,
        max_duration_ms=300,
    )

    assert result.speech_detected is True
    assert result.truncated_at_max_duration is True
    assert result.wav_path is not None
    assert Path(result.wav_path).exists()


@pytest.mark.anyio
async def test_wav_recorder_raises_microphone_unavailable_when_no_mic(tmp_path: Path) -> None:
    recorder = WavRecorder(audio_dir=tmp_path, mic_probe=lambda: False)

    with pytest.raises(SparkSpeakError) as exc_info:
        await recorder.record_utterance()

    assert exc_info.value.error_code == ErrorCode.MICROPHONE_UNAVAILABLE
    assert exc_info.value.fallback_hint == "text"
    assert exc_info.value.recoverable is True


@pytest.mark.anyio
async def test_wav_recorder_raises_microphone_unavailable_when_stream_fails(tmp_path: Path) -> None:
    recorder = WavRecorder(
        audio_dir=tmp_path,
        mic_probe=lambda: True,
        stream_factory=lambda _sr, _bs: _FakeInputStream([], fail_on_open=True),
    )

    with pytest.raises(SparkSpeakError) as exc_info:
        await recorder.record_utterance()

    assert exc_info.value.error_code == ErrorCode.MICROPHONE_UNAVAILABLE
    assert exc_info.value.fallback_hint == "text"
