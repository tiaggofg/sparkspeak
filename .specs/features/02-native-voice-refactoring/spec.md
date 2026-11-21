# Multimodal WAV Input & Native Voice Output Refactoring Specification

**Approved**: 2026-11-20 - user: "está aprovado"
**Status**: Approved

## Problem Statement

In SparkSpeak v0.1, local speech-to-text (`faster-whisper` + Silero VAD) and local text-to-speech (`piper-tts`) introduced ~500 MB of heavy ML dependencies (`ctranslate2`, `onnxruntime`, `tokenizers`, `.data/models/`) while converting the learner's voice into plain text before the LLM ever saw it. That text bottleneck blinded the tutor to real pronunciation nuances (phonemes like `/θ/` vs `/t/`, `-ed` endings, Brazilian Portuguese vowel epenthesis, syllable stress, and intonation) because STT models normalize phonetic slips into standard English spelling. By refactoring SparkSpeak to:
1. **Remove local STT (`faster-whisper`) and local TTS (`piper-tts`)** entirely,
2. **Capture raw learner speech into a single lightweight 16 kHz mono `.wav` buffer (`record_utterance`)** that the Antigravity agent reads directly as native multimodal `audio/wav` via `read_file`, and
3. **Delegate tutor spoken output to Antigravity's native Voice output**,
the tutor hears the learner's actual voice waveform to coach real pronunciation and grammar nuances while the MCP server stays fast, deterministic, and free of local neural models.

## Goals

- [ ] Remove local neural STT (`faster-whisper`) and local neural TTS (`piper-tts`), their model downloaders (`sparkspeak-setup-models`, `.data/models/`), and the `speak_text` / `listen_and_transcribe` tools.
- [ ] Replace `listen_and_transcribe` with an ultra-lightweight `record_utterance` MCP tool (`sounddevice` + `numpy` RMS silence endpointing + Python stdlib `wave`, zero neural weights) that writes `.data/audio/last_utterance.wav` and returns its absolute `wav_path` for native multimodal audio ingestion via Antigravity's `read_file`.
- [ ] Delegate all spoken tutor output to Antigravity's native Voice output by formatting tutor responses in short, natural spoken English (1–3 sentences, zero markdown tables or code blocks).
- [ ] Preserve 100% of the SQLite database (`.data/sparkspeak.db`), schema migrations (`001_initial.sql`), FSRS spaced-repetition engine (`py-fsrs`), and deterministic state tools (`start_session`, `get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `log_turn_and_errors`, `end_session`).
- [ ] Update `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` to orchestrate the multimodal audio loop (`record_utterance` $\rightarrow$ `read_file(wav_path)` $\rightarrow$ evaluate pronunciation & grammar directly from audio $\rightarrow$ speak concise response via Antigravity Voice + background `submit_review` / `log_mistake`).

## Out of Scope

Explicitly excluded from this refactoring to prevent scope creep.

| Feature | Reason |
| --- | --- |
| Local neural TTS synthesis (`piper-tts` / `edge-tts` / Kokoro) | Tutor spoken output is handled by Antigravity's native Voice feature |
| Local or cloud STT transcription inside the MCP server | Converting audio to text strips phonetic and prosodic information; Gemini reads `.data/audio/last_utterance.wav` directly via `read_file` |
| Destructive SQLite schema migrations or table drops | Existing `.data/sparkspeak.db` files and `001_initial.sql` remain 100% compatible without data loss |
| Multi-file audio archive retention on disk | `.data/audio/last_utterance.wav` is overwritten on each spoken turn so disk usage remains bounded (~100 KB) |

---

## Assumptions & Open Questions

Every ambiguity is resolved or recorded here - nothing is left silently unclear.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Multimodal audio input architecture (Option 2) | MCP tool `record_utterance` records 16 kHz 16-bit mono PCM with RMS energy VAD into `.data/audio/last_utterance.wav`; agent immediately calls `read_file` on `wav_path` so Gemini hears the raw audio | Confirmed by user ("vamos seguir com a opção 2"); verified that Antigravity's `read_file` natively injects `audio/wav` into Gemini's multimodal context | y |
| Tutor audio output layer | Remove `piper-tts` and `speak_text`; use Antigravity's native Voice output to speak the tutor's short conversational replies | Confirmed by user ("para o output de audio, quando o modelo precisar falar, aí da pra usar o voice do antigravity") | y |
| Silence detection (VAD) without neural weights | Pure `numpy` RMS energy threshold (`rms_threshold=0.015`, `silence_timeout_ms=1500`, `initial_speech_timeout_ms=10000`, `max_duration_ms=45000`) | Eliminates `faster-whisper` and `onnxruntime` dependencies while keeping automatic end-of-speech detection fast and dependency-light | y |
| Low-latency error logging tool (`log_mistake`) | Expose flat `log_mistake` tool alongside `log_turn_and_errors`, `start_session`, `get_due_cards`, `submit_review`, `add_card`, and `end_session` | Allows the tutor to log pronunciation, grammar, phrasal verb, vocabulary, or register slips in a single concise call while preserving session promotion at `end_session` | y |
| CLI scripts (`sparkspeak-setup-models` & `sparkspeak-health`) | Remove `sparkspeak-setup-models` and `sparkspeak-health` from `pyproject.toml` and delete `src/sparkspeak/cli/` | No local neural models (`.onnx` / Whisper) exist to download anymore | y |

**Open questions:** none - all resolved and confirmed above.

---

## User Stories

### P1: Removal of Heavy Local STT/TTS Models & Lightweight WAV Capture (`record_utterance`) ⭐ MVP

**User Story**: As a learner practicing English pronunciation and conversation, I want the MCP server to capture my voice into a clean `.wav` file without heavy local STT/TTS engines so that Gemini can listen to my actual pronunciation via `read_file` while the server boots instantly.

**Why P1**: Replaces 500 MB of text-bottlenecked local ML (`faster-whisper` + `piper-tts`) with direct multimodal audio capture.

**Acceptance Criteria**:

1. The project configuration (`pyproject.toml`) SHALL declare only `mcp>=1.0.0`, `fsrs>=4.0.0`, `sounddevice>=0.5.0`, and `numpy>=1.26.0` as runtime dependencies, with `faster-whisper` and `piper-tts` completely removed.
2. The MCP server SHALL NOT expose `speak_text`, `listen_and_transcribe`, or `get_audio_status`.
3. WHEN the tutor calls `record_utterance` THEN the MCP server SHALL capture 16 kHz mono 16-bit PCM audio from the default PipeWire input source using RMS energy endpointing, stop after `silence_timeout_ms` (default 1500 ms) of trailing silence, write the audio to `.data/audio/last_utterance.wav`, and return `speech_detected: true`, the absolute `wav_path`, `duration_ms`, `peak_rms`, and `truncated_at_max_duration`.
4. IF no speech energy exceeds `rms_threshold` within `initial_speech_timeout_ms` (default 10000 ms) THEN `record_utterance` SHALL stop cleanly and return `speech_detected: false`, `wav_path: null`, and `duration_ms: 0` without raising an error.
5. IF the PipeWire microphone input source is missing or fails to open THEN `record_utterance` SHALL return a structured recoverable error with `error_code: "MICROPHONE_UNAVAILABLE"` and `fallback_hint: "text"`.

**Independent Test**: Run `pytest` unit and integration tests feeding synthetic PCM speech + silence frames into `WavRecorder` and calling `record_utterance` over `stdio`, verifying valid 16 kHz 16-bit mono WAV output at `.data/audio/last_utterance.wav` and `MICROPHONE_UNAVAILABLE` fallback when no mic is present.

---

### P2: Lean Deterministic Core (SRS + SQLite + `log_mistake`)

**User Story**: As a learner in an active voice session, I want deterministic FSRS card scheduling and background mistake logging (`get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `start_session`, `end_session`) with compact JSON responses so that my pronunciation and grammar mistakes are tracked and promoted to flashcards with zero latency.

**Why P2**: Preserves the deterministic SQLite + FSRS memory layer and streamlines payload sizes for live conversation.

**Acceptance Criteria**:

1. WHEN `start_session` is called THEN the MCP server SHALL create an active `study_sessions` row in SQLite and return `session_id`, `deck`, `mode`, `effective_input_mode`, `mic_available`, and `due_summary`.
2. WHEN `get_due_cards` is called THEN the MCP server SHALL return due review cards ordered by `due_at ASC` followed by up to `new_cards_limit` unseen cards with compact card fields (`card_id`, `deck_slug`, `front_prompt`, `back_reference`, `context_example`, `card_type`, `is_new`, `due_at`) and `queue_stats`.
3. WHEN `submit_review` is called with `card_id`, `rating` in `{1, 2, 3, 4}`, and `user_response_raw` THEN the MCP server SHALL atomically update the card's FSRS schedule in SQLite, append an immutable `review_logs` row, and return `card_id`, `rating`, `fsrs_state`, `scheduled_days`, `next_due_at`, and `idempotent_replay`.
4. WHEN `log_mistake` is called with `session_id`, `utterance_raw`, `correction`, `category`, and optional `explanation` THEN the MCP server SHALL record the learner turn and upsert the error into `error_logs` with SHA-256 fingerprint deduplication, returning `session_id`, `turn_index`, `error_id`, `category`, `occurrence_count`, and `promoted_card_id`.
5. WHEN `end_session` is called THEN the MCP server SHALL idempotently finalize the session and promote unpromoted session errors into `auto_extracted` flashcards in `cards` (mapping `pronunciation_asr` errors to `pronunciation` cards).

**Independent Test**: Run `stdio` MCP integration tests verifying `start_session`, `get_due_cards`, `submit_review`, `log_mistake`, `add_card`, and `end_session` against `.data/sparkspeak.db`.

---

### P3: Multimodal Pronunciation & Voice-Output Pedagogical Skill (`SKILL.md`)

**User Story**: As an engineer practicing spoken English in Antigravity, I want the `english-tutor` skill to record my speech via `record_utterance`, listen to the `.wav` file directly via `read_file`, coach my pronunciation and grammar nuances, and reply in short voice-friendly sentences spoken by Antigravity Voice while logging FSRS reviews and mistakes silently in the background.

**Why P3**: Connects the raw `.wav` capture, Gemini's native multimodal audio understanding, Antigravity's Voice output, and background FSRS/error persistence into one seamless loop.

**Acceptance Criteria**:

1. WHILE in a `voice` study session, WHEN it is the learner's turn to speak THEN the `english-tutor` skill SHALL invoke `record_utterance`, and WHEN `speech_detected` is `true` THEN the agent SHALL immediately call `read_file` on `wav_path` to listen to the raw audio before responding.
2. WHEN evaluating the learner's spoken audio from `read_file` THEN the `english-tutor` skill SHALL assess both linguistic accuracy (grammar, vocabulary, phrasal verbs, register) and acoustic pronunciation nuances (phonemes such as `/θ/` vs `/t/`, `-ed` past tense endings, vowel epenthesis, syllable stress, and rhythm), logging detected slips silently via `log_mistake`.
3. WHILE generating tutor responses intended for Antigravity Voice output, the `english-tutor` skill SHALL keep replies to 1–3 natural spoken sentences (under 40 words), avoid markdown tables, code blocks, or internal IDs, and end with a single speaking prompt or question.
4. IF `record_utterance` returns `MICROPHONE_UNAVAILABLE`, `speech_detected: false` twice consecutively, or the learner types in chat / requests text mode THEN the `english-tutor` skill SHALL switch seamlessly to `input_mode="text"` without losing `session_id` or card progress.

**Independent Test**: Verify `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` and `references/` contain the exact `record_utterance` $\rightarrow$ `read_file` multimodal protocol, pronunciation coaching rubric, Antigravity Voice output constraints, and text fallback rules.

---

## 1. Mapa de Impacto (Antes vs. Depois)

### 1.1. Arquivos do Repositório

| Caminho | Status | Antes (v0.1 — `faster-whisper` + `piper-tts`) | Depois (v0.2 — `.wav` Multimodal + Antigravity Voice) |
| --- | --- | --- | --- |
| `src/sparkspeak/infrastructure/audio/piper_tts.py` | **REMOVIDO** | Síntese local ONNX `piper-tts` + playback PipeWire | Removido (output de voz delegado ao Voice do Antigravity) |
| `src/sparkspeak/infrastructure/audio/whisper_stt.py` | **REMOVIDO** | Silero VAD ONNX + transcrição `faster-whisper` (`int8`) | Removido (substituído por captura `.wav` direta para o Gemini ouvir via `read_file`) |
| `src/sparkspeak/cli/setup_models.py` | **REMOVIDO** | Download de ~220 MB de pesos HuggingFace (Piper/Whisper) | Removido (zero modelos neurais locais) |
| `src/sparkspeak/cli/__init__.py` | **REMOVIDO** | Pacote CLI de setup de modelos | Removido |
| `tests/unit/test_piper_tts.py` | **REMOVIDO** | Testes unitários do adaptador Piper TTS | Removido |
| `tests/unit/test_cli_setup.py` | **REMOVIDO** | Testes do downloader de modelos ONNX/Whisper | Removido |
| `tests/integration/test_mcp_tts_tool.py` | **REMOVIDO** | Testes de integração da tool MCP `speak_text` | Removido |
| `tests/integration/test_whisper_wav_fixture.py` | **REMOVIDO** | Teste acoplado ao `faster-whisper` | Removido |
| `src/sparkspeak/infrastructure/audio/wav_recorder.py` | **NOVO** | Não existia | Gravador `.wav` 16 kHz mono 16-bit PCM com VAD por energia RMS (`numpy` + `sounddevice` + `wave`), salvando em `.data/audio/last_utterance.wav` |
| `src/sparkspeak/infrastructure/audio/pipewire_device.py` | **ALTERADO** | Probe de input/output + `play_pcm` para TTS | Enxugado para apenas probe de microfone (`has_input_device`) e abertura de `InputStream` |
| `src/sparkspeak/infrastructure/audio/ports.py` | **ALTERADO** | `TTSEngine`, `STTEngine`, `SpeakResult`, `TranscribeResult`, `AudioStatus` | Enxugado para `UtteranceRecorder` e `RecordUtteranceResult` (`speech_detected`, `wav_path`, `duration_ms`, `peak_rms`, `truncated_at_max_duration`) |
| `src/sparkspeak/application/audio_service.py` | **ALTERADO** | Orquestrava `speak_text`, `listen_and_transcribe` e `get_audio_status` | Orquestra apenas `record_utterance` sob `asyncio.Lock` e `is_mic_available()` |
| `src/sparkspeak/config.py` | **ALTERADO** | Resolvia `db_path`, `backups_dir` e `models_dir` (`SPARKSPEAK_MODELS_DIR`) | Substitui `models_dir` por `audio_dir` (`.data/audio/`, override `SPARKSPEAK_AUDIO_DIR`) para armazenar `last_utterance.wav` |
| `src/sparkspeak/domain/errors.py` | **ALTERADO** | 10 códigos (incluindo `TTS_MODEL_MISSING`, `AUDIO_OUTPUT_UNAVAILABLE`, `MODEL_NOT_INSTALLED`) | 6 códigos enxutos (`INVALID_ARGUMENT`, `INVALID_RATING`, `CARD_NOT_FOUND`, `DECK_NOT_FOUND`, `SESSION_NOT_FOUND`, `MICROPHONE_UNAVAILABLE`) |
| `src/sparkspeak/application/session_service.py` | **ALTERADO** | `start_session` recebia `audio_status` completo; só tinha `log_turn_and_errors` | `start_session` recebe `mic_available: bool`; adiciona `log_mistake` plano mantendo `log_turn_and_errors` |
| `src/sparkspeak/mcp/server.py` | **ALTERADO** | 9 tools incluindo `speak_text`, `listen_and_transcribe`, `get_audio_status` | Expõe 8 tools enxutas: `start_session`, `get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `log_turn_and_errors`, `end_session`, `record_utterance` |
| `pyproject.toml` | **ALTERADO** | `mcp`, `fsrs`, `faster-whisper`, `piper-tts`, `sounddevice`, `numpy` + 3 scripts CLI | Remove `faster-whisper` e `piper-tts`; mantém `mcp`, `fsrs`, `sounddevice`, `numpy` + único script `sparkspeak-mcp` |
| `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` | **ALTERADO** | Baseado em `speak_text` e transcrição `listen_and_transcribe` | Fluxo Multimodal: `record_utterance` $\rightarrow$ `read_file(wav_path)` (escuta pronúncia real) $\rightarrow$ resposta falada pelo Voice do Antigravity + `log_mistake` / `submit_review` |
| `src/sparkspeak/domain/srs_engine.py` | **MANTIDO** | Algoritmo determinístico FSRS (`py-fsrs`, `desired_retention=0.90`) | **Intacto (100% preservado)** |
| `src/sparkspeak/domain/models.py` | **MANTIDO** | Entidades de domínio (`Deck`, `Card`, `StudySession`, `ReviewResult`, `ErrorLogRecord`) | **Intacto (100% preservado)** |
| `src/sparkspeak/application/review_service.py` | **MANTIDO** | `get_due_cards`, `submit_review` e `add_card` | **Intacto (100% preservado)** |
| `src/sparkspeak/infrastructure/db/*` | **MANTIDO** | SQLite WAL, `migrator.py`, `repositories.py`, `001_initial.sql`, `001_default_decks.sql` | **Intacto (zero alteração destrutiva no banco)** |

### 1.2. Dependências (`pyproject.toml` e Sistema Operacional)

| Dependência / Camada | Antes (v0.1) | Depois (v0.2) | Ganho Arquitetural |
| --- | --- | --- | --- |
| `mcp>=1.0.0` | Presente | **Mantida** | Servidor `stdio` JSON-RPC oficial |
| `fsrs>=4.0.0` | Presente | **Mantida** | Agendamento determinístico de repetição espaçada |
| `sounddevice>=0.5.0` | Presente | **Mantida** | Captura leve 16 kHz PCM do microfone via PipeWire/PortAudio |
| `numpy>=1.26.0` | Presente | **Mantida** | Cálculo instantâneo de energia RMS para detecção de silêncio (VAD sem IA pesada) |
| `faster-whisper>=1.1.0` | Presente | **Removida** | Elimina `ctranslate2`, `tokenizers`, `huggingface-hub`, `av` (~350 MB+) e elimina o gargalo de texto na pronúncia |
| `piper-tts>=1.2.0` | Presente | **Removida** | Elimina `onnxruntime` e `piper-phonemize` (~150 MB+); voz do tutor fica a cargo do Antigravity Voice |
| `.data/models/` (~220 MB) | Obrigatório | **Removido** | Substituído por `.data/audio/last_utterance.wav` (~100 KB reciclado a cada fala) |

### 1.3. Tools MCP Expostas (`sparkspeak`)

| Tool MCP | Status | Papel na Nova Arquitetura (v0.2) |
| --- | --- | --- |
| `record_utterance` | **NOVA (Substitui `listen_and_transcribe`)** | Grava a fala do aluno com endpointing de silêncio RMS em `.data/audio/last_utterance.wav` e retorna `wav_path` para o agente ouvir o áudio real via `read_file` |
| `get_due_cards` | **MANTIDA (Payload Enxuto)** | Busca cartões vencidos e novos no SQLite com JSON compacto para baixa latência |
| `submit_review` | **MANTIDA (Payload Enxuto)** | Calcula próximo agendamento FSRS (`1..4`) e persiste em `cards` + `review_logs` |
| `add_card` | **MANTIDA** | Cria ou deduplica flashcard (`vocab`, `phrasal_verb`, `grammar_fix`, `pronunciation`, `tech_scenario`) |
| `log_mistake` | **NOVA (Atalho de Baixa Latência)** | Registra erro de pronúncia, gramática, vocabulário, phrasal verb ou registro em 1 chamada plana com deduplicação SHA-256 |
| `log_turn_and_errors` | **MANTIDA (Compatibilidade)** | Registra turno completo + lista de erros em lote |
| `start_session` | **ALTERADA (Mais Enxuta)** | Inicia sessão no SQLite e informa `mic_available` e `due_summary` |
| `end_session` | **MANTIDA** | Encerra sessão e promove erros do dia (incluindo pronúncia) para novos flashcards `auto_extracted` |
| `speak_text` | **REMOVIDA** | Removida — o output de voz é feito pelo Voice do Antigravity |
| `listen_and_transcribe` | **REMOVIDA** | Removida — substituída por `record_utterance` + `read_file` multimodal |
| `get_audio_status` | **REMOVIDA** | Removida — `start_session` já informa `mic_available: bool` |

---

## 2. Plano de Limpeza e Migração Segura

### Passo 1: Preservação Intacta do Banco SQLite (`.data/sparkspeak.db`)
- **Zero migrations destrutivas**: O schema em `src/sparkspeak/infrastructure/db/migrations/001_initial.sql` já suporta 100% da nova arquitetura:
  - `cards.card_type` já inclui `'pronunciation'` (além de `'vocab'`, `'phrasal_verb'`, `'grammar_fix'`, `'tech_scenario'`).
  - `error_logs.category` já inclui `'pronunciation_asr'` (mapeado automaticamente em `SessionService._ERROR_TO_CARD_TYPE` para `card_type = 'pronunciation'` na hora de promover erros para flashcards em `end_session`).
  - `session_turns.audio_duration_ms` recebe o `duration_ms` retornado por `record_utterance`.
- Qualquer banco `.data/sparkspeak.db` existente continua funcionando sem perda de nenhum cartão, revisão ou histórico.

### Passo 2: Substituição do Módulo de Áudio Pesado pelo `WavRecorder` Leve
1. Deletar `src/sparkspeak/infrastructure/audio/piper_tts.py`, `src/sparkspeak/infrastructure/audio/whisper_stt.py` e `src/sparkspeak/cli/`.
2. Criar `src/sparkspeak/infrastructure/audio/wav_recorder.py`:
   - Captura chunks mono 16 kHz via `sounddevice.InputStream`.
   - Calcula o RMS de cada frame (`sqrt(mean(chunk ** 2))`): inicia gravação quando `rms >= rms_threshold` (inclui buffer de *pre-roll* de ~200 ms para não cortar a primeira consoante falada!) e encerra após `silence_timeout_ms` (default `1500` ms) de silêncio contínuo.
   - Converte o array `float32` para PCM 16-bit (`int16`) e grava atomicamente em `.data/audio/last_utterance.wav` usando o módulo nativo `wave` da biblioteca padrão do Python.
3. Atualizar `src/sparkspeak/config.py`:
   - Substituir `models_dir` (`SPARKSPEAK_MODELS_DIR`) por `audio_dir` (`SPARKSPEAK_AUDIO_DIR`, default `.data/audio`).
4. Atualizar `src/sparkspeak/domain/errors.py`:
   - Remover `TTS_MODEL_MISSING`, `AUDIO_OUTPUT_UNAVAILABLE`, `MODEL_NOT_INSTALLED` e `AUDIO_LOCK_BUSY`, mantendo `MICROPHONE_UNAVAILABLE` + os 5 códigos de domínio/SQLite.

### Passo 3: Remoção de Dependências Pesadas (`pyproject.toml` e `.data/models/`)
1. Remover `faster-whisper>=1.1.0` e `piper-tts>=1.2.0` de `pyproject.toml`, e remover os scripts `sparkspeak-setup-models` e `sparkspeak-health`.
2. Rodar `uv lock && uv sync` para desinstalar `faster-whisper`, `piper-tts`, `ctranslate2`, `onnxruntime`, `huggingface-hub` e `av`.
3. Remover `.data/models/` caso exista, mantendo `.data/sparkspeak.db` e `.data/backups/` intocados.

### Passo 4: Atualização dos Testes Automatizados e Documentação
1. Remover testes obsoletos de Piper/Whisper/CLI (`test_piper_tts.py`, `test_cli_setup.py`, `test_mcp_tts_tool.py`, `test_whisper_wav_fixture.py`).
2. Criar `tests/unit/test_wav_recorder.py` e atualizar `tests/unit/test_audio_service.py` e `tests/integration/test_mcp_stt_tool.py` (renomeado/adaptado para `record_utterance`) validando:
   - Gravação determinística de `.wav` 16 kHz mono 16-bit com *pre-roll* e corte por silêncio RMS.
   - Timeout limpo quando não há fala (`speech_detected: false`).
   - Erro estruturado `MICROPHONE_UNAVAILABLE` quando não há dispositivo PipeWire.
3. Registrar `ADR-0006` em `docs/adr/0006-multimodal-wav-input-and-native-voice-output.md` marcando `ADR-0004` como `Superseded` e atualizar `.specs/STATE.md` e `docs/`.

---

## 3. Novo Contrato do Servidor MCP Enxuto

### 3.1. `record_utterance` (Captura `.wav` para Escuta Multimodal via `read_file`)
Grava a fala do aluno no microfone até detectar pausa natural e salva o arquivo `.wav` para leitura direta pelo modelo Gemini via `read_file`.
- **Parâmetros**:
  - `silence_timeout_ms: int = 1500` (intervalo válido: `500..5000`)
  - `initial_speech_timeout_ms: int = 10000` (intervalo válido: `2000..30000`)
  - `max_duration_ms: int = 45000` (intervalo válido: `3000..90000`)
- **Resposta JSON (Fala Detectada)**:
  ```json
  {
    "speech_detected": true,
    "wav_path": "/home/user/workspace/sparkspeak/.data/audio/last_utterance.wav",
    "duration_ms": 3250,
    "peak_rms": 0.142,
    "truncated_at_max_duration": false
  }
  ```
- **Resposta JSON (Silêncio / Timeout Inicial)**:
  ```json
  {
    "speech_detected": false,
    "wav_path": null,
    "duration_ms": 0,
    "peak_rms": 0.002,
    "truncated_at_max_duration": false
  }
  ```

### 3.2. `start_session`
- **Parâmetros**: `deck_slug: str | None = None`, `mode: str = "mixed"`, `input_mode: str = "voice"`
- **Resposta JSON Enxuta**:
  ```json
  {
    "session_id": "d4e5f6a7-...",
    "deck": {
      "id": 3,
      "slug": "tech-meetings",
      "name": "Software Engineering Meetings",
      "persona_prompt": "..."
    },
    "mode": "mixed",
    "effective_input_mode": "voice",
    "mic_available": true,
    "due_summary": {
      "due_reviews": 4,
      "new_cards": 10
    }
  }
  ```

### 3.3. `get_due_cards`
- **Parâmetros**: `deck_slug: str | None = None`, `limit: int = 5`, `new_cards_limit: int = 2`, `include_new: bool = True`
- **Resposta JSON Enxuta**:
  ```json
  {
    "cards": [
      {
        "card_id": 12,
        "deck_slug": "phrasal-verbs",
        "front_prompt": "Rephrase using a phrasal verb: 'We need to postpone the deployment.'",
        "back_reference": "We need to put off the deployment.",
        "context_example": "Let's put off the release until the hotfix is verified.",
        "card_type": "phrasal_verb",
        "is_new": false,
        "due_at": "2026-11-20T18:00:00.000Z"
      }
    ],
    "queue_stats": {
      "returned": 1,
      "total_due_reviews": 1,
      "total_new_available": 8
    }
  }
  ```

### 3.4. `submit_review`
- **Parâmetros**: `card_id: int`, `rating: int`, `user_response_raw: str`, `input_mode: str = "voice"`, `session_id: str | None = None`, `duration_ms: int | None = None`, `idempotency_key: str | None = None`
- **Resposta JSON Enxuta**:
  ```json
  {
    "card_id": 12,
    "rating": 3,
    "fsrs_state": "Review",
    "scheduled_days": 4,
    "next_due_at": "2026-11-24T18:50:00.000Z",
    "idempotent_replay": false
  }
  ```

### 3.5. `log_mistake` (e `log_turn_and_errors`)
- **Parâmetros de `log_mistake`**:
  - `session_id: str`
  - `utterance_raw: str` (transcrição fiel ou descrição fonética do que o aluno disse, ex.: `"I work-ed (/wɜːrkɪd/) on the deploy"`)
  - `correction: str` (forma correta e pronúncia alvo, ex.: `"I worked (/wɜːrkt/) on the deployment"`)
  - `category: str = "grammar"` (`"grammar"`, `"vocabulary"`, `"phrasal_verb"`, `"pronunciation_asr"`, `"register"`)
  - `explanation: str = ""` (dica curta, ex.: `"Past tense -ed after unvoiced /k/ sounds like /t/, not an extra syllable /ɪd/."`)
  - `deck_slug: str | None = None`
  - `input_mode: str = "voice"`
  - `audio_duration_ms: int | None = None`
- **Resposta JSON Enxuta**:
  ```json
  {
    "session_id": "d4e5f6a7-...",
    "turn_index": 3,
    "error_id": 7,
    "category": "pronunciation_asr",
    "occurrence_count": 2,
    "promoted_card_id": null
  }
  ```

### 3.6. `add_card` e `end_session`
- Mantêm seus contratos determinísticos: `add_card` cria/deduplica cartões (`vocab`, `phrasal_verb`, `grammar_fix`, `pronunciation`, `tech_scenario`) e `end_session` encerra a sessão promovendo automaticamente todos os erros únicos/recorrentes do dia para novos flashcards `auto_extracted`.

---

## 4. Atualização do `SKILL.md` (Prompt Pedagógico Multimodal Voice-First)

Novo conteúdo especificado para `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`:

```markdown
---
name: english-tutor
description: >-
  Run interactive English spaced-repetition reviews (FSRS) and spoken/text roleplay
  sessions using SparkSpeak MCP tools, native multimodal WAV audio listening, and
  Antigravity Voice output. Activate when the user asks to practice English, review
  flashcards, improve pronunciation, or drill technical meeting English.
---

# English Tutor (SparkSpeak — Multimodal Pronunciation & FSRS)

You are an encouraging, sharp English conversation and pronunciation coach for software engineers.
- **Spoken Input (Multimodal Native Audio)**: Captured locally as a `.wav` file via `record_utterance` and heard directly by you via `read_file(Path=wav_path)`—giving you direct access to the learner's real voice, phonemes, word stress, intonation, and grammar without STT auto-correction.
- **Spoken Output (Antigravity Voice)**: Your replies are spoken aloud by Antigravity's native Voice output. Keep your text concise, natural, and effortless to listen to.
- **Deterministic Memory & SRS**: Handled strictly by the local `sparkspeak` MCP server (SQLite + FSRS).

## Critical Invariants (Never Violate)

1. **Always Listen to the WAV File After Recording**:
   - Whenever `record_utterance()` returns `speech_detected: true` and a `wav_path`, you **MUST** immediately call `read_file(Path=wav_path)` in the very next step so you hear the learner's raw audio before replying.
2. **Voice-Output Friendly Formatting**:
   - Because Antigravity Voice reads your replies aloud, keep active conversation turns short (**1 to 3 natural sentences, max ~45 words**).
   - **Never** output markdown tables, code blocks, long bulleted lists, file paths, UUIDs, or ISO timestamps during active conversation turns.
   - Always end your turn with **one clear question or speaking prompt** so the learner does most of the talking.
3. **Coach Real Pronunciation & Grammar Nuances**:
   - When listening to the `.wav` via `read_file`, pay attention to both **what** was said (grammar, prepositions, phrasal verbs, engineering register) and **how** it was pronounced:
     - `-ed` endings (e.g., pronouncing *"worked"* or *"stopped"* with an extra `/ɪd/` syllable instead of `/t/`).
     - Vowel epenthesis typical of Brazilian Portuguese speakers (adding `/i/` before `s+consonant` like *"es-tart"*, or after final consonants like *"deploy-ee"*).
     - Dental fricatives `/θ/` and `/ð/` (*"think"*, *"this"*), vowel contrasts (`/ɪ/` vs `/iː/` in *"ship/sheep"*), and word stress (*"DE-vel-op-ment"* vs *"de-VEL-op-ment"*).
   - Highlight at most **1–2 high-impact corrections per turn** (1 pronunciation tip or 1 grammar/phrasal-verb recast) so you never overwhelm the learner.
4. **Silent Background MCP Logging**:
   - Call `submit_review`, `log_mistake`, and `add_card` silently in the background. Never narrate tool names or IDs aloud.
   - Never fabricate SRS intervals; always use `scheduled_days` returned by `submit_review`.
5. **Always Close Sessions**:
   - Call `end_session` when the learner wraps up so today's pronunciation and grammar slips become FSRS flashcards.

## Session Workflow

### 1. Bootstrap
- Identify the target deck (`conversational`, `phrasal-verbs`, or `tech-meetings`) and mode (`active_review`, `roleplay`, or `mixed`).
- Call `start_session(deck_slug=..., mode=..., input_mode="voice")` (or `input_mode="text"` if the user requests a silent text session).
- If `mic_available` is `false`, let the learner know in 1 sentence and proceed seamlessly in `text` mode.

### 2. Multimodal Voice Turn Loop (`input_mode="voice"`)
1. Speak your prompt or roleplay line (1–3 short sentences) and immediately call `record_utterance()` so the microphone opens for the learner's reply.
2. When `record_utterance()` returns `speech_detected: true`:
   - Immediately call `read_file(Path=wav_path)` to hear the learner's recording.
   - Evaluate pronunciation, fluency, and grammar from the audio.
   - Call `submit_review` (in `active_review`) and/or `log_mistake` (whenever a grammar, phrasal verb, vocabulary, register, or `pronunciation_asr` slip is heard).
   - Reply with brief, encouraging feedback + the next prompt, and call `record_utterance()` for the next turn.
3. **Fallback to Text**: If `record_utterance()` returns `MICROPHONE_UNAVAILABLE`, if `speech_detected: false` happens twice in a row, or if the learner types in chat / asks for text mode, switch seamlessly to `text` mode without losing `session_id`.

### 3. Mode A: Active Recall Drill (`active_review`)
- Call `get_due_cards(deck_slug=..., limit=5)`.
- Present **1 card at a time** conversationally using its `front_prompt`.
- After hearing (or reading) the learner's answer, give a 1-sentence correction/confirmation, rate 1–4 (`1=Again`, `2=Hard`, `3=Good`, `4=Easy`; see `references/pedagogy-modes.md`), and call `submit_review`.
- If a pronunciation mistake reduced clarity, rate `2 (Hard)` or `3 (Good)` depending on intelligibility and log the phonetic slip via `log_mistake(category="pronunciation_asr", ...)`.

### 4. Mode B: Conversational Roleplay (`roleplay`)
- Adopt the deck's persona (`references/personas.md`).
- Keep turns brief (1–3 sentences), recast grammar/vocab slips naturally, give a quick 1-sentence pronunciation cue when you hear a clear phonetic deviation, and record mistakes silently via `log_mistake`.

### 5. Post-Session Wrap-Up
- When the learner finishes, call `end_session(session_id=..., promote_errors=True, summary_notes=...)`.
- Give a warm 2–3 sentence wrap-up covering `cards_reviewed`, new flashcards created from today's grammar/pronunciation mistakes (`errors_extracted`), and the #1 recurring pattern (`recurring_errors`).

## Reference Guides (Load On Demand)
- `references/pedagogy-modes.md`: Detailed `active_review` vs `roleplay` rules and FSRS rating rubric (1–4).
- `references/personas.md`: Personas for `conversational`, `phrasal-verbs`, and `tech-meetings`.
- `references/error-taxonomy.md`: Error categories (`grammar`, `vocabulary`, `phrasal_verb`, `pronunciation_asr`, `register`) and pronunciation/grammar card extraction rules.
```

---

## Edge Cases & Implicit-Requirement Dimensions

- **Input validation & bounds**: IF `silence_timeout_ms` is outside `[500, 5000]`, `initial_speech_timeout_ms` is outside `[2000, 30000]`, or `max_duration_ms` is outside `[3000, 90000]`, THEN `record_utterance` SHALL return `INVALID_ARGUMENT`.
- **Failure / partial-failure states**: IF PipeWire input capture fails mid-stream or PortAudio is missing THEN `record_utterance` SHALL return `MICROPHONE_UNAVAILABLE` (`isError=true`, `recoverable=true`, `fallback_hint="text"`) without crashing the MCP server.
- **Idempotency / retry / duplicate handling**: IF `submit_review` is retried with the same `idempotency_key` THEN the MCP server SHALL return the cached review result (`idempotent_replay: true`); IF `log_mistake` receives a repeated pronunciation or grammar error with the same SHA-256 fingerprint THEN it SHALL increment `occurrence_count`.
- **Auth boundaries & rate limits**: N/A because SparkSpeak runs strictly as a local single-user `stdio` child process spawned by Antigravity.
- **Concurrency / ordering**: The MCP server SHALL serialize microphone capture with an `asyncio.Lock` inside `AudioService` so concurrent `record_utterance` calls never contend on the PipeWire input device, and use SQLite WAL mode with `busy_timeout = 5000`.
- **Data lifecycle / expiry**: `record_utterance` writes to `.data/audio/last_utterance.wav` atomically (via temp file + rename), overwriting the previous turn's WAV so audio recordings never accumulate on disk; `.data/sparkspeak.db` retains all FSRS and error history indefinitely.
- **Observability**: The MCP server SHALL emit all logs strictly to `stderr` so `stdout` carries only MCP JSON-RPC frames.
- **External-dependency failure**: IF `libportaudio2` is missing on the host OS THEN `start_session` reports `mic_available: false` and `record_utterance` returns `MICROPHONE_UNAVAILABLE` with `fallback_hint: "text"`.
- **State-transition integrity**: IF `end_session` is called on an already-ended session THEN the MCP server SHALL return the existing summary idempotently without re-promoting errors.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| REFAC-01 | P1: Removal of Heavy Local STT/TTS Models & Lightweight WAV Capture (`record_utterance`) | Tasks | In Tasks |
| REFAC-02 | P1: Removal of Heavy Local STT/TTS Models & Lightweight WAV Capture (`record_utterance`) | Tasks | In Tasks |
| AUDIO-05 | P1: Removal of Heavy Local STT/TTS Models & Lightweight WAV Capture (`record_utterance`) | Tasks | In Tasks |
| SRS-05 | P2: Lean Deterministic Core (SRS + SQLite + `log_mistake`) | Tasks | In Tasks |
| SRS-06 | P2: Lean Deterministic Core (SRS + SQLite + `log_mistake`) | Tasks | In Tasks |
| SRS-07 | P2: Lean Deterministic Core (SRS + SQLite + `log_mistake`) | Tasks | In Tasks |
| SKILL-02 | P3: Multimodal Pronunciation & Voice-Output Pedagogical Skill (`SKILL.md`) | Tasks | In Tasks |
| SKILL-03 | P3: Multimodal Pronunciation & Voice-Output Pedagogical Skill (`SKILL.md`) | Tasks | In Tasks |

**Coverage:** 8 total, 8 mapped to tasks, 0 unmapped

---

## Success Criteria

- [x] `faster-whisper` and `piper-tts` are removed from `pyproject.toml`, and `piper_tts.py`, `whisper_stt.py`, and `src/sparkspeak/cli/` are deleted.
- [x] `record_utterance` captures 16 kHz mono 16-bit PCM with RMS silence endpointing into `.data/audio/last_utterance.wav`, and Antigravity's `read_file` loads that `.wav` as native `audio/wav` multimodal input.
- [x] `start_session`, `get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `log_turn_and_errors`, and `end_session` preserve 100% compatibility with existing `.data/sparkspeak.db` files.
- [x] `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md` guides the agent through `speak_text` $\rightarrow$ `record_utterance` $\rightarrow$ `read_file(wav_path)` pronunciation + grammar analysis $\rightarrow$ concise chat text.

## Post-Implementation Adjustment (User-Validated)

During live session validation, Antigravity's chat loop did not auto-speak agent text replies aloud. Per user selection (`kokoro-onnx` A/B voice test), tutor spoken output was implemented via `KokoroTTSAdapter` (`kokoro-onnx>=0.4.0`, `speak_text` tool) with 4 curated natural voices (`af_heart`, `af_jessica`, `am_liam`, `am_puck`) while keeping `record_utterance` + `read_file(wav_path)` multimodal input and minimal 1-line chat replies.
