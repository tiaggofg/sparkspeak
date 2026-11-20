# Segurança e Privacidade

## 1. Execução Local-First e Isolamento de Rede

- O servidor MCP `sparkspeak-mcp` roda exclusivamente como processo filho local via `stdio` JSON-RPC iniciado pelo Google Antigravity, sem sockets TCP ou APIs HTTP expostas.
- Nenhuma transcrição, áudio ou histórico de estudo é enviado para APIs externas: `piper-tts`, Silero VAD e `faster-whisper` executam offline usando modelos cacheados em `.data/models/`.

## 2. Higiene do Canal `stdio`

- `src/sparkspeak/mcp/server.py` configura `logging.basicConfig(stream=sys.stderr, force=True)` antes de importar `mcp`, `faster_whisper` ou `piper`, garantindo que `stdout` permaneça 100% reservado a frames JSON-RPC.

## 3. Persistência, Integridade e Privacidade de Dados

- O banco `.data/sparkspeak.db` e os modelos `.data/models/` ficam em `.gitignore` para nunca vazar dados pessoais de estudo no repositório Git.
- Todas as conexões SQLite aplicam `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL` e `PRAGMA busy_timeout = 5000`.
- `review_logs`, `study_sessions` e `session_turns` são preservados para rastreabilidade; cartões desativados usam `suspended = 1` em vez de remoção física.
- Operações de áudio compartilham um único `asyncio.Lock` em `AudioService` para impedir captura simultânea do próprio TTS pelo microfone.
