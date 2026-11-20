# AGENTS.md — <!-- Nome do Projeto -->

Este documento define o contexto arquitetural, convenções de código, comandos essenciais e regras de verificação para agentes de IA trabalhando neste repositório.

> As regras gerais de fluxo Spec-Driven, verificação pós-implementação, aprovação e sincronização de documentação vivem em `.agents/rules/` e são gerenciadas via `agent-spec-kit` (`.agents/update-spec-kit.sh`).

---

## 1. Visão Geral do Projeto

<!-- Descreva em 2-4 frases o propósito do projeto e suas principais capacidades de domínio. -->

---

## 2. Stack Tecnológica e Estrutura do Repositório

```text
<!-- Nome do projeto -->/
├── <!-- backend/ ou src/ -->
├── <!-- frontend/ -->
├── docs/                   # Documentação técnica
├── .specs/                 # Spec-Driven Development (STATE.md e features/)
└── .agents/                # Regras e skills do harness
```

- **Linguagem & Framework**: <!-- ex: Java 25 + Spring Boot / TypeScript + Node / Angular / Next.js -->
- **Persistência**: <!-- ex: PostgreSQL / MongoDB / SQLite -->
- **Testes**: <!-- ex: JUnit 5 / Vitest / Playwright -->

---

## 3. Diretrizes de Arquitetura e Invariantes Críticas

<!-- Liste invariantes que nunca podem ser violadas neste projeto (ex: isolamento de domínio, segurança, privacidade, padrões de UI). -->

- **Invariante 1**: ...
- **Invariante 2**: ...

---

## 4. Comandos de Desenvolvimento e Testes

```bash
# Subir dependências locais (se aplicável)
# docker compose up -d

# Testes automatizados
# ...

# Build
# ...

# Executar aplicação localmente
# ...
```

---

## 5. Regras do Harness (Spec-Driven & Pós-Ciclo)

As regras detalhadas estão em `.agents/rules/` (sempre ativas):
- **Planejamento vs Implementação**: `.agents/rules/spec-handoff-only.md`
- **Verificação Pós-Implementação**: `.agents/rules/post-implementation-testing.md`
- **Documentação e Aprovação antes de Commit/Push**: `.agents/rules/post-cycle-approval-and-docs.md`
- **Execução de Tasks Aprovadas**: `.agents/skills/implement-spec-tasks/SKILL.md`
