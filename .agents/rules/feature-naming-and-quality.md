---
trigger: always_on
---

# Regra de Nomeação de Features e Análise Estática Determinística

## 1. Padrão Obrigatório de Pastas de Feature
Toda nova feature criada em `.specs/features/<feature>/` **DEVE** seguir o padrão:

```text
^[0-9]+-[a-zA-Z][a-zA-Z0-9-]*$
```

- Exemplos válidos: `01-user-auth`, `02-payment-webhook`, `001-secret-santa`.
- Exemplos inválidos: `user-auth` (sem prefixo numérico), `01_user_auth` (underscore).
- Antes de apresentar uma nova spec ou iniciar implementação, valide com:
  ```bash
  .agents/scripts/validate-feature-name.sh <nome-da-feature>
  ```

## 2. Análise Estática Determinística (Lint + SonarQube Local)
Antes de concluir qualquer ciclo de implementação e solicitar aprovação para commit/push:
- Execute o lint do projeto e a análise do SonarQube local de forma determinística via:
  ```bash
  .agents/scripts/quality-check.sh --up
  ```
- O script consulta a API do SonarQube (`/api/qualitygates/project_status` e `/api/issues/search`) e só retorna código `0` se o lint e o Quality Gate estiverem `OK`.
- Caso haja bloqueios de lint ou falha no Quality Gate, corrija os apontamentos antes de pedir aprovação ao usuário.
