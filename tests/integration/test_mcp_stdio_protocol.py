"""Integration tests for SparkSpeak stdio MCP server protocol (Phase 1 tools)."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _server_params(tmp_path: Path) -> StdioServerParameters:
    db_path = tmp_path / "test_sparkspeak.db"
    backups_dir = tmp_path / "backups"
    models_dir = tmp_path / "models"
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(db_path)
    env["SPARKSPEAK_BACKUPS_DIR"] = str(backups_dir)
    env["SPARKSPEAK_MODELS_DIR"] = str(models_dir)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "sparkspeak.mcp.server"],
        env=env,
    )


def _parse_tool_json(result: Any) -> dict[str, Any]:
    assert result.content, "Expected non-empty tool content"
    text = result.content[0].text
    parsed: dict[str, Any] = json.loads(text)
    return parsed


def test_start_session_persists_active_row(tmp_path: Path) -> None:
    """C1: start_session persists an active study_sessions row in SQLite."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                "start_session",
                {"deck_slug": "phrasal-verbs", "mode": "active_review", "input_mode": "text"},
            )
            assert not result.is_error
            payload = _parse_tool_json(result)
            assert payload["session_id"]
            assert payload["deck"]["slug"] == "phrasal-verbs"
            assert payload["mode"] == "active_review"
            assert payload["effective_input_mode"] == "text"
            assert payload["due_summary"]["new_cards"] > 0

            conn = sqlite3.connect(tmp_path / "test_sparkspeak.db")
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, mode, input_mode_default, status FROM study_sessions WHERE id = ?",
                (payload["session_id"],),
            ).fetchone()
            conn.close()
            assert row is not None
            assert row["status"] == "active"
            assert row["mode"] == "active_review"
            assert row["input_mode_default"] == "text"

    asyncio.run(_run())


def test_text_mode_never_invokes_audio(tmp_path: Path) -> None:
    """C5: Text mode session runs active_review and roleplay without calling audio hardware."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            for mode in ("active_review", "roleplay"):
                start_res = await session.call_tool(
                    "start_session",
                    {"deck_slug": "conversational", "mode": mode, "input_mode": "text"},
                )
                assert not start_res.is_error
                start_data = _parse_tool_json(start_res)
                assert start_data["effective_input_mode"] == "text"
                session_id = start_data["session_id"]

                due_res = await session.call_tool(
                    "get_due_cards",
                    {"deck_slug": "conversational", "limit": 2},
                )
                assert not due_res.is_error
                due_data = _parse_tool_json(due_res)
                assert len(due_data["cards"]) >= 1
                card_id = due_data["cards"][0]["card_id"]

                rev_res = await session.call_tool(
                    "submit_review",
                    {
                        "card_id": card_id,
                        "rating": 3,
                        "user_response_raw": "How have you been lately?",
                        "input_mode": "text",
                        "session_id": session_id,
                    },
                )
                assert not rev_res.is_error
                rev_data = _parse_tool_json(rev_res)
                assert rev_data["card_id"] == card_id
                assert rev_data["rating"] == 3
                assert rev_data["next_due_at"]

                if mode == "roleplay":
                    turn_res = await session.call_tool(
                        "log_turn_and_errors",
                        {
                            "session_id": session_id,
                            "speaker": "user",
                            "raw_transcript": "How have you been lately?",
                            "input_mode": "text",
                            "errors": [],
                        },
                    )
                    assert not turn_res.is_error

                end_res = await session.call_tool(
                    "end_session",
                    {"session_id": session_id, "summary_notes": f"Text {mode} completed"},
                )
                assert not end_res.is_error
                end_data = _parse_tool_json(end_res)
                assert end_data["status"] == "ended"
                assert end_data["cards_reviewed"] == 1

    asyncio.run(_run())


def test_add_card_and_end_session_idempotency(tmp_path: Path) -> None:
    """add_card deduplicates and end_session is idempotent over stdio."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            add_1 = await session.call_tool(
                "add_card",
                {
                    "deck_slug": "tech-meetings",
                    "front_prompt": "How do you escalate a P0 incident?",
                    "back_reference": "Page the on-call lead immediately.",
                    "card_type": "tech_scenario",
                },
            )
            assert not add_1.is_error
            data_1 = _parse_tool_json(add_1)
            assert data_1["created"] is True

            add_2 = await session.call_tool(
                "add_card",
                {
                    "deck_slug": "tech-meetings",
                    "front_prompt": "  how do you escalate a p0 incident? ",
                    "back_reference": "Page the on-call lead immediately.",
                    "card_type": "tech_scenario",
                },
            )
            assert not add_2.is_error
            data_2 = _parse_tool_json(add_2)
            assert data_2["created"] is False
            assert data_2["card_id"] == data_1["card_id"]

            start_res = await session.call_tool("start_session", {"input_mode": "text"})
            session_id = _parse_tool_json(start_res)["session_id"]

            end_1 = await session.call_tool("end_session", {"session_id": session_id})
            end_2 = await session.call_tool("end_session", {"session_id": session_id})
            assert _parse_tool_json(end_1)["ended_at"] == _parse_tool_json(end_2)["ended_at"]

    asyncio.run(_run())


def test_structured_error_envelope_and_stdout_hygiene(tmp_path: Path) -> None:
    """Invalid rating/card returns isError=true JSON envelope and stdout is strictly JSON-RPC."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            bad_rating = await session.call_tool(
                "submit_review",
                {
                    "card_id": 1,
                    "rating": 5,
                    "user_response_raw": "test",
                    "input_mode": "text",
                },
            )
            assert bad_rating.is_error is True
            err_1 = _parse_tool_json(bad_rating)
            assert err_1["error_code"] == "INVALID_RATING"
            assert err_1["recoverable"] is True

            missing_card = await session.call_tool(
                "submit_review",
                {
                    "card_id": 999999,
                    "rating": 3,
                    "user_response_raw": "test",
                    "input_mode": "text",
                },
            )
            assert missing_card.is_error is True
            err_2 = _parse_tool_json(missing_card)
            assert err_2["error_code"] == "CARD_NOT_FOUND"
            assert err_2["recoverable"] is True

    asyncio.run(_run())

    # Raw subprocess check: zero non-JSON-RPC bytes on stdout
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "hygiene.db")
    env["SPARKSPEAK_BACKUPS_DIR"] = str(tmp_path / "backups")
    env["SPARKSPEAK_MODELS_DIR"] = str(tmp_path / "models")
    init_req = (
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "1.0"},
                },
            }
        )
        + "\n"
    )
    proc = subprocess.run(
        [sys.executable, "-m", "sparkspeak.mcp.server"],
        input=init_req,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    stdout_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert stdout_lines, "Expected JSON-RPC response on stdout"
    for line in stdout_lines:
        parsed = json.loads(line)
        assert parsed.get("jsonrpc") == "2.0"
