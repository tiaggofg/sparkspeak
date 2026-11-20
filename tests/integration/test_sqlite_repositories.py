"""Integration tests for SQLite repositories."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import ErrorLogInput
from sparkspeak.domain.srs_engine import SRSEngine
from sparkspeak.infrastructure.db.connection import open_connection
from sparkspeak.infrastructure.db.migrator import run_migrations
from sparkspeak.infrastructure.db.repositories import SQLiteRepository


def _setup_repo(tmp_path: Path) -> SQLiteRepository:
    db_path = tmp_path / "sparkspeak.db"
    backups_dir = tmp_path / "backups"
    run_migrations(db_path=db_path, backups_dir=backups_dir)
    return SQLiteRepository(db_path=db_path)


def test_get_due_cards_orders_due_before_new(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)
    now_iso = "2026-11-20T18:00:00.000Z"

    c1 = repo.add_card(
        deck_slug="phrasal-verbs",
        front_prompt="Card due earlier",
        back_reference="bring up",
        card_type="phrasal_verb",
    )
    c2 = repo.add_card(
        deck_slug="phrasal-verbs",
        front_prompt="Card due later",
        back_reference="call off",
        card_type="phrasal_verb",
    )
    # Mark both as reviewed (is_new = 0) with explicit due_at ordering
    with open_connection(repo.db_path) as conn:
        conn.execute(
            "UPDATE cards SET is_new = 0, due_at = '2026-11-20T10:00:00.000Z' WHERE id = ?",
            (c2.card_id,),
        )
        conn.execute(
            "UPDATE cards SET is_new = 0, due_at = '2026-11-20T14:00:00.000Z' WHERE id = ?",
            (c1.card_id,),
        )

    result = repo.get_due_cards(
        deck_slug="phrasal-verbs",
        limit=10,
        new_cards_limit=2,
        include_new=True,
        now_iso=now_iso,
    )

    assert len(result.cards) == 4  # 2 due reviews + 2 new cards
    assert result.cards[0].id == c2.card_id
    assert result.cards[1].id == c1.card_id
    assert result.cards[0].is_new is False
    assert result.cards[1].is_new is False
    assert result.cards[2].is_new is True
    assert result.cards[3].is_new is True
    assert result.queue_stats.total_due_reviews == 2
    assert result.queue_stats.returned == 4


def test_submit_review_updates_fsrs_and_logs(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)
    engine = SRSEngine(desired_retention=0.90)
    session = repo.create_session(mode="active_review", input_mode_default="text")
    due = repo.get_due_cards(deck_slug="phrasal-verbs", limit=1)
    card = due.cards[0]

    now = datetime(2026, 11, 20, 18, 0, 0, tzinfo=UTC)
    scheduled = engine.schedule_review(card, rating=3, now=now)

    saved = repo.apply_review(
        card_id=card.id,
        result=scheduled,
        user_response_raw="We should put off the meeting.",
        input_mode="text",
        session_id=session.id,
        duration_ms=1200,
        idempotency_key="rev-key-1",
    )

    assert saved.idempotent_replay is False
    updated_card = repo.get_card_by_id(card.id)
    assert updated_card is not None
    assert updated_card.is_new is False
    assert updated_card.reps == 1
    assert updated_card.due_at == scheduled.next_due_at
    assert updated_card.stability == pytest.approx(scheduled.stability)

    updated_session = repo.get_session(session.id)
    assert updated_session is not None
    assert updated_session.cards_reviewed == 1

    # Idempotent replay must not double-increment reps or review_logs
    replayed = repo.apply_review(
        card_id=card.id,
        result=scheduled,
        user_response_raw="We should put off the meeting.",
        input_mode="text",
        session_id=session.id,
        idempotency_key="rev-key-1",
    )
    assert replayed.idempotent_replay is True
    assert repo.get_card_by_id(card.id).reps == 1  # type: ignore[union-attr]
    assert repo.get_session(session.id).cards_reviewed == 1  # type: ignore[union-attr]


def test_add_card_deduplicates_normalized_front(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)

    first = repo.add_card(
        deck_slug="tech-meetings",
        front_prompt="Explain why the deploy rolled back!",
        back_reference="The deployment rolled back due to failing health checks.",
        card_type="tech_scenario",
    )
    second = repo.add_card(
        deck_slug="tech-meetings",
        front_prompt="  explain   why the deploy rolled back  ",
        back_reference="Duplicate prompt should not create a new card.",
        card_type="tech_scenario",
    )

    assert first.created is True
    assert second.created is False
    assert second.card_id == first.card_id


def test_get_due_cards_unknown_deck_raises_deck_not_found(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)

    with pytest.raises(SparkSpeakError) as exc_info:
        repo.get_due_cards(deck_slug="non-existent-deck")

    assert exc_info.value.error_code == ErrorCode.DECK_NOT_FOUND


def test_end_session_is_idempotent(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)
    session = repo.create_session(mode="mixed", input_mode_default="text")

    ended_1 = repo.end_session(session.id, summary_notes="Great work")
    ended_2 = repo.end_session(session.id, summary_notes="Should not overwrite")

    assert ended_1.status == "ended"
    assert ended_1.ended_at is not None
    assert ended_2.ended_at == ended_1.ended_at
    assert ended_2.summary_notes == "Great work"


def test_log_turn_and_upsert_error_increments_occurrence_count(tmp_path: Path) -> None:
    repo = _setup_repo(tmp_path)
    deck = repo.get_deck_by_slug("tech-meetings")
    assert deck is not None
    session = repo.create_session(mode="roleplay", input_mode_default="voice", deck_id=deck.id)

    err = ErrorLogInput(
        category="grammar",
        utterance_raw="I goed to standup",
        correction="I went to standup",
        explanation="Irregular past tense of go is went.",
    )
    turn1, logs1 = repo.log_turn_and_errors(
        session_id=session.id,
        deck_id=deck.id,
        speaker="user",
        raw_transcript="I goed to standup",
        input_mode="voice",
        errors=[err],
    )
    turn2, logs2 = repo.log_turn_and_errors(
        session_id=session.id,
        deck_id=deck.id,
        speaker="user",
        raw_transcript="Yesterday I goed to standup again",
        input_mode="voice",
        errors=[err],
    )

    assert turn1 == 1
    assert turn2 == 2
    assert len(logs1) == 1
    assert logs1[0].occurrence_count == 1
    assert logs2[0].id == logs1[0].id
    assert logs2[0].occurrence_count == 2
