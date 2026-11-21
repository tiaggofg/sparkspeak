"""Audio port protocols and result DTOs for WAV capture and Kokoro TTS output."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class RecordUtteranceResult:
    """Result of capturing a learner utterance into a 16 kHz mono WAV file."""

    speech_detected: bool
    wav_path: str | None
    duration_ms: int
    peak_rms: float
    truncated_at_max_duration: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for MCP JSON tool responses."""
        return {
            "speech_detected": self.speech_detected,
            "wav_path": self.wav_path,
            "duration_ms": self.duration_ms,
            "peak_rms": self.peak_rms,
            "truncated_at_max_duration": self.truncated_at_max_duration,
        }


@dataclass(frozen=True, slots=True)
class SpeakResult:
    """Result of synthesizing and playing a tutor utterance."""

    spoken: bool
    voice: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for MCP JSON tool responses."""
        return {
            "spoken": self.spoken,
            "voice": self.voice,
            "duration_ms": self.duration_ms,
        }


class UtteranceRecorder(Protocol):
    """Port for RMS-gated microphone capture into a WAV file."""

    def is_mic_available(self) -> bool: ...

    async def record_utterance(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> RecordUtteranceResult: ...


class TTSEngine(Protocol):
    """Port for local neural text-to-speech synthesis and playback."""

    def is_ready(self) -> bool: ...

    async def speak(
        self,
        text: str,
        *,
        voice: str = "af_heart",
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult: ...
