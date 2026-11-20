"""Application service for study session lifecycle and mode switching."""

from dataclasses import dataclass

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import (
    Deck,
    InputMode,
    SessionMode,
    SessionSummary,
    StudySession,
)
from sparkspeak.infrastructure.db.repositories import SQLiteRepository


@dataclass(frozen=True, slots=True)
class StartSessionResult:
    session_id: str
    deck: Deck | None
    mode: SessionMode
    effective_input_mode: InputMode
    audio_status: dict[str, bool]
    due_reviews: int
    new_cards: int


class SessionService:
    """Orchestrates start_session, mode fallback switching, and idempotent end_session."""

    def __init__(self, repo: SQLiteRepository) -> None:
        self._repo = repo

    def start_session(
        self,
        *,
        deck_slug: str | None = None,
        mode: SessionMode = "mixed",
        input_mode: InputMode = "voice",
        audio_status: dict[str, bool] | None = None,
    ) -> StartSessionResult:
        if mode not in ("active_review", "roleplay", "mixed"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid session mode {mode!r}.",
                details={"field": "mode", "value": mode},
            )
        if input_mode not in ("voice", "text"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid input_mode {input_mode!r}.",
                details={"field": "input_mode", "value": input_mode},
            )

        deck: Deck | None = None
        if deck_slug is not None:
            deck = self._repo.get_deck_by_slug(deck_slug)
            if deck is None:
                raise SparkSpeakError(
                    error_code=ErrorCode.DECK_NOT_FOUND,
                    message=f"Deck {deck_slug!r} was not found.",
                    details={"deck_slug": deck_slug},
                )

        default_audio = audio_status or {
            "tts_ready": False,
            "stt_ready": False,
            "pipewire_input": False,
            "pipewire_output": False,
        }
        session = self._repo.create_session(
            mode=mode,
            input_mode_default=input_mode,
            deck_id=deck.id if deck is not None else None,
        )
        due_reviews, new_cards = self._repo.count_due_summary(deck_slug=deck_slug)

        return StartSessionResult(
            session_id=session.id,
            deck=deck,
            mode=mode,
            effective_input_mode=input_mode,
            audio_status=default_audio,
            due_reviews=due_reviews,
            new_cards=new_cards,
        )

    def switch_input_mode(self, session_id: str, input_mode: InputMode) -> StudySession:
        if input_mode not in ("voice", "text"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid input_mode {input_mode!r}.",
                details={"field": "input_mode", "value": input_mode},
            )
        return self._repo.update_session_input_mode(session_id, input_mode)

    def end_session(
        self,
        session_id: str,
        *,
        summary_notes: str | None = None,
    ) -> SessionSummary:
        ended = self._repo.end_session(session_id, summary_notes=summary_notes)
        return SessionSummary(
            session_id=ended.id,
            status=ended.status,
            started_at=ended.started_at,
            ended_at=ended.ended_at,
            cards_reviewed=ended.cards_reviewed,
            errors_extracted=ended.errors_extracted,
            summary_notes=ended.summary_notes,
        )
