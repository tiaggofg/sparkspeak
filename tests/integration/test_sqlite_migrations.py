"""Integration tests for SQLite connection pragmas, migrations, and seed loading."""

import sqlite3
from pathlib import Path

import pytest

from sparkspeak.infrastructure.db.connection import open_connection
from sparkspeak.infrastructure.db.migrator import run_migrations

_DB_FILENAME = "sparkspeak.db"


def test_migrations_idempotent_wal_fk(tmp_path: Path) -> None:
    db_path = tmp_path / "data" / _DB_FILENAME
    backups_dir = tmp_path / "backups"

    applied_first = run_migrations(db_path=db_path, backups_dir=backups_dir)
    assert applied_first == [1]

    applied_second = run_migrations(db_path=db_path, backups_dir=backups_dir)
    assert applied_second == []

    with open_connection(db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert fk == 1
    assert str(journal).lower() == "wal"
    assert timeout == 5000
    assert {
        "schema_migrations",
        "decks",
        "cards",
        "study_sessions",
        "review_logs",
        "session_turns",
        "error_logs",
    }.issubset(tables)


def test_seed_decks_and_cards_are_loaded_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / _DB_FILENAME
    backups_dir = tmp_path / "backups"

    run_migrations(db_path=db_path, backups_dir=backups_dir)
    run_migrations(db_path=db_path, backups_dir=backups_dir)

    with open_connection(db_path) as conn:
        slugs = {row["slug"] for row in conn.execute("SELECT slug FROM decks").fetchall()}
        card_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]

    assert slugs == {"conversational", "phrasal-verbs", "tech-meetings"}
    assert card_count >= 7


def test_backup_created_before_pending_migration_on_existing_db(tmp_path: Path) -> None:
    db_path = tmp_path / _DB_FILENAME
    backups_dir = tmp_path / "backups"

    # Pre-create an existing non-empty DB without schema_migrations
    with sqlite3.connect(db_path) as raw:
        raw.execute("CREATE TABLE legacy_note (id INTEGER PRIMARY KEY)")
        raw.commit()

    applied = run_migrations(db_path=db_path, backups_dir=backups_dir)

    assert applied == [1]
    backups = list(backups_dir.glob("*.db.bak"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0


def test_foreign_key_constraint_is_enforced_on_connection(tmp_path: Path) -> None:
    db_path = tmp_path / _DB_FILENAME
    backups_dir = tmp_path / "backups"
    run_migrations(db_path=db_path, backups_dir=backups_dir)

    with open_connection(db_path) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO cards (
                deck_id, front_prompt, normalized_front, back_reference,
                card_type, source_type
            ) VALUES (99999, 'front', 'front', 'back', 'vocab', 'manual')
            """
        )
