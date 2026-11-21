"""Unit tests for KokoroTTSAdapter."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.kokoro_tts import (
    CURATED_KOKORO_VOICES,
    KOKORO_MODEL_FILENAME,
    KOKORO_VOICES_FILENAME,
    KokoroTTSAdapter,
)


class _FakeKokoroEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float, str]] = []

    def create(
        self, text: str, *, voice: str, speed: float, lang: str
    ) -> tuple[np.ndarray, int]:
        self.calls.append((text, voice, speed, lang))
        return np.zeros(24000, dtype=np.float32), 24000


def test_kokoro_curated_voices_match_selected_set() -> None:
    assert CURATED_KOKORO_VOICES == ("af_heart", "af_jessica", "am_liam", "am_puck")


def test_kokoro_missing_models_raises_tts_model_missing(tmp_path: Path) -> None:
    adapter = KokoroTTSAdapter(models_dir=tmp_path)
    assert adapter.is_ready() is False

    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(adapter.speak("Hello there"))

    assert exc_info.value.error_code == ErrorCode.TTS_MODEL_MISSING
    assert exc_info.value.recoverable is True
    assert exc_info.value.fallback_hint == "text"


def test_kokoro_speak_synthesizes_and_plays_pcm(tmp_path: Path) -> None:
    (tmp_path / KOKORO_MODEL_FILENAME).write_bytes(b"stub-onnx")
    (tmp_path / KOKORO_VOICES_FILENAME).write_bytes(b"stub-voices")
    fake_engine = _FakeKokoroEngine()
    played: list[tuple[int, int, bool]] = []

    def _fake_player(audio: np.ndarray, sample_rate: int, blocking: bool) -> None:
        played.append((len(audio), sample_rate, blocking))

    adapter = KokoroTTSAdapter(
        models_dir=tmp_path,
        player=_fake_player,
        engine_loader=lambda _m, _v: fake_engine,
    )
    assert adapter.is_ready() is True

    res = asyncio.run(adapter.speak("Ready to try one more?", voice="am_liam", speed=1.0))

    assert res.spoken is True
    assert res.voice == "am_liam"
    assert res.duration_ms == 1000
    assert fake_engine.calls == [("Ready to try one more?", "am_liam", 1.0, "en-us")]
    assert played == [(24000, 24000, True)]
