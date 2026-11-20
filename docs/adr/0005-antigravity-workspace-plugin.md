# ADR-0005: Empacotamento como Workspace Plugin do Antigravity

- **Status**: Accepted
- **Date**: 2026-11-20
- **Scope**: `.agents/plugins/sparkspeak/`

## Contexto
O usuário utilizará o SparkSpeak exclusivamente dentro deste projeto no Google Antigravity, sem poluir outros repositórios de trabalho com tools de tutoria de inglês ou prompts pedagógicos no contexto.

## Decisão
Empacotar o harness como plugin nativo de workspace em `.agents/plugins/sparkspeak/` contendo `plugin.json`, `mcp_config.json` e `skills/english-tutor/SKILL.md` (+ `references/`), aproveitando *progressive disclosure* para carregar instruções pedagógicas apenas durante sessões de estudo.

## Alternativas Consideradas
- **Configuração global (`~/.gemini/config/mcp_config.json`)**: carregaria o servidor MCP em todos os workspaces do usuário desnecessariamente.
- **Hooks síncronos (`hooks.json`)**: adicionariam latência em turnos normais de código; o ciclo de sessão é gerido pela Skill + tools MCP.

## Consequências
- **Positivas**: Isolamento total no projeto `sparkspeak`, configuração versionável em equipe e ativação sob demanda.
- **Trade-offs / Riscos**: Para estudar a partir de outro workspace no futuro, será necessário referenciar o plugin ou registrá-lo globalmente.
