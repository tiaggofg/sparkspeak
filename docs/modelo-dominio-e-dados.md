# Modelo de Domínio e Dados

## 1. Diagrama de Classes / Serviços

```mermaid
classDiagram
  class SRSEngine {
    +float desired_retention
    +validate_rating(rating)
    +schedule_review(card, rating) ReviewResult
  }

  class ReviewService {
    +get_due_cards(deck_slug, limit, new_cards_limit, include_new) DueCardsResult
    +submit_review(card_id, rating, user_response_raw, input_mode, session_id, idempotency_key) ReviewResult
    +add_card(deck_slug, front_prompt, back_reference, card_type, source_type) AddCardResult
  }

  class SessionService {
    +start_session(deck_slug, mode, input_mode) StartSessionResult
    +switch_input_mode(session_id, input_mode) StudySession
    +log_turn_and_errors(session_id, speaker, raw_transcript, input_mode, errors) LogTurnResult
    +end_session(session_id, promote_errors, summary_notes) SessionSummary
  }

  class AudioService {
    +get_audio_status() AudioStatus
    +speak_text(text, voice, speed, blocking) SpeakResult
    +listen_and_transcribe(silence_timeout_ms, initial_speech_timeout_ms, max_duration_ms) TranscribeResult
  }

  ReviewService --> SRSEngine
```

## 2. Modelo de Persistência (ER SQLite — `001_initial.sql`)

```mermaid
erDiagram
  decks ||--o{ cards : contains
  decks ||--o{ study_sessions : scopes
  decks ||--o{ error_logs : categorizes
  cards ||--o{ review_logs : tracks
  cards ||--o{ error_logs : promoted_from
  study_sessions ||--o{ review_logs : records
  study_sessions ||--o{ session_turns : logs
  study_sessions ||--o{ error_logs : captures
  session_turns ||--o{ error_logs : detects

  decks {
    INTEGER id PK
    TEXT slug UK
    TEXT name
    TEXT target_cefr
    TEXT persona_prompt
  }

  cards {
    INTEGER id PK
    INTEGER deck_id FK
    TEXT front_prompt
    TEXT normalized_front
    TEXT back_reference
    TEXT card_type
    TEXT source_type
    INTEGER fsrs_state
    INTEGER is_new
    REAL stability
    REAL difficulty
    TEXT due_at
    INTEGER suspended
  }

  study_sessions {
    TEXT id PK
    INTEGER deck_id FK
    TEXT mode
    TEXT input_mode_default
    TEXT status
    TEXT started_at
    TEXT ended_at
    INTEGER cards_reviewed
    INTEGER errors_extracted
  }

  review_logs {
    INTEGER id PK
    TEXT idempotency_key UK
    INTEGER card_id FK
    TEXT session_id FK
    INTEGER rating
    INTEGER fsrs_state_before
    INTEGER fsrs_state_after
    INTEGER scheduled_days
  }

  session_turns {
    INTEGER id PK
    TEXT session_id FK
    INTEGER turn_index
    TEXT speaker
    TEXT raw_transcript
    TEXT input_mode
  }

  error_logs {
    INTEGER id PK
    TEXT session_id FK
    INTEGER turn_id FK
    INTEGER deck_id FK
    TEXT category
    TEXT fingerprint_hash
    INTEGER occurrence_count
    INTEGER promoted_card_id FK
  }
```

## 3. Índices e Constraints

- `UNIQUE (deck_id, normalized_front)` em `cards` (deduplicação em `add_card`).
- `UNIQUE (session_id, turn_index)` em `session_turns`.
- `UNIQUE (idempotency_key)` em `review_logs` (replay seguro de `submit_review`).
- `idx_cards_due_queue` em `cards(suspended, is_new, due_at, deck_id)`.
- `idx_review_logs_card_time` em `review_logs(card_id, reviewed_at DESC)` e `idx_review_logs_session` em `review_logs(session_id)`.
- `idx_error_logs_fingerprint` em `error_logs(fingerprint_hash)` e `idx_error_logs_session` em `error_logs(session_id, promoted_card_id)`.

## 4. Máquina de Estados

```mermaid
stateDiagram-v2
  [*] --> Learning : "is_new=1, fsrs_state=1"
  Learning --> Review : "Rating Good/Easy"
  Review --> Review : "Rating Hard/Good/Easy"
  Review --> Relearning : "Rating Again (lapse)"
  Relearning --> Review : "Rating Good/Easy"
```
