# Tasks

Backlog canonico operacional migrado de `../../ROADMAP.md`.

## Politica de tarefas

- Formato de ID: `R*` e `V*` (mantido do historico original).
- Status possiveis: `todo`, `doing`, `done`, `blocked`.
- Itens concluidos foram arquivados em `tasks.done.md`.

## Backlog ativo

| ID | Task | Milestone | Prioridade | Dependencia | Criterio de aceite | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R7.1 | Core Python estabilizado e desacoplado da UI. | M7 | P1 | none | Contrato de arquitetura mantido e sem dependencia de UI no core. | doing |
| R7.2 | Shell principal em PySide6 (janela, barra global, tabs e status). | M7 | P1 | none | Shell PySide6 permanece como entrada principal estavel. | doing |
| R7.3 | Migracao incremental das abas criticas (Repositorios, Commit, Historico). | M7 | P1 | none | Fluxos criticos permanecem funcionais sem regressao. | doing |
| R7.4 | Polimento visual e UX desktop. | M7 | P1 | R7.3 | Interface consistente e feedback visual adequado. | doing |
| R7.4.1 | Paridade funcional obrigatoria com a UI atual. | M7 | P1 | R7.4 | Fluxos principais com paridade funcional confirmada. | doing |
| R7.4.2 | Rodada final de testes de regressao e usabilidade. | M7 | P0 | R7.4.1 | Execucao de testes e checklist final sem bloqueios criticos. | doing |
| R7.4.2.2 | Checklist manual de usabilidade final. | M7 | P0 | R7.4.2 | Checklist manual executado e sem regressao bloqueante. | todo |
| R7.4.2.3 | Fechamento progressivo de bugs da rodada em `bugs.md`. | M7 | P0 | R7.4.2.2 | Bugs P0/P1 tratados e validados no fluxo final. | doing |
| R7.8 | Rework da aba Configuracoes (post-bugs). | M8 | P1 | R7.4.2.3 | Aba Configuracoes simplificada com persistencia correta. | todo |
| R7.9 | Diff com deteccao de linha modificada (post-bugs). | M8 | P1 | R7.4.2.3 | Diff com estados adicionado/removido/modificado sem regressao. | todo |
| V0.4.0 | Fechamento do proximo ciclo de versao. | M8 | P0 | R7.8, R7.9 | Ciclo v0.4.0 fechado com changelog e validacao final. | todo |

## Fonte de migracao

- Roadmap historico completo: `../../ROADMAP.md`
- Arquitetura detalhada: `../ARCHITECTURE.md`
- Decisoes detalhadas: `../DECISIONS.md`
