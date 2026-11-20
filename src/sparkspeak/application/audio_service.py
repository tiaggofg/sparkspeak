"""Application service serializing TTS and STT operations under a single AudioLock."""

import asyncio
from collections.abc import Callable

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.ports import (
    AudioStatus,
    SpeakResult,
    STTEngine,
    TranscribeResult,
    TTSEngine,
)

MIN_SPEED = 0.75
MAX_SPEED = 1.25
MAX_TTS_TEXT_LEN = 2000


class AudioService:
    """Coordinates single-flight audio hardware access via asyncio.Lock."""

    def __init__(
        self,
        *,
        tts: TTSEngine | None = None,
        stt: STTEngine | None = None,
        device_probe: Callable[[], AudioStatus] | None = None,
    ) -> None:
        self._tts = tts
        self._stt = stt
        self._device_probe = device_probe
        self._lock = asyncio.Lock()

    def get_audio_status(self) -> AudioStatus:
        """Return current readiness of TTS, STT, and PipeWire input/output."""
        if self._device_probe is not None:
            return self._device_probe()
        return AudioStatus(
            tts_ready=self._tts.is_ready() if self._tts is not None else False,
            stt_ready=self._stt.is_ready() if self._stt is not None else False,
            pipewire_input=self._stt is not None,
            pipewire_output=self._tts is not None,
        )

    async def speak_text(
        self,
        text: str,
        *,
        voice: str = "en_US-lessac-medium",
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
                message="TTS engine is not configured; run `uv run sparkspeak-setup-models`.",
                recoverable=True,
                fallback_hint="text",
                details={"setup_command": "uv run sparkspeak-setup-models"},
            )

        async with self._lock:
            return await self._tts.speak(
                stripped,
                voice=voice,
                speed=speed,
                blocking=blocking,
            )

    async def listen_and_transcribe(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> TranscribeResult:
        """Capture and transcribe speech under AudioLock."""
        if self._stt is None:
            raise SparkSpeakError(
                error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
                message="STT engine is not configured or microphone is unavailable.",
                recoverable=True,
                fallback_hint="text",
            )
        async with self._lock:
            return await self._stt.listen_and_transcribe(
                silence_timeout_ms=silence_timeout_ms,
                initial_speech_timeout_ms=initial_speech_timeout_ms,
                max_duration_ms=max_duration_ms,
            )
