"""Domain DTOs and entities for SparkSpeak."""

from dataclasses import dataclass, field
from typing import Literal

CardType = Literal[
    "vocab",
    "phrasal_verb",
    "grammar_fix",
    "pronunciation",
    "tech_scenario",
]
SourceType = Literal["seed", "manual", "auto_extracted"]
SessionMode = Literal["active_review", "roleplay", "mixed"]
InputMode = Literal["voice", "text"]
SessionStatus = Literal["active", "ended"]
Speaker = Literal["tutor", "user"]
ErrorCategory = Literal[
    "grammar",
    "vocabulary",
    "phrasal_verb",
    "pronunciation_asr",
    "register",
]


@dataclass(frozen=True, slots=True)
class Deck:
    id: int
    slug: str
    name: str
    description: str
    target_cefr: str
    persona_prompt: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Card:
    id: int
    deck_id: int
    deck_slug: str
    front_prompt: str
    normalized_front: str
    back_reference: str
    context_example: str | None
    card_type: CardType
    source_type: SourceType
    fsrs_state: int
    is_new: bool
    stability: float | None
    difficulty: float | None
    step: int | None
    reps: int
    lapses: int
    scheduled_days: int
    due_at: str
    last_review_at: str | None
    suspended: bool


@dataclass(frozen=True, slots=True)
class StudySession:
    id: str
    deck_id: int | None
    mode: SessionMode
    input_mode_default: InputMode
    status: SessionStatus
    started_at: str
    ended_at: str | None
    cards_reviewed: int
    errors_extracted: int
    summary_notes: str | None


@dataclass(frozen=True, slots=True)
class ReviewResult:
    card_id: int
    rating: int
    fsrs_state: str
    fsrs_state_int: int
    scheduled_days: int
    next_due_at: str
    stability: float | None
    difficulty: float | None
    step: int | None
    reps: int
    lapses: int
    idempotent_replay: bool = False


@dataclass(frozen=True, slots=True)
class DueCardsQueueStats:
    returned: int
    total_due_reviews: int
    total_new_available: int


@dataclass(frozen=True, slots=True)
class DueCardsResult:
    cards: list[Card]
    queue_stats: DueCardsQueueStats


@dataclass(frozen=True, slots=True)
class AddCardResult:
    card_id: int
    created: bool
    deck_slug: str
    due_at: str


@dataclass(frozen=True, slots=True)
class ErrorLogInput:
    category: ErrorCategory
    utterance_raw: str
    correction: str
    explanation: str


@dataclass(frozen=True, slots=True)
class ErrorLogRecord:
    id: int
    session_id: str
    turn_id: int | None
    deck_id: int
    category: ErrorCategory
    utterance_raw: str
    correction: str
    explanation: str
    fingerprint_hash: str
    occurrence_count: int
    promoted_card_id: int | None
    created_at: str
    last_seen_at: str


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    status: SessionStatus
    started_at: str
    ended_at: str | None
    cards_reviewed: int
    errors_extracted: int
    summary_notes: str | None
    promoted_cards: list[AddCardResult] = field(default_factory=list)
    recurring_errors: list[ErrorLogRecord] = field(default_factory=list)
