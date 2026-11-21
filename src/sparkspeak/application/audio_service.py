"""Application service serializing microphone WAV capture and TTS playback under AudioLock."""

import asyncio

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.kokoro_tts import DEFAULT_KOKORO_VOICE
from sparkspeak.infrastructure.audio.ports import (
    RecordUtteranceResult,
    SpeakResult,
    TTSEngine,
    UtteranceRecorder,
)

MIN_SPEED = 0.75
MAX_SPEED = 1.25
MAX_TTS_TEXT_LEN = 2000
MIN_SILENCE_TIMEOUT_MS = 500
MAX_SILENCE_TIMEOUT_MS = 5000
MIN_INITIAL_SPEECH_TIMEOUT_MS = 2000
MAX_INITIAL_SPEECH_TIMEOUT_MS = 30000
MIN_MAX_DURATION_MS = 3000
MAX_MAX_DURATION_MS = 90000


def _validate_int_range(value: int, field: str, low: int, high: int) -> None:
    if isinstance(value, bool) or value < low or value > high:
        raise SparkSpeakError(
            error_code=ErrorCode.INVALID_ARGUMENT,
            message=f"{field} must be between {low} and {high}; got {value!r}.",
            recoverable=True,
            fallback_hint="text",
            details={"field": field, "value": value},
        )


class AudioService:
    """Coordinates single-flight microphone WAV capture and TTS playback via asyncio.Lock."""

    def __init__(
        self,
        *,
        recorder: UtteranceRecorder | None = None,
        tts: TTSEngine | None = None,
    ) -> None:
        self._recorder = recorder
        self._tts = tts
        self._lock = asyncio.Lock()

    def is_mic_available(self) -> bool:
        """Return True if a microphone input source is available."""
        if self._recorder is None:
            return False
        return self._recorder.is_mic_available()

    def is_tts_available(self) -> bool:
        """Return True if the local TTS engine and models are ready."""
        if self._tts is None:
            return False
        return self._tts.is_ready()

    async def speak_text(
        self,
        text: str,
        *,
        voice: str = DEFAULT_KOKORO_VOICE,
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult:
        """Validate arguments and play synthesized speech under AudioLock."""
        stripped = text.strip()
        if not stripped:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="text must not be empty.",
                recoverable=True,
                fallback_hint="text",
                details={"field": "text"},
            )
        if len(stripped) > MAX_TTS_TEXT_LEN:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"text must be at most {MAX_TTS_TEXT_LEN} characters.",
                recoverable=True,
                fallback_hint="text",
                details={"field": "text", "length": len(stripped)},
            )
        if isinstance(speed, bool) or speed < MIN_SPEED or speed > MAX_SPEED:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"speed must be between {MIN_SPEED} and {MAX_SPEED}; got {speed!r}.",
                recoverable=True,
                fallback_hint="text",
                details={"field": "speed", "value": speed},
            )
        if self._tts is None:
            raise SparkSpeakError(
                error_code=ErrorCode.TTS_MODEL_MISSING,
                message="TTS engine is not configured.",
                recoverable=True,
                fallback_hint="text",
            )
        async with self._lock:
            return await self._tts.speak(
                stripped,
                voice=voice,
                speed=speed,
                blocking=blocking,
            )

    async def record_utterance(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> RecordUtteranceResult:
        """Validate timeout bounds and record an utterance under AudioLock."""
        _validate_int_range(
            silence_timeout_ms,
            "silence_timeout_ms",
            MIN_SILENCE_TIMEOUT_MS,
            MAX_SILENCE_TIMEOUT_MS,
        )
        _validate_int_range(
            initial_speech_timeout_ms,
            "initial_speech_timeout_ms",
            MIN_INITIAL_SPEECH_TIMEOUT_MS,
            MAX_INITIAL_SPEECH_TIMEOUT_MS,
        )
        _validate_int_range(
            max_duration_ms,
            "max_duration_ms",
            MIN_MAX_DURATION_MS,
            MAX_MAX_DURATION_MS,
        )
        if self._recorder is None:
            raise SparkSpeakError(
                error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
                message="Microphone recorder is not configured or unavailable.",
                recoverable=True,
                fallback_hint="text",
            )
        async with self._lock:
            return await self._recorder.record_utterance(
                silence_timeout_ms=silence_timeout_ms,
                initial_speech_timeout_ms=initial_speech_timeout_ms,
                max_duration_ms=max_duration_ms,
            )
