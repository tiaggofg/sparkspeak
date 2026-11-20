# ADR-0004: Pipeline de Áudio Offline PipeWire (`piper-tts` + Silero VAD + `faster-whisper`)

- **Status**: Accepted
- **Date**: 2026-11-20
- **Scope**: `src/sparkspeak/infrastructure/audio/`, `src/sparkspeak/application/audio_service.py`

## Contexto
O Voice Mode nativo da IDE corrige automaticamente erros de fala antes de entregar o texto ao LLM, inviabilizando feedback pedagógico real. Além disso, chamadas simultâneas de microfone e alto-falante causam eco e disputa no PipeWire.

## Decisão
Implementar I/O de áudio determinístico no mesmo processo MCP sob um `asyncio.Lock` único (`AudioLock`):
- **Output (TTS)**: `piper-tts` offline (`en_US-lessac-medium` ONNX) tocando via `sounddevice` no sink padrão do PipeWire (atrás de uma porta `TTSEngine` plugável).
- **Input (STT)**: captura PCM 16 kHz mono via `sounddevice` com detecção de silêncio **Silero VAD** (`silence_timeout_ms=1500`, `initial_speech_timeout_ms=10000`, `max_duration_ms=45000`) e transcrição literal local via **`faster-whisper`** (`compute_type="int8"`, `language="en"`, sem reescrita gramatical).
- **Fallback**: erros recuperáveis de hardware/modelo retornam contrato estruturado com `fallback_hint: "text"`.

## Alternativas Consideradas
- **Servidor MCP externo (`tts-mcp` / `kokoro-tts-mcp`)**: separaria o controle de áudio em dois processos independentes sem lock compartilhado; Kokoro também exige ~600 MB+ RAM e maior CPU.
- **`edge-tts`**: vozes neurais de alta qualidade, mas exige conexão de internet e depende de endpoint não-oficial.

## Consequências
- **Positivas**: Operação 100% offline, preservação fiel dos erros do aluno, baixa latência e isolamento contra auto-gravação do TTS.
- **Trade-offs / Riscos**: Exige download prévio dos pesos locais via CLI (`sparkspeak-setup-models`).
