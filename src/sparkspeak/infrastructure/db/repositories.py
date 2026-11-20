"""SQLite repository implementations for decks, cards, reviews, sessions, and errors."""

import hashlib
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sparkspeak.domain.errors import ErrorCode, SparkSpeakError
from sparkspeak.domain.models import (
    AddCardResult,
    Card,
    CardType,
    Deck,
    DueCardsQueueStats,
    DueCardsResult,
    ErrorCategory,
    ErrorLogInput,
    ErrorLogRecord,
    InputMode,
    ReviewResult,
    SessionMode,
    SessionStatus,
    SourceType,
    Speaker,
    StudySession,
)
from sparkspeak.domain.srs_engine import format_utc_iso
from sparkspeak.infrastructure.db.connection import open_connection

_NON_ALNUM_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")

_STATE_NAMES: dict[int, str] = {
    1: "learning",
    2: "review",
    3: "relearning",
}


def normalize_text(text: str) -> str:
    """Normalize text for deduplication and error fingerprinting."""
    cleaned = _NON_ALNUM_RE.sub("", text.lower())
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def compute_error_fingerprint(deck_id: int, category: str, correction: str) -> str:
    """Compute SHA-256 fingerprint over deck_id, category, and normalized correction."""
    raw = f"{deck_id}:{category}:{normalize_text(correction)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _row_to_deck(row: sqlite3.Row) -> Deck:
    return Deck(
        id=int(row["id"]),
        slug=str(row["slug"]),
        name=str(row["name"]),
        description=str(row["description"]),
        target_cefr=str(row["target_cefr"]),
        persona_prompt=str(row["persona_prompt"]),
        created_at=str(row["created_at"]),
    )


def _row_to_card(row: sqlite3.Row) -> Card:
    return Card(
        id=int(row["id"]),
        deck_id=int(row["deck_id"]),
        deck_slug=str(row["deck_slug"]),
        front_prompt=str(row["front_prompt"]),
        normalized_front=str(row["normalized_front"]),
        back_reference=str(row["back_reference"]),
        context_example=str(row["context_example"]) if row["context_example"] is not None else None,
        card_type=cast(CardType, row["card_type"]),
        source_type=cast(SourceType, row["source_type"]),
        fsrs_state=int(row["fsrs_state"]),
        is_new=bool(row["is_new"]),
        stability=float(row["stability"]) if row["stability"] is not None else None,
        difficulty=float(row["difficulty"]) if row["difficulty"] is not None else None,
        step=int(row["step"]) if row["step"] is not None else None,
        reps=int(row["reps"]),
        lapses=int(row["lapses"]),
        scheduled_days=int(row["scheduled_days"]),
        due_at=str(row["due_at"]),
        last_review_at=str(row["last_review_at"]) if row["last_review_at"] is not None else None,
        suspended=bool(row["suspended"]),
    )


def _row_to_session(row: sqlite3.Row) -> StudySession:
    return StudySession(
        id=str(row["id"]),
        deck_id=int(row["deck_id"]) if row["deck_id"] is not None else None,
        mode=cast(SessionMode, row["mode"]),
        input_mode_default=cast(InputMode, row["input_mode_default"]),
        status=cast(SessionStatus, row["status"]),
        started_at=str(row["started_at"]),
        ended_at=str(row["ended_at"]) if row["ended_at"] is not None else None,
        cards_reviewed=int(row["cards_reviewed"]),
        errors_extracted=int(row["errors_extracted"]),
        summary_notes=str(row["summary_notes"]) if row["summary_notes"] is not None else None,
    )


def _row_to_error_log(row: sqlite3.Row) -> ErrorLogRecord:
    return ErrorLogRecord(
        id=int(row["id"]),
        session_id=str(row["session_id"]),
        turn_id=int(row["turn_id"]) if row["turn_id"] is not None else None,
        deck_id=int(row["deck_id"]),
        category=cast(ErrorCategory, row["category"]),
        utterance_raw=str(row["utterance_raw"]),
        correction=str(row["correction"]),
        explanation=str(row["explanation"]),
        fingerprint_hash=str(row["fingerprint_hash"]),
        occurrence_count=int(row["occurrence_count"]),
        promoted_card_id=(
            int(row["promoted_card_id"]) if row["promoted_card_id"] is not None else None
        ),
        created_at=str(row["created_at"]),
        last_seen_at=str(row["last_seen_at"]),
    )


class SQLiteRepository:
    """Repository encapsulating SparkSpeak SQLite queries and transactions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_deck_by_slug(self, slug: str) -> Deck | None:
        with open_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM decks WHERE slug = ?", (slug,)).fetchone()
            return _row_to_deck(row) if row is not None else None

    def get_deck_by_id(self, deck_id: int) -> Deck | None:
        with open_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
            return _row_to_deck(row) if row is not None else None

    def list_decks(self) -> list[Deck]:
        with open_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM decks ORDER BY id ASC").fetchall()
            return [_row_to_deck(r) for r in rows]

    def get_card_by_id(self, card_id: int) -> Card | None:
        with open_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT c.*, d.slug AS deck_slug
                FROM cards c
                JOIN decks d ON d.id = c.deck_id
                WHERE c.id = ?
                """,
                (card_id,),
            ).fetchone()
            return _row_to_card(row) if row is not None else None

    def count_due_summary(
        self,
        deck_slug: str | None = None,
        now_iso: str | None = None,
    ) -> tuple[int, int]:
        now = now_iso or format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            deck_id = self._resolve_deck_id(conn, deck_slug)
            return self._count_due_and_new(conn, deck_id, now)

    def get_due_cards(
        self,
        *,
        deck_slug: str | None = None,
        limit: int = 10,
        new_cards_limit: int = 3,
        include_new: bool = True,
        now_iso: str | None = None,
    ) -> DueCardsResult:
        now = now_iso or format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            deck_id = self._resolve_deck_id(conn, deck_slug)
            total_due, total_new = self._count_due_and_new(conn, deck_id, now)

            deck_filter = "AND c.deck_id = ?" if deck_id is not None else ""
            due_params: list[object] = [now]
            if deck_id is not None:
                due_params.append(deck_id)
            due_params.append(limit)

            due_rows = conn.execute(
                f"""
                SELECT c.*, d.slug AS deck_slug
                FROM cards c
                JOIN decks d ON d.id = c.deck_id
                WHERE c.suspended = 0
                  AND c.is_new = 0
                  AND c.due_at <= ?
                  {deck_filter}
                ORDER BY c.due_at ASC, c.id ASC
                LIMIT ?
                """,
                due_params,
            ).fetchall()
            cards = [_row_to_card(r) for r in due_rows]

            remaining = max(0, limit - len(cards))
            new_cap = min(remaining, new_cards_limit) if include_new else 0
            if new_cap > 0:
                new_params: list[object] = []
                if deck_id is not None:
                    new_params.append(deck_id)
                new_params.append(new_cap)

                new_rows = conn.execute(
                    f"""
                    SELECT c.*, d.slug AS deck_slug
                    FROM cards c
                    JOIN decks d ON d.id = c.deck_id
                    WHERE c.suspended = 0
                      AND c.is_new = 1
                      {deck_filter}
                    ORDER BY c.id ASC
                    LIMIT ?
                    """,
                    new_params,
                ).fetchall()
                cards.extend(_row_to_card(r) for r in new_rows)

        return DueCardsResult(
            cards=cards,
            queue_stats=DueCardsQueueStats(
                returned=len(cards),
                total_due_reviews=total_due,
                total_new_available=total_new,
            ),
        )

    def apply_review(
        self,
        *,
        card_id: int,
        result: ReviewResult,
        user_response_raw: str,
        input_mode: InputMode,
        session_id: str | None = None,
        duration_ms: int | None = None,
        idempotency_key: str | None = None,
        reviewed_at: str | None = None,
    ) -> ReviewResult:
        now = reviewed_at or format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key is not None:
                    existing = conn.execute(
                        """
                        SELECT rl.*, c.due_at, c.step, c.reps, c.lapses
                        FROM review_logs rl
                        JOIN cards c ON c.id = rl.card_id
                        WHERE rl.idempotency_key = ?
                        """,
                        (idempotency_key,),
                    ).fetchone()
                    if existing is not None:
                        conn.execute("COMMIT")
                        state_int = int(existing["fsrs_state_after"])
                        return ReviewResult(
                            card_id=int(existing["card_id"]),
                            rating=int(existing["rating"]),
                            fsrs_state=_STATE_NAMES[state_int],
                            fsrs_state_int=state_int,
                            scheduled_days=int(existing["scheduled_days"]),
                            next_due_at=str(existing["due_at"]),
                            stability=(
                                float(existing["stability_after"])
                                if existing["stability_after"] is not None
                                else None
                            ),
                            difficulty=(
                                float(existing["difficulty_after"])
                                if existing["difficulty_after"] is not None
                                else None
                            ),
                            step=int(existing["step"]) if existing["step"] is not None else None,
                            reps=int(existing["reps"]),
                            lapses=int(existing["lapses"]),
                            idempotent_replay=True,
                        )

                card_row = conn.execute(
                    "SELECT id, fsrs_state FROM cards WHERE id = ?",
                    (card_id,),
                ).fetchone()
                if card_row is None:
                    raise SparkSpeakError(
                        error_code=ErrorCode.CARD_NOT_FOUND,
                        message=f"Card {card_id} was not found.",
                        details={"card_id": card_id},
                    )

                if session_id is not None:
                    sess_row = conn.execute(
                        "SELECT id FROM study_sessions WHERE id = ?",
                        (session_id,),
                    ).fetchone()
                    if sess_row is None:
                        raise SparkSpeakError(
                            error_code=ErrorCode.SESSION_NOT_FOUND,
                            message=f"Session {session_id!r} was not found.",
                            details={"session_id": session_id},
                        )

                prev_state = int(card_row["fsrs_state"])
                conn.execute(
                    """
                    UPDATE cards
                    SET fsrs_state = ?,
                        is_new = 0,
                        stability = ?,
                        difficulty = ?,
                        step = ?,
                        reps = ?,
                        lapses = ?,
                        scheduled_days = ?,
                        due_at = ?,
                        last_review_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        result.fsrs_state_int,
                        result.stability,
                        result.difficulty,
                        result.step,
                        result.reps,
                        result.lapses,
                        result.scheduled_days,
                        result.next_due_at,
                        now,
                        now,
                        card_id,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO review_logs (
                        idempotency_key, card_id, session_id, rating,
                        fsrs_state_before, fsrs_state_after, stability_after,
                        difficulty_after, scheduled_days, user_response_raw,
                        input_mode, duration_ms, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        idempotency_key,
                        card_id,
                        session_id,
                        result.rating,
                        prev_state,
                        result.fsrs_state_int,
                        result.stability,
                        result.difficulty,
                        result.scheduled_days,
                        user_response_raw,
                        input_mode,
                        duration_ms,
                        now,
                    ),
                )

                if session_id is not None:
                    conn.execute(
                        """
                        UPDATE study_sessions
                        SET cards_reviewed = cards_reviewed + 1
                        WHERE id = ?
                        """,
                        (session_id,),
                    )

                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return result

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
        normalized = normalize_text(front_prompt)
        now = format_utc_iso(datetime.now(UTC))

        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                deck_row = conn.execute(
                    "SELECT id FROM decks WHERE slug = ?",
                    (deck_slug,),
                ).fetchone()
                if deck_row is None:
                    raise SparkSpeakError(
                        error_code=ErrorCode.DECK_NOT_FOUND,
                        message=f"Deck {deck_slug!r} was not found.",
                        details={"deck_slug": deck_slug},
                    )
                deck_id = int(deck_row["id"])

                existing = conn.execute(
                    "SELECT id, due_at FROM cards WHERE deck_id = ? AND normalized_front = ?",
                    (deck_id, normalized),
                ).fetchone()
                if existing is not None:
                    conn.execute("COMMIT")
                    return AddCardResult(
                        card_id=int(existing["id"]),
                        created=False,
                        deck_slug=deck_slug,
                        due_at=str(existing["due_at"]),
                    )

                cur = conn.execute(
                    """
                    INSERT INTO cards (
                        deck_id, front_prompt, normalized_front, back_reference,
                        context_example, card_type, source_type, due_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        deck_id,
                        front_prompt,
                        normalized,
                        back_reference,
                        context_example,
                        card_type,
                        source_type,
                        now,
                        now,
                        now,
                    ),
                )
                assert cur.lastrowid is not None
                card_id = int(cur.lastrowid)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return AddCardResult(
            card_id=card_id,
            created=True,
            deck_slug=deck_slug,
            due_at=now,
        )

    def create_session(
        self,
        *,
        mode: SessionMode,
        input_mode_default: InputMode,
        deck_id: int | None = None,
    ) -> StudySession:
        session_id = str(uuid.uuid4())
        now = format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO study_sessions (
                        id, deck_id, mode, input_mode_default, status, started_at
                    ) VALUES (?, ?, ?, ?, 'active', ?)
                    """,
                    (session_id, deck_id, mode, input_mode_default, now),
                )
                row = conn.execute(
                    "SELECT * FROM study_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        assert row is not None
        return _row_to_session(row)

    def get_session(self, session_id: str) -> StudySession | None:
        with open_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM study_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return _row_to_session(row) if row is not None else None

    def update_session_input_mode(
        self,
        session_id: str,
        input_mode: InputMode,
    ) -> StudySession:
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    UPDATE study_sessions
                    SET input_mode_default = ?
                    WHERE id = ?
                    """,
                    (input_mode, session_id),
                )
                if cur.rowcount == 0:
                    raise SparkSpeakError(
                        error_code=ErrorCode.SESSION_NOT_FOUND,
                        message=f"Session {session_id!r} was not found.",
                        details={"session_id": session_id},
                    )
                row = conn.execute(
                    "SELECT * FROM study_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        assert row is not None
        return _row_to_session(row)

    def end_session(
        self,
        session_id: str,
        *,
        summary_notes: str | None = None,
        errors_extracted: int = 0,
    ) -> StudySession:
        now = format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM study_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if row is None:
                    raise SparkSpeakError(
                        error_code=ErrorCode.SESSION_NOT_FOUND,
                        message=f"Session {session_id!r} was not found.",
                        details={"session_id": session_id},
                    )
                if row["status"] == "ended":
                    conn.execute("COMMIT")
                    return _row_to_session(row)

                conn.execute(
                    """
                    UPDATE study_sessions
                    SET status = 'ended',
                        ended_at = ?,
                        errors_extracted = ?,
                        summary_notes = ?
                    WHERE id = ?
                    """,
                    (now, errors_extracted, summary_notes, session_id),
                )
                updated = conn.execute(
                    "SELECT * FROM study_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        assert updated is not None
        return _row_to_session(updated)

    def log_turn_and_errors(
        self,
        *,
        session_id: str,
        deck_id: int,
        speaker: Speaker,
        raw_transcript: str,
        input_mode: InputMode,
        audio_duration_ms: int | None = None,
        errors: list[ErrorLogInput] | None = None,
    ) -> tuple[int, list[ErrorLogRecord]]:
        now = format_utc_iso(datetime.now(UTC))
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                sess = conn.execute(
                    "SELECT id FROM study_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if sess is None:
                    raise SparkSpeakError(
                        error_code=ErrorCode.SESSION_NOT_FOUND,
                        message=f"Session {session_id!r} was not found.",
                        details={"session_id": session_id},
                    )

                max_row = conn.execute(
                    "SELECT COALESCE(MAX(turn_index), 0) AS max_idx "
                    "FROM session_turns WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                next_turn_idx = int(max_row["max_idx"]) + 1

                turn_cur = conn.execute(
                    """
                    INSERT INTO session_turns (
                        session_id, turn_index, speaker, raw_transcript,
                        input_mode, audio_duration_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        next_turn_idx,
                        speaker,
                        raw_transcript,
                        input_mode,
                        audio_duration_ms,
                        now,
                    ),
                )
                assert turn_cur.lastrowid is not None
                turn_id = int(turn_cur.lastrowid)

                recorded_errors: list[ErrorLogRecord] = []
                for item in errors or []:
                    fp = compute_error_fingerprint(deck_id, item.category, item.correction)
                    existing = conn.execute(
                        """
                        SELECT id FROM error_logs
                        WHERE fingerprint_hash = ?
                        ORDER BY id ASC
                        LIMIT 1
                        """,
                        (fp,),
                    ).fetchone()
                    if existing is not None:
                        err_id = int(existing["id"])
                        conn.execute(
                            """
                            UPDATE error_logs
                            SET occurrence_count = occurrence_count + 1,
                                last_seen_at = ?,
                                session_id = ?,
                                turn_id = ?
                            WHERE id = ?
                            """,
                            (now, session_id, turn_id, err_id),
                        )
                    else:
                        err_cur = conn.execute(
                            """
                            INSERT INTO error_logs (
                                session_id, turn_id, deck_id, category,
                                utterance_raw, correction, explanation,
                                fingerprint_hash, occurrence_count,
                                created_at, last_seen_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                            """,
                            (
                                session_id,
                                turn_id,
                                deck_id,
                                item.category,
                                item.utterance_raw,
                                item.correction,
                                item.explanation,
                                fp,
                                now,
                                now,
                            ),
                        )
                        assert err_cur.lastrowid is not None
                        err_id = int(err_cur.lastrowid)

                    err_row = conn.execute(
                        "SELECT * FROM error_logs WHERE id = ?",
                        (err_id,),
                    ).fetchone()
                    assert err_row is not None
                    recorded_errors.append(_row_to_error_log(err_row))

                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return next_turn_idx, recorded_errors

    def get_session_errors(self, session_id: str) -> list[ErrorLogRecord]:
        with open_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM error_logs
                WHERE session_id = ?
                ORDER BY occurrence_count DESC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return [_row_to_error_log(r) for r in rows]

    def mark_error_promoted(self, error_id: int, card_id: int) -> None:
        with open_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "UPDATE error_logs SET promoted_card_id = ? WHERE id = ?",
                    (card_id, error_id),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _resolve_deck_id(conn: sqlite3.Connection, deck_slug: str | None) -> int | None:
        if deck_slug is None:
            return None
        row = conn.execute("SELECT id FROM decks WHERE slug = ?", (deck_slug,)).fetchone()
        if row is None:
            raise SparkSpeakError(
                error_code=ErrorCode.DECK_NOT_FOUND,
                message=f"Deck {deck_slug!r} was not found.",
                details={"deck_slug": deck_slug},
            )
        return int(row["id"])

    @staticmethod
    def _count_due_and_new(
        conn: sqlite3.Connection,
        deck_id: int | None,
        now_iso: str,
    ) -> tuple[int, int]:
        if deck_id is None:
            due_row = conn.execute(
                """
                SELECT COUNT(*) FROM cards
                WHERE suspended = 0 AND is_new = 0 AND due_at <= ?
                """,
                (now_iso,),
            ).fetchone()
            new_row = conn.execute(
                "SELECT COUNT(*) FROM cards WHERE suspended = 0 AND is_new = 1"
            ).fetchone()
        else:
            due_row = conn.execute(
                """
                SELECT COUNT(*) FROM cards
                WHERE suspended = 0 AND is_new = 0 AND due_at <= ? AND deck_id = ?
                """,
                (now_iso, deck_id),
            ).fetchone()
            new_row = conn.execute(
                """
                SELECT COUNT(*) FROM cards
                WHERE suspended = 0 AND is_new = 1 AND deck_id = ?
                """,
                (deck_id,),
            ).fetchone()
        return int(due_row[0]), int(new_row[0])
