# SparkSpeak

Local-first English tutor harness for Google Antigravity combining an on-demand pedagogical skill (`english-tutor`), native multimodal WAV audio listening (`record_utterance` + `read_file`), offline Kokoro ONNX natural TTS (`speak_text`), and a deterministic Python `stdio` MCP server (`sparkspeak-mcp`).

## Capabilities

- **Deterministic FSRS Scheduling**: Uses `py-fsrs` (`desired_retention=0.90`) backed by SQLite (WAL mode, `PRAGMA foreign_keys = ON`) with versioned SQL migrations and seed decks (`conversational`, `phrasal-verbs`, `tech-meetings`).
- **Offline Kokoro ONNX Natural TTS (`speak_text`)**: Speaks tutor replies locally with natural neural voices (`af_heart`, `af_jessica`, `am_liam`, `am_puck`) over PipeWire, keeping chat text minimal.
- **Lightweight WAV Capture (`record_utterance`)**: Captures 16 kHz mono 16-bit PCM via `sounddevice` with `numpy` RMS silence endpointing (200 ms pre-roll, zero local STT weights) into `.data/audio/last_utterance.wav` for direct multimodal listening via `read_file`.
- **Low-Latency Mistake Logging & Promotion**: Records learner pronunciation, grammar, phrasal verb, vocabulary, and register slips via `log_mistake` (or `log_turn_and_errors`) with SHA-256 `fingerprint_hash` deduplication, promoting errors into `auto_extracted` flashcards on `end_session(promote_errors=true)`.

## System Dependencies (Ubuntu 24.04 / PipeWire)

Text mode works without audio libraries. For microphone capture (`record_utterance`), install PortAudio:

```bash
sudo apt update && sudo apt install -y libportaudio2
```

> If `start_session` reports `"mic_available": false` or `record_utterance` returns `MICROPHONE_UNAVAILABLE`, `libportaudio2` or a PipeWire input device is missing and the session falls back to `text` mode seamlessly.

## Quick Start

```bash
# Install Python dependencies
uv sync

# Start MCP server manually (stdio)
uv run sparkspeak-mcp
```

## MCP Tools

- `start_session(deck_slug?, mode?, input_mode?)`
- `get_due_cards(deck_slug?, limit?, new_cards_limit?, include_new?)`
- `submit_review(card_id, rating, user_response_raw, input_mode?, session_id?, duration_ms?, idempotency_key?)`
- `add_card(deck_slug, front_prompt, back_reference, card_type, context_example?, source_type?)`
- `log_mistake(session_id, utterance_raw, correction, category?, explanation?, deck_slug?, input_mode?, audio_duration_ms?)`
- `log_turn_and_errors(session_id, speaker, raw_transcript, input_mode, deck_slug?, audio_duration_ms?, errors?)`
- `end_session(session_id, promote_errors?, summary_notes?)`
- `speak_text(text, voice?, speed?, blocking?)`
- `record_utterance(silence_timeout_ms?, initial_speech_timeout_ms?, max_duration_ms?)`

## Verification & Quality Checks

```bash
uv run ruff check src tests
uv run mypy src
uv run pytest -v
```

See [docs/README.md](./docs/README.md) for architecture diagrams, data model, sequence flows, and ADRs.
