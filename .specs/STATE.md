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
- **Status**: active

### AD-005
- **Decision**: Empacotar Skill e servidor MCP como Workspace Plugin do Antigravity em `.agents/plugins/sparkspeak/` (`plugin.json`, `mcp_config.json`, `skills/english-tutor/SKILL.md`).
- **Reason**: Escopo estrito ao projeto no Antigravity conforme preferência do usuário, mantendo *progressive disclosure* da Skill sem hooks síncronos globais.
- **Trade-off**: Disponível apenas quando este workspace está aberto; ver `docs/adr/0005-antigravity-workspace-plugin.md`.
- **Scope**: `.agents/plugins/sparkspeak/`
- **Date**: 2026-11-20
- **Status**: active

## Handoff

- **Feature**: `01-english-tutor-harness`
- **Phase / Task**: T1–T20 implementadas, verificadas pelo Verifier independente (`c39e952`) e aguardando revisão/aprovação final do usuário para push
- **Completed**:
  - `.specs/features/01-english-tutor-harness/spec.md` (Approved)
  - `.specs/features/01-english-tutor-harness/design.md` (Approved)
  - `.specs/features/01-english-tutor-harness/tasks.md` (Approved, T1–T20 `[x]`)
  - `.specs/features/01-english-tutor-harness/proofs.md` (`17 pass, 0 fail` em `c39e952`)
  - `.specs/features/01-english-tutor-harness/verification.md` (`Verdict: PASS`, 3 findings fechados em `c39e952`)
  - `docs/adr/0001..0005` + `docs/adr/README.md` + `docs/*.md` + `README.md`
- **In-progress** (file:line): none
- **Next step**: Aguardar aprovação explícita do usuário para `git push` (e instalação opcional de `libportaudio2` + `uv run sparkspeak-setup-models` para áudio PipeWire ao vivo)
- **Blockers**: Ambiente sem `libportaudio2` / hardware PipeWire e sem pesos baixados em `.data/models/` (testes de áudio executados com mocks e fixture WAV determinístico)
- **Uncommitted files**: Arquivos iniciais do harness/specs/docs pré-existentes (`.agents/`, `.specs/`, `docs/adr/`, `AGENTS.md`, `sonar-project.properties`, etc.)
- **Branch**: main
