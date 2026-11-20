"""Unit tests for AudioService validation and single-flight asyncio.Lock."""

import asyncio

import pytest

from sparkspeak.application.audio_service import AudioService
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.ports import AudioStatus, SpeakResult, TranscribeResult


class _FakeTTS:
    def __init__(self, delay_s: float = 0.0, ready: bool = True) -> None:
        self.delay_s = delay_s
        self.ready = ready
        self.events: list[str] = []

    def is_ready(self) -> bool:
        return self.ready

    async def speak(
        self,
        text: str,
        *,
        voice: str = "en_US-lessac-medium",
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult:
        self.events.append(f"tts_start:{text}")
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        self.events.append(f"tts_end:{text}")
        return SpeakResult(spoken=True, voice=voice, duration_ms=150)


class _FakeSTT:
    def __init__(self, events: list[str], delay_s: float = 0.0) -> None:
        self.events = events
        self.delay_s = delay_s

    def is_ready(self) -> bool:
        return True

    async def listen_and_transcribe(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> TranscribeResult:
        self.events.append("stt_start")
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)
        self.events.append("stt_end")
        return TranscribeResult(
            speech_detected=True,
            transcript="hello world",
            duration_ms=500,
            truncated_at_max_duration=False,
            avg_logprob=-0.2,
            no_speech_prob=0.01,
        )


def test_speak_text_rejects_empty_text() -> None:
    svc = AudioService(tts=_FakeTTS())
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.speak_text("   "))
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT
    assert exc_info.value.fallback_hint == "text"


@pytest.mark.parametrize("bad_speed", [0.5, 0.74, 1.26, 2.0])
def test_speak_text_rejects_out_of_range_speed(bad_speed: float) -> None:
    svc = AudioService(tts=_FakeTTS())
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.speak_text("Hello there", speed=bad_speed))
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_speak_text_rejects_overlong_text() -> None:
    svc = AudioService(tts=_FakeTTS())
    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.speak_text("a" * 2001))
    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_concurrent_tts_and_stt_serialize_under_audio_lock() -> None:
    tts = _FakeTTS(delay_s=0.03)
    stt = _FakeSTT(events=tts.events, delay_s=0.03)
    svc = AudioService(tts=tts, stt=stt)

    async def _run() -> None:
        await asyncio.gather(
            svc.speak_text("First prompt"),
            svc.listen_and_transcribe(),
        )

    asyncio.run(_run())
    assert tts.events == [
        "tts_start:First prompt",
        "tts_end:First prompt",
        "stt_start",
        "stt_end",
    ]


def test_missing_tts_engine_raises_recoverable_error() -> None:
    svc = AudioService(
        tts=None,
        stt=None,
        device_probe=lambda: AudioStatus(
            tts_ready=False,
            stt_ready=False,
            pipewire_input=False,
            pipewire_output=False,
        ),
    )
    status = svc.get_audio_status()
    assert status.tts_ready is False
    assert status.pipewire_output is False

    with pytest.raises(SparkSpeakError) as exc_info:
        asyncio.run(svc.speak_text("Hello"))
    assert exc_info.value.error_code == ErrorCode.TTS_MODEL_MISSING
    assert exc_info.value.recoverable is True
    assert exc_info.value.fallback_hint == "text"
