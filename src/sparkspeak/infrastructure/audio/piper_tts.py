"""Offline Piper ONNX TTS adapter implementing TTSEngine."""

import asyncio
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.pipewire_device import has_output_device, play_pcm
from sparkspeak.infrastructure.audio.ports import SpeakResult

DEFAULT_PIPER_VOICE = "en_US-lessac-medium"


class _AudioChunkLike(Protocol):
    @property
    def sample_rate(self) -> int: ...

    @property
    def audio_float_array(self) -> npt.NDArray[np.float32]: ...


class _PiperVoiceLike(Protocol):
    def synthesize(
        self,
        text: str,
        syn_config: Any = None,
        include_alignments: bool = False,
    ) -> Iterable[_AudioChunkLike]: ...


VoiceLoader = Callable[[Path, Path | None], _PiperVoiceLike]
PlaybackFn = Callable[[npt.NDArray[np.float32], int, bool], None]


def _default_voice_loader(model_path: Path, config_path: Path | None) -> _PiperVoiceLike:
    from piper.voice import PiperVoice  # noqa: PLC0415

    return PiperVoice.load(model_path, config_path=config_path)


class PiperTTSAdapter:
    """Synthesizes English speech offline using Piper ONNX and plays via PipeWire."""

    def __init__(
        self,
        models_dir: Path,
        *,
        default_voice: str = DEFAULT_PIPER_VOICE,
        voice_loader: VoiceLoader | None = None,
        playback_fn: PlaybackFn | None = None,
        output_available_fn: Callable[[], bool] | None = None,
    ) -> None:
        self._piper_dir = models_dir / "piper"
        self._default_voice = default_voice
        self._voice_loader = voice_loader or _default_voice_loader
        self._playback_fn = playback_fn or play_pcm
        self._output_available_fn = output_available_fn or has_output_device
        self._voices: dict[str, _PiperVoiceLike] = {}

    def _model_paths(self, voice: str) -> tuple[Path, Path]:
        model_path = self._piper_dir / f"{voice}.onnx"
        config_path = self._piper_dir / f"{voice}.onnx.json"
        return model_path, config_path

    def is_ready(self) -> bool:
        """Return True if the default Piper .onnx model exists locally."""
        model_path, _ = self._model_paths(self._default_voice)
        return model_path.is_file()

    def _get_or_load_voice(self, voice: str) -> _PiperVoiceLike:
        if voice in self._voices:
            return self._voices[voice]
        model_path, config_path = self._model_paths(voice)
        if not model_path.is_file():
            raise SparkSpeakError(
                error_code=ErrorCode.TTS_MODEL_MISSING,
                message=(
                    f"Piper TTS model '{voice}' not found at {model_path}. "
                    "Run `uv run sparkspeak-setup-models` to download it."
                ),
                recoverable=True,
                fallback_hint="text",
                details={
                    "voice": voice,
                    "expected_path": str(model_path),
                    "setup_command": "uv run sparkspeak-setup-models",
                },
            )
        cfg = config_path if config_path.is_file() else None
        try:
            loaded = self._voice_loader(model_path, cfg)
        except Exception as exc:
            raise SparkSpeakError(
                error_code=ErrorCode.MODEL_NOT_INSTALLED,
                message=(
                    f"Failed to load Piper TTS model '{voice}': {exc}. "
                    "Run `uv run sparkspeak-setup-models`."
                ),
                recoverable=True,
                fallback_hint="text",
                details={"voice": voice, "reason": str(exc)},
            ) from exc
        self._voices[voice] = loaded
        return loaded

    def _synthesize_and_play_sync(
        self,
        text: str,
        *,
        voice: str,
        speed: float,
        blocking: bool,
    ) -> SpeakResult:
        piper_voice = self._get_or_load_voice(voice)
        if not self._output_available_fn():
            raise SparkSpeakError(
                error_code=ErrorCode.AUDIO_OUTPUT_UNAVAILABLE,
                message="No active PipeWire output sink detected.",
                recoverable=True,
                fallback_hint="text",
            )

        from piper.config import SynthesisConfig  # noqa: PLC0415

        syn_config = SynthesisConfig(length_scale=1.0 / speed)
        chunks = list(piper_voice.synthesize(text, syn_config=syn_config))
        if not chunks:
            return SpeakResult(spoken=False, voice=voice, duration_ms=0)

        sample_rate = chunks[0].sample_rate
        pcm = np.concatenate([chunk.audio_float_array for chunk in chunks]).astype(
            np.float32, copy=False
        )
        duration_ms = int(round((len(pcm) / sample_rate) * 1000)) if sample_rate > 0 else 0
        self._playback_fn(pcm, sample_rate, blocking)
        return SpeakResult(spoken=True, voice=voice, duration_ms=duration_ms)

    async def speak(
        self,
        text: str,
        *,
        voice: str = DEFAULT_PIPER_VOICE,
        speed: float = 1.0,
        blocking: bool = True,
    ) -> SpeakResult:
        """Synthesize text via Piper ONNX and stream PCM to PipeWire."""
        return await asyncio.to_thread(
            self._synthesize_and_play_sync,
            text,
            voice=voice,
            speed=speed,
            blocking=blocking,
        )
