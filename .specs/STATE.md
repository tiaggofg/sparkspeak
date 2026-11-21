# STATE

## Decisions

### AD-001
- **Decision**: Usar Python 3.12+ gerenciado por `uv` com o SDK oficial `mcp` (`MCPServer` / FastMCP) via transporte `stdio` (logs apenas em `stderr`) para o servidor MCP local.
- **Reason**: Cold start rápido (~100–250 ms) e ecossistema nativo sem JNI para `sounddevice` (PipeWire), `faster-whisper`, Silero VAD, `piper-tts` e `fsrs`.
- **Trade-off**: Requer dependências de sistema (`portaudio19-dev`, `ffmpeg`) no Ubuntu 24.04; ver `docs/adr/0001-python-uv-mcp-server.md`.
- **Scope**: `src/sparkspeak/`, `pyproject.toml`, `.agents/plugins/sparkspeak/mcp_config.json`
- **Date**: 2026-11-20
- **Status**: active

### AD-002
- **Decision**: Adotar FSRS (`py-fsrs`, `desired_retention=0.90`) como algoritmo determinístico de repetição espaçada em vez de SM-2.
- **Reason**: Modela Difficulty, Stability e Retrievability evitando *ease hell* e registra `review_logs` completos para futura otimização.
- **Trade-off**: Exige persistência de campos FSRS adicionais (`fsrs_state`, `stability`, `difficulty`, `step`, `reps`, `lapses`); ver `docs/adr/0002-fsrs-spaced-repetition.md`.
- **Scope**: `src/sparkspeak/domain/srs_engine.py`, `cards`, `review_logs`
- **Date**: 2026-11-20
- **Status**: active

### AD-003
- **Decision**: Manter banco SQLite (`.data/sparkspeak.db`, modo `WAL`, `foreign_keys = ON`) e modelos locais (`.data/models/`) dentro do repositório, excluídos via `.gitignore` (override via `SPARKSPEAK_DB_PATH`), versionando migrations SQL e seeds.
- **Reason**: Solicitação explícita do usuário de manter os dados no diretório do projeto sem poluir o histórico Git com binários mutáveis.
- **Trade-off**: Backup/sync entre máquinas fica externo ao Git (snapshots locais pré-migration em `.data/backups/`); ver `docs/adr/0003-sqlite-repo-gitignored-migrations.md`.
- **Scope**: `.data/`, `.gitignore`, `src/sparkspeak/infrastructure/db/`
- **Date**: 2026-11-20
- **Status**: active

### AD-004
- **Decision**: Pipeline de áudio offline PipeWire em processo único sob `asyncio.Lock` (`AudioLock`), com `piper-tts` (`en_US-lessac-medium` ONNX) para TTS e captura 16 kHz + Silero VAD + `faster-whisper` (`int8`, transcrição literal sem autocorreção) para STT, com fallback para texto.
- **Reason**: Preserva erros reais de fala do aluno, evita auto-gravação da saída TTS e funciona 100% offline no Ubuntu 24.04.
- **Trade-off**: Exige download prévio dos pesos via `sparkspeak-setup-models`; ver `docs/adr/0004-offline-pipewire-audio-pipeline.md`.
- **Scope**: `src/sparkspeak/infrastructure/audio/`, `src/sparkspeak/application/audio_service.py`
- **Date**: 2026-11-20
- **Status**: superseded by AD-006

### AD-005
- **Decision**: Empacotar Skill e servidor MCP como Workspace Plugin do Antigravity em `.agents/plugins/sparkspeak/` (`plugin.json`, `mcp_config.json`, `skills/english-tutor/SKILL.md`).
- **Reason**: Escopo estrito ao projeto no Antigravity conforme preferência do usuário, mantendo *progressive disclosure* da Skill sem hooks síncronos globais.
- **Trade-off**: Disponível apenas quando este workspace está aberto; ver `docs/adr/0005-antigravity-workspace-plugin.md`.
- **Scope**: `.agents/plugins/sparkspeak/`
- **Date**: 2026-11-20
- **Status**: active

### AD-006
- **Decision**: Substituir `faster-whisper` (STT local) e `piper-tts` (TTS local) por captura ultraleve de `.wav` 16 kHz mono 16-bit PCM com endpointing de silêncio por energia RMS (`record_utterance` -> `.data/audio/last_utterance.wav`), lido diretamente como áudio multimodal (`audio/wav`) pelo Gemini via `read_file` do Antigravity, combinado com **`kokoro-onnx`** (`speak_text`, vozes curadas `af_heart`, `af_jessica`, `am_liam`, `am_puck` em `.data/models/`) para saída de voz natural offline e texto mínimo no chat.
- **Reason**: Qualquer STT intermediário converte fala em texto e mascara nuances reais de pronúncia (fonemas `/θ/`, terminação `-ed`, vogal epentética, *word stress* e entonação). Ao ler o `.wav` diretamente via `read_file`, o Gemini ouve o áudio bruto real do aluno; e o `kokoro-onnx` fornece saída de voz humana offline no PipeWire sem depender de chaves de API externas.
- **Trade-off**: Requer `speak_text` -> `record_utterance` -> `read_file(wav_path)` na Skill durante sessões em modo `voice` e os dois arquivos do Kokoro em `.data/models/` (~338 MB).
- **Scope**: `pyproject.toml`, `src/sparkspeak/infrastructure/audio/`, `src/sparkspeak/application/`, `src/sparkspeak/mcp/server.py`, `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`
- **Date**: 2026-11-20
- **Status**: active

## Handoff

- **Feature**: `02-native-voice-refactoring`
- **Phase / Task**: Completed (`T1`–`T8` + `kokoro-onnx` hybrid voice output) — Approved by user
- **Completed**:
  - `T1`–`T4`: Removed `faster-whisper`, `piper-tts`, `src/sparkspeak/cli/`, and obsolete tests; implemented `WavRecorder`, `KokoroTTSAdapter` (`af_heart`, `af_jessica`, `am_liam`, `am_puck`), `AudioService`, `audio_dir` + `models_dir` config
  - `T5`–`T6`: Added `SessionService.log_mistake`, `mic_available`, and `tts_available`; exposed 9 MCP tools (`start_session`, `get_due_cards`, `submit_review`, `add_card`, `log_mistake`, `log_turn_and_errors`, `end_session`, `record_utterance`, `speak_text`)
  - `T7`–`T8`: Updated `english-tutor` `SKILL.md` + `personas.md` + `error-taxonomy.md`, created `ADR-0006` (superseding `ADR-004`), and synced `README.md` and `docs/*.md`
- **In-progress** (file:line): none
- **Next step**: None (feature committed and pushed)
- **Blockers**: none
- **Uncommitted files**: `.specs/features/02-native-voice-refactoring/spec.md`, `.specs/features/02-native-voice-refactoring/tasks.md`, `.specs/STATE.md`
- **Branch**: main
