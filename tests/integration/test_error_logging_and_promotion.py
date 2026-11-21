"""Integration tests for log_turn_and_errors and SHA-256 fingerprint deduplication."""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sparkspeak.application.session_service import SessionService
from sparkspeak.config import load_config
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import ErrorLogInput
from sparkspeak.infrastructure.db.migrator import run_migrations
from sparkspeak.infrastructure.db.repositories import SQLiteRepository


def _setup_service(tmp_path: Path) -> tuple[SessionService, SQLiteRepository, Path]:
    cfg = load_config(project_root=tmp_path)
    run_migrations(cfg.db_path, cfg.backups_dir)
    repo = SQLiteRepository(cfg.db_path)
    return SessionService(repo), repo, cfg.db_path


def _server_params(tmp_path: Path) -> StdioServerParameters:
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "err_log_test.db")
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


def test_repeated_error_increments_count(tmp_path: Path) -> None:
    """C12: Repeated mistakes increment error_logs.occurrence_count without duplicating rows."""
    svc, _repo, db_path = _setup_service(tmp_path)
    started = svc.start_session(deck_slug="phrasal-verbs", mode="roleplay", input_mode="voice")

    err_1 = ErrorLogInput(
        category="grammar",
        utterance_raw="We need put off the meeting for tomorrow",
        correction="We need to put off the meeting until tomorrow.",
        explanation="Use 'need to' + infinitive and 'until' for rescheduled deadlines.",
    )
    turn_1 = svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="We need put off the meeting for tomorrow",
        input_mode="voice",
        audio_duration_ms=3400,
        errors=[err_1],
    )
    assert turn_1.turn_index == 1
    assert len(turn_1.errors) == 1
    assert turn_1.errors[0].occurrence_count == 1

    # Same correction with different casing/whitespace -> same SHA-256 fingerprint_hash
    err_2 = ErrorLogInput(
        category="grammar",
        utterance_raw="I need put off the deploy for Friday",
        correction="  we need to put off the meeting   until tomorrow. ",
        explanation="Same preposition/infinitive pattern.",
    )
    turn_2 = svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="I need put off the deploy for Friday",
        input_mode="voice",
        audio_duration_ms=2900,
        errors=[err_2],
    )
    assert turn_2.turn_index == 2
    assert len(turn_2.errors) == 1
    assert turn_2.errors[0].id == turn_1.errors[0].id
    assert turn_2.errors[0].occurrence_count == 2
    assert turn_2.errors[0].fingerprint_hash == turn_1.errors[0].fingerprint_hash

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
        turns_count = conn.execute(
            "SELECT COUNT(*) FROM session_turns WHERE session_id = ?",
            (started.session_id,),
        ).fetchone()[0]
    assert count == 1
    assert turns_count == 2


def test_different_category_or_deck_creates_distinct_fingerprint(tmp_path: Path) -> None:
    """Distinct (deck_id, category, correction) produces distinct error_logs rows."""
    svc, _repo, db_path = _setup_service(tmp_path)
    s1 = svc.start_session(deck_slug="conversational", mode="roleplay", input_mode="text")
    s2 = svc.start_session(deck_slug="tech-meetings", mode="roleplay", input_mode="text")

    svc.log_turn_and_errors(
        session_id=s1.session_id,
        speaker="user",
        raw_transcript="I depend of the API",
        input_mode="text",
        errors=[
            ErrorLogInput(
                category="grammar",
                utterance_raw="depend of",
                correction="depend on",
                explanation="Use 'depend on'.",
            )
        ],
    )
    svc.log_turn_and_errors(
        session_id=s2.session_id,
        speaker="user",
        raw_transcript="It depend of latency",
        input_mode="text",
        errors=[
            ErrorLogInput(
                category="grammar",
                utterance_raw="depend of",
                correction="depend on",
                explanation="Use 'depend on'.",
            )
        ],
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT fingerprint_hash, occurrence_count FROM error_logs").fetchall()
    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] == 1 and rows[1][1] == 1


def test_log_turn_and_errors_validates_inputs(tmp_path: Path) -> None:
    """Invalid speaker, category, or unknown session_id raises structured SparkSpeakError."""
    svc, _repo, _db_path = _setup_service(tmp_path)
    started = svc.start_session(deck_slug="conversational", mode="roleplay", input_mode="text")

    with pytest.raises(SparkSpeakError) as exc_speaker:
        svc.log_turn_and_errors(
            session_id=started.session_id,
            speaker="bot",  # type: ignore[arg-type]
            raw_transcript="Hello",
            input_mode="text",
        )
    assert exc_speaker.value.error_code == ErrorCode.INVALID_ARGUMENT

    with pytest.raises(SparkSpeakError) as exc_session:
        svc.log_turn_and_errors(
            session_id="non-existent-session",
            speaker="user",
            raw_transcript="Hello",
            input_mode="text",
        )
    assert exc_session.value.error_code == ErrorCode.SESSION_NOT_FOUND


def test_mcp_stdio_log_turn_and_errors_roundtrip(tmp_path: Path) -> None:
    """log_turn_and_errors works end-to-end over MCP stdio and increments occurrence_count."""

    async def _run() -> None:
        params = _server_params(tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            start_res = await session.call_tool(
                "start_session",
                {"deck_slug": "tech-meetings", "mode": "roleplay", "input_mode": "text"},
            )
            session_id = _parse_json(start_res)["session_id"]

            err_payload = [
                {
                    "category": "phrasal_verb",
                    "utterance_raw": "We need to figure it in",
                    "correction": "We need to figure it out",
                    "explanation": "Use 'figure out' for solving a problem.",
                }
            ]
            r1 = await session.call_tool(
                "log_turn_and_errors",
                {
                    "session_id": session_id,
                    "speaker": "user",
                    "raw_transcript": "We need to figure it in before deploy",
                    "input_mode": "text",
                    "errors": err_payload,
                },
            )
            assert r1.is_error is False
            d1 = _parse_json(r1)
            assert d1["turn_index"] == 1
            assert d1["errors"][0]["occurrence_count"] == 1

            r2 = await session.call_tool(
                "log_turn_and_errors",
                {
                    "session_id": session_id,
                    "speaker": "user",
                    "raw_transcript": "Let us figure it in later",
                    "input_mode": "text",
                    "errors": err_payload,
                },
            )
            assert r2.is_error is False
            d2 = _parse_json(r2)
            assert d2["turn_index"] == 2
            assert d2["errors"][0]["occurrence_count"] == 2

    asyncio.run(_run())


def test_log_mistake_upserts_and_increments_occurrence_count(tmp_path: Path) -> None:
    """C7: log_mistake deduplicates via SHA-256 fingerprint and end_session promotes it."""
    svc, _repo, db_path = _setup_service(tmp_path)
    started = svc.start_session(deck_slug="tech-meetings", mode="roleplay", input_mode="voice")

    first = svc.log_mistake(
        session_id=started.session_id,
        utterance_raw="I work-ed (/wɜːrkɪd/) on the deploy",
        correction="I worked (/wɜːrkt/) on the deployment",
        category="pronunciation_asr",
        explanation="Past tense -ed after /k/ sounds like /t/.",
        audio_duration_ms=2500,
    )
    second = svc.log_mistake(
        session_id=started.session_id,
        utterance_raw="She work-ed on the hotfix",
        correction="  i worked (/wɜːrkt/) on the deployment ",
        category="pronunciation_asr",
        explanation="Same -ed ending rule.",
        audio_duration_ms=2100,
    )

    assert first.turn_index == 1
    assert first.occurrence_count == 1
    assert second.turn_index == 2
    assert second.error_id == first.error_id
    assert second.occurrence_count == 2

    summary = svc.end_session(started.session_id, promote_errors=True)
    assert summary.errors_extracted == 1
    assert len(summary.promoted_cards) == 1
    promoted_card_id = summary.promoted_cards[0].card_id

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
        card_type = conn.execute(
            "SELECT card_type FROM cards WHERE id = ?",
            (promoted_card_id,),
        ).fetchone()[0]
    assert count == 1
    assert card_type == "pronunciation"
