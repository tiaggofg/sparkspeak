"""Sequential idempotent SQLite migration and seed runner."""

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from sparkspeak.infrastructure.db.connection import open_connection

_DB_DIR = Path(__file__).resolve().parent
DEFAULT_MIGRATIONS_DIR = _DB_DIR / "migrations"
DEFAULT_SEEDS_DIR = _DB_DIR / "seeds"


def _parse_version(path: Path) -> int:
    prefix = path.name.split("_", 1)[0]
    return int(prefix)


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if row is None:
        return set()
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r["version"]) for r in rows}


def _create_backup(db_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backups_dir / f"{db_path.stem}-{stamp}.db.bak"
    shutil.copy2(db_path, backup_path)
    return backup_path


def run_migrations(
    db_path: Path,
    backups_dir: Path,
    *,
    migrations_dir: Path | None = None,
    seeds_dir: Path | None = None,
    load_seeds: bool = True,
) -> list[int]:
    """Apply pending SQL migrations in numeric order and optionally run idempotent seeds."""
    mig_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    seed_dir = seeds_dir or DEFAULT_SEEDS_DIR

    migration_files = sorted(mig_dir.glob("*.sql"), key=_parse_version)
    db_existed = db_path.exists() and db_path.stat().st_size > 0

    with open_connection(db_path) as conn:
        applied = _applied_versions(conn)
        pending = [p for p in migration_files if _parse_version(p) not in applied]

        if db_existed and pending:
            _create_backup(db_path, backups_dir)

        newly_applied: list[int] = []
        for sql_file in pending:
            version = _parse_version(sql_file)
            sql_text = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql_text)
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                (version, sql_file.name),
            )
            newly_applied.append(version)

        if load_seeds and seed_dir.exists():
            for seed_file in sorted(seed_dir.glob("*.sql")):
                conn.executescript(seed_file.read_text(encoding="utf-8"))
                conn.execute("PRAGMA foreign_keys = ON;")

    return newly_applied
