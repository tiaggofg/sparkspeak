"""16kHz PipeWire PCM capture with Silero VAD endpointing and faster-whisper STT."""

import asyncio
import wave
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.pipewire_device import _import_sounddevice
from sparkspeak.infrastructure.audio.ports import TranscribeResult

SAMPLE_RATE_HZ = 16000
CHANNELS = 1
VAD_FRAME_SAMPLES = 512  # 32ms at 16kHz (required by Silero VAD)
VAD_FRAME_MS = 32
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_VAD_THRESHOLD = 0.5


class _WhisperModelLike(Protocol):
    def transcribe(
        self,
        audio: npt.NDArray[np.float32],
        **kwargs: Any,
    ) -> tuple[Iterable[Any], Any]: ...


ModelLoader = Callable[[str, Path], _WhisperModelLike]
VadProbFn = Callable[[npt.NDArray[np.float32]], float]
StreamFactory = Callable[[int, int, int], Iterable[npt.NDArray[np.float32]]]
CaptureFn = Callable[..., tuple[npt.NDArray[np.float32], bool, bool]]


def load_wav_pcm_16k(wav_path: Path) -> npt.NDArray[np.float32]:
    """Load a 16kHz mono 16-bit PCM WAV file into a float32 array in [-1.0, 1.0]."""
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        if framerate != SAMPLE_RATE_HZ or channels != CHANNELS or sampwidth != 2:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=(
                    f"WAV must be 16kHz mono 16-bit PCM; got {framerate}Hz, "
                    f"{channels}ch, {sampwidth * 8}-bit."
                ),
                details={"path": str(wav_path)},
            )
        raw = wf.readframes(wf.getnframes())
    pcm_i16 = np.frombuffer(raw, dtype=np.int16)
    return (pcm_i16.astype(np.float32) / 32768.0).copy()


def _default_model_loader(model_size: str, download_root: Path) -> _WhisperModelLike:
    from faster_whisper import WhisperModel  # type: ignore[import-untyped]  # noqa: PLC0415

    return cast(
        _WhisperModelLike,
        WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=str(download_root),
            local_files_only=True,
        ),
    )


def _default_vad_prob_fn() -> VadProbFn:
    from faster_whisper.vad import get_vad_model  # type: ignore[import-untyped]  # noqa: PLC0415

    vad_model = get_vad_model()

    def _score(chunk: npt.NDArray[np.float32]) -> float:
        audio_1d = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if len(audio_1d) < VAD_FRAME_SAMPLES:
            audio_1d = np.pad(audio_1d, (0, VAD_FRAME_SAMPLES - len(audio_1d)))
        elif len(audio_1d) > VAD_FRAME_SAMPLES:
            audio_1d = audio_1d[:VAD_FRAME_SAMPLES]
        prob = vad_model(audio_1d)
        return float(np.asarray(prob).item())

    return _score


def _iter_sounddevice_chunks(
    sample_rate: int,
    blocksize: int,
    channels: int,
) -> Iterator[npt.NDArray[np.float32]]:
    """Yield mono float32 PCM chunks from PipeWire default input via sounddevice."""
    try:
        sd = _import_sounddevice()
        stream = sd.InputStream(
            samplerate=sample_rate,
            blocksize=blocksize,
            channels=channels,
            dtype="float32",
        )
    except Exception as exc:
        raise SparkSpeakError(
            error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
            message=f"PipeWire input source unavailable: {exc}",
            recoverable=True,
            fallback_hint="text",
            details={"reason": str(exc)},
        ) from exc

    with stream:
        while True:
            data, _overflowed = stream.read(blocksize)
            yield np.asarray(data, dtype=np.float32).reshape(-1).copy()


class WhisperSTTAdapter:
    """Captures 16kHz mono PCM with Silero VAD endpointing and transcribes verbatim."""

    def __init__(
        self,
        models_dir: Path,
        *,
        model_size: str = DEFAULT_WHISPER_MODEL,
        vad_threshold: float = DEFAULT_VAD_THRESHOLD,
        model_loader: ModelLoader | None = None,
        vad_prob_fn: VadProbFn | None = None,
        stream_factory: StreamFactory | None = None,
        capture_fn: CaptureFn | None = None,
    ) -> None:
        self._whisper_dir = models_dir / "whisper"
        self._model_size = model_size
        self._vad_threshold = vad_threshold
        self._model_loader = model_loader
        self._vad_prob_fn = vad_prob_fn
        self._stream_factory = stream_factory or _iter_sounddevice_chunks
        self._capture_fn = capture_fn
        self._model: _WhisperModelLike | None = None

    def is_ready(self) -> bool:
        """Return True if local faster-whisper weights or an injected loader are available."""
        if self._model_loader is not None:
            return True
        return self._whisper_dir.is_dir() and any(self._whisper_dir.iterdir())

    def _get_or_load_model(self) -> _WhisperModelLike:
        if self._model is not None:
            return self._model
        if not self.is_ready():
            raise SparkSpeakError(
                error_code=ErrorCode.MODEL_NOT_INSTALLED,
                message=(
                    f"Whisper STT model '{self._model_size}' is not installed in "
                    f"{self._whisper_dir}. Run `uv run sparkspeak-setup-models`."
                ),
                recoverable=True,
                fallback_hint="text",
                details={
                    "model_size": self._model_size,
                    "expected_dir": str(self._whisper_dir),
                    "setup_command": "uv run sparkspeak-setup-models",
                },
            )
        loader = self._model_loader or _default_model_loader
        try:
            self._model = loader(self._model_size, self._whisper_dir)
        except Exception as exc:
            raise SparkSpeakError(
                error_code=ErrorCode.MODEL_NOT_INSTALLED,
                message=(
                    f"Failed to load Whisper STT model '{self._model_size}': {exc}. "
                    "Run `uv run sparkspeak-setup-models`."
                ),
                recoverable=True,
                fallback_hint="text",
                details={"model_size": self._model_size, "reason": str(exc)},
            ) from exc
        return self._model

    def _record_vad_bounded(
        self,
        *,
        silence_timeout_ms: int,
        initial_speech_timeout_ms: int,
        max_duration_ms: int,
        vad_prob_fn: VadProbFn,
    ) -> tuple[npt.NDArray[np.float32], bool, bool]:
        if self._capture_fn is not None:
            return self._capture_fn(
                silence_timeout_ms=silence_timeout_ms,
                initial_speech_timeout_ms=initial_speech_timeout_ms,
                max_duration_ms=max_duration_ms,
                vad_prob_fn=vad_prob_fn,
            )

        try:
            chunks_iter = self._stream_factory(SAMPLE_RATE_HZ, VAD_FRAME_SAMPLES, CHANNELS)
        except SparkSpeakError:
            raise
        except Exception as exc:
            raise SparkSpeakError(
                error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
                message=f"PipeWire input source unavailable: {exc}",
                recoverable=True,
                fallback_hint="text",
                details={"reason": str(exc)},
            ) from exc

        captured: list[npt.NDArray[np.float32]] = []
        speech_started = False
        elapsed_ms = 0
        trailing_silence_ms = 0
        truncated = False

        for chunk in chunks_iter:
            mono = np.asarray(chunk, dtype=np.float32).reshape(-1)
            chunk_ms = max(1, int(round((len(mono) / SAMPLE_RATE_HZ) * 1000)))
            elapsed_ms += chunk_ms
            prob = vad_prob_fn(mono)
            is_speech = prob >= self._vad_threshold

            if is_speech:
                speech_started = True
                trailing_silence_ms = 0
                captured.append(mono)
            elif speech_started:
                captured.append(mono)
                trailing_silence_ms += chunk_ms
                if trailing_silence_ms >= silence_timeout_ms:
                    break
            elif elapsed_ms >= initial_speech_timeout_ms:
                return np.empty(0, dtype=np.float32), False, False

            if elapsed_ms >= max_duration_ms:
                truncated = speech_started
                break

        if not speech_started or not captured:
            return np.empty(0, dtype=np.float32), False, False

        return np.concatenate(captured).astype(np.float32, copy=False), True, truncated

    def _listen_and_transcribe_sync(
        self,
        *,
        silence_timeout_ms: int,
        initial_speech_timeout_ms: int,
        max_duration_ms: int,
    ) -> TranscribeResult:
        model = self._get_or_load_model()
        vad_fn = self._vad_prob_fn or _default_vad_prob_fn()

        audio, speech_detected, truncated = self._record_vad_bounded(
            silence_timeout_ms=silence_timeout_ms,
            initial_speech_timeout_ms=initial_speech_timeout_ms,
            max_duration_ms=max_duration_ms,
            vad_prob_fn=vad_fn,
        )
        if not speech_detected or len(audio) == 0:
            return TranscribeResult(
                speech_detected=False,
                transcript="",
                duration_ms=0,
                truncated_at_max_duration=False,
            )

        segments_iter, _info = model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            initial_prompt=None,
        )
        segments = list(segments_iter)
        transcript = " ".join(str(seg.text).strip() for seg in segments if str(seg.text).strip())
        avg_logprob = (
            float(sum(float(seg.avg_logprob) for seg in segments) / len(segments))
            if segments and hasattr(segments[0], "avg_logprob")
            else None
        )
        no_speech_prob = (
            float(sum(float(seg.no_speech_prob) for seg in segments) / len(segments))
            if segments and hasattr(segments[0], "no_speech_prob")
            else None
        )
        duration_ms = int(round((len(audio) / SAMPLE_RATE_HZ) * 1000))

        return TranscribeResult(
            speech_detected=bool(transcript) or speech_detected,
            transcript=transcript,
            duration_ms=duration_ms,
            truncated_at_max_duration=truncated,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
        )

    async def listen_and_transcribe(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> TranscribeResult:
        """Capture 16kHz PCM with Silero VAD and return raw verbatim transcript."""
        return await asyncio.to_thread(
            self._listen_and_transcribe_sync,
            silence_timeout_ms=silence_timeout_ms,
            initial_speech_timeout_ms=initial_speech_timeout_ms,
            max_duration_ms=max_duration_ms,
        )
