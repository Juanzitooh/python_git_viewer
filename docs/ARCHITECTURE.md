# Arquitetura

## Visao geral

O projeto e dividido em duas camadas principais:

- `viewer/core`: dominio e operacoes Git (estado, commit, branch, comparacao, conflitos, persistencia, utilitarios).
- `viewer/pyside`: interface grafica PySide6 (janela, abas, controladores, renderizacao, tema e widgets).

## Contrato de arquitetura (R7.7)

Regra obrigatoria:

- O `core` permanece **100% Python puro**, sem dependencia de toolkit de UI.
- A UI pode evoluir (PySide6 hoje), mas o `core` nao deve ser reescrito para outra linguagem/framework.

Regras praticas:

- `viewer/core` **nao** pode importar `tkinter`, `PySide6` ou `viewer.pyside`.
- Fluxos de negocio/Git devem entrar em `viewer/core`.
- `viewer/pyside` apenas orquestra eventos, estado visual e chamadas ao core.

## Beneficios

- Testes de dominio independentes da UI.
- Menor acoplamento entre camada visual e regras Git.
- Possibilidade de novos frontends sem reimplementar o dominio.
