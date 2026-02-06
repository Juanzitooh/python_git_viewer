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
- Painel de status do repositorio com upstream e ahead/behind.
- Fluxo guiado de merge/rebase/squash com resumo e alertas.
- Panes redimensionaveis nas abas Historico e Commit.
- Tema claro/escuro e fontes configuraveis persistidas.
- Modo de leitura para diffs grandes (Historico, Comparar e Stash).
- Indicadores de performance no topo (tempo de operacoes principais).
- Operacoes Git em background para evitar travamentos da UI.
- Cache de diffs com invalidacao segura ao mudar estado do repo.
- Paginacao de commits com carregamento assíncrono.
- Testes para parsing de diff e numstat.
- Pipeline de build via CI para Windows e Linux.
- Releases automaticas com checksums.
- Icone e metadata do executavel via PyInstaller.

## [0.1.0] - 2026-02-05

- Build com PyInstaller via `compile.py`.
- Criacao de `.venv` automatica no build.
- `requirements.txt` e `requirements-dev.txt` iniciais.
- `.gitignore` para artefatos e caches.
- README com instrucoes de build e execucao.
