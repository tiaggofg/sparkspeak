# Deploy e CI/CD

## 1. Execução Local (Ubuntu 24.04 + Python 3.12 + `uv`)

```bash
# 1. Instalar dependências Python
uv sync

# 2. Baixar voz Piper ONNX (en_US-lessac-medium) e pré-cachear faster-whisper (base)
uv run sparkspeak-setup-models

# 3. Verificar modelos e dispositivos PipeWire
uv run sparkspeak-health

# 4. Iniciar servidor MCP manualmente (stdio)
uv run sparkspeak-mcp
```

Variáveis de ambiente opcionais (definidas em `src/sparkspeak/config.py`):
- `SPARKSPEAK_DB_PATH`: caminho alternativo para o SQLite (padrão `.data/sparkspeak.db`).
- `SPARKSPEAK_BACKUPS_DIR`: diretório de backups pré-migração (padrão `.data/backups`).
- `SPARKSPEAK_MODELS_DIR`: diretório de modelos locais (padrão `.data/models`).

## 2. Plugin Google Antigravity

O plugin do workspace reside em `.agents/plugins/sparkspeak/`:
- `plugin.json`: manifesto do plugin.
- `mcp_config.json`: registra o servidor `stdio` (`uv run sparkspeak-mcp`).
- `skills/english-tutor/SKILL.md` + `references/`: instruções pedagógicas carregadas sob demanda.

## 3. Verificação e Quality Gate

```bash
# Lint, tipagem estática e suíte completa
uv run ruff check src tests
uv run mypy src
uv run pytest -v

# Quality Gate determinístico (Lint + SonarQube local)
.agents/scripts/quality-check.sh --up
```
