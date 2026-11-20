"""PipeWire/PortAudio device probing and PCM playback via sounddevice."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError


@dataclass(frozen=True, slots=True)
class DeviceProbeResult:
    has_input: bool
    has_output: bool
    input_device_name: str | None = None
    output_device_name: str | None = None
    error: str | None = None


def _import_sounddevice() -> Any:
    import sounddevice as sd  # type: ignore[import-untyped]  # noqa: PLC0415

    return sd


def probe_pipewire_devices() -> DeviceProbeResult:
    """Probe default PipeWire/PortAudio input and output availability safely."""
    try:
        sd = _import_sounddevice()
        devices = sd.query_devices()
    except Exception as exc:  # noqa: BLE001
        return DeviceProbeResult(has_input=False, has_output=False, error=str(exc))

    has_input = False
    has_output = False
    in_name: str | None = None
    out_name: str | None = None

    try:
        default_in = sd.query_devices(kind="input")
        if isinstance(default_in, dict) and int(default_in.get("max_input_channels", 0)) > 0:
            has_input = True
            in_name = str(default_in.get("name", ""))
    except Exception:  # noqa: BLE001
        pass

    try:
        default_out = sd.query_devices(kind="output")
        if isinstance(default_out, dict) and int(default_out.get("max_output_channels", 0)) > 0:
            has_output = True
            out_name = str(default_out.get("name", ""))
    except Exception:  # noqa: BLE001
        pass

    if not has_input or not has_output:
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            if not has_input and int(dev.get("max_input_channels", 0)) > 0:
                has_input = True
                in_name = str(dev.get("name", ""))
            if not has_output and int(dev.get("max_output_channels", 0)) > 0:
                has_output = True
                out_name = str(dev.get("name", ""))

    return DeviceProbeResult(
        has_input=has_input,
        has_output=has_output,
        input_device_name=in_name,
        output_device_name=out_name,
    )


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
