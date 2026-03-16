# AGENTS - Roadmap

Este diretorio e a camada canonica de planejamento do projeto.
Os documentos legados continuam validos como fonte historica:

- `ROADMAP.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `CHANGELOG.md`

## Ordem de leitura

1. `vision.md`
2. `roadmap.md`
3. `milestones.md`
4. `tasks.md`
5. `status.md`
6. `architecture.md`
7. `decisions.md`
8. `tasks.done.md` (historico)

## Mapa de contexto

- Roadmap historico completo: `../../ROADMAP.md`
- Arquitetura detalhada: `../ARCHITECTURE.md`
- ADRs detalhadas: `../DECISIONS.md`
- Bugs da rodada: `../../bugs.md`

## Loop de execucao

1. Ler `status.md`.
2. Executar `NEXT_TASK` em `tasks.md`.
3. Validar escopo minimo (testes/checklist).
4. Atualizar `status.md`, `tasks.md`, `milestones.md` e `CHANGELOG.md`.
5. Arquivar tarefas concluidas em `tasks.done.md` quando aplicavel.

## Regras locais

- Manter `ROADMAP.md` como historico consolidado da evolucao.
- Novas tarefas operacionais entram em `tasks.md`.
- Mudancas arquiteturais devem registrar impacto em `decisions.md`.
