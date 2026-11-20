# 01-english-tutor-harness proofs

**HEAD**: c39e952
**Tree**: dirty - .agents/rules/, .agents/scripts/, .agents/skills/, .agents/update-spec-kit.sh, .release-please-manifest.json
**Shell**: /bin/sh
**Result**: 17 pass, 0 fail

| Check | Proof | Result |
| --- | --- | --- |
| C1 | `run integration / tests/integration/test_mcp_stdio_protocol.py::test_start_session_persists_active_row PASSED` | pass |
| C2 | `run integration / tests/integration/test_sqlite_repositories.py::test_get_due_cards_orders_due_before_new PASS` | pass |
| C3 | `run integration / tests/integration/test_sqlite_repositories.py::test_submit_review_updates_fsrs_and_logs PASS` | pass |
| C4 | `run integration / tests/integration/test_sqlite_repositories.py::test_submit_review_invalid_rating_and_unknown` | pass |
| C5 | `run integration / tests/integration/test_mcp_stdio_protocol.py::test_text_mode_never_invokes_audio PASSED` | pass |
| C6 | `run integration / tests/integration/test_sqlite_migrations.py::test_migrations_idempotent_wal_fk PASSED` | pass |
| C7 | `run unit / tests/unit/test_piper_tts.py::test_speak_text_plays_pcm_to_device PASSED` | pass |
| C8 | `run integration / tests/integration/test_mcp_tts_tool.py::test_speak_text_validation_and_missing_model PASSED` | pass |
| C9 | `run integration / tests/integration/test_whisper_wav_fixture.py::test_verbatim_error_preservation PASSED` | pass |
| C10 | `run integration / tests/integration/test_mcp_stt_tool.py::test_stt_timeouts_and_missing_mic PASSED` | pass |
| C11 | `run unit / tests/unit/test_review_and_session_service.py::test_voice_to_text_switch_preserves_session PASSED` | pass |
| C12 | `run integration / tests/integration/test_error_logging_and_promotion.py::test_repeated_error_increments_count ` | pass |
| C13 | `run integration / tests/integration/test_sqlite_repositories.py::test_add_card_deduplicates_normalized_front P` | pass |
| C14 | `run integration / tests/integration/test_post_session_extraction.py::test_end_session_promotes_errors_once PAS` | pass |
| Build | `uv run ruff check src tests` | pass |
| Build | `uv run mypy src` | pass |
| Build | `uv run pytest -v` | pass |

## Output

`Run integration` - exit 0

```
tests/integration/test_sqlite_repositories.py::test_get_due_cards_orders_due_before_new PASSED [ 65%]
tests/integration/test_sqlite_repositories.py::test_submit_review_updates_fsrs_and_logs PASSED [ 68%]
tests/integration/test_sqlite_repositories.py::test_submit_review_invalid_rating_and_unknown_card_leave_db_unchanged PASSED [ 71%]
tests/integration/test_sqlite_repositories.py::test_add_card_deduplicates_normalized_front PASSED [ 74%]
tests/integration/test_sqlite_repositories.py::test_get_due_cards_unknown_deck_raises_deck_not_found PASSED [ 77%]
tests/integration/test_sqlite_repositories.py::test_end_session_is_idempotent PASSED [ 80%]
tests/integration/test_sqlite_repositories.py::test_log_turn_and_upsert_error_increments_occurrence_count PASSED [ 82%]
tests/integration/test_whisper_wav_fixture.py::test_verbatim_error_preservation PASSED [ 85%]
tests/integration/test_whisper_wav_fixture.py::test_initial_speech_timeout_returns_no_speech_detected PASSED [ 88%]
tests/integration/test_whisper_wav_fixture.py::test_max_duration_truncates_and_sets_flag PASSED [ 91%]
tests/integration/test_whisper_wav_fixture.py::test_missing_microphone_raises_microphone_unavailable PASSED [ 94%]
tests/integration/test_whisper_wav_fixture.py::test_missing_whisper_model_raises_model_not_installed PASSED [ 97%]
tests/integration/test_whisper_wav_fixture.py::test_load_wav_pcm_16k_validates_fixture_format PASSED [100%]

============================= 35 passed in 13.08s ==============================
```

`Run unit` - exit 0

```
tests/unit/test_review_and_session_service.py::test_submit_review_updates_schedule_and_replays_idempotently PASSED [ 66%]
tests/unit/test_review_and_session_service.py::test_start_session_unknown_deck_raises_deck_not_found PASSED [ 69%]
tests/unit/test_review_and_session_service.py::test_end_session_is_idempotent_and_preserves_ended_at PASSED [ 72%]
tests/unit/test_review_and_session_service.py::test_voice_to_text_switch_preserves_session PASSED [ 75%]
tests/unit/test_srs_engine.py::test_new_card_good_rating_computes_deterministic_schedule PASSED [ 77%]
tests/unit/test_srs_engine.py::test_new_card_easy_schedules_further_than_again PASSED [ 80%]
tests/unit/test_srs_engine.py::test_review_card_again_transitions_to_relearning_and_increments_lapses PASSED [ 83%]
tests/unit/test_srs_engine.py::test_review_card_good_remains_in_review_and_grows_interval PASSED [ 86%]
tests/unit/test_srs_engine.py::test_relearning_card_good_graduates_back_to_review PASSED [ 88%]
tests/unit/test_srs_engine.py::test_invalid_rating_raises_without_mutation[0] PASSED [ 91%]
tests/unit/test_srs_engine.py::test_invalid_rating_raises_without_mutation[5] PASSED [ 94%]
tests/unit/test_srs_engine.py::test_invalid_rating_raises_without_mutation[-1] PASSED [ 97%]
tests/unit/test_srs_engine.py::test_invalid_rating_raises_without_mutation[99] PASSED [100%]

============================== 36 passed in 0.94s ==============================
```
