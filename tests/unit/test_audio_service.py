"""Unit tests for AudioService validation and single-flight asyncio.Lock."""

import asyncio

import pytest

from sparkspeak.application.audio_service import AudioService
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.ports import RecordUtteranceResult, SpeakResult


class _FakeRecorder:
    def __init__(
        self,
        *,
        available: bool = True,
        delay_s: float = 0.0,
        events: list[str] | None = None,
    ) -> None:
        self._available = available
        self._delay_s = delay_s
        self.events = events if events is not None else []

    def is_mic_available(self) -> bool:
        return self._available

    async def record_utterance(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> RecordUtteranceResult:
        self.events.append(f"rec_start:{silence_timeout_ms}")
        if self._delay_s > 0:
            await asyncio.sleep(self._delay_s)
        self.events.append(f"rec_end:{silence_timeout_ms}")
        return RecordUtteranceResult(
            speech_detected=True,
            wav_path="/tmp/last_utterance.wav",
            duration_ms=420,
            peak_rms=0.18,
            truncated_at_max_duration=False,
        )


class _FakeTTS:
    def __init__(
        self,
        *,
        ready: bool = True,
        delay_s: float = 0.0,
        events: list[str] | None = None,
    ) -> None:
        self._ready = ready
        self._delay_s = delay_s
        self.events = events if events is not None else []

    def is_ready(self) -> bool:
        return self._ready

    async def speak(
        self,
        text: str,
        *,
        voice: str = "af_heart",
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult:
        self.events.append(f"tts_start:{text}")
        if self._delay_s > 0:
            await asyncio.sleep(self._delay_s)
        self.events.append(f"tts_end:{text}")
        return SpeakResult(spoken=True, voice=voice, duration_ms=500)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"silence_timeout_ms": 499},
        {"silence_timeout_ms": 5001},
        {"initial_speech_timeout_ms": 1999},
        {"initial_speech_timeout_ms": 30001},
        {"max_duration_ms": 2999},
        {"max_duration_ms": 90001},
    ],
)
def test_record_utterance_rejects_out_of_bounds_timeouts(kwargs: dict[str, int]) -> None:
    svc = AudioService(recorder=_FakeRecorder())
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.record_utterance(**kwargs))
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.fallback_hint == "text"


@pytest.mark.parametrize("bad_speed", [0.5, 0.74, 1.26, 2.0])
def test_speak_text_rejects_out_of_range_speed(bad_speed: float) -> None:
    svc = AudioService(tts=_FakeTTS())
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.speak_text("Hello there", speed=bad_speed))
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_speak_text_rejects_empty_and_overlong_text() -> None:
    svc = AudioService(tts=_FakeTTS())
    with pytest.raises(SparkSpeakError) as exc_empty:
        asyncio.run(svc.speak_text("   "))
    assert exc_empty.value.error_code == ErrorCode.INVALID_ARGUMENT

    with pytest.raises(SparkSpeakError) as exc_long:
        asyncio.run(svc.speak_text("a" * 2001))
    assert exc_long.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_concurrent_tts_and_record_serialize_under_audio_lock() -> None:
    events: list[str] = []
    tts = _FakeTTS(delay_s=0.03, events=events)
    recorder = _FakeRecorder(delay_s=0.03, events=events)
    svc = AudioService(recorder=recorder, tts=tts)

    async def _run() -> None:
        await asyncio.gather(
            svc.speak_text("First prompt"),
            svc.record_utterance(silence_timeout_ms=600),
        )

    asyncio.run(_run())
    assert events == [
        "tts_start:First prompt",
        "tts_end:First prompt",
        "rec_start:600",
        "rec_end:600",
    ]


def test_missing_recorder_and_tts_raise_recoverable_errors() -> None:
    svc = AudioService(recorder=None, tts=None)
    assert svc.is_mic_available() is False
    assert svc.is_tts_available() is False

    with pytest.raises(SparkSpeakError) as exc_mic:
        asyncio.run(svc.record_utterance())
    assert exc_mic.value.error_code == ErrorCode.MICROPHONE_UNAVAILABLE
    assert exc_mic.value.fallback_hint == "text"

    with pytest.raises(SparkSpeakError) as exc_tts:
        asyncio.run(svc.speak_text("Hello"))
    assert exc_tts.value.error_code == ErrorCode.TTS_MODEL_MISSING
    assert exc_tts.value.fallback_hint == "text"


def test_availability_delegates_to_adapters() -> None:
    svc = AudioService(recorder=_FakeRecorder(available=True), tts=_FakeTTS(ready=True))
    assert svc.is_mic_available() is True
    assert svc.is_tts_available() is True
