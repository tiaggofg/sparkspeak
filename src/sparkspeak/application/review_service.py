"""Application service for flashcard due queues, FSRS reviews, and card creation."""

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import (
    AddCardResult,
    CardType,
    DueCardsResult,
    InputMode,
    ReviewResult,
    SourceType,
)
from sparkspeak.domain.srs_engine import SRSEngine
from sparkspeak.infrastructure.db.repositories import SQLiteRepository


def _validate_non_empty_text(value: str, field_name: str, max_len: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise SparkSpeakError(
            error_code=ErrorCode.INVALID_ARGUMENT,
            message=f"{field_name} must not be empty.",
            details={"field": field_name},
        )
    if len(stripped) > max_len:
        raise SparkSpeakError(
            error_code=ErrorCode.INVALID_ARGUMENT,
            message=f"{field_name} must be at most {max_len} characters.",
            details={"field": field_name, "length": len(stripped), "max_length": max_len},
        )
    return stripped


class ReviewService:
    """Orchestrates input validation, FSRS scheduling, and SQLite review persistence."""

    def __init__(self, repo: SQLiteRepository, srs_engine: SRSEngine | None = None) -> None:
        self._repo = repo
        self._srs = srs_engine or SRSEngine(desired_retention=0.90)

    def get_due_cards(
        self,
        *,
        deck_slug: str | None = None,
        limit: int = 10,
        new_cards_limit: int = 3,
        include_new: bool = True,
    ) -> DueCardsResult:
        if isinstance(limit, bool) or limit < 1 or limit > 50:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"limit must be between 1 and 50; got {limit!r}.",
                details={"field": "limit", "value": limit},
            )
        if isinstance(new_cards_limit, bool) or new_cards_limit < 0 or new_cards_limit > 20:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"new_cards_limit must be between 0 and 20; got {new_cards_limit!r}.",
                details={"field": "new_cards_limit", "value": new_cards_limit},
            )
        return self._repo.get_due_cards(
            deck_slug=deck_slug,
            limit=limit,
            new_cards_limit=new_cards_limit,
            include_new=include_new,
        )

    def submit_review(
        self,
        *,
        card_id: int,
        rating: int,
        user_response_raw: str,
        input_mode: InputMode,
        session_id: str | None = None,
        duration_ms: int | None = None,
        idempotency_key: str | None = None,
    ) -> ReviewResult:
        SRSEngine.validate_rating(rating)
        response_text = _validate_non_empty_text(user_response_raw, "user_response_raw", 2000)

        if input_mode not in ("voice", "text"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"input_mode must be 'voice' or 'text'; got {input_mode!r}.",
                details={"field": "input_mode", "value": input_mode},
            )
        if duration_ms is not None and duration_ms < 0:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="duration_ms must be non-negative.",
                details={"field": "duration_ms", "value": duration_ms},
            )
        if idempotency_key is not None and len(idempotency_key) > 128:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="idempotency_key must be at most 128 characters.",
                details={"field": "idempotency_key"},
            )

        card = self._repo.get_card_by_id(card_id)
        if card is None:
            raise SparkSpeakError(
                error_code=ErrorCode.CARD_NOT_FOUND,
                message=f"Card {card_id} was not found.",
                details={"card_id": card_id},
            )

        scheduled = self._srs.schedule_review(card, rating=rating)
        return self._repo.apply_review(
            card_id=card_id,
            result=scheduled,
            user_response_raw=response_text,
            input_mode=input_mode,
            session_id=session_id,
            duration_ms=duration_ms,
            idempotency_key=idempotency_key,
        )

    def add_card(
        self,
        *,
        deck_slug: str,
        front_prompt: str,
        back_reference: str,
        card_type: CardType,
        context_example: str | None = None,
        source_type: SourceType = "manual",
    ) -> AddCardResult:
        front = _validate_non_empty_text(front_prompt, "front_prompt", 1000)
        back = _validate_non_empty_text(back_reference, "back_reference", 1000)
        if context_example is not None and len(context_example) > 1000:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="context_example must be at most 1000 characters.",
                details={"field": "context_example", "length": len(context_example)},
            )
        return self._repo.add_card(
            deck_slug=deck_slug,
            front_prompt=front,
            back_reference=back,
            card_type=card_type,
            context_example=context_example,
            source_type=source_type,
        )
