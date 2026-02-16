# R7 - Plano de Desligamento do Tkinter

Data: 2026-02-16

## Objetivo

Concluir a migracao para PySide6 e remover o frontend legado Tkinter do caminho principal do projeto.

## Inventario do Legado Tkinter

- Entrypoint legado:
  - `main.py` (atual) importa `viewer.app` (Tkinter).
- Frontend legado:
  - `viewer/app.py`
  - `viewer/ui/diff_render.py`
  - `viewer/ui/ui_branches.py`
  - `viewer/ui/ui_commit.py`
  - `viewer/ui/ui_global.py`
  - `viewer/ui/ui_history.py`
  - `viewer/ui/ui_import.py`
  - `viewer/ui/ui_repos.py`
  - `viewer/ui/ui_settings.py`
  - `viewer/ui/ui_stash.py`
- Referencias em documentacao:
  - `README.md`
  - `AGENTS.global.md`
  - `CHECKLIST_R7_4_2.md`
  - `docs/SELECTION_TRACE.md`

## Estado Atual PySide6

- Entrypoint PySide6: `main_pyside6.py`.
- Shell principal: `viewer/pyside/window.py`.
- Fluxos principais em uso diario ja estao na UI PySide6 (Repositorios, Commit, Historico, Importar, Comparar, Configuracoes).

## Plano de Execucao

1. Remover arquivos e imports do frontend Tkinter (`viewer/app.py` + `viewer/ui/*`).
2. Trocar entrypoint oficial:
   - `main_pyside6.py` -> `main.py`.
3. Atualizar docs para PySide6-only:
   - comandos de execucao;
   - arquitetura e estrutura do projeto;
   - notas operacionais.
4. Validar:
   - `python3 -m compileall`;
   - suite de testes;
   - smoke run do app (`python3 main.py`).

## Criterio de Conclusao

- Nenhum caminho de runtime depende de Tkinter.
- Documentacao oficial nao orienta mais o fluxo antigo.
- `main.py` passa a ser a entrada oficial PySide6.
