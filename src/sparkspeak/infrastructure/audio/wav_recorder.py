"""Lightweight 16 kHz mono 16-bit PCM WAV recorder with RMS energy endpointing."""

import asyncio
import os
import wave
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.pipewire_device import (
    _import_sounddevice,
    has_input_device,
)
from sparkspeak.infrastructure.audio.ports import RecordUtteranceResult

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION_MS = 32
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 512 samples
DEFAULT_RMS_THRESHOLD = 0.015
PRE_ROLL_MS = 200


def compute_rms(frame: npt.NDArray[np.float32]) -> float:
    """Compute root-mean-square energy for a float32 PCM frame."""
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float32))))


def float32_to_pcm16(audio: npt.NDArray[np.float32]) -> bytes:
    """Convert normalized float32 [-1.0, 1.0] samples to little-endian PCM int16 bytes."""
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype("<i2")
    return pcm16.tobytes()


def write_wav_atomic(target_path: Path, pcm16_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    """Atomically write 16-bit mono PCM WAV to target_path via temp file + os.replace."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f".{target_path.name}.tmp")
    with wave.open(str(tmp_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16_bytes)
    os.replace(tmp_path, target_path)


@dataclass(slots=True)
class _EndpointState:
    """Tracks RMS speech detection, pre-roll buffering, and silence/max-duration cutoffs."""

    rms_threshold: float
    initial_frames_limit: int
    silence_frames_limit: int
    max_speech_frames: int
    pre_roll: deque[npt.NDArray[np.float32]]
    captured: list[npt.NDArray[np.float32]] = field(default_factory=list)
    speech_started: bool = False
    silent_frames: int = 0
    initial_frames: int = 0
    peak_rms: float = 0.0
    truncated: bool = False

    def feed(self, frame: npt.NDArray[np.float32]) -> bool:
        """Consume one PCM frame and return True when capture should stop."""
        rms = compute_rms(frame)
        self.peak_rms = max(self.peak_rms, rms)

        if not self.speech_started:
            return self._handle_pre_speech(frame, rms)
        return self._handle_active_speech(frame, rms)

    def _handle_pre_speech(self, frame: npt.NDArray[np.float32], rms: float) -> bool:
        if rms >= self.rms_threshold:
            self.speech_started = True
            self.captured.extend(self.pre_roll)
            self.captured.append(frame.copy())
            self.silent_frames = 0
            return False
        self.pre_roll.append(frame.copy())
        self.initial_frames += 1
        return self.initial_frames >= self.initial_frames_limit

    def _handle_active_speech(self, frame: npt.NDArray[np.float32], rms: float) -> bool:
        self.captured.append(frame.copy())
        self.silent_frames = 0 if rms >= self.rms_threshold else self.silent_frames + 1
        if self.silent_frames >= self.silence_frames_limit:
            return True
        if len(self.captured) >= self.max_speech_frames:
            self.truncated = True
            return True
        return False


class WavRecorder:
    """Captures 16 kHz mono 16-bit PCM speech into `.data/audio/last_utterance.wav`."""

    def __init__(
        self,
        audio_dir: Path,
        *,
        rms_threshold: float = DEFAULT_RMS_THRESHOLD,
        pre_roll_ms: int = PRE_ROLL_MS,
        sample_rate: int = SAMPLE_RATE,
        mic_probe: Callable[[], bool] | None = None,
        stream_factory: Callable[[int, int], Any] | None = None,
    ) -> None:
        self._audio_dir = audio_dir
        self._rms_threshold = rms_threshold
        self._pre_roll_ms = pre_roll_ms
        self._sample_rate = sample_rate
        self._mic_probe = mic_probe or has_input_device
        self._stream_factory = stream_factory

    def is_mic_available(self) -> bool:
        """Return True when a PipeWire/PortAudio microphone input source is present."""
        return bool(self._mic_probe())

    async def record_utterance(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> RecordUtteranceResult:
        """Record a single spoken utterance using RMS silence endpointing."""
        if not self.is_mic_available():
            raise SparkSpeakError(
                error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
                message="No active PipeWire microphone input source detected.",
                recoverable=True,
                fallback_hint="text",
            )

        return await asyncio.to_thread(
            self._record_sync,
            silence_timeout_ms=silence_timeout_ms,
            initial_speech_timeout_ms=initial_speech_timeout_ms,
            max_duration_ms=max_duration_ms,
        )

    def _open_stream(self) -> Any:
        if self._stream_factory is not None:
            return self._stream_factory(self._sample_rate, FRAME_SAMPLES)
        sd = _import_sounddevice()
        return sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
        )

    def _capture_frames(
        self,
        *,
        silence_timeout_ms: int,
        initial_speech_timeout_ms: int,
        max_duration_ms: int,
    ) -> _EndpointState:
        frame_ms = max(1, round(FRAME_SAMPLES * 1000 / self._sample_rate))
        pre_roll_frames = max(1, self._pre_roll_ms // frame_ms)
        state = _EndpointState(
            rms_threshold=self._rms_threshold,
            initial_frames_limit=max(1, initial_speech_timeout_ms // frame_ms),
            silence_frames_limit=max(1, silence_timeout_ms // frame_ms),
            max_speech_frames=max(1, max_duration_ms // frame_ms),
            pre_roll=deque(maxlen=pre_roll_frames),
        )

        with self._open_stream() as stream:
            while True:
                raw, _overflowed = stream.read(FRAME_SAMPLES)
                frame = np.asarray(raw, dtype=np.float32).reshape(-1)
                if frame.size == 0 or state.feed(frame):
                    break
        return state

    def _record_sync(
        self,
        *,
        silence_timeout_ms: int,
        initial_speech_timeout_ms: int,
        max_duration_ms: int,
    ) -> RecordUtteranceResult:
        try:
            state = self._capture_frames(
                silence_timeout_ms=silence_timeout_ms,
                initial_speech_timeout_ms=initial_speech_timeout_ms,
                max_duration_ms=max_duration_ms,
            )
        except SparkSpeakError:
            raise
        except Exception as exc:
            raise SparkSpeakError(
                error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
                message=f"Microphone input stream failed: {exc}",
                recoverable=True,
                fallback_hint="text",
                details={"reason": str(exc)},
            ) from exc

        if not state.speech_started or not state.captured:
            return RecordUtteranceResult(
                speech_detected=False,
                wav_path=None,
                duration_ms=0,
                peak_rms=round(state.peak_rms, 6),
                truncated_at_max_duration=False,
            )

        audio = np.concatenate(state.captured)
        duration_ms = int(round(len(audio) * 1000 / self._sample_rate))
        wav_path = (self._audio_dir / "last_utterance.wav").resolve()
        write_wav_atomic(wav_path, float32_to_pcm16(audio), sample_rate=self._sample_rate)

        return RecordUtteranceResult(
            speech_detected=True,
            wav_path=str(wav_path),
            duration_ms=duration_ms,
            peak_rms=round(state.peak_rms, 6),
            truncated_at_max_duration=state.truncated,
        )
