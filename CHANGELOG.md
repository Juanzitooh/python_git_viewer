# Changelog

Todas as mudancas relevantes deste projeto serao documentadas aqui.

## [Unreleased]

- Filtro de commits por texto, autor, arquivo e intervalo de datas na aba Historico.
- Filtro de commits por branch, tag e status do repositorio na aba Historico.
- Diff por palavra com realce de mudancas pequenas.
- Stage/unstage por hunk e por linha direto no diff do arquivo.
- Stash manager com criar, aplicar e descartar stashes.
- Modularizacao inicial: modelos e funcoes Git em modulos dedicados.
- Extracao de utilitarios de diff para `diff_utils.py`.
- Modularizacao da UI em modulos por aba.
- Modularizacao da barra global e fluxos de repositorio em `ui_global.py`.
- Estrutura organizada em pacote `viewer/` com subpastas `core/` e `ui/`.
- Abertura de arquivos no VS Code por duplo clique e atalho para abrir o repositorio.
- Atalhos de teclado para navegacao, refresh e commit.
- Aba de comparacao de branches com resumo e diffs por arquivo.
- Persistencia de configuracoes, favoritos e repositorios recentes via JSON.
- Aba de repositorios para abrir e favoritar rapidamente.

## [0.1.0] - 2026-02-05

- Build com PyInstaller via `compile.py`.
- Criacao de `.venv` automatica no build.
- `requirements.txt` e `requirements-dev.txt` iniciais.
- `.gitignore` para artefatos e caches.
- README com instrucoes de build e execucao.
