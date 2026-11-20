"""Integration tests for automatic post-session error-to-card promotion."""

import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from sparkspeak.application.session_service import SessionService
from sparkspeak.config import load_config
from sparkspeak.domain.models import ErrorLogInput
from sparkspeak.infrastructure.db.migrator import run_migrations
from sparkspeak.infrastructure.db.repositories import SQLiteRepository

_COUNT_AUTO_EXTRACTED_SQL = "SELECT COUNT(*) FROM cards WHERE source_type = 'auto_extracted'"


def _setup(tmp_path: Path) -> tuple[SessionService, SQLiteRepository, Path]:
    cfg = load_config(project_root=tmp_path)
    run_migrations(cfg.db_path, cfg.backups_dir)
    repo = SQLiteRepository(cfg.db_path)
    return SessionService(repo), repo, cfg.db_path


def _server_params(tmp_path: Path) -> StdioServerParameters:
    env = os.environ.copy()
    env["SPARKSPEAK_DB_PATH"] = str(tmp_path / "post_session_test.db")
    env["SPARKSPEAK_BACKUPS_DIR"] = str(tmp_path / "backups")
    env["SPARKSPEAK_MODELS_DIR"] = str(tmp_path / "models")
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "sparkspeak.mcp.server"],
        env=env,
    )


def _count_auto_extracted(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        count: int = conn.execute(
            _COUNT_AUTO_EXTRACTED_SQL
        ).fetchone()[0]
    return count


def _parse_json(result: Any) -> dict[str, Any]:
    assert result.content
    parsed: dict[str, Any] = json.loads(result.content[0].text)
    return parsed


def test_end_session_promotes_errors_once(tmp_path: Path) -> None:
    """C14: end_session(promote_errors=True) creates 1 auto_extracted card and is idempotent."""
    svc, repo, db_path = _setup(tmp_path)
    started = svc.start_session(deck_slug="phrasal-verbs", mode="roleplay", input_mode="text")

    # Simulate a 4-turn roleplay with a repeated preposition/phrasal error.
    repeated_err = ErrorLogInput(
        category="grammar",
        utterance_raw="I depend of the cache",
        correction="I depend on the cache",
        explanation="Use 'depend on', not 'depend of'.",
    )
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="tutor",
        raw_transcript="How does your service handle cache misses?",
        input_mode="text",
    )
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="I depend of the cache for fast reads.",
        input_mode="text",
        errors=[repeated_err],
    )
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="tutor",
        raw_transcript="Got it, you depend on the cache. What about fallback?",
        input_mode="text",
    )
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="Yes, I depend of the cache even on retries.",
        input_mode="text",
        errors=[repeated_err],
    )

    summary_1 = svc.end_session(
        started.session_id,
        promote_errors=True,
        summary_notes="Good roleplay; watch 'depend on'.",
    )
    assert summary_1.status == "ended"
    assert summary_1.ended_at is not None
    assert summary_1.errors_extracted == 1
    assert len(summary_1.promoted_cards) == 1
    assert summary_1.promoted_cards[0].created is True
    assert len(summary_1.recurring_errors) == 1
    assert summary_1.recurring_errors[0].occurrence_count == 2

    with sqlite3.connect(db_path) as conn:
        auto_cards = conn.execute(
            "SELECT id, source_type, card_type FROM cards WHERE source_type = 'auto_extracted'"
        ).fetchall()
        err_row = conn.execute(
            "SELECT occurrence_count, promoted_card_id FROM error_logs"
        ).fetchone()
        sess_row = conn.execute(
            "SELECT status, errors_extracted FROM study_sessions WHERE id = ?",
            (started.session_id,),
        ).fetchone()

    assert len(auto_cards) == 1
    assert auto_cards[0][1] == "auto_extracted"
    assert auto_cards[0][2] == "grammar_fix"
    assert err_row == (2, auto_cards[0][0])
    assert sess_row == ("ended", 1)

    # Idempotent replay on already-ended session
    summary_2 = svc.end_session(started.session_id, promote_errors=True)
    assert summary_2.ended_at == summary_1.ended_at
    assert summary_2.errors_extracted == 1

    assert _count_auto_extracted(db_path) == 1


def test_end_session_without_promotion_leaves_errors_unpromoted(tmp_path: Path) -> None:
    """end_session(promote_errors=False) closes session without creating cards."""
    svc, _repo, db_path = _setup(tmp_path)
    started = svc.start_session(deck_slug="conversational", mode="roleplay", input_mode="text")
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="Yesterday I goed home",
        input_mode="text",
        errors=[
            ErrorLogInput(
                category="grammar",
                utterance_raw="goed",
                correction="went",
                explanation="Irregular past tense of 'go' is 'went'.",
            )
        ],
    )

    summary = svc.end_session(started.session_id, promote_errors=False)
    assert summary.status == "ended"
    assert summary.errors_extracted == 0
    assert summary.promoted_cards == []

    with sqlite3.connect(db_path) as conn:
        promoted_id = conn.execute("SELECT promoted_card_id FROM error_logs").fetchone()[0]
    assert _count_auto_extracted(db_path) == 0
    assert promoted_id is None


def test_end_session_deduplicates_against_existing_card(tmp_path: Path) -> None:
    """If an error's prompt already exists in cards, no duplicate card is created."""
    svc, repo, db_path = _setup(tmp_path)
    started = svc.start_session(deck_slug="tech-meetings", mode="roleplay", input_mode="text")
    repo.add_card(
        deck_slug="tech-meetings",
        front_prompt="Fix vocabulary: 'actualy'",
        back_reference="actually",
        card_type="vocab",
        source_type="manual",
    )
    svc.log_turn_and_errors(
        session_id=started.session_id,
        speaker="user",
        raw_transcript="Actualy we can ship it",
        input_mode="text",
        errors=[
            ErrorLogInput(
                category="vocabulary",
                utterance_raw="actualy",
                correction="actually",
                explanation="Spelling/usage.",
            )
        ],
    )

    summary = svc.end_session(started.session_id, promote_errors=True)
    assert summary.errors_extracted == 0
    assert summary.promoted_cards == []
    assert _count_auto_extracted(db_path) == 0


def test_mcp_stdio_end_session_promotes_errors(tmp_path: Path) -> None:
    """end_session(promote_errors=True) over MCP stdio returns promoted_cards."""

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

            for _ in range(2):
                await session.call_tool(
                    "log_turn_and_errors",
                    {
                        "session_id": session_id,
                        "speaker": "user",
                        "raw_transcript": "We need to scale up the latency",
                        "input_mode": "text",
                        "errors": [
                            {
                                "category": "register",
                                "utterance_raw": "scale up the latency",
                                "correction": "reduce latency / scale up throughput",
                                "explanation": "Latency is reduced; throughput is scaled up.",
                            }
                        ],
                    },
                )

            end_res = await session.call_tool(
                "end_session",
                {"session_id": session_id, "promote_errors": True},
            )
            assert end_res.is_error is False
            end_data = _parse_json(end_res)
            assert end_data["status"] == "ended"
            assert end_data["errors_extracted"] == 1
            assert len(end_data["promoted_cards"]) == 1
            assert len(end_data["recurring_errors"]) == 1
            assert end_data["recurring_errors"][0]["occurrence_count"] == 2

    asyncio.run(_run())
