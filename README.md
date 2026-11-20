# SparkSpeak

Local-first English tutor harness for Google Antigravity combining an on-demand pedagogical skill (`english-tutor`) with a deterministic Python `stdio` MCP server (`sparkspeak-mcp`).

## Capabilities

- **Deterministic FSRS Scheduling**: Uses `py-fsrs` (`desired_retention=0.90`) backed by SQLite (WAL mode, `PRAGMA foreign_keys = ON`) with versioned SQL migrations and seed decks (`conversational`, `phrasal-verbs`, `tech-meetings`).
- **Offline PipeWire TTS (`piper-tts`)**: Speaks tutor prompts locally via `en_US-lessac-medium` ONNX and `sounddevice`, with quiet-mode and text fallback.
- **VAD-Gated Raw STT (`faster-whisper` + Silero VAD)**: Captures 16kHz mono PCM, endpoints speech with Silero VAD, and transcribes verbatim (`compute_type="int8"`, `language="en"`) without grammar auto-correction.
- **Post-Session Error Extraction**: Logs turns and recurring mistakes via SHA-256 `fingerprint_hash` deduplication (`log_turn_and_errors`) and promotes errors into `auto_extracted` flashcards on `end_session(promote_errors=true)`.

## System Dependencies (Ubuntu 24.04 / PipeWire)

Text mode works without audio libraries. For local voice mode (`speak_text` and `listen_and_transcribe`), install PortAudio and `ffmpeg`:

```bash
sudo apt update && sudo apt install -y libportaudio2 ffmpeg
```

> If `uv run sparkspeak-health` reports `"probe_error": "PortAudio library not found"`, `libportaudio2` is missing on the host system.

## Quick Start

```bash
# Install Python dependencies
uv sync

# Download Piper ONNX voice + pre-cache faster-whisper base model into .data/models/
# (HF Hub unauthenticated-request warning is harmless)
uv run sparkspeak-setup-models

# Check local models and PipeWire input/output devices
uv run sparkspeak-health
```

Expected `uv run sparkspeak-health` output when voice mode is ready:

```json
{
  "models_dir": ".../.data/models",
  "piper_model_installed": true,
  "whisper_cache_present": true,
  "pipewire_input": true,
  "pipewire_output": true,
  "input_device": "default",
  "output_device": "default",
  "probe_error": null
}
```

## MCP Tools

- `start_session(deck_slug?, mode?, input_mode?)`
- `get_due_cards(deck_slug?, limit?, new_cards_limit?, include_new?)`
- `submit_review(card_id, rating, user_response_raw, input_mode, session_id?, duration_ms?, idempotency_key?)`
- `add_card(deck_slug, front_prompt, back_reference, card_type, context_example?, source_type?)`
- `log_turn_and_errors(session_id, speaker, raw_transcript, input_mode, deck_slug?, audio_duration_ms?, errors?)`
- `end_session(session_id, promote_errors?, summary_notes?)`
- `speak_text(text, voice?, speed?, blocking?)`
- `listen_and_transcribe(silence_timeout_ms?, initial_speech_timeout_ms?, max_duration_ms?)`
- `get_audio_status()`

## Verification & Quality Checks

```bash
uv run ruff check src tests
uv run mypy src
uv run pytest -v
```

See [docs/README.md](./docs/README.md) for architecture diagrams, data model, sequence flows, and ADRs.
