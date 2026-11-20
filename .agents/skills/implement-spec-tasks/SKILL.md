---
name: implement-spec-tasks
description: >-
  Implements approved feature tasks from .specs/features/<feature>/tasks.md.
  Use when starting an implementation session from an approved spec/tasks/handoff, loading full context
  from .specs/, AGENTS.md, docs/, and the codebase, executing tasks, verifying with tests and real E2E/HTTP checks,
  and updating documentation before asking for commit/push approval.
---

# Implement Spec Tasks

Execute este runbook (via `/implement-spec-tasks` ou `/implement-spec-tasks <feature> [tasks]`) ao iniciar uma nova sessão responsável por implementar uma spec aprovada em `.specs/features/<feature>/`.

---

## Etapa 1 — Carregar Contexto Obrigatório (Antes de Editar Código)

1. **Identificar a Feature e Escopo**:
   - Se o usuário informou `<feature>` (e opcionalmente tasks específicas, ex.: `T1..T3`), use esse escopo.
   - Caso contrário, leia `.specs/STATE.md` (`## Handoff`) para identificar a feature ativa e implemente todas as tasks pendentes (`- [ ]`).
   - Se a feature não estiver clara ou não houver tasks pendentes, liste as features em `.specs/features/` que possuem pendências e pergunte ao usuário qual executar.

2. **Estado, Spec & Plano (`.specs/`)** — leia **na ordem abaixo** apenas os trechos necessários:
   - `.specs/STATE.md`: leia as decisões arquiteturais ativas (`AD-001`..`AD-NNN`) e a seção `## Handoff`.
   - `.specs/features/<feature>/spec.md`: leia integralmente o Problem Statement, Goals, Out of Scope, Decisões, Contratos e Critérios de Aceitação (EARS). **Confirme que `spec.md` está aprovada** (`**Status**: Approved`); caso contrário, pare e peça aprovação antes de editar código.
   - `.specs/features/<feature>/design.md` (se existir): leia a arquitetura e decisões de componentes da feature.
   - `.specs/features/<feature>/tasks.md`: mapeie todas as tasks, dependências, testes e critérios de verificação.

3. **Regras e Arquitetura do Projeto**:
   - `AGENTS.md`: leia o contexto arquitetural, stack, invariantes críticas e comandos de build/teste do repositório.
   - `docs/` (se existir): leia os documentos técnicos relevantes ao escopo da task (arquitetura, modelo de dados, fluxos, API, segurança, deploy).

4. **Código-Fonte Relacionado**:
   - Localize os módulos, endpoints, componentes e testes existentes que serão tocados antes de propor ou escrever código novo.

---

## Etapa 2 — Respeitar Invariantes Arquiteturais do Projeto

- Nunca viole as invariantes definidas em `AGENTS.md` e nas decisões `AD-NNN` de `.specs/STATE.md` (ex.: isolamento de domínio/Clean Architecture, regras de privacidade/sigilo em payloads, convenções de idioma/UX, acessibilidade e padrões de código do projeto).
- Caso identifique conflito entre uma task e uma decisão arquitetural ativa (`AD-NNN`), pare e alinhe com o usuário ou registre a nova decisão seguindo o processo do projeto.

---

## Etapa 3 — Implementação Orientada às Tasks (`tasks.md`)

1. Execute as tasks na ordem definida em `.specs/features/<feature>/tasks.md` (respeitando dependências).
2. Antes de editar cada arquivo/serviço/componente, leia os arquivos existentes e seus respectivos testes para reutilizar padrões e helpers já presentes no repositório.
3. Crie ou atualize testes unitários e de integração junto com cada grupo de tasks.
4. Marque cada checkbox `- [x]` em `.specs/features/<feature>/tasks.md` apenas depois que o item e seus testes estiverem implementados e verificados.

---

## Etapa 4 — Verificação Obrigatória Pós-Implementação

Siga estritamente `.agents/rules/post-implementation-testing.md` e os comandos definidos em `AGENTS.md`:

1. **Testes Automatizados e Build**:
   - Execute toda a suíte de testes e build das camadas alteradas (Backend, Frontend, testes de arquitetura/contrato, lint/typecheck).
2. **Análise Estática Determinística (Lint + SonarQube Local)**:
   - Execute `.agents/scripts/quality-check.sh --up` para validar lint e consultar deterministicamente o Quality Gate do SonarQube local.
3. **Validação Prática Real (Obrigatória)**:
   - Suba os serviços necessários do projeto (banco, backend, frontend) para validação real.
   - **Se tocou Frontend ou Full-Stack**: execute validação E2E real via **Playwright** (MCP Playwright, subagente `browser` ou script headless) em mobile e desktop cobrindo todos os fluxos e estados da spec, inspecionando visualmente screenshots, layout/overflow e ausência de erros no console.
   - **Se tocou Somente Backend**: execute requisições HTTP reais (`curl` / script) contra a API em execução validando payloads, autenticação, status codes (sucesso + erro) e persistência.
   - **Se tocou CLI / Script / Biblioteca**: execute comandos reais cobrindo casos de sucesso e erro.
   - Remova artefatos/screenshots temporários de validação e encerre processos daemons temporários ao finalizar.

---

## Etapa 5 — Documentação, Handoff e Aprovação

Siga estritamente `.agents/rules/post-cycle-approval-and-docs.md`:

1. **Sincronizar Documentação (`README.md` e `docs/`)**:
   - Revise e atualize os arquivos impactados em `README.md` e `docs/` para refletir fielmente o estado atual do código.
2. **Atualizar Spec & Estado**:
   - Garanta que todas as tasks concluídas estejam marcadas em `.specs/features/<feature>/tasks.md`.
   - Atualize `.specs/STATE.md` (novas `AD-xxx` se houver decisão arquitetural duradoura e `## Handoff` indicando entrega verificada aguardando aprovação).
3. **Solicitar Aprovação (Sem Commit/Push Antes)**:
   - Apresente um resumo objetivo do que foi implementado e dos resultados reais observados nos testes/Playwright/requests.
   - **Pergunte explicitamente ao usuário se as alterações estão aprovadas** para então realizar `git add`, `git commit` (Conventional Commits) e `git push` somente após a confirmação.
