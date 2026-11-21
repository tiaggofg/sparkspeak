"""Configuration and local storage path resolution for SparkSpeak."""

import os
from dataclasses import dataclass
from pathlib import Path


def _default_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True, slots=True)
class SparkSpeakConfig:
    """Resolved local paths and runtime defaults for SparkSpeak."""

    project_root: Path
    db_path: Path
    backups_dir: Path
    audio_dir: Path
    models_dir: Path


def load_config(project_root: Path | None = None) -> SparkSpeakConfig:
    """Resolve SparkSpeak paths, honoring SPARKSPEAK_* environment overrides."""
    root = project_root or _default_project_root()
    data_dir = root / ".data"

    db_env = os.environ.get("SPARKSPEAK_DB_PATH")
    backups_env = os.environ.get("SPARKSPEAK_BACKUPS_DIR")
    audio_env = os.environ.get("SPARKSPEAK_AUDIO_DIR")
    models_env = os.environ.get("SPARKSPEAK_MODELS_DIR")

    return SparkSpeakConfig(
        project_root=root,
        db_path=Path(db_env) if db_env else data_dir / "sparkspeak.db",
        backups_dir=Path(backups_env) if backups_env else data_dir / "backups",
        audio_dir=Path(audio_env) if audio_env else data_dir / "audio",
        models_dir=Path(models_env) if models_env else data_dir / "models",
    )
