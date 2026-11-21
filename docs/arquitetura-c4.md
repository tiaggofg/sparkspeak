# Arquitetura e Diagramas C4

## 1. Diagrama de Contexto (C1)

```mermaid
flowchart LR
  User["Aprendiz (Ubuntu 24.04)"] <-->|"Antigravity Voice + Mic PipeWire"| AGY["Google Antigravity + SparkSpeak"]
  AGY <-->|"Buffer WAV (.data/audio/last_utterance.wav)"| WAV[("Áudio Bruto 16 kHz PCM")]
  AGY <-->|"Persistência local (.data/sparkspeak.db)"| DB[("SQLite WAL")]
```

## 2. Diagrama de Containers (C2)

```mermaid
flowchart TB
  subgraph Host["Google Antigravity IDE / CLI"]
    LLM["Antigravity Gemini (Multimodal Audio + Native Voice) + Skill english-tutor"]
    MCPHost["MCP Client (stdio)"]
  end

  subgraph Server["SparkSpeak MCP Server (Python 3.12 + uv)"]
    Router["MCPServer Tool Router (src/sparkspeak/mcp/server.py)"]
    Services["Application Services (SessionService, ReviewService, AudioService)"]
    Domain["Domain (SRSEngine py-fsrs, Models, Errors)"]
    Repo["SQLiteRepository + Migrator"]
    Audio["Adapters (WavRecorder, KokoroTTSAdapter, PipeWire)"]
  end

  subgraph OS["Ubuntu 24.04"]
    PW["PipeWire / PortAudio (sounddevice)"]
    WAV[(".data/audio/last_utterance.wav")]
    SQLite[("SQLite .data/sparkspeak.db")]
  end

  LLM <--> MCPHost
  LLM -->|"read_file(wav_path)"| WAV
  MCPHost <-->|"JSON-RPC over stdio (logs -> stderr)"| Router
  Router --> Services
  Services --> Domain
  Services --> Repo
  Services --> Audio
  Repo <--> SQLite
  Audio <--> PW
  Audio -->|"Gravação atômica"| WAV
```

## 3. Componentes e Camadas (C3)

- **Domain (`src/sparkspeak/domain/`)**: `srs_engine.py` (wrapper puro de `py-fsrs` com `desired_retention=0.90`), `models.py` (DTOs imutáveis) e `errors.py` (`ErrorCode`, `SparkSpeakError`).
- **Application (`src/sparkspeak/application/`)**: `review_service.py` (validação de limites, `get_due_cards`, `submit_review`, `add_card`), `session_service.py` (`start_session` com `mic_available`, `switch_input_mode`, `log_mistake`, `log_turn_and_errors`, `end_session` com promoção de erros) e `audio_service.py` (`asyncio.Lock` single-flight para `record_utterance`).
- **Infrastructure (`src/sparkspeak/infrastructure/`)**:
  - `db/`: `connection.py` (WAL, `foreign_keys=ON`, `busy_timeout=5000`), `migrator.py` (backup pré-migração + `001_initial.sql` + `001_default_decks.sql`) e `repositories.py`.
  - `audio/`: `ports.py` (`UtteranceRecorder`, `TTSEngine`, `RecordUtteranceResult`, `SpeakResult`), `pipewire_device.py`, `wav_recorder.py` (`WavRecorder` 16 kHz mono 16-bit PCM com endpointing RMS) e `kokoro_tts.py` (`KokoroTTSAdapter` offline com vozes `af_heart`, `af_jessica`, `am_liam`, `am_puck`).
- **MCP (`src/sparkspeak/mcp/`)**: `server.py` (entrypoint `sparkspeak-mcp`, expondo 9 tools enxutas).
