"""Audio port protocols and result DTOs for TTS and STT adapters."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SpeakResult:
    spoken: bool
    voice: str
    duration_ms: int


@dataclass(frozen=True, slots=True)
class TranscribeResult:
    speech_detected: bool
    transcript: str
    duration_ms: int
    truncated_at_max_duration: bool = False
    avg_logprob: float | None = None
    no_speech_prob: float | None = None


@dataclass(frozen=True, slots=True)
class AudioStatus:
    tts_ready: bool
    stt_ready: bool
    pipewire_input: bool
    pipewire_output: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "tts_ready": self.tts_ready,
            "stt_ready": self.stt_ready,
            "pipewire_input": self.pipewire_input,
            "pipewire_output": self.pipewire_output,
        }


class TTSEngine(Protocol):
    """Port for local text-to-speech synthesis and playback."""

    def is_ready(self) -> bool: ...

    async def speak(
        self,
        text: str,
        *,
        voice: str = "en_US-lessac-medium",
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult: ...


class STTEngine(Protocol):
    """Port for VAD-gated microphone capture and raw transcription."""

    def is_ready(self) -> bool: ...

    async def listen_and_transcribe(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> TranscribeResult: ...
