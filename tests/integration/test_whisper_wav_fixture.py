"""Integration tests for 16kHz WAV parsing, Silero VAD endpointing, and raw STT."""

import asyncio
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.whisper_stt import (
    SAMPLE_RATE_HZ,
    WhisperSTTAdapter,
    load_wav_pcm_16k,
)

FIXTURE_WAV = (
    Path(__file__).resolve().parent.parent / "fixtures" / "audio" / "grammar_error_sample.wav"
)


class _FakeWhisperModel:
    """Fake faster-whisper WhisperModel capturing transcription kwargs verbatim."""

    def __init__(self, transcript_text: str) -> None:
        self.transcript_text = transcript_text
        self.calls: list[dict[str, Any]] = []

    def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        **kwargs: Any,
    ) -> tuple[list[SimpleNamespace], SimpleNamespace]:
        self.calls.append({"audio_len": len(audio), "kwargs": kwargs})
        segments = [
            SimpleNamespace(
                text=self.transcript_text,
                avg_logprob=-0.34,
                no_speech_prob=0.02,
            )
        ]
        info = SimpleNamespace(language="en", duration=len(audio) / SAMPLE_RATE_HZ)
        return segments, info


def test_verbatim_error_preservation(tmp_path: Path) -> None:
    """C9: WAV 16kHz PCM flows through VAD + Whisper preserving learner errors verbatim."""
    pcm = load_wav_pcm_16k(FIXTURE_WAV)
    assert pcm.dtype == np.float32
    assert len(pcm) == int(1.6 * SAMPLE_RATE_HZ)

    raw_learner_text = "Yesterday I goed to the standup and explain the issue"
    fake_model = _FakeWhisperModel(raw_learner_text)

    # Chunk the fixture WAV into 32ms (512-sample) frames as sounddevice would yield.
    frame_size = 512
    frames = [pcm[i : i + frame_size] for i in range(0, len(pcm), frame_size)]

    def fake_capture(
        *,
        silence_timeout_ms: int,
        initial_speech_timeout_ms: int,
        max_duration_ms: int,
        vad_prob_fn: Any,
    ) -> tuple[npt.NDArray[np.float32], bool, bool]:
        assert silence_timeout_ms == 1500
        assert initial_speech_timeout_ms == 10000
        assert max_duration_ms == 45000
        # Exercise the VAD callback on real WAV frames.
        for frame in frames[:5]:
            prob = vad_prob_fn(frame)
            assert 0.0 <= prob <= 1.0
        return pcm, True, False

    adapter = WhisperSTTAdapter(
        models_dir=tmp_path / "models",
        model_loader=lambda _size, _root: fake_model,
        capture_fn=fake_capture,
    )

    result = asyncio.run(adapter.listen_and_transcribe())

    assert result.speech_detected is True
    assert result.transcript == raw_learner_text
    assert "goed" in result.transcript
    assert "explain" in result.transcript
    assert result.truncated_at_max_duration is False
    assert result.duration_ms > 0
    assert result.avg_logprob == pytest.approx(-0.34)
    assert result.no_speech_prob == pytest.approx(0.02)

    assert len(fake_model.calls) == 1
    call_kwargs = fake_model.calls[0]["kwargs"]
    assert call_kwargs["language"] == "en"
    assert call_kwargs["vad_filter"] is True
    assert call_kwargs.get("initial_prompt") is None


def test_initial_speech_timeout_returns_no_speech_detected(tmp_path: Path) -> None:
    """Silence beyond initial_speech_timeout_ms returns speech_detected=False without error."""
    silence_chunk = np.zeros(512, dtype=np.float32)

    def silence_stream(
        _sample_rate: int, _blocksize: int, _channels: int
    ) -> list[npt.NDArray[np.float32]]:
        # 10 chunks * 32ms = 320ms > 200ms timeout
        return [silence_chunk for _ in range(10)]

    fake_model = _FakeWhisperModel("should not be called")
    adapter = WhisperSTTAdapter(
        models_dir=tmp_path / "models",
        model_loader=lambda _size, _root: fake_model,
        stream_factory=silence_stream,
    )

    result = asyncio.run(
        adapter.listen_and_transcribe(
            silence_timeout_ms=500,
            initial_speech_timeout_ms=200,
            max_duration_ms=3000,
        )
    )

    assert result.speech_detected is False
    assert result.transcript == ""
    assert result.duration_ms == 0
    assert result.truncated_at_max_duration is False
    assert fake_model.calls == []


def test_max_duration_truncates_and_sets_flag(tmp_path: Path) -> None:
    """Continuous speech hitting max_duration_ms sets truncated_at_max_duration=True."""
    speech_chunk = np.full(512, 0.25, dtype=np.float32)

    def continuous_stream(
        _sample_rate: int, _blocksize: int, _channels: int
    ) -> list[npt.NDArray[np.float32]]:
        return [speech_chunk for _ in range(25)]

    fake_model = _FakeWhisperModel("I was explain the architecture")
    adapter = WhisperSTTAdapter(
        models_dir=tmp_path / "models",
        model_loader=lambda _size, _root: fake_model,
        stream_factory=continuous_stream,
        vad_prob_fn=lambda _chunk: 0.95,
    )

    result = asyncio.run(
        adapter.listen_and_transcribe(
            silence_timeout_ms=1500,
            initial_speech_timeout_ms=2000,
            max_duration_ms=320,
        )
    )

    assert result.speech_detected is True
    assert result.truncated_at_max_duration is True
    assert result.transcript == "I was explain the architecture"
    assert result.duration_ms <= 352


def test_missing_microphone_raises_microphone_unavailable(tmp_path: Path) -> None:
    """Failing to open input device raises recoverable MICROPHONE_UNAVAILABLE."""
    whisper_dir = tmp_path / "models" / "whisper"
    whisper_dir.mkdir(parents=True)
    (whisper_dir / "model.bin").write_bytes(b"stub")

    def broken_stream(_sample_rate: int, _blocksize: int, _channels: int) -> Any:
        raise OSError("PortAudio library not found")

    adapter = WhisperSTTAdapter(
        models_dir=tmp_path / "models",
        model_loader=lambda _size, _root: _FakeWhisperModel("unused"),
        stream_factory=broken_stream,
    )

    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(adapter.listen_and_transcribe())

    err = exc_info.value
    assert err.error_code == ErrorCode.MICROPHONE_UNAVAILABLE
    assert err.recoverable is True
    assert err.fallback_hint == "text"


def test_missing_whisper_model_raises_model_not_installed(tmp_path: Path) -> None:
    """Missing local Whisper cache raises recoverable MODEL_NOT_INSTALLED."""
    adapter = WhisperSTTAdapter(models_dir=tmp_path / "models")
    assert adapter.is_ready() is False

    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(adapter.listen_and_transcribe())

    err = exc_info.value
    assert err.error_code == ErrorCode.MODEL_NOT_INSTALLED
    assert err.recoverable is True
    assert err.fallback_hint == "text"
    assert "sparkspeak-setup-models" in err.message


def test_load_wav_pcm_16k_validates_fixture_format(tmp_path: Path) -> None:
    """load_wav_pcm_16k rejects non-16kHz WAV files cleanly."""
    bad_wav = tmp_path / "bad_rate.wav"
    with wave.open(str(bad_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(b"\x00\x00" * 800)

    with pytest.raises(SparkSpeakError) as exc_info:
        load_wav_pcm_16k(bad_wav)
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT
