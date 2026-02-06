# Roadmap

Legenda
- [ ] planejado
- [~] em andamento
- [x] concluido (incluir data)

## M0 - Fundacao

- [x] R0.1 Script de build com PyInstaller e `.venv` (2026-02-05)
- [x] R0.2 `.gitignore` para artefatos e caches (2026-02-05)
- [x] R0.3 Documentacao basica de build e execucao (2026-02-05)

## M1 - Uso Diario

- [x] R1.1 Busca global de commits por autor, mensagem, arquivo e data (2026-02-05)
- [x] R1.2 Filtro rapido por branch, tag e status do repo (2026-02-06)
- [x] R1.3 Diff por palavra com realce de mudancas pequenas (2026-02-06)
- [x] R1.4 Stage/unstage por hunk e por linha (2026-02-06)
- [x] R1.5 Stash manager com criar, aplicar e descartar (2026-02-06)

## M2 - Produtividade

- [x] R2.1 Atalhos de teclado para navegacao, commit e refresh (2026-02-06)
- [x] R2.2 Comparacao de branches lado a lado (2026-02-06)
- [x] R2.3 Fluxo guiado de merge e rebase com alertas (2026-02-06)
- [x] R2.4 Historico de repositorios recentes (2026-02-06)
- [x] R2.5 Painel de status com ahead/behind e upstream (2026-02-06)
- [x] R2.6 Abrir arquivos e repositorio no VS Code (2026-02-06)
- [x] R2.7 Favoritos e aba de repositorios (2026-02-06)

## M3 - Visual e UX

- [ ] R3.1 Tema claro e escuro com fontes configuraveis
- [ ] R3.2 Layout responsivo com panes redimensionaveis
- [ ] R3.3 Modo de leitura para diffs grandes
- [ ] R3.4 Indicadores de performance para operacoes longas

## M4 - Confiabilidade e Performance

- [ ] R4.1 Operacoes de Git assincronas sem travar UI
- [ ] R4.2 Cache de diffs com invalidacao segura
- [ ] R4.3 Suporte a repositorios grandes com paginacao robusta
- [ ] R4.4 Suite de testes para parsing de diff e numstat
- [x] R4.5 Modularizacao inicial (models e git_client) (2026-02-06)
- [x] R4.6 Modularizar UI em modulos (historico, commit, stash, diff) (2026-02-06)
- [x] R4.7 Extrair utilitarios de diff (diff_utils) (2026-02-06)
- [x] R4.8 Modularizar barra global e fluxos de repo (2026-02-06)
- [x] R4.9 Organizar estrutura em pacote `viewer/` (2026-02-06)

## M5 - Distribuicao

- [ ] R5.1 Pipeline de build para Windows e Linux via CI
- [ ] R5.2 Releases com checksums e notas de versao
- [ ] R5.3 Icone e metadata do executavel

## Regras de Manutencao

- Toda entrega deve marcar o item correspondente como concluido com data.
- Mudancas relevantes devem entrar no `CHANGELOG.md`.
