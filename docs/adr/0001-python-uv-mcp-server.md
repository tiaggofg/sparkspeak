# ADR-0001: Python 3.12+ com `uv` e SDK Oficial `mcp` para o Servidor MCP Local

- **Status**: Accepted
- **Date**: 2026-11-20
- **Scope**: `src/sparkspeak/`, `pyproject.toml`, `.agents/plugins/sparkspeak/mcp_config.json`

## Contexto
O servidor MCP do SparkSpeak roda localmente via transporte `stdio` como processo filho do Google Antigravity no Ubuntu 24.04 e precisa orquestrar persistência SQLite, algoritmo FSRS e pipeline de áudio offline (PipeWire, Silero VAD, `faster-whisper`, `piper-tts`).

## Decisão
Adotar **Python 3.12+** gerenciado por **`uv`** com o **SDK oficial `mcp` (`MCPServer` / FastMCP)**, mantendo logging estritamente em `stderr` para preservar o stream JSON-RPC em `stdout`.

## Alternativas Consideradas
- **Java 25 + Spring AI MCP**: excelente ecossistema corporativo, porém sofre com cold-start de 2–5 s na JVM em processos `stdio` (ou exige GraalVM Native Image com complexidade extra de AOT) e não possui bindings nativos diretos para PipeWire/PortAudio, Silero VAD, `faster-whisper` (CTranslate2) e `py-fsrs` sem wrappers JNI/ProcessBuilder.

## Consequências
- **Positivas**: Startup em `stdio` ~100–250 ms, footprint base reduzido, integração direta com `sounddevice`, `faster-whisper`, `piper-tts` e `fsrs` no mesmo processo com `asyncio.Lock`.
- **Trade-offs / Riscos**: Dependência de pacotes nativos do sistema (`portaudio19-dev`, `ffmpeg`) documentada no setup e verificada via CLI de healthcheck.
