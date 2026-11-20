# Fluxos e Diagramas de Sequência

## 1. Fluxo Principal de Sessão e Fallback

```mermaid
flowchart TD
  Start([start_session]) --> CheckAudio{"audio_status OK?"}
  CheckAudio -->|Sim| VoiceLoop["Voz: speak_text + listen_and_transcribe"]
  CheckAudio -->|Não / Texto| TextLoop["Texto: chat Antigravity"]
  VoiceLoop -->|"MICROPHONE_UNAVAILABLE / 2x silêncio / 'texto'"| TextLoop
  VoiceLoop --> Evaluate["Avaliação + submit_review + log_turn_and_errors"]
  TextLoop --> Evaluate
  Evaluate --> More{"Mais cards/turnos?"}
  More -->|Sim| CheckAudio
  More -->|Encerrar| Close["end_session(promote_errors=true)"]
  Close --> End([Resumo + Cards Extraídos])
```

## 2. Sequência: Captura VAD + Transcrição Verbatim + Review FSRS

```mermaid
sequenceDiagram
  autonumber
  actor U as Aprendiz
  participant L as Antigravity LLM + SKILL.md
  participant M as SparkSpeak MCP
  participant PW as PipeWire + Whisper/Silero
  participant DB as SQLite (FSRS)

  L->>M: speak_text(text="How do you say 'adiar' with 'put'?")
  M->>PW: Piper ONNX -> sounddevice sink
  PW-->>U: Áudio em inglês
  M-->>L: {spoken: true, duration_ms}

  L->>M: listen_and_transcribe(silence_timeout_ms=1500, max_duration_ms=45000)
  U->>PW: "We need put off the meeting for tomorrow"
  PW->>M: 16kHz PCM -> Silero VAD -> faster-whisper (int8, language="en")
  M-->>L: {speech_detected: true, transcript: "We need put off the meeting for tomorrow"}

  L->>M: submit_review(card_id, rating=2, user_response_raw, input_mode="voice", session_id)
  M->>DB: TX: py-fsrs schedule + INSERT review_logs
  M-->>L: {next_due_at, scheduled_days, fsrs_state}

  L->>M: log_turn_and_errors(session_id, speaker="user", raw_transcript, errors=[...])
  M->>DB: INSERT session_turns + UPSERT error_logs (fingerprint_hash)
```

## 3. Sequência: Encerramento e Promoção Automática de Cards

```mermaid
sequenceDiagram
  autonumber
  actor U as Aprendiz
  participant L as Antigravity LLM
  participant M as SparkSpeak MCP
  participant DB as SQLite

  U->>L: "Encerrar sessão"
  L->>M: end_session(session_id, promote_errors=true, summary_notes)
  M->>DB: SELECT error_logs WHERE session_id=? AND promoted_card_id IS NULL
  loop Para cada erro elegível
    M->>DB: add_card(source_type="auto_extracted") com dedup por normalized_front
    M->>DB: UPDATE error_logs SET promoted_card_id=?
  end
  M->>DB: UPDATE study_sessions SET status='ended', ended_at=?, errors_extracted=?
  M-->>L: {cards_reviewed, errors_extracted, promoted_cards, recurring_errors}
  L-->>U: Apresenta métricas reais e flashcards criados
```
