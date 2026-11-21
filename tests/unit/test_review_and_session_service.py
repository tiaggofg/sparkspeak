"""Unit tests for ReviewService and SessionService."""

from pathlib import Path

import pytest

from sparkspeak.application.review_service import ReviewService
from sparkspeak.application.session_service import SessionService
from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.srs_engine import SRSEngine
from sparkspeak.infrastructure.db.migrator import run_migrations
from sparkspeak.infrastructure.db.repositories import SQLiteRepository


def _make_services(tmp_path: Path) -> tuple[ReviewService, SessionService, SQLiteRepository]:
    db_path = tmp_path / "sparkspeak.db"
    backups_dir = tmp_path / "backups"
    run_migrations(db_path=db_path, backups_dir=backups_dir)
    repo = SQLiteRepository(db_path=db_path)
    return ReviewService(repo=repo, srs_engine=SRSEngine()), SessionService(repo=repo), repo


@pytest.mark.parametrize("bad_limit", [0, -5, 51])
def test_get_due_cards_rejects_out_of_bounds_limit(tmp_path: Path, bad_limit: int) -> None:
    review_svc, _, _ = _make_services(tmp_path)

    with pytest.raises(SparkSpeakError) as exc_info:
        review_svc.get_due_cards(limit=bad_limit)

    assert exc_info.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_add_card_rejects_overlong_front_or_back(tmp_path: Path) -> None:
    review_svc, _, _ = _make_services(tmp_path)

    with pytest.raises(SparkSpeakError) as exc_front:
        review_svc.add_card(
            deck_slug="tech-meetings",
            front_prompt="x" * 1001,
            back_reference="valid back",
            card_type="tech_scenario",
        )
    assert exc_front.value.error_code == ErrorCode.INVALID_ARGUMENT

    with pytest.raises(SparkSpeakError) as exc_back:
        review_svc.add_card(
            deck_slug="tech-meetings",
            front_prompt="valid front",
            back_reference="y" * 1001,
            card_type="tech_scenario",
        )
    assert exc_back.value.error_code == ErrorCode.INVALID_ARGUMENT


def test_submit_review_rejects_invalid_rating_and_unknown_card(tmp_path: Path) -> None:
    review_svc, _, _ = _make_services(tmp_path)

    with pytest.raises(SparkSpeakError) as exc_rating:
        review_svc.submit_review(
            card_id=1,
            rating=5,
            user_response_raw="hello",
            input_mode="text",
        )
    assert exc_rating.value.error_code == ErrorCode.INVALID_RATING

    with pytest.raises(SparkSpeakError) as exc_card:
        review_svc.submit_review(
            card_id=99999,
            rating=3,
            user_response_raw="hello",
            input_mode="text",
        )
    assert exc_card.value.error_code == ErrorCode.CARD_NOT_FOUND


def test_submit_review_updates_schedule_and_replays_idempotently(tmp_path: Path) -> None:
    review_svc, session_svc, _ = _make_services(tmp_path)
    started = session_svc.start_session(
        deck_slug="phrasal-verbs", mode="active_review", input_mode="text"
    )
    due = review_svc.get_due_cards(deck_slug="phrasal-verbs", limit=5)
    card_id = due.cards[0].id

    first = review_svc.submit_review(
        card_id=card_id,
        rating=3,
        user_response_raw="We had to put off the release.",
        input_mode="text",
        session_id=started.session_id,
        idempotency_key="idem-123",
    )
    replay = review_svc.submit_review(
        card_id=card_id,
        rating=3,
        user_response_raw="We had to put off the release.",
        input_mode="text",
        session_id=started.session_id,
        idempotency_key="idem-123",
    )

    assert first.idempotent_replay is False
    assert first.reps == 1
    assert replay.idempotent_replay is True
    assert replay.reps == 1


def test_start_session_unknown_deck_raises_deck_not_found(tmp_path: Path) -> None:
    _, session_svc, _ = _make_services(tmp_path)

    with pytest.raises(SparkSpeakError) as exc_info:
        session_svc.start_session(deck_slug="missing-deck")

    assert exc_info.value.error_code == ErrorCode.DECK_NOT_FOUND


def test_end_session_is_idempotent_and_preserves_ended_at(tmp_path: Path) -> None:
    _, session_svc, _ = _make_services(tmp_path)
    started = session_svc.start_session(deck_slug="conversational", input_mode="text")

    first = session_svc.end_session(started.session_id, summary_notes="Good session")
    second = session_svc.end_session(started.session_id, summary_notes="Ignored")

    assert first.status == "ended"
    assert first.ended_at is not None
    assert second.ended_at == first.ended_at
    assert second.summary_notes == "Good session"


def test_voice_to_text_switch_preserves_session(tmp_path: Path) -> None:
    review_svc, session_svc, repo = _make_services(tmp_path)
    started = session_svc.start_session(
        deck_slug="phrasal-verbs", mode="mixed", input_mode="voice"
    )
    due = review_svc.get_due_cards(deck_slug="phrasal-verbs", limit=2)
    review_svc.submit_review(
        card_id=due.cards[0].id,
        rating=3,
        user_response_raw="put off",
        input_mode="voice",
        session_id=started.session_id,
    )

    switched = session_svc.switch_input_mode(started.session_id, "text")
    persisted = repo.get_session(started.session_id)

    assert switched.id == started.session_id
    assert switched.status == "active"
    assert switched.input_mode_default == "text"
    assert switched.cards_reviewed == 1
    assert persisted is not None
    assert persisted.input_mode_default == "text"
    assert persisted.cards_reviewed == 1


def test_start_session_exposes_mic_available_without_audio_status(tmp_path: Path) -> None:
    _, session_svc, _ = _make_services(tmp_path)
    started = session_svc.start_session(
        deck_slug="tech-meetings",
        mode="mixed",
        input_mode="voice",
        mic_available=True,
    )
    assert started.mic_available is True
    assert not hasattr(started, "audio_status")


def test_log_mistake_records_turn_and_deduplicates_fingerprint(tmp_path: Path) -> None:
    _, session_svc, _ = _make_services(tmp_path)
    started = session_svc.start_session(deck_slug="tech-meetings", input_mode="voice")

    first = session_svc.log_mistake(
        session_id=started.session_id,
        utterance_raw="I work-ed (/wɜːrkɪd/) on the deploy",
        correction="I worked (/wɜːrkt/) on the deployment",
        category="pronunciation_asr",
        explanation="Past tense -ed after /k/ sounds like /t/, not /ɪd/.",
        audio_duration_ms=2100,
    )
    second = session_svc.log_mistake(
        session_id=started.session_id,
        utterance_raw="We work-ed on the release",
        correction="  i worked (/wɜːrkt/) on the deployment ",
        category="pronunciation_asr",
    )

    assert first.session_id == started.session_id
    assert first.turn_index == 1
    assert first.category == "pronunciation_asr"
    assert first.occurrence_count == 1
    assert first.promoted_card_id is None
    assert second.turn_index == 2
    assert second.error_id == first.error_id
    assert second.occurrence_count == 2
