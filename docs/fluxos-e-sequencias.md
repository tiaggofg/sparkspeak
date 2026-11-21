# Fluxos e Diagramas de Sequência

## 1. Fluxo Principal de Sessão e Fallback

```mermaid
flowchart TD
  Start([start_session]) --> CheckAudio{"mic_available?"}
  CheckAudio -->|Sim| VoiceLoop["Voz: speak_text (Kokoro) + record_utterance + read_file(wav_path)"]
  CheckAudio -->|Não / Texto| TextLoop["Texto: chat Antigravity"]
  VoiceLoop -->|"MICROPHONE_UNAVAILABLE / 2x silêncio / 'texto'"| TextLoop
  VoiceLoop --> Evaluate["Avaliação multimodal + submit_review + log_mistake"]
  TextLoop --> Evaluate
  Evaluate --> More{"Mais cards/turnos?"}
  More -->|Sim| CheckAudio
  More -->|Encerrar| Close["end_session(promote_errors=true)"]
  Close --> End([Resumo + Cards Extraídos])
```

## 2. Sequência: Captura WAV + Escuta Multimodal + Review FSRS

```mermaid
sequenceDiagram
  autonumber
  actor U as Aprendiz
  participant V as Antigravity Voice + Gemini
  participant M as SparkSpeak MCP
  participant PW as PipeWire + WavRecorder
  participant DB as SQLite (FSRS)

  V->>M: speak_text(text="...", voice="af_heart")
  M->>PW: Kokoro ONNX -> sounddevice sink
  PW-->>U: Áudio natural em inglês
  V->>M: record_utterance(silence_timeout_ms=1500, max_duration_ms=45000)
  U->>PW: "I work-ed (/wɜːrkɪd/) on the deploy"
  PW->>M: 16kHz mono PCM -> RMS endpointing -> .data/audio/last_utterance.wav
  M-->>V: {speech_detected: true, wav_path, duration_ms, peak_rms}

  V->>V: read_file(Path=wav_path) -> ouve áudio bruto (audio/wav)
  V->>M: log_mistake(session_id, utterance_raw, correction, category="pronunciation_asr")
  M->>DB: INSERT session_turns + UPSERT error_logs (fingerprint_hash)

  V->>M: submit_review(card_id, rating=2, user_response_raw, input_mode="voice", session_id)
  M->>DB: TX: py-fsrs schedule + INSERT review_logs
  M-->>V: {next_due_at, scheduled_days, fsrs_state}
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
