# 01-english-tutor-harness verification

**Verdict**: PASS
**Proofs**: `proofs.md` at c39e952
**Verifier**: independent sub-agent (author != verifier)

## Checks

| Check | Test | Holds |
| --- | --- | --- |
| C1 | `test_mcp_stdio_protocol.py` `test_start_session_persists_active_row` | yes |
| C2 | `test_sqlite_repositories.py` `test_get_due_cards_orders_due_before_new` | yes |
| C3 | `test_sqlite_repositories.py` `test_submit_review_updates_fsrs_and_logs` | yes (fixed in `c39e952`) |
| C4 | `test_sqlite_repositories.py` `test_submit_review_invalid_rating_and_unknown_card_leave_db_unchanged` | yes (fixed in `c39e952`) |
| C5 | `test_mcp_stdio_protocol.py` `test_text_mode_never_invokes_audio` | yes (fixed in `c39e952`) |
| C6 | `test_sqlite_migrations.py` `test_migrations_idempotent_wal_fk` | yes |
| C7 | `test_piper_tts.py` `test_speak_text_plays_pcm_to_device` | yes |
| C8 | `test_mcp_tts_tool.py` `test_speak_text_validation_and_missing_model` | yes |
| C9 | `test_whisper_wav_fixture.py` `test_verbatim_error_preservation` | yes |
| C10 | `test_mcp_stt_tool.py` `test_stt_timeouts_and_missing_mic` | yes |
| C11 | `test_review_and_session_service.py` `test_voice_to_text_switch_preserves_session` | yes |
| C12 | `test_error_logging_and_promotion.py` `test_repeated_error_increments_count` | yes |
| C13 | `test_sqlite_repositories.py` `test_add_card_deduplicates_normalized_front` | yes |
| C14 | `test_post_session_extraction.py` `test_end_session_promotes_errors_once` | yes |

## Findings

| Finding | Evidence | Fix | Closed |
| --- | --- | --- | --- |
| C3 does not directly verify `review_logs` row contents or `difficulty`/`fsrs_state` persistence | `tests/integration/test_sqlite_repositories.py:69-113` never queries `review_logs` and only asserts `is_new`, `reps`, `due_at`, `stability` on `cards` | Query `review_logs` in `test_submit_review_updates_fsrs_and_logs` to assert 1 immutable row with expected `card_id`, `session_id`, `rating`, `fsrs_state_after`, and assert `updated_card.difficulty` and `updated_card.fsrs_state` | `c39e952` (C3) |
| C4 proves in-memory `SRSEngine` instead of `submit_review` + SQLite immutability and `CARD_NOT_FOUND` | `tests/unit/test_srs_engine.py:156-165` tests `SRSEngine.schedule_review` on a dataclass without DB or MCP layer | Point C4 to an integration test calling `submit_review` (over MCP stdio or `ReviewService` + SQLite) with invalid rating and unknown `card_id`, asserting `INVALID_RATING`/`CARD_NOT_FOUND` and unchanged `cards`/`review_logs`/`study_sessions` rows | `c39e952` (C4) |
| C5 only tests `roleplay` mode, omitting `active_review` | `tests/integration/test_mcp_stdio_protocol.py:75-129` starts only `mode="roleplay"` | Exercise both `active_review` and `roleplay` in `test_text_mode_never_invokes_audio` without invoking `speak_text`/`listen_and_transcribe` | `c39e952` (C5) |
