# English Tutor Harness Specification

**Approved**: 2026-11-20 - user: "aceito tudo o que foi recomendado. . automática com resumo e voz do tutor com piper-tts. A stack e está aprovada"
**Status**: Approved

## Problem Statement

Software engineers learning spoken English need realistic conversation practice, immediate yet non-intrusive feedback, and scientifically timed spaced repetition without paying external LLM API costs or switching out of their daily development environment. Native IDE voice modes auto-correct and normalize spoken transcripts before the tutor sees them, hiding real pronunciation and grammar errors, while LLM memory alone hallucinates spaced-repetition intervals and drops long-term error history. SparkSpeak solves this by pairing the Google Antigravity LLM (as the pedagogical engine loaded on demand via an Agent Skill) with deterministic local MCP servers for FSRS scheduling, SQLite persistence, and PipeWire offline audio I/O on Ubuntu 24.04.

## Goals

- [ ] Deliver a native Google Antigravity English-tutoring harness with zero external LLM API costs, loading pedagogical instructions on demand via `.agents/skills/english-tutor/SKILL.md` (or plugin bundle).
- [ ] Guarantee 100% deterministic spaced-repetition scheduling (FSRS) and durable local persistence in SQLite with versioned migrations.
- [ ] Capture spoken English on Ubuntu 24.04 (PipeWire/ALSA) with VAD-gated local STT (`faster-whisper`) that preserves real grammatical and pronunciation errors without LLM/IDE auto-correction.
- [ ] Synthesize natural spoken tutor responses locally with low latency via PipeWire TTS (`piper-tts`) while supporting seamless runtime fallback to chat text mode.
- [ ] Automatically log recurring errors during sessions and extract/promote them into SRS flashcards during structured post-session review.

## Out of Scope

Explicitly excluded from this feature to prevent scope creep.

| Feature | Reason |
| --- | --- |
| Custom web/desktop GUI dashboard | Antigravity chat is the primary user interface for this harness |
| Cloud sync / multi-user authentication | Single-user local-first workstation setup on Ubuntu 24.04 |
| External paid LLM/STT/TTS cloud APIs | Core constraint is zero external API cost and local-first privacy |
| Phoneme-level forced alignment scoring (MFA/Azure Pronunciation) | Overkill for MVP; raw ASR transcript + confidence metadata suffices |
| Mobile companion app | Out of workstation Antigravity scope |

---

## Assumptions & Open Questions

Every ambiguity or product decision is recorded here for user confirmation before implementation.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| SQLite database file location | `.data/sparkspeak.db` inside repo, excluded via `.gitignore` (override via `SPARKSPEAK_DB_PATH`) | Keeps DB local to the project directory without committing mutable binary data to Git; SQL migrations and seed decks stay versioned | y |
| Antigravity MCP registration scope | Workspace plugin bundle at `.agents/plugins/sparkspeak/` (`plugin.json`, `mcp_config.json`, `skills/english-tutor/`) | Scopes MCP + Skill strictly to this project inside Antigravity as requested | y |
| Spaced repetition algorithm | FSRS (`py-fsrs`, `desired_retention=0.90`) | Eliminates SM-2 "ease hell", models Difficulty/Stability/Retrievability, and supports future weight optimization from `review_logs` | y |
| Local MCP server runtime stack | Python 3.12+ with `uv` and official `mcp` SDK (`MCPServer` / FastMCP pattern) | Sub-250ms stdio startup, native ecosystem for `faster-whisper`, Silero VAD, `piper-tts`, `sounddevice`, and `fsrs` without JVM/GraalVM JNI complexity | y |
| Default local TTS engine | `piper-tts` (`en_US-lessac-medium` ONNX) via `sounddevice`/PipeWire | Fully offline, low CPU latency (~100-300ms), zero network dependency; `TTSEngine` port allows optional `edge-tts` or Kokoro later | y |
| Post-session error-to-card promotion | Auto-create cards for new recurring/high-value errors (`add_card` with deduplication) and show summary at session end | Minimizes end-of-session friction while preventing duplicate cards via normalized `fingerprint_hash` | y |
| Voice capture endpointing | Silero VAD with `silence_timeout_ms=1500`, `initial_speech_timeout_ms=10000`, `max_duration_ms=45000` | Prevents infinite mic hang in noisy/silent rooms while allowing natural thinking pauses during English speech | y |

**Open questions:** none - all resolved and confirmed above.

---

## User Stories

### P1: Core Spaced Repetition & Text Tutor Session ⭐ MVP

**User Story**: As an engineer studying English in Antigravity, I want to start a study session in text mode with deterministic FSRS card scheduling and SQLite persistence so that my review intervals and progress are never hallucinated or lost.

**Why P1**: Proves the entire Skill + MCP + SQLite + FSRS loop end-to-end before adding audio hardware complexity.

**Acceptance Criteria** (EARS notation):

1. WHEN the user asks to start an English study session THEN the system SHALL activate the `english-tutor` skill and call `start_session` to persist a new row in `study_sessions` with status `active`.
2. WHEN the `english-tutor` skill requests due cards via `get_due_cards` THEN the MCP server SHALL return cards from SQLite ordered by `due_at ASC` (overdue and due now first, followed by up to `new_cards_limit` `new` cards), filtered by optional `deck_slug`.
3. WHEN the user answers a flashcard and the tutor evaluates the response THEN the MCP server SHALL execute `submit_review` inside a SQLite transaction that computes the next `due_at`, `stability`, `difficulty`, and `fsrs_state` using `py-fsrs` and appends an immutable row to `review_logs`.
4. IF `submit_review` receives an invalid `rating` outside `{1, 2, 3, 4}` or an unknown `card_id` THEN the MCP server SHALL return a structured error with `error_code` (`INVALID_RATING` or `CARD_NOT_FOUND`) and leave SQLite state unchanged.
5. WHILE `input_mode` is `text` the `english-tutor` skill SHALL conduct both Active Recall (`active_review`) and Roleplay (`roleplay`) exercises strictly via Antigravity chat messages without invoking audio hardware tools.
6. The MCP server SHALL execute all pending SQLite schema migrations idempotently on startup with `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL`.

**Independent Test**: Run MCP server via stdio or pytest integration tests, seed 3 decks, start a session, query `get_due_cards`, submit ratings 1-4 via `submit_review`, and verify updated `due_at` and `review_logs` rows in SQLite.

---

### P2: Local Spoken Tutor Output via PipeWire TTS

**User Story**: As a learner practicing listening comprehension, I want the tutor's prompts and roleplay replies to be spoken aloud locally through my Ubuntu 24.04 PipeWire audio output so that I practice listening instead of only reading.

**Why P2**: Half of the Duolingo-style audio loop; independently testable without microphone capture and low risk.

**Acceptance Criteria** (EARS notation):

1. WHEN the tutor produces a spoken prompt in voice-enabled mode THEN the MCP server SHALL synthesize the text via `piper-tts` (`speak_text`) and play PCM audio to the default PipeWire sink via `sounddevice`.
2. WHEN `speak_text` is called with `speed` outside `[0.75, 1.25]` or empty `text` THEN the MCP server SHALL reject the call with `INVALID_ARGUMENT` before invoking synthesis.
3. IF the Piper `.onnx` voice model is missing or the PipeWire output device is unavailable THEN `speak_text` SHALL return a recoverable error (`TTS_MODEL_MISSING` or `AUDIO_OUTPUT_UNAVAILABLE`) with `fallback_hint: "text"` so the tutor continues seamlessly in text mode.
4. WHEN the user requests quiet mode or text-only output THEN the `english-tutor` skill SHALL suppress `speak_text` calls for the remainder of the session unless re-enabled.

**Independent Test**: Invoke `speak_text` with a sample English sentence on Ubuntu 24.04 PipeWire and verify audible playback and non-blocking/blocking timing; simulate missing `.onnx` path and verify `TTS_MODEL_MISSING` structured error.

---

### P3: Local Microphone Capture with VAD & Raw STT

**User Story**: As a learner practicing speaking, I want my microphone audio captured with automatic silence detection and transcribed locally preserving my real mistakes so the tutor hears what I actually said rather than an auto-corrected transcript.

**Why P3**: Completes the full hands-free voice conversation loop while preserving raw learner errors.

**Acceptance Criteria** (EARS notation):

1. WHEN the tutor calls `listen_and_transcribe` THEN the MCP server SHALL record 16kHz mono PCM from the PipeWire default source, apply Silero VAD speech endpointing, stop recording after `silence_timeout_ms` (default 1500ms) of trailing silence, and transcribe locally via `faster-whisper` (`compute_type="int8"`, `language="en"`).
2. The `listen_and_transcribe` tool SHALL return the verbatim `faster-whisper` transcript without LLM rewriting, grammar correction, or custom vocabulary biasing that masks learner errors.
3. IF no speech is detected within `initial_speech_timeout_ms` (default 10000ms) THEN `listen_and_transcribe` SHALL stop recording cleanly and return `speech_detected: false` with empty transcript and no error crash.
4. IF the PipeWire input source is missing, muted, or fails to open THEN `listen_and_transcribe` SHALL return `MICROPHONE_UNAVAILABLE` with `recoverable: true` and `fallback_hint: "text"`.
5. WHILE in a voice session, WHEN the user types a text message in chat or says they cannot speak THEN the `english-tutor` skill SHALL switch the active turn/session to text input without losing session history or card progress.
6. WHEN `listen_and_transcribe` exceeds `max_duration_ms` (default 45000ms) THEN the MCP server SHALL finalize capture at the bound, transcribe the captured buffer, and include `truncated_at_max_duration: true` in the response.

**Independent Test**: Feed a pre-recorded WAV fixture containing intentional English grammar errors into the VAD+Whisper pipeline to verify verbatim error preservation; test live PipeWire mic capture and simulate disconnected mic to verify `MICROPHONE_UNAVAILABLE`.

---

### P4: Post-Session Error Analysis & Automatic Card Extraction

**User Story**: As a learner finishing a conversation or review session, I want the tutor to log my recurring mistakes and automatically create or update spaced-repetition flashcards so I systematically eliminate repeated errors over time.

**Why P4**: Closes the continuous improvement loop between freeform roleplay and structured FSRS drills.

**Acceptance Criteria** (EARS notation):

1. WHEN a substantive learner turn occurs in `active_review` or `roleplay` THEN the `english-tutor` skill SHALL record the turn and detected mistakes via `log_turn_and_errors` into `session_turns` and `error_logs`.
2. WHEN `add_card` or error promotion receives a card whose normalized `front_prompt` (or `fingerprint_hash`) already exists in the target deck THEN the MCP server SHALL avoid creating a duplicate card, increment `occurrence_count` if linked to an error, and return `created: false` with the existing `card_id`.
3. WHEN the user ends a study session or requests wrap-up THEN the `english-tutor` skill SHALL review the session's `error_logs`, promote eligible new errors to flashcards via `add_card` (`source_type="auto_extracted"`), call `end_session`, and present a concise summary of reviewed cards, new cards added, and recurring error patterns.

**Independent Test**: Simulate a 4-turn roleplay containing a repeated preposition mistake, invoke `log_turn_and_errors` and `end_session`, and verify `error_logs.occurrence_count = 2` and exactly 1 `auto_extracted` card created in `cards`.

---

## Edge Cases & Implicit-Requirement Dimensions

- **Input validation & bounds**: IF `front_prompt` or `back_reference` exceeds 1000 characters, or `limit` in `get_due_cards` is outside `[1, 50]`, THEN the MCP server SHALL return `INVALID_ARGUMENT` with field details.
- **Failure / partial-failure states**: IF `faster-whisper` or `piper-tts` model loading fails during a tool call THEN the MCP server SHALL return a structured MCP tool error (`isError=true`, JSON payload with `error_code`, `recoverable`, `fallback_hint`) without crashing the `stdio` server process.
- **Idempotency / duplicate handling**: IF `submit_review` is retried with the same `idempotency_key` THEN the MCP server SHALL return the previously persisted review result without double-advancing FSRS state or duplicating `review_logs`.
- **Auth boundaries & rate limits**: N/A because SparkSpeak runs strictly as a local single-user `stdio` child process spawned by Antigravity on the user's workstation without network exposure.
- **Concurrency / ordering**: The MCP server SHALL serialize SQLite write transactions using `PRAGMA busy_timeout = 5000` and WAL mode, and enforce single-flight audio hardware access via an `asyncio.Lock` so `speak_text` and `listen_and_transcribe` never contend on PipeWire simultaneously.
- **Data lifecycle / expiry**: `review_logs`, `study_sessions`, and `session_turns` are retained indefinitely for FSRS optimization and learning history; suspended cards remain in SQLite with `suspended = 1` rather than hard-deleted so foreign-key auditability is preserved.
- **Observability**: The MCP server SHALL write all structured logs strictly to `stderr` (never `stdout`) so the MCP JSON-RPC `stdio` transport stream is never corrupted.
- **External-dependency failure**: IF audio models (Piper `.onnx` or Whisper weights) are not cached locally on first audio tool invocation THEN the MCP server SHALL return `MODEL_NOT_INSTALLED` with the exact CLI setup command (`uv run sparkspeak-setup-models`) rather than blocking the MCP turn with an opaque multi-minute download.
- **State-transition integrity**: IF `end_session` is called on a session already marked `ended` THEN the MCP server SHALL return the existing session summary idempotently without overwriting `ended_at`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| SRS-01 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| SRS-02 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| SRS-03 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| SRS-04 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| SKILL-01 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| DB-01 | P1: Core Spaced Repetition & Text Tutor Session | Tasks | Pending |
| AUDIO-01 | P2: Local Spoken Tutor Output via PipeWire TTS | Tasks | Pending |
| AUDIO-02 | P2: Local Spoken Tutor Output via PipeWire TTS | Tasks | Pending |
| AUDIO-03 | P3: Local Microphone Capture with VAD & Raw STT | Tasks | Pending |
| AUDIO-04 | P3: Local Microphone Capture with VAD & Raw STT | Tasks | Pending |
| AUDIO-05 | P3: Local Microphone Capture with VAD & Raw STT | Tasks | Pending |
| POST-01 | P4: Post-Session Error Analysis & Automatic Card Extraction | Tasks | Pending |
| POST-02 | P4: Post-Session Error Analysis & Automatic Card Extraction | Tasks | Pending |
| POST-03 | P4: Post-Session Error Analysis & Automatic Card Extraction | Tasks | Pending |

**Coverage:** 14 total, 14 mapped to tasks, 0 unmapped

---

## Sources

- Antigravity Customization System Docs: `.gemini/antigravity/builtin/skills/agy-customizations/docs/skills.md`, `mcp_servers.md`, `plugins.md`, `hooks.md`
- Community inspiration: `fluent-spaced-repetition-review` (`m98/fluent`) skill structure for agentic spaced-repetition tutoring
- FSRS Official Python SDK: `open-spaced-repetition/py-fsrs` (`fsrs` PyPI package)
- Local Audio Stack on Ubuntu 24.04: PipeWire 1.0.5, `faster-whisper` (CTranslate2 + Silero VAD), `piper-tts`, `sounddevice`

---

## Success Criteria

- [ ] User can complete a full 10-card text review + roleplay session in Antigravity with zero fabricated SRS dates and verified FSRS intervals in SQLite.
- [ ] On Ubuntu 24.04 PipeWire, `speak_text` plays intelligible English speech within < 500ms of synthesis start, and `listen_and_transcribe` captures spoken answers with Silero VAD endpointing while preserving verbatim grammatical mistakes.
- [ ] Switching mid-session from voice to text mode works in 1 turn without losing session state or corrupting `study_sessions`.
- [ ] Ending a session with repeated mistakes automatically populates `error_logs` and creates deduplicated `auto_extracted` flashcards in SQLite.
