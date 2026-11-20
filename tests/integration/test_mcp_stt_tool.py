"""Integration tests for listen_and_transcribe MCP tool and voice-to-text fallback."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sparkspeak.config import load_config
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.infrastructure.audio.ports import TranscribeResult
from sparkspeak.mcp.server import create_server


def _server_params(tmp_path: Path) -> StdioServerParameters:
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "stt_test.db")
    env["SPARKSPEAK_BACKUPS_DIR"] = str(tmp_path / "backups")
    env["SPARKSPEAK_MODELS_DIR"] = str(tmp_path / "models")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "sparkspeak.mcp.server"],
        env=env,
    )


def _parse_json(result: Any) -> dict[str, Any]:
    assert result.content
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    return parsed


class _ScenarioSTT:
    """Controllable STTEngine stub for testing timeout, cap, and mic failure."""

    def __init__(self) -> None:
        self.mode = "silence"

    def is_ready(self) -> bool:
        return True

    async def listen_and_transcribe(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> TranscribeResult:
        if self.mode == "silence":
            return TranscribeResult(
                speech_detected=False,
                transcript="",
                duration_ms=0,
                truncated_at_max_duration=False,
            )
        if self.mode == "max_cap":
            return TranscribeResult(
                speech_detected=True,
                transcript="Yesterday I goed to the standup",
                duration_ms=max_duration_ms,
                truncated_at_max_duration=True,
                avg_logprob=-0.31,
                no_speech_prob=0.01,
            )
        raise SparkSpeakError(
            error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
            message="No active PipeWire input source detected.",
            recoverable=True,
            fallback_hint="text",
        )


def test_stt_timeouts_and_missing_mic(tmp_path: Path) -> None:
    """C10: listen_and_transcribe handles silence timeout, max cap, and missing mic."""

    async def _run() -> None:
        cfg = load_config(project_root=tmp_path)
        stub_stt = _ScenarioSTT()
        server = create_server(cfg, stt_adapter=stub_stt)
        tool = server._tool_manager.get_tool("listen_and_transcribe")
        assert tool is not None

        # 1. Silence timeout -> speech_detected=False, no error
        stub_stt.mode = "silence"
        silence_res = await tool.fn(initial_speech_timeout_ms=2000)
        assert silence_res.is_error is False
        silence_payload = _parse_json(silence_res)
        assert silence_payload["speech_detected"] is False
        assert silence_payload["transcript"] == ""
        assert silence_payload["duration_ms"] == 0
        assert silence_payload["truncated_at_max_duration"] is False

        # 2. Max duration cap -> truncated_at_max_duration=True + verbatim transcript
        stub_stt.mode = "max_cap"
        cap_res = await tool.fn(max_duration_ms=3000)
        assert cap_res.is_error is False
        cap_payload = _parse_json(cap_res)
        assert cap_payload["speech_detected"] is True
        assert cap_payload["truncated_at_max_duration"] is True
        assert cap_payload["transcript"] == "Yesterday I goed to the standup"

        # 3. Missing microphone -> MICROPHONE_UNAVAILABLE with fallback_hint="text"
        stub_stt.mode = "missing_mic"
        mic_res = await tool.fn()
        assert mic_res.is_error is True
        mic_payload = _parse_json(mic_res)
        assert mic_payload["error_code"] == "MICROPHONE_UNAVAILABLE"
        assert mic_payload["recoverable"] is True
        assert mic_payload["fallback_hint"] == "text"

    asyncio.run(_run())


def test_listen_and_transcribe_stdio_missing_model_and_invalid_bounds(tmp_path: Path) -> None:
    """listen_and_transcribe validates bounds and returns MODEL_NOT_INSTALLED over stdio."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert "listen_and_transcribe" in {t.name for t in tools.tools}

            bad_bounds = await session.call_tool(
                "listen_and_transcribe",
                {"silence_timeout_ms": 100},
            )
            assert bad_bounds.is_error is True
            assert _parse_json(bad_bounds)["error_code"] == "INVALID_ARGUMENT"

            missing_model = await session.call_tool("listen_and_transcribe", {})
            assert missing_model.is_error is True
            err = _parse_json(missing_model)
            assert err["error_code"] == "MODEL_NOT_INSTALLED"
            assert err["recoverable"] is True
            assert err["fallback_hint"] == "text"

    asyncio.run(_run())


def test_get_audio_status_reflects_installed_whisper_model(tmp_path: Path) -> None:
    """When whisper model cache exists, get_audio_status reports stt_ready=True."""
    whisper_dir = tmp_path / "models" / "whisper"
    whisper_dir.mkdir(parents=True)
    (whisper_dir / "model.bin").write_bytes(b"stub-weights")

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            status_res = await session.call_tool("get_audio_status", {})
            assert status_res.is_error is False
            data = _parse_json(status_res)
            assert data["stt_ready"] is True

    asyncio.run(_run())
