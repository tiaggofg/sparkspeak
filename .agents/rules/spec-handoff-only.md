---
trigger: always_on
---

# Regra de Separação entre Planejamento (Spec + Tasks) e Implementação

Quando uma especificação em `.specs/features/<feature>/spec.md` for aprovada pelo usuário e seu plano de tarefas (`.specs/features/<feature>/tasks.md`) for gerado na sessão atual:

1. **Não implementar na sessão atual**:
   - Após aprovar a `spec.md`, gerar/atualizar o `tasks.md` e atualizar o Handoff em `.specs/STATE.md`, **a sessão atual NÃO DEVE editar código de produção ou testes** (código-fonte da aplicação, testes automatizados, pipelines de CI/CD ou arquivos de deploy), nem iniciar a execução das tasks.
   - **Única exceção**: quando o usuário ordenar explicitamente que a implementação seja feita na própria sessão atual (por exemplo: *"implemente agora nesta mesma sessão"*).

2. **Protocolo obrigatório de encerramento após Spec + Tasks**:
   - Garantir que `spec.md` esteja com `**Status**: Approved` (registrando data e palavras de aprovação do usuário).
   - Garantir que `tasks.md` exista em `.specs/features/<feature>/tasks.md` com todas as tasks pendentes (`- [ ]`).
   - Atualizar a seção `## Handoff` de `.specs/STATE.md` apontando para a feature aprovada e as tasks prontas para execução.
   - Encerrar a resposta informando os caminhos dos artefatos gerados e orientando o usuário a abrir uma **nova sessão** executando o comando/skill reutilizável `/implement-spec-tasks <feature>` (ou apenas `/implement-spec-tasks`, que lê automaticamente a feature ativa em `.specs/STATE.md` e executa `.agents/skills/implement-spec-tasks/SKILL.md`).
