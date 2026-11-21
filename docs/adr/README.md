# Architecture Decision Records (ADRs)

Este diretório armazena as decisões arquiteturais relevantes do projeto em arquivos individuais numerados no formato `NNNN-titulo-em-kebab-case.md` (ex.: `0001-escolha-banco-de-dados.md`).

Use [`0000-template.md`](./0000-template.md) como base para cada novo ADR e mantenha o resumo ativo sincronizado em `.specs/STATE.md` (`## Decisions`).

## Índice

| ADR | Título | Status | Data |
| :--- | :--- | :--- | :--- |
| [0000](./0000-template.md) | Template de ADR | template | — |
| [0001](./0001-python-uv-mcp-server.md) | Python 3.12+ com `uv` e SDK Oficial `mcp` para o Servidor MCP Local | Accepted | 2026-11-20 |
| [0002](./0002-fsrs-spaced-repetition.md) | Algoritmo FSRS (`py-fsrs`) em vez de SM-2 | Accepted | 2026-11-20 |
| [0003](./0003-sqlite-repo-gitignored-migrations.md) | Persistência SQLite Local no Repositório (Gitignored) com Migrations Versionadas | Accepted | 2026-11-20 |
| [0004](./0004-offline-pipewire-audio-pipeline.md) | Pipeline de Áudio Offline PipeWire (`piper-tts` + Silero VAD + `faster-whisper`) | Superseded by 0006 | 2026-11-20 |
| [0005](./0005-antigravity-workspace-plugin.md) | Empacotamento como Workspace Plugin do Antigravity | Accepted | 2026-11-20 |
| [0006](./0006-multimodal-wav-input-and-native-voice-output.md) | Captura WAV Multimodal Nativa e Output via Antigravity Voice | Accepted | 2026-11-20 |
