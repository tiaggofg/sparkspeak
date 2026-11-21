"""Integration tests for record_utterance MCP tool and voice-to-text fallback."""

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
from sparkspeak.infrastructure.audio.ports import RecordUtteranceResult
from sparkspeak.mcp.server import create_server


def _server_params(tmp_path: Path) -> StdioServerParameters:
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "record_test.db")
    env["SPARKSPEAK_BACKUPS_DIR"] = str(tmp_path / "backups")
    env["SPARKSPEAK_AUDIO_DIR"] = str(tmp_path / "audio")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "sparkspeak.mcp.server"],
        env=env,
    )


def _parse_json(result: Any) -> dict[str, Any]:
    assert result.content
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    return parsed


class _ScenarioRecorder:
    """Controllable UtteranceRecorder stub for testing timeout, cap, and mic failure."""

    def __init__(self, wav_path: Path) -> None:
        self.mode = "silence"
        self.wav_path = wav_path

    def is_mic_available(self) -> bool:
        return self.mode != "missing_mic"

    async def record_utterance(
        self,
        *,
        silence_timeout_ms: int = 1500,
        initial_speech_timeout_ms: int = 10000,
        max_duration_ms: int = 45000,
    ) -> RecordUtteranceResult:
        if self.mode == "silence":
            return RecordUtteranceResult(
                speech_detected=False,
                wav_path=None,
                duration_ms=0,
                peak_rms=0.002,
                truncated_at_max_duration=False,
            )
        if self.mode == "max_cap":
            return RecordUtteranceResult(
                speech_detected=True,
                wav_path=str(self.wav_path),
                duration_ms=max_duration_ms,
                peak_rms=0.145,
                truncated_at_max_duration=True,
            )
        raise SparkSpeakError(
            error_code=ErrorCode.MICROPHONE_UNAVAILABLE,
            message="No active PipeWire input source detected.",
            recoverable=True,
            fallback_hint="text",
        )


def test_record_utterance_timeouts_and_missing_mic(tmp_path: Path) -> None:
    """C4: record_utterance handles silence timeout, max cap, and missing mic."""

    async def _run() -> None:
        cfg = load_config(project_root=tmp_path)
        stub_recorder = _ScenarioRecorder(cfg.audio_dir / "last_utterance.wav")
        server = create_server(cfg, recorder=stub_recorder)
        tool = server._tool_manager.get_tool("record_utterance")
        assert tool is not None

        # 1. Silence timeout -> speech_detected=False, wav_path=None, no error
        stub_recorder.mode = "silence"
        silence_res = await tool.fn(initial_speech_timeout_ms=2000)
        assert silence_res.is_error is False
        silence_payload = _parse_json(silence_res)
        assert silence_payload["speech_detected"] is False
        assert silence_payload["wav_path"] is None
        assert silence_payload["duration_ms"] == 0
        assert silence_payload["truncated_at_max_duration"] is False

        # 2. Max duration cap -> truncated_at_max_duration=True + wav_path
        stub_recorder.mode = "max_cap"
        cap_res = await tool.fn(max_duration_ms=3000)
        assert cap_res.is_error is False
        cap_payload = _parse_json(cap_res)
        assert cap_payload["speech_detected"] is True
        assert cap_payload["truncated_at_max_duration"] is True
        assert cap_payload["wav_path"] == str(cfg.audio_dir / "last_utterance.wav")

        # 3. Missing microphone -> MICROPHONE_UNAVAILABLE with fallback_hint="text"
        stub_recorder.mode = "missing_mic"
        mic_res = await tool.fn()
        assert mic_res.is_error is True
        mic_payload = _parse_json(mic_res)
        assert mic_payload["error_code"] == "MICROPHONE_UNAVAILABLE"
        assert mic_payload["recoverable"] is True
        assert mic_payload["fallback_hint"] == "text"

    asyncio.run(_run())


def test_record_utterance_stdio_invalid_bounds(tmp_path: Path) -> None:
    """record_utterance validates timeout bounds over stdio."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert "record_utterance" in {t.name for t in tools.tools}

            bad_bounds = await session.call_tool(
                "record_utterance",
                {"silence_timeout_ms": 100},
            )
            assert bad_bounds.is_error is True
            assert _parse_json(bad_bounds)["error_code"] == "INVALID_ARGUMENT"

    asyncio.run(_run())
