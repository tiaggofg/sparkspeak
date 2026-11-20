# English Tutor Harness Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, the walk, check_proofs, the Verifier and the screens sub-agent).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/01-english-tutor-harness/design.md`
**Status**: Approved
**Approved**: 2026-11-20 - user: "aprovado, pode executar com subagentes"
**Build**: `uv run ruff check src tests; uv run mypy src; uv run pytest -v`
**Run unit**: `uv run pytest tests/unit -v`
**Run integration**: `uv run pytest tests/integration -v`

---

## Test Coverage Matrix

> Generated from project guidelines (`AGENTS.md`, `.agents/rules/post-implementation-testing.md`, `.agents/rules/feature-naming-and-quality.md`) and approved spec (`spec.md`). Provisional until tasks are approved.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Domain (`domain/srs_engine.py`, `models.py`, `errors.py`) | unit | All branches; 1:1 to spec ACs; all edge cases & bounds | `tests/unit/test_*.py` | `uv run pytest tests/unit -v` |
| Application Services (`application/*.py`) | unit | All orchestration branches, idempotency, lock serialization, fallback | `tests/unit/test_*.py` | `uv run pytest tests/unit -v` |
| SQLite Persistence & Migrations (`infrastructure/db/*.py`) | integration | Schema migrations, WAL/FK pragmas, transactions, deduplication | `tests/integration/test_sqlite_*.py` | `uv run pytest tests/integration -v` |
| Audio Adapters (`infrastructure/audio/*.py`) | unit + integration | Error paths, WAV fixture raw-error preservation, PipeWire probing | `tests/integration/test_whisper_*.py` | `uv run pytest tests/integration -v` |
| MCP Server & Stdio (`mcp/server.py`) | integration | Real stdio JSON-RPC roundtrip, stderr hygiene, structured errors | `tests/integration/test_mcp_stdio_protocol.py` | `uv run pytest tests/integration -v` |
| Config / Schema SQL / Skill / Plugin Manifests | none | Build/lint/validation gate only | - | `uv run ruff check src tests` |

## Gate Check Commands

> Generated from approved Python + `uv` stack - confirm before Execute.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After tasks with unit tests only | `uv run pytest tests/unit -v` |
| Full | After tasks with integration tests | `uv run pytest tests/unit tests/integration -v` |
| Build | After phase completion or config/schema-only tasks | `uv run ruff check src tests && uv run mypy src && uv run pytest -v` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Foundation, SQLite & FSRS Core

```
T1 → T2 → T3 → T4 → T5 → T6 → T7
```

### Phase 2: Text-Mode MCP Server & Antigravity Plugin

```
T8 → T9 → T10 → T11
```

### Phase 3: Offline TTS Output (Piper + PipeWire)

```
T12 → T13 → T14 → T15
```

### Phase 4: VAD + Raw STT Input & Post-Session Extraction

```
T16 → T17 → T18 → T19 → T20
```

---

## Task Breakdown

### T1: Bootstrap Python Project Manifest & Gitignore

**What**: Create `pyproject.toml` (dependencies `mcp`, `fsrs`, `faster-whisper`, `piper-tts`, `sounddevice`, `numpy`, dev tools `pytest`, `ruff`, `mypy`, console script entrypoints) and `.gitignore` ignoring `.data/` and Python caches.
**Where**: `pyproject.toml`
**Depends on**: None
**Reuses**: `.agents/scripts/quality-check.sh` ruff detection
**Requirement**: DB-01

**Done when**:

- [x] `pyproject.toml` declares Python `>=3.12`, dependencies, `ruff` & `mypy` config, and `sparkspeak-mcp` / `sparkspeak-setup-models` scripts
- [x] `.gitignore` excludes `.data/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- [x] `uv sync` resolves cleanly without errors
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

### T2: Define Config, Domain Models & Structured Error Envelope

**What**: Implement `config.py` (repo `.data/sparkspeak.db`, `.data/backups/`, `.data/models/`, `SPARKSPEAK_*` env overrides), `domain/models.py` DTOs, and `domain/errors.py` recoverable MCP error codes with unit tests.
**Where**: `src/sparkspeak/config.py`
**Depends on**: T1
**Reuses**: None
**Requirement**: SRS-04

**Done when**:

- [x] Path resolution defaults to `.data/sparkspeak.db` and honors `SPARKSPEAK_DB_PATH`
- [x] Structured error envelope serializes `error_code`, `message`, `recoverable`, `fallback_hint`, `details`
- [x] Unit tests in `tests/unit/test_config_and_errors.py` pass (4+ tests)
- [x] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T3: Implement Deterministic FSRS Engine Wrapper

**What**: Implement `domain/srs_engine.py` wrapping `py-fsrs` (`desired_retention=0.90`), rating validation `{1..4}`, and state mapping with comprehensive unit tests.
**Where**: `src/sparkspeak/domain/srs_engine.py`
**Depends on**: T2
**Reuses**: `src/sparkspeak/domain/models.py`
**Requirement**: SRS-03

**Done when**:

- [x] Computes next `due_at`, `stability`, `difficulty`, `fsrs_state`, `scheduled_days` deterministically for ratings 1-4
- [x] Rejects ratings outside `{1, 2, 3, 4}` with `INVALID_RATING` error
- [x] Unit tests in `tests/unit/test_srs_engine.py` pass (6+ tests covering New/Learning/Review/Relearning & invalid ratings)
- [x] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T4: Create Initial SQLite DDL & Seed Decks SQL

**What**: Write `001_initial.sql` (all 7 tables and 5 indexes from design) and `001_default_decks.sql` seeding `conversational`, `phrasal-verbs`, and `tech-meetings` decks with initial cards.
**Where**: `src/sparkspeak/infrastructure/db/migrations/001_initial.sql`
**Depends on**: T3
**Reuses**: None
**Requirement**: DB-01

**Done when**:

- [x] DDL defines `schema_migrations`, `decks`, `cards`, `study_sessions`, `review_logs`, `session_turns`, `error_logs` and all 5 indexes
- [x] Seed SQL inserts 3 decks (`conversational`, `phrasal-verbs`, `tech-meetings`) and starter cards idempotently
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

### T5: Implement SQLite Connection Manager & Idempotent Migrator

**What**: Implement `connection.py` (`PRAGMA foreign_keys = ON`, `journal_mode = WAL`, `busy_timeout = 5000`) and `migrator.py` (sequential SQL runner, timestamped `.data/backups/` snapshot, seed loader) with integration tests.
**Where**: `src/sparkspeak/infrastructure/db/migrator.py`
**Depends on**: T4
**Reuses**: `src/sparkspeak/config.py`
**Requirement**: DB-01

**Done when**:

- [x] Running migrator twice on fresh and existing DBs is idempotent and enforces WAL + foreign keys
- [x] Backup file is created in `.data/backups/` before applying pending migrations to an existing DB
- [x] Integration tests in `tests/integration/test_sqlite_migrations.py` pass (4+ tests)
- [x] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T6: Implement SQLite Repositories for Decks, Cards, Reviews & Sessions

**What**: Implement `repositories.py` covering due-queue queries (`due_at ASC`, `new_cards_limit`), transactional `submit_review` with `idempotency_key`, deduplicated `add_card`, `study_sessions`, `session_turns`, and `error_logs` upserts.
**Where**: `src/sparkspeak/infrastructure/db/repositories.py`
**Depends on**: T5
**Reuses**: `src/sparkspeak/domain/models.py`
**Requirement**: SRS-01, SRS-02, SRS-03, POST-02

**Done when**:

- [x] `get_due_cards` returns due reviews ordered by `due_at ASC` before up to `new_cards_limit` unseen cards
- [x] `submit_review` updates `cards` and inserts `review_logs` atomically, returning cached output on duplicate `idempotency_key`
- [x] `add_card` deduplicates by `(deck_id, normalized_front)` returning `created: false` on conflict
- [x] Integration tests in `tests/integration/test_sqlite_repositories.py` pass (6+ tests)
- [x] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T7: Implement Review & Session Application Services

**What**: Implement `review_service.py` (bounds validation for `limit`, `front_prompt`, `back_reference`, FSRS scheduling orchestration) and `session_service.py` (`start_session`, idempotent `end_session`) with unit tests.
**Where**: `src/sparkspeak/application/review_service.py`
**Depends on**: T6
**Reuses**: `src/sparkspeak/domain/srs_engine.py`
**Requirement**: SRS-01, SRS-02, SRS-03, SRS-04

**Done when**:

- [x] Input validation enforces `limit in [1, 50]`, text length `<= 1000`, valid `rating`
- [x] `end_session` is idempotent on already-ended sessions
- [x] Unit tests in `tests/unit/test_review_and_session_service.py` pass (7+ tests)
- [x] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T8: Implement Stdio MCP Server Entrypoint (Phase 1 Tools)

**What**: Implement `mcp/server.py` using `mcp.server.MCPServer` over `stdio`, redirecting all logging to `stderr`, exposing `start_session`, `get_due_cards`, `submit_review`, `add_card`, `end_session` with structured `isError` responses.
**Where**: `src/sparkspeak/mcp/server.py`
**Depends on**: None
**Reuses**: `src/sparkspeak/application/review_service.py`
**Requirement**: SRS-01, SRS-02, SRS-03, SRS-04

**Done when**:

- [x] Zero non-JSON-RPC bytes are emitted to `stdout` during server startup and tool execution
- [x] Integration test `tests/integration/test_mcp_stdio_protocol.py` spawns `sparkspeak-mcp` over stdio and completes `start_session` -> `get_due_cards` -> `submit_review` -> `end_session` (4+ tests)
- [x] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T9: Configure Antigravity Workspace Plugin & MCP Config

**What**: Create `.agents/plugins/sparkspeak/plugin.json` and `mcp_config.json` registering `uv run --directory . sparkspeak-mcp` for the project workspace.
**Where**: `.agents/plugins/sparkspeak/mcp_config.json`
**Depends on**: T8
**Reuses**: `.gemini/antigravity/builtin/skills/agy-customizations/docs/plugins.md`
**Requirement**: SKILL-01

**Done when**:

- [x] `plugin.json` and `mcp_config.json` validate as well-formed JSON matching Antigravity plugin schema
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

### T10: Author English Tutor `SKILL.md` (Text Mode MVP)

**What**: Create `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` defining progressive-disclosure triggers, `active_review` and `roleplay` loops, FSRS rating rubric, and strict anti-hallucination rule for MCP review dates.
**Where**: `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`
**Depends on**: T9
**Reuses**: `docs/adr/0005-antigravity-workspace-plugin.md`
**Requirement**: SKILL-01

**Done when**:

- [x] `SKILL.md` includes valid YAML frontmatter (`name: english-tutor`, descriptive trigger `description`)
- [x] Covers `active_review`, `roleplay`, text-only fallback, and mandatory `submit_review` / `end_session` calls
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

### T11: Create Pedagogical Reference Guides for Progressive Disclosure

**What**: Author `references/pedagogy-modes.md`, `references/personas.md`, and `references/error-taxonomy.md` under the `english-tutor` skill directory.
**Where**: `.agents/plugins/sparkspeak/skills/english-tutor/references/pedagogy-modes.md`
**Depends on**: T10
**Reuses**: `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`
**Requirement**: SKILL-01

**Done when**:

- [x] Reference files document the 1-4 FSRS rating rubric, 3 deck personas (`conversational`, `phrasal-verbs`, `tech-meetings`), and error classification categories
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

### T12: Define Audio Ports & Single-Flight AudioLock Service

**What**: Implement `infrastructure/audio/ports.py` (`TTSEngine`, `STTEngine` protocols) and `application/audio_service.py` with `asyncio.Lock` serializing TTS and STT calls.
**Where**: `src/sparkspeak/application/audio_service.py`
**Depends on**: None
**Reuses**: `src/sparkspeak/domain/errors.py`
**Requirement**: AUDIO-01, AUDIO-03

**Done when**:

- [ ] Concurrent TTS/STT invocations serialize cleanly under `asyncio.Lock`
- [ ] Validates `speed in [0.75, 1.25]` and non-empty `text`, raising `INVALID_ARGUMENT` otherwise
- [ ] Unit tests in `tests/unit/test_audio_service.py` pass (5+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T13: Implement PipeWire Device Probing & Piper TTS Adapter

**What**: Implement `infrastructure/audio/pipewire_device.py` (`sounddevice` output/input capability probe & playback) and `piper_tts.py` (`PiperVoice` ONNX synthesis with `TTS_MODEL_MISSING` / `AUDIO_OUTPUT_UNAVAILABLE` errors).
**Where**: `src/sparkspeak/infrastructure/audio/piper_tts.py`
**Depends on**: T12
**Reuses**: `src/sparkspeak/infrastructure/audio/ports.py`
**Requirement**: AUDIO-01, AUDIO-02

**Done when**:

- [ ] Missing `.onnx` model raises recoverable `TTS_MODEL_MISSING` with `fallback_hint: "text"`
- [ ] Unavailable PipeWire sink raises recoverable `AUDIO_OUTPUT_UNAVAILABLE` with `fallback_hint: "text"`
- [ ] Unit tests in `tests/unit/test_piper_tts.py` pass (4+ tests with mocked `sounddevice`/model)
- [ ] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T14: Implement Model Setup & Audio Healthcheck CLI

**What**: Create `cli/setup_models.py` providing `sparkspeak-setup-models` (downloads `en_US-lessac-medium.onnx` + `.json` and pre-caches `faster-whisper` `base` model into `.data/models/`) and `sparkspeak-health` PipeWire check.
**Where**: `src/sparkspeak/cli/setup_models.py`
**Depends on**: T13
**Reuses**: `src/sparkspeak/config.py`
**Requirement**: AUDIO-02

**Done when**:

- [ ] `sparkspeak-health` checks `.data/models/` and PipeWire devices and outputs JSON status without crashing on missing devices
- [ ] Unit tests in `tests/unit/test_cli_setup.py` pass (2+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T15: Expose `speak_text` & `get_audio_status` MCP Tools and Quiet-Mode Skill Rules

**What**: Register `speak_text` and `get_audio_status` in `mcp/server.py`, include `audio_status` in `start_session`, and update `SKILL.md` for voice output + quiet-mode suppression.
**Where**: `src/sparkspeak/mcp/server.py`
**Depends on**: T14
**Reuses**: `src/sparkspeak/application/audio_service.py`
**Requirement**: AUDIO-01, AUDIO-02

**Done when**:

- [ ] `speak_text` rejects invalid speed/empty text with `INVALID_ARGUMENT` and returns `TTS_MODEL_MISSING` cleanly over MCP stdio
- [ ] Integration tests in `tests/integration/test_mcp_tts_tool.py` pass (3+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T16: Implement 16kHz Capture + Silero VAD Endpointing & Faster-Whisper STT

**What**: Implement `infrastructure/audio/whisper_stt.py` recording 16kHz mono PCM via `sounddevice`, applying Silero VAD (`silence_timeout_ms=1500`, `initial_speech_timeout_ms=10000`, `max_duration_ms=45000`), and transcribing verbatim via `faster-whisper` (`int8`, `language="en"`).
**Where**: `src/sparkspeak/infrastructure/audio/whisper_stt.py`
**Depends on**: None
**Reuses**: `src/sparkspeak/infrastructure/audio/pipewire_device.py`
**Requirement**: AUDIO-03, AUDIO-04

**Done when**:

- [ ] Preserves intentional learner grammar errors verbatim from WAV fixture in `tests/fixtures/audio/`
- [ ] Returns `speech_detected: false` cleanly on initial silence timeout and `truncated_at_max_duration: true` at max duration
- [ ] Raises `MICROPHONE_UNAVAILABLE` when input device fails to open
- [ ] Integration test `tests/integration/test_whisper_wav_fixture.py` passes (4+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T17: Expose `listen_and_transcribe` MCP Tool & Voice-to-Text Fallback

**What**: Register `listen_and_transcribe` in `mcp/server.py` and update `SKILL.md` to handle seamless voice-to-text switching on `MICROPHONE_UNAVAILABLE`, consecutive `speech_detected: false`, or user text override.
**Where**: `src/sparkspeak/mcp/server.py`
**Depends on**: T16
**Reuses**: `src/sparkspeak/application/audio_service.py`
**Requirement**: AUDIO-03, AUDIO-04, AUDIO-05

**Done when**:

- [ ] `listen_and_transcribe` returns structured `MICROPHONE_UNAVAILABLE` (`fallback_hint: "text"`) on mocked missing mic over MCP stdio
- [ ] Integration tests in `tests/integration/test_mcp_stt_tool.py` pass (3+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T18: Implement Turn & Error Logging with Fingerprint Deduplication

**What**: Add `log_turn_and_errors` orchestration in `session_service.py` computing SHA-256 `fingerprint_hash` over `(deck_id, category, normalized_correction)` and upserting `error_logs.occurrence_count`.
**Where**: `src/sparkspeak/application/session_service.py`
**Depends on**: T17
**Reuses**: `src/sparkspeak/infrastructure/db/repositories.py`
**Requirement**: POST-01, POST-02

**Done when**:

- [ ] Repeated mistakes increment `error_logs.occurrence_count` instead of creating duplicate error patterns
- [ ] Integration tests in `tests/integration/test_error_logging_and_promotion.py` pass (4+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T19: Implement Post-Session Automatic Card Extraction in `end_session`

**What**: Extend `end_session` in `session_service.py` and `mcp/server.py` to promote eligible session `error_logs` to `cards` (`source_type="auto_extracted"`) via deduplicated `add_card` and return session metrics + promoted cards.
**Where**: `src/sparkspeak/application/session_service.py`
**Depends on**: T18
**Reuses**: `src/sparkspeak/application/review_service.py`
**Requirement**: POST-02, POST-03

**Done when**:

- [ ] Calling `end_session(promote_errors=true)` creates at most 1 `auto_extracted` card per unique error and populates `error_logs.promoted_card_id`
- [ ] Updates `study_sessions.ended_at`, `cards_reviewed`, `errors_extracted` idempotently
- [ ] Integration tests in `tests/integration/test_post_session_extraction.py` pass (4+ tests)
- [ ] Gate check passes: `uv run pytest tests/unit tests/integration -v`

**Tests**: integration
**Gate**: full

---

### T20: Update Skill Closure Protocol, Docs & Quality Gate Verification

**What**: Update `SKILL.md` for `log_turn_and_errors` + `end_session(promote_errors=true)` post-session summary, sync `README.md` / `docs/` Mermaid diagrams & contracts, and pass `.agents/scripts/quality-check.sh --up` plus live PipeWire verification.
**Where**: `docs/README.md`
**Depends on**: T19
**Reuses**: `docs/arquitetura-c4.md`
**Requirement**: POST-01, POST-03

**Done when**:

- [ ] `docs/` (`arquitetura-c4.md`, `modelo-dominio-e-dados.md`, `fluxos-e-sequencias.md`, `seguranca-e-privacidade.md`, `deploy-e-ci-cd.md`) and `README.md` match implemented code and SQLite schema
- [ ] `.agents/scripts/quality-check.sh --up` exits `0` (lint + SonarQube Quality Gate `OK`)
- [ ] Live PipeWire TTS + STT check passes on Ubuntu 24.04
- [ ] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: none
**Gate**: build

---

## Checks

**C1** - `start_session` persists an active `study_sessions` row in SQLite (SRS-01, AC 1)
Proof: run integration | PASSED tests/integration/test_mcp_stdio_protocol.py::test_start_session_persists_active_row

**C2** - `get_due_cards` orders overdue/due cards by `due_at ASC` before `new` cards up to `new_cards_limit` (SRS-02, AC 2)
Proof: run integration | PASSED tests/integration/test_sqlite_repositories.py::test_get_due_cards_orders_due_before_new

**C3** - `submit_review` updates FSRS state transactionally and inserts an immutable `review_logs` row (SRS-03, AC 3)
Proof: run integration | PASSED tests/integration/test_sqlite_repositories.py::test_submit_review_updates_fsrs_and_logs

**C4** - `submit_review` rejects invalid rating outside `{1..4}` with `INVALID_RATING` and leaves DB unchanged (SRS-04, AC 4)
Proof: run unit | PASSED tests/unit/test_srs_engine.py::test_invalid_rating_raises_without_mutation

**C5** - Text mode session runs `active_review` and `roleplay` without calling audio hardware tools (SKILL-01, AC 5)
Proof: run integration | PASSED tests/integration/test_mcp_stdio_protocol.py::test_text_mode_never_invokes_audio

**C6** - SQLite migrations run idempotently on startup with `foreign_keys=ON` and `journal_mode=WAL` (DB-01, AC 6)
Proof: run integration | PASSED tests/integration/test_sqlite_migrations.py::test_migrations_idempotent_wal_fk

**C7** - `speak_text` synthesizes English audio via `piper-tts` and sends PCM to PipeWire sink (AUDIO-01, AC 1)
Proof: run unit | PASSED tests/unit/test_piper_tts.py::test_speak_text_plays_pcm_to_device

**C8** - `speak_text` rejects out-of-range speed or empty text with `INVALID_ARGUMENT` and returns `TTS_MODEL_MISSING` when `.onnx` is absent (AUDIO-02, AC 2-3)
Proof: run integration | PASSED tests/integration/test_mcp_tts_tool.py::test_speak_text_validation_and_missing_model

**C9** - `listen_and_transcribe` captures 16kHz PCM with Silero VAD endpointing and preserves verbatim learner grammar mistakes (AUDIO-03, AC 1-2)
Proof: run integration | PASSED tests/integration/test_whisper_wav_fixture.py::test_verbatim_error_preservation

**C10** - `listen_and_transcribe` returns `speech_detected: false` on silence timeout, `truncated_at_max_duration: true` at cap, and `MICROPHONE_UNAVAILABLE` when input device fails (AUDIO-04, AC 3-4, 6)
Proof: run integration | PASSED tests/integration/test_mcp_stt_tool.py::test_stt_timeouts_and_missing_mic

**C11** - Switching mid-session from voice to text preserves active session state and card progress (AUDIO-05, AC 5)
Proof: run unit | PASSED tests/unit/test_review_and_session_service.py::test_voice_to_text_switch_preserves_session

**C12** - `log_turn_and_errors` persists turns and increments `occurrence_count` on repeated errors (POST-01, AC 1)
Proof: run integration | PASSED tests/integration/test_error_logging_and_promotion.py::test_repeated_error_increments_count

**C13** - `add_card` deduplicates by normalized `front_prompt` returning `created: false` and existing `card_id` (POST-02, AC 2)
Proof: run integration | PASSED tests/integration/test_sqlite_repositories.py::test_add_card_deduplicates_normalized_front

**C14** - `end_session(promote_errors=true)` extracts eligible session errors into `auto_extracted` flashcards and records summary metrics (POST-03, AC 3)
Proof: run integration | PASSED tests/integration/test_post_session_extraction.py::test_end_session_promotes_errors_once

---

## Handoff

The feature's live state, written as it happens - a compaction gives no warning.

**Settled mid-build:** none
**Dispatched:** batch-1 (Phase 1: T1-T7) returned; batch-2 (Phase 2-3: T8-T15)
**Walked:** none

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4

Phase 1: T1 → T2 → T3 → T4 → T5 → T6 → T7
Phase 2: T8 → T9 → T10 → T11
Phase 3: T12 → T13 → T14 → T15
Phase 4: T16 → T17 → T18 → T19 → T20
```
