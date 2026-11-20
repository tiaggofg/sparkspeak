---
trigger: always_on
---

# Regra de Verificação Pós-Implementação (Playwright & Backend Requests)

Após finalizar qualquer implementação, refatoração funcional ou correção de bug neste projeto, você **DEVE** validar a entrega executando testes reais de acordo com o escopo da alteração:

## 1. Alterações com Frontend ou Full-Stack (UI + API)
- Sempre que uma implementação envolver o **Frontend** (ou **Frontend + Backend**), após rodar os testes unitários e build do projeto (conforme `AGENTS.md`), execute um **teste fim a fim via Playwright** (via MCP Playwright, subagente `browser` no Antigravity ou script Playwright headless) sobre a aplicação em execução.
- Verifique na prática a renderização dos componentes, interações de clique/preenchimento, navegação entre rotas da aplicação, fluxos críticos de negócio, responsividade (mobile e desktop) e respostas reais da API, sem erros no console.

## 2. Alterações Exclusivamente no Backend (Somente Backend)
- Quando a implementação for **somente no Backend** (sem mudanças de interface ou comportamento visual no Frontend), após rodar a suíte de testes automatizados, valide a alteração executando **requests HTTP reais** (via `curl`, script de requests ou cliente HTTP) diretamente contra o servidor backend em execução.
- Verifique os payloads JSON de request/response, headers/cookies de autenticação, status codes HTTP esperados (sucesso e casos de erro) e efeitos colaterais no banco de dados.

## 3. Alterações de CLI, Scripts ou Bibliotecas (Sem UI/HTTP)
- Execute o binário/comando/script diretamente com entradas reais (casos de sucesso e erro) além da suíte de testes automatizados.

## 4. Critério de Conclusão
- Nenhuma tarefa de implementação deve ser dada como concluída sem a evidência da execução da validação prática real correspondente ao escopo alterado (Playwright, requests HTTP reais ou execução real de CLI).
