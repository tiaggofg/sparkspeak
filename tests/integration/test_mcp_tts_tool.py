"""Integration tests for speak_text and get_audio_status MCP tools over stdio."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params(tmp_path: Path) -> StdioServerParameters:
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "tts_test.db")
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


def test_speak_text_validation_and_missing_model(tmp_path: Path) -> None:
    """C8: speak_text rejects invalid speed/empty text and returns TTS_MODEL_MISSING."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            empty_res = await session.call_tool("speak_text", {"text": "   "})
            assert empty_res.is_error is True
            assert _parse_json(empty_res)["error_code"] == "INVALID_ARGUMENT"

            bad_speed = await session.call_tool(
                "speak_text",
                {"text": "Hello", "speed": 1.5},
            )
            assert bad_speed.is_error is True
            assert _parse_json(bad_speed)["error_code"] == "INVALID_ARGUMENT"

            missing_model = await session.call_tool(
                "speak_text",
                {"text": "Hello engineer", "speed": 1.0},
            )
            assert missing_model.is_error is True
            err = _parse_json(missing_model)
            assert err["error_code"] == "TTS_MODEL_MISSING"
            assert err["recoverable"] is True
            assert err["fallback_hint"] == "text"

    asyncio.run(_run())


def test_get_audio_status_reports_readiness_and_start_session_includes_it(
    tmp_path: Path,
) -> None:
    """get_audio_status and start_session report consistent audio readiness flags."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            status_res = await session.call_tool("get_audio_status", {})
            assert status_res.is_error is False
            status_data = _parse_json(status_res)
            assert set(status_data.keys()) == {
                "tts_ready",
                "stt_ready",
                "pipewire_input",
                "pipewire_output",
            }
            assert status_data["tts_ready"] is False

            start_res = await session.call_tool("start_session", {"input_mode": "voice"})
            assert start_res.is_error is False
            start_data = _parse_json(start_res)
            assert start_data["audio_status"] == status_data

    asyncio.run(_run())


def test_start_session_reflects_installed_piper_model(tmp_path: Path) -> None:
    """When Piper .onnx exists, get_audio_status reports tts_ready=True."""
    piper_dir = tmp_path / "models" / "piper"
    piper_dir.mkdir(parents=True)
    (piper_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-onnx")

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            status_res = await session.call_tool("get_audio_status", {})
            assert status_res.is_error is False
            status_data = _parse_json(status_res)
            assert status_data["tts_ready"] is True

    asyncio.run(_run())
