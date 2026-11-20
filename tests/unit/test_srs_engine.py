"""Unit tests for the deterministic FSRS engine wrapper."""

from datetime import UTC, datetime

import pytest

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import Card
from sparkspeak.domain.srs_engine import SRSEngine

_DEFAULT_DUE_ISO = "2026-11-20T12:00:00.000Z"
_UTC_OFFSET = "+00:00"


def _make_card(
    *,
    fsrs_state: int = 1,
    is_new: bool = True,
    stability: float | None = None,
    difficulty: float | None = None,
    step: int | None = 0,
    reps: int = 0,
    lapses: int = 0,
    due_at: str = _DEFAULT_DUE_ISO,
    last_review_at: str | None = None,
) -> Card:
    return Card(
        id=42,
        deck_id=1,
        deck_slug="phrasal-verbs",
        front_prompt="To delay or postpone",
        normalized_front="to delay or postpone",
        back_reference="put off",
        context_example="We had to put off the meeting.",
        card_type="phrasal_verb",
        source_type="seed",
        fsrs_state=fsrs_state,
        is_new=is_new,
        stability=stability,
        difficulty=difficulty,
        step=step,
        reps=reps,
        lapses=lapses,
        scheduled_days=0,
        due_at=due_at,
        last_review_at=last_review_at,
        suspended=False,
    )


def test_new_card_good_rating_computes_deterministic_schedule() -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card()
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    result_a = engine.schedule_review(card, rating=3, now=now)
    result_b = engine.schedule_review(card, rating=3, now=now)

    assert result_a == result_b
    assert result_a.card_id == 42
    assert result_a.rating == 3
    assert result_a.fsrs_state in {"learning", "review"}
    assert result_a.fsrs_state_int in {1, 2}
    assert result_a.stability is not None and result_a.stability > 0
    assert result_a.difficulty is not None and result_a.difficulty > 0
    assert result_a.reps == 1
    assert result_a.lapses == 0
    assert datetime.fromisoformat(result_a.next_due_at.replace("Z", _UTC_OFFSET)) > now


def test_new_card_easy_schedules_further_than_again() -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card()
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    again = engine.schedule_review(card, rating=1, now=now)
    easy = engine.schedule_review(card, rating=4, now=now)

    again_due = datetime.fromisoformat(again.next_due_at.replace("Z", _UTC_OFFSET))
    easy_due = datetime.fromisoformat(easy.next_due_at.replace("Z", _UTC_OFFSET))

    assert easy_due > again_due
    assert easy.scheduled_days >= again.scheduled_days
    assert easy.fsrs_state == "review"
    assert again.fsrs_state == "learning"


def test_review_card_again_transitions_to_relearning_and_increments_lapses() -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card(
        fsrs_state=2,
        is_new=False,
        stability=5.0,
        difficulty=5.0,
        step=None,
        reps=3,
        lapses=0,
        due_at=_DEFAULT_DUE_ISO,
        last_review_at="2026-11-15T12:00:00.000Z",
    )
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    result = engine.schedule_review(card, rating=1, now=now)

    assert result.fsrs_state == "relearning"
    assert result.fsrs_state_int == 3
    assert result.lapses == 1
    assert result.reps == 4


def test_review_card_good_remains_in_review_and_grows_interval() -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card(
        fsrs_state=2,
        is_new=False,
        stability=5.0,
        difficulty=5.0,
        step=None,
        reps=3,
        lapses=0,
        due_at=_DEFAULT_DUE_ISO,
        last_review_at="2026-11-15T12:00:00.000Z",
    )
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    result = engine.schedule_review(card, rating=3, now=now)

    assert result.fsrs_state == "review"
    assert result.fsrs_state_int == 2
    assert result.scheduled_days >= 1
    assert result.lapses == 0
    assert result.reps == 4


def test_relearning_card_good_graduates_back_to_review() -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card(
        fsrs_state=3,
        is_new=False,
        stability=1.5,
        difficulty=6.0,
        step=0,
        reps=4,
        lapses=1,
        due_at=_DEFAULT_DUE_ISO,
        last_review_at="2026-11-20T11:50:00.000Z",
    )
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC)

    result = engine.schedule_review(card, rating=3, now=now)

    assert result.fsrs_state == "review"
    assert result.fsrs_state_int == 2
    assert result.reps == 5
    assert result.lapses == 1


@pytest.mark.parametrize("bad_rating", [0, 5, -1, 99])
def test_invalid_rating_raises_without_mutation(bad_rating: int) -> None:
    engine = SRSEngine(desired_retention=0.90)
    card = _make_card(fsrs_state=2, is_new=False, stability=4.0, difficulty=5.0, reps=2)
    snapshot = (card.fsrs_state, card.stability, card.difficulty, card.reps, card.due_at)

    with pytest.raises(SparkSpeakError) as exc_info:
        engine.schedule_review(card, rating=bad_rating)

    assert exc_info.value.error_code == ErrorCode.INVALID_RATING
    assert (card.fsrs_state, card.stability, card.difficulty, card.reps, card.due_at) == snapshot
