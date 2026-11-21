"""PipeWire/PortAudio device probing and PCM playback via sounddevice."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError


@dataclass(frozen=True, slots=True)
class DeviceProbeResult:
    """Result of probing PipeWire/PortAudio input and output availability."""

    has_input: bool
    has_output: bool
    input_device_name: str | None = None
    output_device_name: str | None = None
    error: str | None = None


def _import_sounddevice() -> Any:
    import sounddevice as sd  # type: ignore[import-untyped]  # noqa: PLC0415

    return sd


def _probe_direction(
    sd: Any,
    devices: Any,
    kind: str,
    channel_key: str,
) -> tuple[bool, str | None]:
    try:
        default_dev = sd.query_devices(kind=kind)
        if isinstance(default_dev, dict) and int(default_dev.get(channel_key, 0)) > 0:
            return True, str(default_dev.get("name", ""))
    except Exception:  # noqa: BLE001
        pass

    for dev in devices:
        if isinstance(dev, dict) and int(dev.get(channel_key, 0)) > 0:
            return True, str(dev.get("name", ""))
    return False, None


def probe_pipewire_devices() -> DeviceProbeResult:
    """Probe default PipeWire/PortAudio input and output availability safely."""
    try:
        sd = _import_sounddevice()
        devices = sd.query_devices()
    except Exception as exc:  # noqa: BLE001
        return DeviceProbeResult(has_input=False, has_output=False, error=str(exc))

    has_input, in_name = _probe_direction(sd, devices, "input", "max_input_channels")
    has_output, out_name = _probe_direction(sd, devices, "output", "max_output_channels")
    return DeviceProbeResult(
        has_input=has_input,
        has_output=has_output,
        input_device_name=in_name,
        output_device_name=out_name,
    )


def has_input_device() -> bool:
    """Return True if a PipeWire/PortAudio microphone input source is available."""
    return probe_pipewire_devices().has_input


def has_output_device() -> bool:
    """Return True if a PipeWire/PortAudio output sink is available."""
    return probe_pipewire_devices().has_output


def play_pcm(
    audio: npt.NDArray[np.float32],
    sample_rate: int,
    blocking: bool = True,
) -> None:
    """Play mono float32 PCM audio to the default PipeWire output sink."""
    try:
        sd = _import_sounddevice()
        sd.play(audio, samplerate=sample_rate)
        if blocking:
            sd.wait()
    except Exception as exc:
        raise SparkSpeakError(
            error_code=ErrorCode.AUDIO_OUTPUT_UNAVAILABLE,
            message=f"PipeWire audio output unavailable: {exc}",
            recoverable=True,
            fallback_hint="text",
            details={"reason": str(exc)},
        ) from exc
