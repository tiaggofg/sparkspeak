"""Deterministic FSRS scheduling wrapper using py-fsrs."""

from datetime import UTC, datetime

from fsrs import Card as FSRSCard
from fsrs import Rating, Scheduler, State

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import Card, ReviewResult

_STATE_NAMES: dict[int, str] = {
    int(State.Learning): "learning",
    int(State.Review): "review",
    int(State.Relearning): "relearning",
}


def parse_utc_iso(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp string into an aware UTC datetime."""
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_utc_iso(dt: datetime) -> str:
    """Format an aware datetime as ISO-8601 UTC with millisecond precision."""
    utc_dt = dt.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_dt.microsecond // 1000:03d}Z"


class SRSEngine:
    """Pure domain wrapper around fsrs.Scheduler."""

    def __init__(self, desired_retention: float = 0.90) -> None:
        self._scheduler = Scheduler(desired_retention=desired_retention)

    @staticmethod
    def validate_rating(rating: int) -> Rating:
        """Validate that rating is an integer in {1, 2, 3, 4}."""
        if isinstance(rating, bool) or rating not in (1, 2, 3, 4):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_RATING,
                message=(
                    "Rating must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy); "
                    f"got {rating!r}."
                ),
                recoverable=True,
                details={"rating": rating},
            )
        return Rating(rating)

    def schedule_review(
        self,
        card: Card,
        rating: int,
        now: datetime | None = None,
    ) -> ReviewResult:
        """Compute next FSRS state and due date without mutating the input Card."""
        fsrs_rating = self.validate_rating(rating)
        review_dt = (now or datetime.now(UTC)).astimezone(UTC)

        fsrs_card = FSRSCard(
            card_id=card.id,
            state=State(card.fsrs_state),
            step=card.step,
            stability=card.stability,
            difficulty=card.difficulty,
            due=parse_utc_iso(card.due_at),
            last_review=parse_utc_iso(card.last_review_at) if card.last_review_at else None,
        )

        updated_card, _ = self._scheduler.review_card(
            fsrs_card,
            fsrs_rating,
            review_datetime=review_dt,
        )

        next_state_int = int(updated_card.state)
        scheduled_days = max(0, (updated_card.due - review_dt).days)
        lapsed = fsrs_rating == Rating.Again and State(card.fsrs_state) == State.Review

        return ReviewResult(
            card_id=card.id,
            rating=int(fsrs_rating),
            fsrs_state=_STATE_NAMES[next_state_int],
            fsrs_state_int=next_state_int,
            scheduled_days=scheduled_days,
            next_due_at=format_utc_iso(updated_card.due),
            stability=updated_card.stability,
            difficulty=updated_card.difficulty,
            step=updated_card.step,
            reps=card.reps + 1,
            lapses=card.lapses + (1 if lapsed else 0),
            idempotent_replay=False,
        )
