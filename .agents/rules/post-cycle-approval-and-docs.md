---
trigger: always_on
---

# Regra de Aprovação, Documentação e Commit/Push Pós-Ciclo

Ao finalizar qualquer ciclo completo de implementação, refatoração ou alteração de infraestrutura/CI/CD:

## 1. Sincronização Obrigatória da Documentação (`README.md`, `docs/`, Mermaid e ADRs)
Antes de solicitar aprovação ou realizar qualquer `git push`, revise e atualize o `README.md` e a documentação técnica em `docs/` para manter tudo 100% sincronizado com o código:
- **Estrutura padrão de `docs/`** (diagramas sempre em **Mermaid** dentro do Markdown):
  - `docs/README.md`: índice geral e princípios arquiteturais.
  - `docs/arquitetura-c4.md`: diagramas C4 (Contexto, Containers, Componentes) e fronteiras de camadas.
  - `docs/modelo-dominio-e-dados.md`: `classDiagram`, `erDiagram` (tabelas/coleções/índices) e `stateDiagram-v2`.
  - `docs/fluxos-e-sequencias.md`: `flowchart` de jornadas e `sequenceDiagram` dos fluxos principais.
  - `docs/api-rest.md`: endpoints, autenticação, DTOs e códigos de erro.
  - `docs/seguranca-e-privacidade.md`: autenticação, autorização, hashing/criptografia e sigilo.
  - `docs/deploy-e-ci-cd.md`: execução local, Docker/Compose e pipelines CI/CD.
  - `docs/adr/NNNN-titulo.md` (+ `docs/adr/README.md`): ADRs formais para decisões arquiteturais duradouras, mantendo o resumo ativo sincronizado em `.specs/STATE.md` (`## Decisions`).

## 2. Padrão Obrigatório de Mensagem de Commit (Angular Conventional Commits)
Todo commit **DEVE** seguir o padrão **Conventional Commits (Angular)**:
- **Título (linha 1)**: `<type>(<escopo opcional>): <descrição curta>` com **no máximo 60 caracteres**.
  - Tipos permitidos: `feat`, `fix`, `build`, `ci`, `docs`, `perf`, `refactor`, `style`, `test`, `chore`, `revert`.
- **Corpo (a partir da linha 3, após linha em branco)**: **obrigatório**, descrevendo de forma objetiva o que foi alterado e o porquê.
- Valide antes de commitar com:
  ```bash
  .agents/scripts/validate-commit-msg.sh --message "<título>\n\n<body...>"
  ```

## 3. Aprovação Explícita Antes de Commit e Push
- **Solicitação de Aprovação**: Apresente um resumo objetivo do que foi implementado e dos resultados reais observados nos testes/verificações e **pergunte explicitamente ao usuário se as alterações estão aprovadas**.
- **Sem Commit/Push Antes da Aprovação**: Nunca execute `git commit` ou `git push` antes de receber a aprovação explícita do usuário para o ciclo concluído (salvo quando o usuário já tiver autorizado explicitamente na sessão).
- **Commit e Push Após Aprovação**: Após confirmação, realize `git add`, `git commit` (seguindo o padrão acima) e `git push` para o repositório remoto, incluindo as atualizações de `README.md`, `docs/` e `.specs/`.
