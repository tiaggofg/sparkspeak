# Multimodal WAV Input & Native Voice Output Refactoring Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, the walk, check_proofs, the Verifier and the screens sub-agent).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/02-native-voice-refactoring/spec.md`
**Status**: Completed (Approved by user)
**Build**: `uv run ruff check src tests; uv run mypy src; uv run pytest -v`
**Run unit**: `uv run pytest tests/unit tests/test_smoke.py -v`
**Run integration**: `uv run pytest tests/integration -v`

---

## Test Coverage Matrix

> Generated from project guidelines (`AGENTS.md`, `.agents/rules/post-implementation-testing.md`, `.agents/rules/feature-naming-and-quality.md`) and approved spec (`spec.md`).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Config & Domain Errors (`config.py`, `domain/errors.py`) | unit | All path resolution overrides (`audio_dir`) and pruned `ErrorCode` enum values | `tests/unit/test_config_and_errors.py` | `uv run pytest tests/unit -v` |
| WAV Audio Capture (`infrastructure/audio/wav_recorder.py`, `pipewire_device.py`, `ports.py`) | unit | RMS speech endpointing, 200ms pre-roll, silence timeout, max duration cap, atomic 16kHz 16-bit WAV write, missing mic error | `tests/unit/test_wav_recorder.py` | `uv run pytest tests/unit -v` |
| Application Services (`application/audio_service.py`, `session_service.py`, `review_service.py`) | unit | `record_utterance` bounds & `asyncio.Lock` serialization, `log_mistake` delegation, `mic_available` in `start_session` | `tests/unit/test_*.py` | `uv run pytest tests/unit -v` |
| MCP Server & Stdio (`mcp/server.py`) | integration | Removed tools rejected, `record_utterance`, `log_mistake`, compact `start_session` / `get_due_cards` / `submit_review` payloads, stdout JSON-RPC hygiene | `tests/integration/test_mcp_*.py` | `uv run pytest tests/integration -v` |
| Manifest, Skill & Architecture Docs (`pyproject.toml`, `SKILL.md`, `docs/`) | unit | Smoke assertions on `pyproject.toml` dependency pruning and `SKILL.md` multimodal protocol invariants | `tests/test_smoke.py` | `uv run pytest tests/test_smoke.py -v` |

## Gate Check Commands

> Generated from codebase (`pyproject.toml` + `uv`) - confirm before Execute.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After tasks with unit tests only | `uv run pytest tests/unit tests/test_smoke.py -v` |
| Full | After tasks with integration tests | `uv run pytest tests/unit tests/integration tests/test_smoke.py -v` |
| Build | After phase completion or final docs/quality task | `uv run ruff check src tests && uv run mypy src && uv run pytest -v` |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Audio Pipeline Pruning & Lightweight WAV Recorder

```
T1 → T2 → T3 → T4
```

### Phase 2: Lean MCP Server Contract, `log_mistake` & Multimodal Skill

```
T5 → T6 → T7 → T8
```

---

## Task Breakdown

### T1: Prune Heavy STT/TTS Dependencies & Obsolete CLI/Audio Modules

**What**: Remove `faster-whisper` and `piper-tts` dependencies and `sparkspeak-setup-models` / `sparkspeak-health` scripts from `pyproject.toml`, delete `piper_tts.py`, `whisper_stt.py`, `src/sparkspeak/cli/`, and their obsolete test files (`test_piper_tts.py`, `test_cli_setup.py`, `test_mcp_tts_tool.py`, `test_whisper_wav_fixture.py`), and add manifest pruning assertions to `tests/test_smoke.py`.
**Where**: `pyproject.toml`
**Depends on**: None
**Reuses**: `tests/test_smoke.py`
**Requirement**: REFAC-01, REFAC-02

**Done when**:

- [x] `pyproject.toml` lists only `mcp>=1.0.0`, `fsrs>=4.0.0`, `sounddevice>=0.5.0`, and `numpy>=1.26.0` in `[project].dependencies` and only `sparkspeak-mcp` in `[project.scripts]`
- [x] `src/sparkspeak/infrastructure/audio/piper_tts.py`, `src/sparkspeak/infrastructure/audio/whisper_stt.py`, and `src/sparkspeak/cli/` are deleted
- [x] Obsolete test files `tests/unit/test_piper_tts.py`, `tests/unit/test_cli_setup.py`, `tests/integration/test_mcp_tts_tool.py`, and `tests/integration/test_whisper_wav_fixture.py` are deleted
- [x] `tests/test_smoke.py` asserts `faster-whisper` and `piper-tts` are absent from `pyproject.toml`
- [x] Gate check passes: `uv run pytest tests/test_smoke.py -v`

**Tests**: unit
**Gate**: quick

---

### T2: Update Config (`audio_dir`), Error Codes & Audio Port Protocols

**What**: Replace `models_dir` (`SPARKSPEAK_MODELS_DIR`) with `audio_dir` (`SPARKSPEAK_AUDIO_DIR`, default `.data/audio`) in `config.py`, remove obsolete TTS/model `ErrorCode` values in `domain/errors.py`, update `infrastructure/audio/ports.py` (`UtteranceRecorder`, `RecordUtteranceResult`), and remove `play_pcm` / output sink probes from `pipewire_device.py`.
**Where**: `src/sparkspeak/config.py`
**Depends on**: T1
**Reuses**: `src/sparkspeak/domain/errors.py`
**Requirement**: REFAC-01, AUDIO-05

**Done when**:

- [x] `SparkSpeakConfig` resolves `audio_dir` (default `<root>/.data/audio`, override `SPARKSPEAK_AUDIO_DIR`) and no longer defines `models_dir`
- [x] `ErrorCode` contains only `INVALID_ARGUMENT`, `INVALID_RATING`, `CARD_NOT_FOUND`, `DECK_NOT_FOUND`, `SESSION_NOT_FOUND`, and `MICROPHONE_UNAVAILABLE`
- [x] `ports.py` defines `RecordUtteranceResult` (`speech_detected`, `wav_path`, `duration_ms`, `peak_rms`, `truncated_at_max_duration`) and `UtteranceRecorder` protocol
- [x] Unit tests in `tests/unit/test_config_and_errors.py` pass (5+ tests)
- [x] Gate check passes: `uv run pytest tests/unit/test_config_and_errors.py -v`

**Tests**: unit
**Gate**: quick

---

### T3: Implement Lightweight 16kHz Mono PCM `WavRecorder` with RMS Endpointing

**What**: Create `src/sparkspeak/infrastructure/audio/wav_recorder.py` capturing 16 kHz mono PCM via `sounddevice`, applying `numpy` RMS silence endpointing with a 200 ms pre-roll buffer, and writing atomic 16-bit PCM WAV files to `.data/audio/last_utterance.wav` with comprehensive unit tests.
**Where**: `src/sparkspeak/infrastructure/audio/wav_recorder.py`
**Depends on**: T2
**Reuses**: `src/sparkspeak/infrastructure/audio/pipewire_device.py`
**Requirement**: AUDIO-05

**Done when**:

- [x] `WavRecorder` detects speech when frame RMS `>= rms_threshold`, retains pre-roll frames, stops after `silence_timeout_ms` of trailing silence, and writes valid 16 kHz mono 16-bit PCM WAV to `audio_dir / "last_utterance.wav"`
- [x] Returns `speech_detected=False`, `wav_path=None`, `duration_ms=0` when no speech occurs within `initial_speech_timeout_ms`
- [x] Caps recording at `max_duration_ms` with `truncated_at_max_duration=True` and raises `MICROPHONE_UNAVAILABLE` (`fallback_hint="text"`) on missing input stream
- [x] Unit tests in `tests/unit/test_wav_recorder.py` pass (5+ tests)
- [x] Gate check passes: `uv run pytest tests/unit/test_wav_recorder.py -v`

**Tests**: unit
**Gate**: quick

---

### T4: Refactor `AudioService` for Single-Flight `record_utterance` Capture

**What**: Update `src/sparkspeak/application/audio_service.py` to remove `speak_text`, `listen_and_transcribe`, and `get_audio_status`, and expose `record_utterance` (serialized under `asyncio.Lock` with timeout bounds validation) and `is_mic_available()`.
**Where**: `src/sparkspeak/application/audio_service.py`
**Depends on**: T3
**Reuses**: `src/sparkspeak/infrastructure/audio/ports.py`
**Requirement**: REFAC-02, AUDIO-05

**Done when**:

- [x] `AudioService.record_utterance` validates `silence_timeout_ms in [500, 5000]`, `initial_speech_timeout_ms in [2000, 30000]`, and `max_duration_ms in [3000, 90000]`
- [x] Concurrent `record_utterance` calls serialize under `asyncio.Lock`
- [x] Unit tests in `tests/unit/test_audio_service.py` pass (4+ tests)
- [x] Gate check passes: `uv run pytest tests/unit -v`

**Tests**: unit
**Gate**: quick

---

### T5: Add `log_mistake` & `mic_available` to `SessionService`

**What**: Update `src/sparkspeak/application/session_service.py` to replace `audio_status` in `start_session` / `StartSessionResult` with `mic_available: bool` and add flat `log_mistake(...)` method for low-latency error logging with SHA-256 fingerprint deduplication.
**Where**: `src/sparkspeak/application/session_service.py`
**Depends on**: None
**Reuses**: `src/sparkspeak/infrastructure/db/repositories.py`
**Requirement**: SRS-05, SRS-07

**Done when**:

- [x] `start_session` accepts `mic_available: bool = False` and returns `StartSessionResult` with `mic_available` instead of `audio_status`
- [x] `SessionService.log_mistake` validates inputs, logs the learner turn, and upserts the error in `error_logs` (incrementing `occurrence_count` on repeated fingerprint)
- [x] Unit tests in `tests/unit/test_review_and_session_service.py` and integration tests in `tests/integration/test_error_logging_and_promotion.py` pass
- [x] Gate check passes: `uv run pytest tests/unit tests/test_smoke.py -v`

**Tests**: unit
**Gate**: quick

---

### T6: Refactor Stdio MCP Server Contract for Lean Payloads & `record_utterance`

**What**: Update `src/sparkspeak/mcp/server.py` to remove `speak_text`, `listen_and_transcribe`, and `get_audio_status`, expose `record_utterance` and `log_mistake`, compact the payloads of `start_session`, `get_due_cards`, and `submit_review`, and update stdio MCP integration tests.
**Where**: `src/sparkspeak/mcp/server.py`
**Depends on**: T5
**Reuses**: `src/sparkspeak/application/audio_service.py`
**Requirement**: REFAC-01, REFAC-02, AUDIO-05, SRS-05, SRS-06, SRS-07

**Done when**:

- [x] `list_tools` exposes exactly `start_session`, `get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `log_turn_and_errors`, `end_session`, and `record_utterance` (zero TTS/STT tools)
- [x] `get_due_cards` and `submit_review` return the lean JSON schemas from Section 3 of `spec.md`
- [x] Integration tests in `tests/integration/test_mcp_stdio_protocol.py` and `tests/integration/test_mcp_stt_tool.py` pass
- [x] Gate check passes: `uv run pytest tests/unit tests/integration tests/test_smoke.py -v`

**Tests**: integration
**Gate**: full

---

### T7: Update `english-tutor` `SKILL.md` & References for Multimodal WAV + Antigravity Voice

**What**: Rewrite `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` and update `references/` for the `record_utterance` -> `read_file(wav_path)` multimodal pronunciation/grammar workflow, Antigravity Voice output brevity rules, silent background `log_mistake` / `submit_review` logging, and text-mode fallback.
**Where**: `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`
**Depends on**: T6
**Reuses**: `.agents/plugins/sparkspeak/skills/english-tutor/references/error-taxonomy.md`
**Requirement**: SKILL-02, SKILL-03

**Done when**:

- [x] `SKILL.md` specifies `record_utterance` -> `read_file(Path=wav_path)` multimodal audio evaluation, pronunciation nuances rubric (`-ed`, vowel epenthesis, `/θ/`, word stress), Antigravity Voice brevity rules, and `log_mistake` usage
- [x] `SKILL.md` contains zero references to removed tools `speak_text`, `listen_and_transcribe`, or `get_audio_status`
- [x] Smoke test in `tests/test_smoke.py` verifies `SKILL.md` contract invariants
- [x] Gate check passes: `uv run pytest tests/unit tests/test_smoke.py -v`

**Tests**: unit
**Gate**: quick

---

### T8: Sync ADRs (`ADR-0006`), Technical Documentation & Final Quality Check

**What**: Create `docs/adr/0006-multimodal-wav-input-and-native-voice-output.md` (marking `ADR-0004` as Superseded), update `README.md`, `docs/*.md`, and `.specs/STATE.md` to match the v0.2 multimodal WAV + Antigravity Voice architecture, and run the full build/lint/typecheck/test gate.
**Where**: `docs/adr/0006-multimodal-wav-input-and-native-voice-output.md`
**Depends on**: T7
**Reuses**: `docs/adr/0004-offline-pipewire-audio-pipeline.md`
**Requirement**: REFAC-01, SKILL-02

**Done when**:

- [x] `docs/adr/0006-multimodal-wav-input-and-native-voice-output.md` is created and `docs/adr/0004-offline-pipewire-audio-pipeline.md` + `docs/adr/README.md` + `.specs/STATE.md` mark `AD-004` as superseded by `AD-006`
- [x] `README.md` and `docs/` (`arquitetura-c4.md`, `fluxos-e-sequencias.md`, `modelo-dominio-e-dados.md`, `deploy-e-ci-cd.md`) reflect `record_utterance` + `read_file` + Antigravity Voice and `log_mistake`
- [x] Gate check passes: `uv run ruff check src tests && uv run mypy src && uv run pytest -v`

**Tests**: integration
**Gate**: build

---

## Checks

**C1** - `pyproject.toml` removes `faster-whisper` and `piper-tts` and retains only `mcp`, `fsrs`, `sounddevice`, and `numpy` (REFAC-01, AC 1)
Proof: run unit | tests/test_smoke.py::test_pyproject_removes_heavy_stt_tts_dependencies PASSED

**C2** - The MCP server `list_tools` exposes `record_utterance` and `log_mistake` and does not expose `speak_text`, `listen_and_transcribe`, or `get_audio_status` (REFAC-02, AC 2)
Proof: run integration | tests/integration/test_mcp_stdio_protocol.py::test_list_tools_exposes_lean_multimodal_contract PASSED

**C3** - `record_utterance` captures 16kHz mono PCM with RMS endpointing and writes a valid 16-bit WAV file to `.data/audio/last_utterance.wav` (AUDIO-05, AC 3)
Proof: run unit | tests/unit/test_wav_recorder.py::test_wav_recorder_writes_16k_mono_wav_with_preroll_and_silence_cutoff PASSED

**C4** - `record_utterance` returns `speech_detected: false` on silence timeout and `MICROPHONE_UNAVAILABLE` with `fallback_hint: "text"` when mic input fails (AUDIO-05, AC 4-5)
Proof: run integration | tests/integration/test_mcp_stt_tool.py::test_record_utterance_timeouts_and_missing_mic PASSED

**C5** - `start_session` persists an active `study_sessions` row and returns `mic_available` and `due_summary` without `audio_status` (SRS-05, AC 1)
Proof: run integration | tests/integration/test_mcp_stdio_protocol.py::test_start_session_persists_active_row PASSED

**C6** - `get_due_cards` and `submit_review` return compact JSON payloads and persist deterministic FSRS scheduling and immutable `review_logs` in SQLite (SRS-06, AC 2-3)
Proof: run integration | tests/integration/test_sqlite_repositories.py::test_submit_review_updates_fsrs_and_logs PASSED

**C7** - `log_mistake` records a learner turn and upserts `error_logs` with SHA-256 fingerprint deduplication, and `end_session` promotes unpromoted errors to `auto_extracted` flashcards (SRS-07, AC 4-5)
Proof: run integration | tests/integration/test_error_logging_and_promotion.py::test_log_mistake_upserts_and_increments_occurrence_count PASSED

**C8** - `english-tutor` `SKILL.md` specifies the `record_utterance` -> `read_file` multimodal pronunciation flow, Antigravity Voice output brevity rules, silent `log_mistake` calls, and text-mode fallback (SKILL-02, SKILL-03, AC 1-4)
Proof: run unit | tests/test_smoke.py::test_skill_md_defines_multimodal_wav_and_voice_output_workflow PASSED

---

## Handoff

The feature's live state, written as it happens - a compaction gives no warning.

**Settled mid-build:** none
**Dispatched:** none
**Walked:** none

---

## Phase Execution Map

```
Phase 1 → Phase 2

Phase 1: T1 → T2 → T3 → T4
Phase 2: T5 → T6 → T7 → T8
```

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: Prune heavy STT/TTS dependencies & obsolete files | Manifest + file deletions + smoke test | ✅ Granular |
| T2: Update Config (`audio_dir`), ErrorCodes & Audio Ports | Config + error enum + port DTOs | ✅ Granular |
| T3: Implement `WavRecorder` with RMS endpointing | 1 adapter module (`wav_recorder.py`) + unit test | ✅ Granular |
| T4: Refactor `AudioService` for `record_utterance` | 1 service module (`audio_service.py`) + unit test | ✅ Granular |
| T5: Add `log_mistake` & `mic_available` to `SessionService` | 1 service module (`session_service.py`) + unit test | ✅ Granular |
| T6: Refactor Stdio MCP Server contract | 1 entrypoint module (`mcp/server.py`) + integration test | ✅ Granular |
| T7: Update `english-tutor` `SKILL.md` & references | Skill instructions + smoke test | ✅ Granular |
| T8: Sync `ADR-0006`, technical docs & final quality check | ADR + docs sync + full build gate | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | Start of Phase 1 | ✅ Match |
| T2 | T1 | `T1 → T2` | ✅ Match |
| T3 | T2 | `T2 → T3` | ✅ Match |
| T4 | T3 | `T3 → T4` | ✅ Match |
| T5 | None | Start of Phase 2 | ✅ Match |
| T6 | T5 | `T5 → T6` | ✅ Match |
| T7 | T6 | `T6 → T7` | ✅ Match |
| T8 | T7 | `T7 → T8` | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1 | Manifest (`pyproject.toml`) | unit | unit | ✅ OK |
| T2 | Config & Domain Errors | unit | unit | ✅ OK |
| T3 | WAV Audio Capture (`wav_recorder.py`) | unit | unit | ✅ OK |
| T4 | Application Service (`audio_service.py`) | unit | unit | ✅ OK |
| T5 | Application Service (`session_service.py`) | unit | unit | ✅ OK |
| T6 | MCP Server & Stdio (`mcp/server.py`) | integration | integration | ✅ OK |
| T7 | Skill (`SKILL.md`) | unit | unit | ✅ OK |
| T8 | Architecture Docs & Full Build | integration | integration | ✅ OK |
