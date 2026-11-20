# Documentação Técnica — SparkSpeak

Documentação viva da arquitetura, domínio, fluxos, contratos MCP, segurança, deploy e decisões arquiteturais (ADRs) do SparkSpeak.

---

## Mapa de Documentos

| Documento | Descrição |
| :--- | :--- |
| [Arquitetura e Diagramas C4](./arquitetura-c4.md) | Diagramas C4 (Contexto, Containers, Componentes) e fronteiras de camadas |
| [Modelo de Domínio e Dados](./modelo-dominio-e-dados.md) | Diagrama de classes, ER SQLite, índices e máquina de estados |
| [Fluxos e Diagramas de Sequência](./fluxos-e-sequencias.md) | Fluxogramas de jornada e diagramas de sequência (Voz, Fallback, Pós-sessão) |
| [Referência da API REST](./api-rest.md) | Nota sobre transporte MCP `stdio` (sem API REST exposta) |
| [Segurança e Privacidade](./seguranca-e-privacidade.md) | Isolamento local-first, higiene de `stdout`, privacidade de áudio e SQLite |
| [Deploy e CI/CD](./deploy-e-ci-cd.md) | Execução local com `uv`, setup de modelos, `sparkspeak-health` e Quality Gate |
| [ADRs (Decisões Arquiteturais)](./adr/README.md) | Registro histórico de Architecture Decision Records (`docs/adr/0001..0005`) |

---

## Princípios Arquiteturais Fundamentais

1. **Separação Pedagógica vs. Determinismo**: O LLM do Antigravity conduz conversação e avaliação semântica via `SKILL.md`; o servidor MCP Python executa FSRS, persistência SQLite e I/O de áudio de forma determinística.
2. **Local-First & Zero Custo Externo**: Todo processamento (SQLite `.data/sparkspeak.db`, `piper-tts`, Silero VAD e `faster-whisper`) roda localmente na estação Ubuntu 24.04 sem chamadas a APIs externas de LLM/STT/TTS.
3. **Preservação Verbatim de Erros**: `listen_and_transcribe` retorna transcrição bruta sem autocorreção gramatical ou *prompt biasing*, garantindo visibilidade real dos erros do aprendiz.
4. **Degradação Graciosa**: Falhas de microfone, sink PipeWire ou modelos ausentes retornam erros estruturados recuperáveis (`recoverable: true`, `fallback_hint: "text"`).
