# Deploy e CI/CD

## 1. Execução Local (Ubuntu 24.04 + Python 3.12 + `uv`)

```bash
# 1. Instalar dependências Python (sem pesos neurais locais)
uv sync

# 2. Iniciar servidor MCP manualmente (stdio)
uv run sparkspeak-mcp
```

Variáveis de ambiente opcionais (definidas em `src/sparkspeak/config.py`):
- `SPARKSPEAK_DB_PATH`: caminho alternativo para o SQLite (padrão `.data/sparkspeak.db`).
- `SPARKSPEAK_BACKUPS_DIR`: diretório de backups pré-migração (padrão `.data/backups`).
- `SPARKSPEAK_AUDIO_DIR`: diretório do buffer WAV temporário (padrão `.data/audio`).
- `SPARKSPEAK_MODELS_DIR`: diretório dos modelos locais do Kokoro ONNX (`kokoro-v1.0.onnx` e `voices-v1.0.bin`, padrão `.data/models`).

## 2. Plugin Google Antigravity

O plugin do workspace reside em `.agents/plugins/sparkspeak/`:
- `plugin.json`: manifesto do plugin.
- `mcp_config.json`: registra o servidor `stdio` (`uv run sparkspeak-mcp`).
- `skills/english-tutor/SKILL.md` + `references/`: instruções pedagógicas multimodais carregadas sob demanda.

## 3. Verificação e Quality Gate

```bash
# Lint, tipagem estática e suíte completa
uv run ruff check src tests
uv run mypy src
uv run pytest -v

# Quality Gate determinístico (Lint + SonarQube local)
.agents/scripts/quality-check.sh --up
```
