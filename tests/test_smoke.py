"""Smoke tests for package bootstrap, manifest, and hybrid multimodal+Kokoro skill."""

import tomllib
from pathlib import Path

import sparkspeak

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_package_imports() -> None:
    assert sparkspeak.__version__ in {"0.1.0", "0.2.0"}


def test_pyproject_removes_heavy_stt_tts_dependencies() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps: list[str] = pyproject["project"]["dependencies"]
    dep_names = {dep.split(">=")[0].split("==")[0].strip() for dep in deps}

    assert dep_names == {"mcp", "fsrs", "kokoro-onnx", "sounddevice", "numpy"}
    assert "faster-whisper" not in dep_names
    assert "piper-tts" not in dep_names

    scripts: dict[str, str] = pyproject["project"]["scripts"]
    assert list(scripts.keys()) == ["sparkspeak-mcp"]


def test_skill_md_defines_multimodal_wav_and_voice_output_workflow() -> None:
    skill_path = (
        PROJECT_ROOT
        / ".agents"
        / "plugins"
        / "sparkspeak"
        / "skills"
        / "english-tutor"
        / "SKILL.md"
    )
    content = skill_path.read_text(encoding="utf-8")

    assert "speak_text" in content
    assert "record_utterance" in content
    assert "read_file" in content
    assert "af_heart" in content
    assert "af_jessica" in content
    assert "am_liam" in content
    assert "am_puck" in content
    assert "log_mistake" in content
    assert "MICROPHONE_UNAVAILABLE" in content
    assert "-ed" in content
    assert "epenthesis" in content.lower()
    assert "listen_and_transcribe" not in content
    assert "get_audio_status" not in content
