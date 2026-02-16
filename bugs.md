# Bugs - R7.4.2 (PySide6)

Fonte:
- Rodada parcial em `CHECKLIST_R7_4_2.md` (somente itens marcados como `BUG`).

Convencao:
- `Status`: `aberto`, `em_progresso`, `resolvido`, `validado`.
- `Tipo`: `bug`, `regressao`, `ux`.
- `Prioridade`: `P0` bloqueador, `P1` alta, `P2` media, `P3` baixa.

## Backlog priorizado

| ID | Status | Prioridade | Area | Tipo | Problema | Evidencia |
|---|---|---|---|---|---|---|
| B001 | resolvido | P0 | Commit/PR | bug | Clique em `Abrir PR` gera traceback (`NameError: core_list_branches`). | Traceback no fim de `CHECKLIST_R7_4_2.md` |
| B002 | resolvido | P1 | Janela/Layout | regressao | Janela/layout em estado maximizado fica mal dimensionada (conteudo estoura/ultrapassa area util), gerando UI quebrada visualmente. | Checklist secao 2 + feedback adicional de maximizacao |
| B003 | resolvido | P2 | Barra global | ux | Pull/Push em zero deveriam ocultar contador/estado para reduzir ruido. | Checklist secao 3 |
| B004 | resolvido | P1 | Repositorios | regressao | Tela virou lista; esperado visual de cards (como UI Tk). | Checklist secao 4 + observacao BUG4 |
| B005 | resolvido | P1 | Repositorios | bug | Duplo clique no repo deveria abrir no VS Code. | Checklist secao 4 |
| B006 | resolvido | P1 | Clone | bug | Campo pasta opcional clona em pasta literal; esperado `pasta/repo` quando informado namespace. | Checklist secao 4 |
| B007 | resolvido | P1 | Commit | regressao | Lista de arquivos sem linha `(todos)` e sem agrupamento por pasta para selecao em lote. | Checklist secao 5 + observacao BUG5 |
| B008 | resolvido | P1 | Commit | ux | Excesso de botoes e fluxo de selecao pior que Tk; checkbox/legenda confusos. | Checklist secao 5 + observacao BUG5 |
| B009 | em_progresso | P1 | Diff (Commit) | regressao | Visual de diff ruim: sem leitura clara de `+/-`, cores e marcadores como no Tk. | Checklist secao 5 + observacao BUG3 |
| B010 | resolvido | P1 | Commit | bug | Stash nao confirmado como funcionando/atualizando tela. | Checklist secao 5 |
| B011 | resolvido | P2 | Commit | ux | Undo commit deveria expor apenas `soft` e `mixed` (remover `hard`). | Checklist secao 5 |
| B012 | resolvido | P1 | Historico | bug | Busca por texto nao filtra conforme esperado em tempo real. | Checklist secao 6 |
| B013 | resolvido | P2 | Historico | ux | Limite fixo de commits deveria migrar para scroll infinito. | Checklist secao 6 |
| B014 | resolvido | P1 | Diff (Historico) | regressao | Diff por palavra/patch pouco legivel comparado ao Tk. | Checklist secao 6 + observacao BUG3 |
| B015 | resolvido | P2 | Historico | bug | Tooltip de commit nao aparece no fluxo manual. | Checklist secao 6 |
| B016 | resolvido | P1 | Historico | bug | Clique direito em commit altera selecao (nao deveria). | Checklist secao 6 |
| B017 | resolvido | P0 | Historico | bug | Menu de contexto de arquivo aparece, mas so ultima opcao clicavel. | Checklist secao 6 |
| B018 | resolvido | P1 | Historico/Exportar | bug | Exportar nao suporta multisselecao com Ctrl no fluxo esperado. | Checklist secao 6 |
| B019 | resolvido | P3 | Importar | ux | Botao `Usar atual` parece sem sentido no fluxo de importacao entre repos. | Checklist secao 7 |
| B020 | resolvido | P1 | Diff (Comparar) | regressao | Visual de diff em comparar tambem esta ruim/sem padrao visual do Tk. | Checklist secao 8 + observacao BUG3 |
| B021 | resolvido | P2 | Configuracoes | ux | `Limite padrao de commits` nao faz sentido se migrar para scroll infinito. | Checklist secao 9 |
| B022 | resolvido | P1 | Persistencia | bug | Ultima aba ativa nao esta restaurando corretamente. | Checklist secao 11 |
| B023 | resolvido | P2 | Persistencia | bug | Persistencia de preferencias em `settings.json` esta incerta no teste. | Checklist secao 11 |
| B024 | resolvido | P1 | Sync/Status | regressao | Auto fetch / auto status update parece nao estar ocorrendo como na UI Tk. | Observacao final do checklist |
| B025 | resolvido | P1 | Repositorios/Branch | bug | Scroll no workspace podia acionar troca de branch acidental via combobox do card, disparando erro de checkout em repositorio sujo. | Validacao manual apos ajuste de combobox sem wheel |

## Plano de ataque sugerido

### Fase 1 (P0/P1 bloqueadores)
1. B001 (crash de PR)
2. B017 (menu de arquivo no Historico)
3. B016 + B018 (context menu/selecoes no Historico)
4. B005 + B006 (duplo clique e clone path)
5. B022 + B024 (persistencia aba e auto refresh)

### Fase 2 (paridade funcional critica de Commit/Historico/Comparar)
1. B007 + B008 (selecao e simplificacao da aba Commit)
2. B009 + B014 + B020 (motor/render de diff legivel)
3. B012 + B013 (busca e scroll infinito no Historico)
4. B010 + B011 (stash/undo commit) menu com opções mais explicativas só soft, hard e mixed é confuso.. 

### Fase 3 (polimento UX)
1. B003 (ruido de pull/push em zero)
2. B019 (rever botao `Usar atual`)
3. B021 (rever limite em configuracoes)
4. B023 (auditoria de preferencias)
5. B004 (retomar visao em cards moderna na aba Repositorios)

## Atualizacoes desta rodada

- Resolvido para nova validacao manual:
  - Corrigido crash de startup no PySide6 quando a aba Commit disparava auto-stage antes da status bar estar disponivel.
  - Stash da aba Commit em PySide6 agora usa apenas os arquivos selecionados na lista (arquivo/pasta/todos), em vez de stashear o worktree inteiro.
  - Botao `Stash` da aba Commit no PySide6 agora abre janela de gerenciamento de stash com lista de stashes, arquivos e diff, incluindo aplicar/pop/descartar.
  - Fluxo de stash no PySide6 migrado para aba dedicada e dinamica: aparece apenas quando o repositorio atual possui stashes e exibe contexto de repositorio/branch no topo.
  - Aba Commit no PySide6 agora sincroniza selecao e stage automaticamente: marcar/desmarcar arquivo, pasta ou `(todos)` aplica stage/unstage real no Git sem etapa manual extra.
  - Aba Commit no PySide6 agora aplica auto-stage inicial por repositorio ao abrir o fluxo, iniciando com arquivos selecionados e stageados por padrao.
  - `B007` aba Commit no PySide6 agora renderiza linha `(todos)` e cabecalhos por pasta, com selecao em lote por check-state e preservacao da selecao por arquivo entre refreshes.
  - `B008` simplificacao do topo da aba Commit no PySide6 com remocao de botoes redundantes de selecao em lote; o fluxo de lote agora e centralizado na propria lista `(todos)/pastas`.
  - `B011` dialogo de Undo commit no PySide6 agora permite somente os modos `soft` e `mixed`.
  - `B003` a barra global agora usa botoes `Behind`/`Ahead` clicaveis no lugar de `Pull/Push`, com tooltip contextual e estado desabilitado quando contador = 0.
  - `B002` layout responsivo da aba Commit ajustado em 2 linhas no topo, reduzindo largura minima global da janela (sem estourar em maximizado).
  - `B001` import faltante de `list_branches` no fluxo de PR.
  - `B005` duplo clique em repositorio agora abre no VS Code apos selecionar.
  - `B006` regra de clone em pasta opcional alterada para namespace (`pasta/repo`) por padrao.
  - `B012` busca do Historico agora recarrega enquanto digita.
  - `B016` menu de contexto de commit preserva selecao anterior.
  - `B017` menu de contexto de arquivos do Historico corrige resolucao de item e clique.
  - `B018` lista de commits do Historico habilitada para multisselecao (`Ctrl`) no exportar.
  - `B009` avancou com janela de diff em tela cheia na aba Commit (modos linha/lado-a-lado/cima-baixo), mantendo selecao por marcador para stage e adicionando menu de contexto com copiar/reverter por linha ou bloco.
  - `B004` aba Repositorios no PySide6 voltou ao formato de cards com scroll, incluindo branch por card, `Ahead/Behind`, status, clique simples para selecionar, duplo clique para abrir no VS Code e card final para adicionar repositorio.
  - Menu de contexto de repositorio (cards e combobox) ganhou acao de exclusao local com confirmacao, removendo tambem entradas de recentes/favoritos apos apagar a pasta.
  - `B019` aba Importar no PySide6 removeu o botao `Usar atual`, simplificando o fluxo para escolha explicita de origem via combobox.
  - `B021` aba Configuracoes no PySide6 removeu `Limite padrao de commits`; Historico agora usa carregamento progressivo por scroll.
  - `B024` shell PySide6 ganhou timers de fundo para auto status update (15s) e auto fetch (180s, com upstream), atualizando estado sem acao manual.
  - `B013` Historico no PySide6 migrou para paginação progressiva por scroll (infinite scroll), removendo o seletor de limite fixo no topo.
  - Historico/Importar/Comparar agora iniciam em `Diff por linha` por padrao (toggle de palavra continua disponivel), reduzindo ruido visual no primeiro uso.
  - `B025` comboboxes criticos (repo/branch global e branch dos cards) passaram a ignorar wheel com dropdown fechado, evitando troca acidental ao usar scroll na tela.
  - Motor de diff em colunas (Historico/Importar/Comparar/Stash) foi reestruturado para layout padrao sem checkbox no estilo `old/new/sinal/conteudo`, preservando ordem do patch por hunk e consolidando pares `-`/`+` em linha `#` (modificada) com tooltip da linha original.
  - `B009` aba Commit no PySide6 agora usa visualizacao em colunas com marcador dedicado (`[ ]/[x]`) no diff principal; clique na coluna de marcador executa stage/unstage de linha ou bloco sem depender de texto corrido.
  - `B020` fluxo de selecao de commit na aba Comparar ficou mais resiliente: hash do commit agora e resolvido para SHA completo antes de abrir arquivos/diff, e falhas de referencia (`bad object`/`ambiguous argument`) no patch deixam de abrir popup bloqueante durante troca de repositorio/branch.
  - `B020` quando carregar detalhes de commit falha, a lista de arquivos do commit ainda tenta ser montada via `list_commit_files`, evitando cair sempre no agregado total.
  - `B020` selecao da aba Comparar foi estabilizada para sempre considerar `currentItem` (commit/arquivo), com listas em modo de selecao unica; reduz inconsistencias onde os arquivos pareciam ficar no agregado total.
  - `B014` Historico tambem passou a usar `currentItem` como referencia principal do commit ativo, evitando mostrar diff de item antigo quando ha multisselecao para exportacao.
  - Scroll acidental em listas/diff foi reduzido com `setAutoScroll(False)` em widgets padrao (`UnifiedListWidget` e `DiffColumnsView`) para mitigar salto de viewport em cliques rapidos.
  - Diff em colunas (Historico/Importar/Comparar/Stash) agora exibe numeracao `Ant`/`Nov` separada, mantendo ordem do patch e facilitando leitura de linhas removidas/adicionadas/modificadas.
  - Render de diff recebeu destaque visual adicional por tipo de linha (fundo suave para `added/removed/modified/hunk`), melhorando contraste e leitura sem depender de simbolos `+/-`.
  - `B014` e `B020` foram consolidados no mesmo motor de diff em colunas com padrao unico de numeracao e selecao, reduzindo divergencia visual entre abas.
  - `B015` aba Historico agora reforca tooltip de commit no hover (`itemEntered`), mostrando hash/data/presenca local-online de forma consistente no fluxo manual.
  - `B022` restauracao da aba ativa foi corrigida com preferencia por `last_tab_name` e fallback seguro por indice (incluindo caso dinamico da aba `Stash`).
  - `B023` persistencia de `last_tab_name` e preferencias de tema/fontes foi consolidada no `settings_store`, com testes de regressao.

- Aguardando validacao manual:
  - Reexecutar os itens marcados no checklist para confirmar status `validado`.

## Template de fechamento por bug

```md
### Bxxx
- Status: resolvido
- Causa raiz:
- Correcao aplicada:
- Arquivos:
- Validacao:
- Resultado:
```
