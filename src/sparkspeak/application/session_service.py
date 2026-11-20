"""Application service for study session lifecycle and mode switching."""

from dataclasses import dataclass

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import (
    Deck,
    ErrorCategory,
    ErrorLogInput,
    ErrorLogRecord,
    InputMode,
    SessionMode,
    SessionSummary,
    Speaker,
    StudySession,
)
from sparkspeak.infrastructure.db.repositories import SQLiteRepository

_VALID_ERROR_CATEGORIES: tuple[ErrorCategory, ...] = (
    "grammar",
    "vocabulary",
    "phrasal_verb",
    "pronunciation_asr",
    "register",
)


@dataclass(frozen=True, slots=True)
class StartSessionResult:
    session_id: str
    deck: Deck | None
    mode: SessionMode
    effective_input_mode: InputMode
    audio_status: dict[str, bool]
    due_reviews: int
    new_cards: int


@dataclass(frozen=True, slots=True)
class LogTurnResult:
    session_id: str
    turn_index: int
    errors: list[ErrorLogRecord]


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

    def log_turn_and_errors(
        self,
        *,
        session_id: str,
        speaker: Speaker,
        raw_transcript: str,
        input_mode: InputMode,
        deck_slug: str | None = None,
        audio_duration_ms: int | None = None,
        errors: list[ErrorLogInput] | None = None,
    ) -> LogTurnResult:
        if speaker not in ("tutor", "user"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid speaker {speaker!r}; expected 'tutor' or 'user'.",
                details={"field": "speaker", "value": speaker},
            )
        if input_mode not in ("voice", "text"):
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid input_mode {input_mode!r}.",
                details={"field": "input_mode", "value": input_mode},
            )
        transcript = raw_transcript.strip()
        if not transcript:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="raw_transcript must not be empty.",
                details={"field": "raw_transcript"},
            )
        if audio_duration_ms is not None and audio_duration_ms < 0:
            raise SparkSpeakError(
                error_code=ErrorCode.INVALID_ARGUMENT,
                message="audio_duration_ms must be non-negative.",
                details={"field": "audio_duration_ms", "value": audio_duration_ms},
            )

        session = self._repo.get_session(session_id)
        if session is None:
            raise SparkSpeakError(
                error_code=ErrorCode.SESSION_NOT_FOUND,
                message=f"Session {session_id!r} was not found.",
                details={"session_id": session_id},
            )

        deck_id = self._resolve_turn_deck_id(session, deck_slug)
        validated_errors = self._validate_error_items(errors or [])
        turn_index, recorded = self._repo.log_turn_and_errors(
            session_id=session_id,
            deck_id=deck_id,
            speaker=speaker,
            raw_transcript=transcript,
            input_mode=input_mode,
            audio_duration_ms=audio_duration_ms,
            errors=validated_errors,
        )
        return LogTurnResult(session_id=session_id, turn_index=turn_index, errors=recorded)

    def _resolve_turn_deck_id(self, session: StudySession, deck_slug: str | None) -> int:
        if deck_slug is not None:
            deck = self._repo.get_deck_by_slug(deck_slug)
            if deck is None:
                raise SparkSpeakError(
                    error_code=ErrorCode.DECK_NOT_FOUND,
                    message=f"Deck {deck_slug!r} was not found.",
                    details={"deck_slug": deck_slug},
                )
            return deck.id
        if session.deck_id is not None:
            return session.deck_id
        fallback_deck = self._repo.get_deck_by_slug("conversational")
        if fallback_deck is None:
            raise SparkSpeakError(
                error_code=ErrorCode.DECK_NOT_FOUND,
                message="No default deck found for error logging.",
            )
        return fallback_deck.id

    @staticmethod
    def _validate_error_items(errors: list[ErrorLogInput]) -> list[ErrorLogInput]:
        validated: list[ErrorLogInput] = []
        for item in errors:
            if item.category not in _VALID_ERROR_CATEGORIES:
                raise SparkSpeakError(
                    error_code=ErrorCode.INVALID_ARGUMENT,
                    message=f"Invalid error category {item.category!r}.",
                    details={"field": "category", "value": item.category},
                )
            if not item.utterance_raw.strip() or not item.correction.strip():
                raise SparkSpeakError(
                    error_code=ErrorCode.INVALID_ARGUMENT,
                    message="Error item utterance_raw and correction must not be empty.",
                    details={"field": "errors"},
                )
            validated.append(item)
        return validated

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
