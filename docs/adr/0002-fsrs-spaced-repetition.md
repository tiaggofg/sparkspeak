# ADR-0002: Algoritmo FSRS (`py-fsrs`) em vez de SM-2

- **Status**: Accepted
- **Date**: 2026-11-20
- **Scope**: `src/sparkspeak/domain/srs_engine.py`, `cards`, `review_logs`

## Contexto
O agendamento de flashcards de inglês não pode depender do LLM (sujeito a alucinação de datas) e precisa evitar o acúmulo desproporcional de revisões quando o aluno erra estruturas gramaticais recorrentes.

## Decisão
Adotar o algoritmo **FSRS (Free Spaced Repetition Scheduler)** via biblioteca oficial **`py-fsrs`** (`fsrs` no PyPI) com `desired_retention = 0.90` e log completo de revisões em `review_logs`.

## Alternativas Consideradas
- **SM-2 clássico**: simples de implementar manualmente, porém sofre de *ease hell* (penalização permanente do `ease_factor` para 1.30 após erros seguidos) e não modela estados intra-dia de aprendizagem/reaprendizagem nem permite otimização empírica posterior.

## Consequências
- **Positivas**: Intervalos calibrados por *Difficulty*, *Stability* e *Retrievability*; implementação determinística mantida pela comunidade Open Spaced Repetition.
- **Trade-offs / Riscos**: Exige armazenar estado FSRS completo (`fsrs_state`, `stability`, `difficulty`, `step`, `reps`, `lapses`) no SQLite.
