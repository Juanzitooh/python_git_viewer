# Architecture

Fonte principal de arquitetura detalhada:

- `../ARCHITECTURE.md`

## Resumo canonico

- Camada de dominio: `viewer/core` (Python puro, sem UI).
- Camada de interface: `viewer/pyside` (frontend e controladores).

## Contrato obrigatorio

- `viewer/core` nao importa `tkinter`, `PySide6` nem `viewer.pyside`.
- Regras de negocio/Git devem viver no core.
- A UI apenas orquestra interacoes e estado visual.

## Impacto para roadmap

- Toda evolucao de UI deve preservar o contrato de desacoplamento.
- Mudancas de fronteira entre core/UI devem ser registradas em `decisions.md`.
