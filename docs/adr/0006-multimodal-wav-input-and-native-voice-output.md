# ADR-0006: Captura WAV Multimodal Nativa e Output via Antigravity Voice

- **Status**: Accepted (supersedes [ADR-0004](./0004-offline-pipewire-audio-pipeline.md))
- **Date**: 2026-11-20
- **Scope**: `pyproject.toml`, `src/sparkspeak/infrastructure/audio/`, `src/sparkspeak/application/`, `src/sparkspeak/mcp/server.py`, `.agents/plugins/sparkspeak/skills/english-tutor/SKILL.md`

## Contexto
Na v0.1 ([ADR-0004](./0004-offline-pipewire-audio-pipeline.md)), `faster-whisper` (STT) e `piper-tts` (TTS) adicionavam ~500 MB de dependências neurais (`ctranslate2`, `onnxruntime`, `huggingface-hub`, `.data/models/`) e convertiam a fala do aluno em texto antes do modelo Gemini ouvi-la. Esse gargalo de texto mascarava nuances acústicas reais de pronúncia (fonemas `/θ/` vs `/t/`, terminação `-ed`, epêntese vocálica, *word stress* e entonação).

## Decisão
Substituir o pipeline local de STT/TTS por arquitetura multimodal nativa:
1. **Input de Áudio (`record_utterance`)**: `WavRecorder` captura PCM 16 kHz mono 16-bit via `sounddevice` com endpointing determinístico por energia RMS (`numpy`, pre-roll de 200 ms, `rms_threshold=0.015`) e grava atomicamente em `.data/audio/last_utterance.wav`.
2. **Escuta Multimodal Direta (`read_file`)**: A skill `english-tutor` lê `wav_path` imediatamente via `read_file` do Antigravity, injetando `audio/wav` bruto no contexto multimodal do Gemini.
3. **Output de Voz (`kokoro-onnx` via `speak_text`)**: As respostas curtas do tutor (1–3 frases) são sintetizadas localmente offline via `kokoro-onnx` (vozes curadas: `af_heart`, `af_jessica`, `am_liam`, `am_puck` em `.data/models/`) e reproduzidas no PipeWire sob o mesmo `asyncio.Lock` do `AudioService`, mantendo o texto no chat mínimo.
4. **Registro de Erros (`log_mistake`)**: Expor atalho plano `log_mistake` com deduplicação SHA-256 preservando `log_turn_and_errors`, FSRS (`py-fsrs`) e SQLite intactos.

## Alternativas Consideradas
- **Manter `faster-whisper` com `word_timestamps` / `logprobs`**: ainda descarta informação fonética e prosódica real e mantém ~350 MB de dependências.
- **TTS local alternativo (`kokoro` / `edge-tts`)**: redundante diante do Voice nativo do Antigravity.

## Consequências
- **Positivas**: Zero pesos neurais locais (~500 MB removidos), cold start instantâneo do servidor MCP, coaching real de pronúncia diretamente do áudio bruto e uso de disco limitado (~100 KB reciclado em `.data/audio/last_utterance.wav`).
- **Trade-offs**: Em modo `voice`, cada turno requer o encadeamento `record_utterance()` -> `read_file(Path=wav_path)` na Skill.
