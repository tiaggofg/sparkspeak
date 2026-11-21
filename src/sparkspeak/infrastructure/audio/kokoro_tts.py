"""Offline Kokoro ONNX neural TTS adapter with PipeWire PCM playback."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.pipewire_device import play_pcm
from sparkspeak.infrastructure.audio.ports import SpeakResult

DEFAULT_KOKORO_VOICE = "af_heart"
CURATED_KOKORO_VOICES: tuple[str, ...] = ("af_heart", "af_jessica", "am_liam", "am_puck")
KOKORO_MODEL_FILENAME = "kokoro-v1.0.onnx"
KOKORO_VOICES_FILENAME = "voices-v1.0.bin"


def _load_kokoro(model_path: Path, voices_path: Path) -> Any:
    from kokoro_onnx import Kokoro  # noqa: PLC0415

    return Kokoro(str(model_path), str(voices_path))


class KokoroTTSAdapter:
    """Synthesizes natural English speech offline via kokoro-onnx and PipeWire."""

    def __init__(
        self,
        models_dir: Path,
        *,
        default_voice: str = DEFAULT_KOKORO_VOICE,
        player: Callable[[npt.NDArray[np.float32], int, bool], None] | None = None,
        engine_loader: Callable[[Path, Path], Any] | None = None,
    ) -> None:
        self._models_dir = models_dir
        self._default_voice = default_voice
        self._player = player or play_pcm
        self._engine_loader = engine_loader or _load_kokoro
        self._engine: Any = None

    @property
    def model_path(self) -> Path:
        return self._models_dir / KOKORO_MODEL_FILENAME

    @property
    def voices_path(self) -> Path:
        return self._models_dir / KOKORO_VOICES_FILENAME

    def is_ready(self) -> bool:
        """Return True when both kokoro-v1.0.onnx and voices-v1.0.bin exist locally."""
        return self.model_path.is_file() and self.voices_path.is_file()

    def _ensure_engine(self) -> Any:
        if not self.is_ready():
            raise SparkSpeakError(
                error_code=ErrorCode.TTS_MODEL_MISSING,
                message=(
                    f"Kokoro TTS model files missing in {self._models_dir}. "
                    f"Expected {KOKORO_MODEL_FILENAME} and {KOKORO_VOICES_FILENAME}."
                ),
                recoverable=True,
                fallback_hint="text",
                details={"models_dir": str(self._models_dir)},
            )
        if self._engine is None:
            self._engine = self._engine_loader(self.model_path, self.voices_path)
        return self._engine

    async def speak(
        self,
        text: str,
        *,
        voice: str = DEFAULT_KOKORO_VOICE,
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult:
        """Synthesize text via Kokoro ONNX and play audio to PipeWire output."""
        selected_voice = voice.strip() or self._default_voice
        return await asyncio.to_thread(
            self._speak_sync,
            text,
            selected_voice,
            speed,
            blocking,
        )

    def _speak_sync(
        self,
        text: str,
        voice: str,
        speed: float,
        blocking: bool,
    ) -> SpeakResult:
        engine = self._ensure_engine()
        try:
            samples, sample_rate = engine.create(
                text,
                voice=voice,
                speed=speed,
                lang="en-us",
            )
        except Exception as exc:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Kokoro TTS synthesis failed for voice {voice!r}: {exc}",
                recoverable=True,
                fallback_hint="text",
                details={"voice": voice, "reason": str(exc)},
            ) from exc

        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        duration_ms = int(round(len(audio) * 1000 / sample_rate)) if sample_rate > 0 else 0
        self._player(audio, int(sample_rate), blocking)
        return SpeakResult(spoken=True, voice=voice, duration_ms=duration_ms)
