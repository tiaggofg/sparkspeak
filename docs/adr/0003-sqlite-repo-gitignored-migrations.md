# ADR-0003: Persistência SQLite Local no Repositório (Gitignored) com Migrations Versionadas

- **Status**: Accepted
- **Date**: 2026-11-20
- **Scope**: `.data/`, `.gitignore`, `src/sparkspeak/infrastructure/db/`

## Contexto
O histórico de revisões, sessões, transcrições e erros recorrentes precisa persistir entre conversas do Antigravity sem gerar ruído binário no controle de versão Git.

## Decisão
Armazenar o banco SQLite (`.data/sparkspeak.db` em modo `WAL` com `PRAGMA foreign_keys = ON`) e caches de modelos (`.data/models/`) dentro do diretório `.data/` na raiz do repositório, **excluídos via `.gitignore`** (sobrescrevível por `SPARKSPEAK_DB_PATH`). Migrations SQL sequenciais e decks iniciais (*seeds*) permanecem versionados no Git, com backup automático em `.data/backups/` antes de cada migration.

## Alternativas Consideradas
- **`~/.local/share/sparkspeak/`**: isola dados fora do repo, mas o usuário optou por manter os arquivos no diretório do projeto para fácil inspeção e portabilidade local sem versionar binários.
- **Comitar o `.db` no Git**: descartado pelo churn de arquivo binário e risco de conflitos/vazamento de gravações textuais pessoais.

## Consequências
- **Positivas**: Schema 100% reprodutível do zero a partir das migrations + seeds; zero sujeira no `git status`.
- **Trade-offs / Riscos**: Backup externo do `.data/sparkspeak.db` fica a cargo do usuário caso deseje sincronizar entre máquinas.
