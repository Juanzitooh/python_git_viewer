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

- [x] R3.1 Tema claro e escuro com fontes configuraveis (2026-02-06)
- [x] R3.2 Layout responsivo com panes redimensionaveis (2026-02-06)
- [x] R3.3 Modo de leitura para diffs grandes (2026-02-06)
- [x] R3.4 Indicadores de performance para operacoes longas (2026-02-06)

## M4 - Confiabilidade e Performance

- [x] R4.1 Operacoes de Git assincronas sem travar UI (2026-02-06)
- [x] R4.2 Cache de diffs com invalidacao segura (2026-02-06)
- [x] R4.3 Suporte a repositorios grandes com paginacao robusta (2026-02-06)
- [x] R4.4 Suite de testes para parsing de diff e numstat (2026-02-06)
- [x] R4.5 Modularizacao inicial (models e git_client) (2026-02-06)
- [x] R4.6 Modularizar UI em modulos (historico, commit, stash, diff) (2026-02-06)
- [x] R4.7 Extrair utilitarios de diff (diff_utils) (2026-02-06)
- [x] R4.8 Modularizar barra global e fluxos de repo (2026-02-06)
- [x] R4.9 Organizar estrutura em pacote `viewer/` (2026-02-06)

## M5 - Distribuicao

- [x] R5.1 Pipeline de build para Windows e Linux via CI (2026-02-06)
- [x] R5.2 Releases com checksums e notas de versao (2026-02-06)
- [x] R5.3 Icone e metadata do executavel (2026-02-06)

## M6 - UX e Interface (base: melhorias_ui.md)

- [x] R6.1 Barra global com titulo dinamico e acoes de copiar caminho/VS Code (2026-02-06)
- [x] R6.2 Barra global simplificada (2026-02-08)
  Escopo: remover caixa de texto de caminho e remover controles redundantes da barra global (branch/origem/destino/nome de acao), mantendo apenas acoes globais de repo.
  Aceite: selecao de repo continua funcional via dialog/aba Repositorios; fluxo de branches continua funcional nas abas dedicadas.
- [x] R6.2.1 Workspace GitHub local e clone por URL/SSH (2026-02-08)
  Escopo: permitir configurar pasta base (padrao `~/Documentos/github`), escanear repositorios Git locais, preparar chave SSH em Python e clonar repositorios via URL HTTPS/SSH para a pasta base.
  Aceite: usuario consegue rastrear repositorios locais por scan, copiar chave publica para GitHub e clonar repositorio abrindo automaticamente no app.
- [x] R6.2.2 Clone contextual na barra global e SSH condicional (2026-02-08)
  Escopo: mover linha de clone (URL/SSH + pasta + clonar) para a barra global e exibir somente na aba Repositorios; ocultar botao de preparar chave SSH quando a chave local ja existir.
  Aceite: na aba Repositorios a barra global exibe linha de clone; ao trocar de aba a linha some; botao de chave SSH aparece apenas quando necessario.
- [x] R6.2.3 Clone com progresso detalhado e bloqueio de UI (2026-02-10)
  Escopo: mostrar log de progresso de `git clone --progress` na janela de clonagem com indicador visual de percentual, permitir cancelamento durante o clone e bloquear interacao da janela principal ate o fim da operacao, com feedback visual no termino.
  Aceite: durante clone apenas o botao de cancelar fica ativo no dialogo, progresso aparece em tempo real e a janela principal permanece travada para evitar acoes concorrentes; ao concluir com sucesso a barra de progresso pisca rapidamente, a aba Repositorios e reaberta e o workspace e reescaneado.
- [x] R6.3 Aba Repositorios com foco operacional (2026-02-08)
  Escopo: reduzir ruido visual removendo bloco redundante de status do repo, realizar scan automatico na inicializacao da pasta base e, ao usar "Abrir recente", executar fetch do repo aberto e navegar automaticamente para a aba Historico.
  Aceite: aba Repositorios abre mais limpa, scan inicial tenta popular Recentes automaticamente e abrir recente atualiza dados + leva para Historico sem acao manual extra.
- [x] R6.3.1 Cards de visao geral do workspace (2026-02-08)
  Escopo: adicionar grade 2x4 de cards abaixo de Workspace GitHub mostrando favoritos e recentes, com branch atual e ahead/behind por repositorio.
  Aceite: usuario tem visao rapida de ate 8 repositorios (favoritos primeiro), com abertura por duplo clique no card.
- [x] R6.3.2 Cards com scroll continuo e fluxo de adicionar repositorio (2026-02-08)
  Escopo: remover combobox de repositorio da barra superior, permitir cards sem limite fixo com rolagem vertical e manter card final "+1" para abrir modal de clonagem.
  Aceite: selecao de repositorio acontece via cards na aba Repositorios; lista pode crescer com scroll; card final sempre abre janela de clone.
- [x] R6.3.3 Cards interativos com troca de branch e atalho VS Code (2026-02-08)
  Escopo: adicionar combobox de branch em cada card para checkout rapido por repositorio, usar clique simples para selecionar repo no app e duplo clique para selecionar + abrir no VS Code.
  Aceite: usuario consegue trocar branch direto no card, selecionar repo com um clique e abrir repo no VS Code com duplo clique.
- [x] R6.3.9 Gerenciar repositorios por menu dos cards (2026-02-10)
  Escopo: incluir acao de exclusao de repositorio no menu de contexto dos cards da aba Repositorios, com confirmacao explicita antes de remover a pasta local.
  Aceite: usuario consegue excluir um repositorio local diretamente pelo card, com janela de confirmacao e atualizacao automatica da lista de favoritos/recentes.
- [x] R6.3.10 Seletor de branch global para abas operacionais (2026-02-10)
  Escopo: mover seletor rapido de branch + acao de criar branch das abas Commit/Historico para a barra superior, exibindo o controle apenas nas abas Commit, Historico e Importar.
  Aceite: barra superior mostra controle de branch somente nas abas operacionais definidas; abas Commit e Historico ficam visualmente mais limpas sem controles duplicados.
- [x] R6.3.4 Barra de atividade para operacoes assincronas (2026-02-08)
  Escopo: exibir um indicador fino no rodape durante operacoes de background para sinalizar progresso da interface em tarefas longas.
  Aceite: ao iniciar qualquer operacao assincrona a barra aparece; ao finalizar todas as operacoes pendentes a barra some automaticamente.
- [x] R6.3.5 Seletor rapido de branch nas abas Historico e Commit (2026-02-08)
  Escopo: adicionar combobox local de branch nas abas Historico e Commit, com troca rapida de branch e botao para criar nova branch ao lado.
  Aceite: usuario consegue trocar de branch sem sair da aba atual e criar uma branch nova com opcao de checkout imediato.
- [x] R6.3.6 Ajuste de layout da aba Commit para lista de arquivos (2026-02-08)
  Escopo: reorganizar o topo da aba Commit em duas linhas para evitar compressao da lista/scroll quando os controles de branch estao visiveis.
  Aceite: lista de arquivos ocupa largura util completa e controles de branch nao reduzem a area de leitura.
- [x] R6.3.7 Cache local do estado SSH para startup rapido (2026-02-08)
  Escopo: persistir em JSON o resultado de autenticacao SSH do GitHub e reutilizar no startup quando a chave local nao mudou.
  Aceite: apos um check SSH autenticado, inicializacoes seguintes evitam o teste remoto e nao registram custo de SSH no startup.
- [x] R6.3.8 Restaurar ultima aba e exibir janela apos carga inicial (2026-02-08)
  Escopo: salvar indice da aba ativa no settings JSON e abrir o app ja nessa aba; manter janela oculta no startup ate concluir carga inicial assincrona.
  Aceite: ao reiniciar, app volta na aba usada por ultimo e so exibe a janela quando o carregamento inicial estabilizar.
- [x] R6.4 Fluxo de importacao de commits dedicado (2026-02-08)
  Escopo: substituir janela de "Importar commits" por fluxo/aba dedicada com repo origem  + branch origem + lista de commits selecionaveis para importar no repo/branch atual.
  Aceite: importacao ocorre pelo fluxo dedicado, mantendo cherry-pick separado na aba Historico principal.
- [x] R6.5 Historico com foco em leitura e filtro (2026-02-08)
  Escopo: trocar filtros inline por modal de "Busca filtrada"; mostrar botao "Tirar filtro" somente quando houver filtro ativo; ajustar linha de commit com data relativa (<24h hora, >=24h data), tooltip com data/hora completa e botao de copiar hash completo.
  Aceite: cabecalho da aba Historico fica mais compacto, filtros continuam completos e metadados de commit ficam mais legiveis.
- [x] R6.5.1 Undo e reordenacao de commits locais (2026-02-08)
  Escopo: adicionar undo do ultimo commit na aba Commit (soft/mixed/hard) e fluxo dedicado na aba Historico para reordenar commits locais [L] com backup automatico antes de reescrever historico.
  Aceite: usuario consegue desfazer ultimo commit por modo escolhido e reordenar commits locais com rollback automatico em caso de falha.
- [x] R6.6 Aba Comparar com fluxo de acao no rodape (2026-02-08)
  Escopo: mover bloco de acao (merge/rebase/squash + executar) para o fim da aba, alinhar executar no canto inferior direito e exibir campo de mensagem somente para squash; melhorar feedback com CTA para aba Commit quando houver alteracoes locais.
  Aceite: layout reduz ruido no topo e estados da acao ficam contextuais ao tipo escolhido.
- [x] R6.6.1 Alternancia rapida origem/destino na comparacao (2026-02-10)
  Escopo: adicionar botao de troca entre os combobox de origem e destino na aba Comparar para inverter rapidamente a direcao da operacao.
  Aceite: com um clique usuario troca origem/destino e a comparacao e atualizada automaticamente.
- [x] R6.8 Atalhos de GitHub para commit e PR (2026-02-10)
  Escopo: permitir abrir commit selecionado no GitHub pelo menu do Historico e exibir botao de abrir PR na aba Commit quando nao houver alteracoes no worktree.
  Aceite: usuario acessa commit e fluxo de PR no navegador sem copiar URL manualmente.
- [x] R6.9 Navegacao GitHub expandida (sem API) (2026-02-10)
  Escopo: adicionar acoes para abrir no navegador a branch atual (`/tree/<branch>`), historico de commits da branch (`/commits/<branch>`), issues (`/issues`), actions (`/actions`) e releases (`/releases`) do repositorio selecionado.
  Aceite: usuario consegue abrir cada destino GitHub por menu de contexto sem precisar copiar URL manualmente.
- [x] R6.9.1 Copiar links GitHub prontos (repo/branch/commit) (2026-02-10)
  Escopo: incluir acoes de copia para URL do repositorio, URL da branch atual e URL de commit selecionado, aproveitando os utilitarios existentes de normalizacao do `origin`.
  Aceite: links copiados para clipboard funcionam diretamente no navegador e refletem o repo/branch/commit correto.
- [x] R6.9.2 Menu GitHub consolidado nas acoes de repositorio (2026-02-10)
  Escopo: organizar atalhos de navegador em um grupo consistente no menu de contexto de cards e combobox de repositorio, evitando duplicacao de comandos na barra superior.
  Aceite: menus de contexto ficam consistentes entre abas e centralizam todas as acoes de GitHub sem poluir a UI.
- [x] R6.10 Menu de contexto para arquivos do commit no Historico (2026-02-10)
  Escopo: adicionar menu de contexto na lista de arquivos de um commit selecionado com acoes de abrir arquivo no VS Code, copiar patch total do arquivo, copiar patch relativo (arquivo especifico) e abrir o caminho do arquivo no explorador.
  Aceite: cada acao respeita validacoes de caminho/arquivo, apresenta erros de forma segura quando o arquivo nao existir localmente e funciona sem alterar selecao de commit de forma inesperada.
- [x] R6.10.1 Padronizar menu de contexto de commits na aba Importar (2026-02-10)
  Escopo: aplicar na lista de commits da aba Importar o mesmo padrao de menu (abrir commit no GitHub, copiar URL de commit, copiar hash, copiar patch e copiar lista de arquivos).
  Aceite: clique direito em commits da aba Importar abre menu consistente com Historico, sem mudar selecao de forma inesperada e com fechamento seguro ao trocar foco/aba.
- [x] R6.10.2 Padronizar menu de contexto de arquivos na aba Comparar (2026-02-10)
  Escopo: aplicar na lista de arquivos da aba Comparar o mesmo padrao de menu de arquivos (abrir no VS Code, abrir na pasta, copiar patch do arquivo e copiar caminho relativo).
  Aceite: menus na aba Comparar reaproveitam as mesmas validacoes e mensagens do Historico, mantendo comportamento uniforme de usabilidade.
- [x] R6.7 Aba Commit com stage/unstage por interacao direta (2026-02-08)
  Escopo: remover dependencia dos botoes de acao em lote e usar clique para alternar stage/unstage em arquivo, hunk e linha; preservar ordem natural dos itens e indicar visualmente selecao de hunk/linha.
  Aceite: fluxo principal de stage/unstage funciona sem combinacao de teclado e sem passos extras.

## M7 - UI Moderna (PySide6) e Distribuicao Linux

- [~] R7.1 Core Python estabilizado e desacoplado da UI
  Escopo: consolidar contratos entre `viewer/core` e camada de interface para que a logica Git permaneca 100% reutilizavel em qualquer frontend.
  Aceite: operacoes Git, parse de diff, estado de repositorio e persistencia funcionam sem dependencia direta de widgets Tk.
- [x] R7.1.1 Extrair renderizacao de diff para camada de UI (2026-02-10)
  Escopo: mover `render_patch_to_widget` e utilitarios de render para `viewer/ui`, removendo dependencia de `tkinter` em `viewer/core/diff_utils.py`.
  Aceite: `viewer/core` permanece apenas com parse/build de dados; renderizacao visual fica isolada na camada de interface.
- [x] R7.1.2 Extrair construcao de links GitHub para o core (2026-02-10)
  Escopo: mover normalizacao de `origin`, descoberta de branch base/head e montagem de URLs (repo/branch/commits/issues/actions/releases/PR/commit) para `viewer/core`.
  Aceite: `ui_global` passa a apenas orquestrar UI (mensagens/clipboard/navegador) usando helpers puros de dominio.
- [x] R7.1.3 Extrair comparacao de branches para o core (2026-02-10)
  Escopo: mover carga de commits/diff numstat e calculos de ahead/behind/conflito da aba Comparar para `viewer/core`.
  Aceite: `ui_branches` apenas apresenta dados e trata feedback visual, com regras Git centralizadas na camada core.
- [x] R7.1.4 Extrair estado de repositorio para o core (2026-02-10)
  Escopo: mover leitura de branches, branch atual, estado dirty e calculo upstream/ahead-behind para `viewer/core`.
  Aceite: `ui_global` passa a consumir helpers de estado de repo sem comandos Git inline para essas regras.
- [x] R7.1.5 Extrair operacoes de branch para o core (2026-02-10)
  Escopo: mover checkout/criacao de branch e stash previo para checkout em modulo de dominio reutilizavel no `viewer/core`.
  Aceite: `ui_global` delega operacoes Git de branch ao core e mantem apenas validacao/interacao visual.
- [x] R7.1.6 Extrair leitura de conteudo de commit para o core (2026-02-10)
  Escopo: mover resolucao de hash, lista de arquivos e leitura de patch de commit para modulo compartilhado em `viewer/core`.
  Aceite: abas Historico/Importar/Comparar reutilizam helpers do core para conteudo de commit, reduzindo duplicacao de `run_git`.
- [x] R7.1.7 Extrair operacoes de cherry-pick/conflito para o core (2026-02-10)
  Escopo: mover fetch de commit para importacao, cherry-pick unitario e leitura de arquivos em conflito para modulo `viewer/core`.
  Aceite: Historico e Importar reutilizam operacoes de cherry-pick/conflito sem comandos Git inline nessas rotas principais.
- [x] R7.1.8 Extrair controle de continuidade/abort de conflito para o core (2026-02-10)
  Escopo: mover deteccao de operacao em conflito e comandos de continuar/abortar (cherry-pick, rebase, merge/squash) para modulo central em `viewer/core`.
  Aceite: aba Historico delega o ciclo de conflito ao core e mantém somente validação de UX/feedback.
- [x] R7.1.9 Extrair reordenacao de commits locais para o core (2026-02-10)
  Escopo: mover carregamento de commits locais e pipeline de reordenacao (backup/reset/replay/restore) para modulo `viewer/core`.
  Aceite: Historico continua com o mesmo fluxo visual, mas delega logica de reordenacao local ao core.
- [x] R7.1.10 Extrair operacoes remotas e tags para o core (2026-02-10)
  Escopo: mover fetch/pull/push e listagem de commits de push para `viewer/core`, alem da listagem de tags usada no filtro do Historico.
  Aceite: `ui_global` e `ui_history` deixam de executar `run_git` inline nesses fluxos, mantendo comportamento funcional inalterado.
- [x] R7.1.11 Extrair estado dos cards de workspace para o core (2026-02-10)
  Escopo: mover leitura de branch, upstream, ahead/behind e arquivos alterados dos cards da aba Repositorios para helpers do `viewer/core`, reaproveitando operacao de checkout de branch no core.
  Aceite: fluxo de cards/workspace em `ui_repos` deixa de executar `run_git` inline para status e checkout.
- [~] R7.2 Shell principal em PySide6 (janela, barra global, tabs e status)
  Escopo: criar estrutura base da nova GUI em PySide6 com layout equivalente ao app atual e suporte a tema claro/escuro.
  Aceite: app abre em PySide6 com navegacao entre abas, barra global funcional e estado basico do repositorio.
- [x] R7.2.1 Bootstrap do shell PySide6 com barra global e tabs (2026-02-10)
  Escopo: criar entrypoint dedicado (`main_pyside6.py`) e janela inicial com seletor de repositorio, branch, fetch/pull/push, status ahead/behind e abas principais.
  Aceite: shell abre em PySide6, aplica tema claro/escuro via settings e persiste ultimo repo/aba.
- [~] R7.3 Migracao incremental das abas criticas (Repositorios, Commit, Historico)
  Escopo: portar as abas de maior uso para PySide6 sem perder funcionalidades atuais.
  Aceite: fluxos centrais (scan/selecionar repo, stage/commit/push, historico e filtros) operam no frontend PySide6.
- [x] R7.3.1 Portar aba Repositorios para o shell PySide6 (2026-02-10)
  Escopo: implementar no PySide6 o fluxo de workspace com raiz configuravel, reescanear repositorios, listar repos encontrados com branch/ahead/behind/status e selecao direta do repositorio ativo.
  Aceite: aba Repositorios no `main_pyside6.py` permite alternar repositorio e refletir estado no seletor global sem depender da UI Tk.
- [x] R7.3.2 Portar fluxo basico de commit para PySide6 (2026-02-10)
  Escopo: implementar na aba Commit do shell PySide6 a listagem de arquivos modificados com selecao, titulo/descricao e acao de commit via core.
  Aceite: usuario consegue selecionar arquivos modificados, criar commit (titulo obrigatorio) e atualizar estado de repositorio/workspace sem sair do PySide6.
- [x] R7.3.3 Portar fluxo basico de historico para PySide6 (2026-02-10)
  Escopo: implementar na aba Historico do shell PySide6 a lista de commits com filtro por texto, painel de detalhes, arquivos do commit e visualizacao de patch com opcao de diff por palavra.
  Aceite: usuario consegue navegar commits, filtrar por texto e inspecionar patch por commit/arquivo no PySide6.
- [x] R7.3.4 Portar fluxo basico de comparacao para PySide6 (2026-02-10)
  Escopo: implementar na aba Comparar do shell PySide6 selecao de origem/destino, resumo de diferencas, lista de commits, lista de arquivos e patch por arquivo com opcao de diff por palavra.
  Aceite: usuario consegue comparar branches no PySide6 com visao de commits/arquivos/patch e indicadores basicos de ahead-behind e possivel conflito.
- [x] R7.3.5 Portar fluxo basico de importacao para PySide6 (2026-02-10)
  Escopo: implementar na aba Importar do shell PySide6 selecao de repositorio/branch de origem, lista de commits e acao de importacao por cherry-pick no repositorio atual.
  Aceite: usuario consegue importar commits selecionados no PySide6 com feedback de progresso/erro e atualizacao das abas relacionadas.
- [x] R7.3.6 Portar configuracoes basicas para PySide6 (2026-02-10)
  Escopo: implementar na aba Configuracoes do shell PySide6 controles para tema, limite de commits e raiz do workspace com persistencia em settings.
  Aceite: usuario consegue salvar configuracoes no PySide6 e ver efeito imediato no tema e no workspace.
- [~] R7.4 Polimento visual e UX "desktop grade"
  Escopo: aplicar identidade visual mais moderna (tipografia, espacamento, componentes, feedback visual e estados de carregamento).
  Aceite: interface final fica consistente, legivel e visualmente superior ao Tkinter, mantendo performance.
- [x] R7.4.0 Polimento inicial do shell PySide6 (2026-02-10)
  Escopo: evoluir layout visual (top bar, tabs, splitters nas abas criticas) e adicionar estado global de carregamento com badge/progresso para operacoes mais pesadas.
  Aceite: interface PySide6 fica mais consistente visualmente e apresenta feedback claro durante scan/fetch/pull/push/carga de historico/importar/comparar.
- [x] R7.4.3 Modularizacao da UI PySide6 por modulos (2026-02-10)
  Escopo: reduzir acoplamento de `shell.py` separando montagem visual, componentes compartilhados e controladores por fluxo, mantendo paridade funcional no meio da migracao.
  Aceite: arquitetura em modulos permite evoluir cada aba/fluxo com menor risco, com `shell.py` atuando como orquestrador leve.
- [x] R7.4.3.1 Extrair builders das abas para `viewer/pyside/tabs/` (2026-02-10)
  Escopo: mover a construcao das abas Repositorios, Commit, Historico, Importar, Comparar e Configuracoes para modulos dedicados em `viewer/pyside/tabs`.
  Aceite: `shell.py` deixa de carregar blocos extensos de layout das abas e passa a delegar para builders modulares sem regressao funcional.
- [x] R7.4.3.2 Extrair barra global e status para modulo dedicado (2026-02-10)
  Escopo: mover criacao e wiring da barra superior (repo/branch/sync) e status bar (mensagens/busy) para modulo de composicao reutilizavel.
  Aceite: `shell.py` passa a apenas conectar callbacks e estado; montagem visual da barra fica isolada.
- [x] R7.4.3.3 Extrair controladores de estado por fluxo (2026-02-10)
  Escopo: separar em controladores os fluxos de repositorio, historico, importacao e comparacao para reduzir metodos longos na janela principal.
  Aceite: handlers de evento ficam por dominio, com responsabilidades claras e menor acoplamento entre abas.
- [x] R7.4.3.3.1 Extrair controlador do Historico em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/history_controller.py` o fluxo de carga/selecionar commit/selecionar arquivo/patch da aba Historico.
  Aceite: callbacks do Historico continuam funcionais via wrappers no `shell.py`, reduzindo tamanho do arquivo principal.
- [x] R7.4.3.3.2 Extrair controlador da aba Comparar em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/compare_controller.py` o fluxo de origem/destino, refresh de comparacao, selecao de arquivo e leitura de patch.
  Aceite: callbacks da aba Comparar seguem funcionais via wrappers no `shell.py`, com logica de dominio UI isolada em controlador.
- [x] R7.4.3.3.3 Extrair controlador da aba Importar em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/import_controller.py` o fluxo de origem/branch, carga de commits, copia de hashes e importacao por cherry-pick.
  Aceite: callbacks da aba Importar seguem funcionais via wrappers no `shell.py`, mantendo o fluxo completo com atualizacao das abas relacionadas.
- [x] R7.4.3.4 Reduzir `shell.py` para bootstrap/orquestracao (2026-02-10)
  Escopo: consolidar a janela principal como ponto de inicializacao, roteamento de eventos e persistencia, removendo logica de montagem/fluxo espalhada.
  Aceite: arquivo principal do PySide6 fica significativamente menor e com manutencao simplificada.
- [x] R7.4.3.4.1 Extrair controlador da aba Commit em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/commit_controller.py` o fluxo de listagem de arquivos modificados, selecao e criacao de commit.
  Aceite: callbacks da aba Commit seguem funcionais via wrappers no `shell.py`, reduzindo metodos de manipulacao direta no arquivo principal.
- [x] R7.4.3.4.2 Extrair controlador da aba Configuracoes em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/settings_controller.py` os fluxos de carregar configuracoes, selecionar pasta e salvar configuracoes.
  Aceite: aba Configuracoes permanece funcional via wrappers no `shell.py`, com persistencia e aplicacao imediata mantidas.
- [x] R7.4.3.4.3 Extrair controlador de workspace/repositorio em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/repo_controller.py` os fluxos de scan do workspace, lista/selecao de repositorio, snapshot dos cards e sincronizacao do estado de repositorio ativo.
  Aceite: fluxos de repositorio/workspace seguem funcionais via wrappers no `shell.py`, reduzindo significativamente o acoplamento da janela principal.
- [x] R7.4.3.4.4 Extrair controlador de branch/sincronizacao em PySide6 (2026-02-10)
  Escopo: mover para `viewer/pyside/controllers/sync_controller.py` os fluxos de checkout de branch, criacao de branch e acoes remotas fetch/pull/push.
  Aceite: operacoes de branch/sincronizacao seguem funcionais via wrappers no `shell.py`, mantendo feedback de erro/estado e atualizacoes de UI.
- [x] R7.4.3.4.5 Limpeza final do shell para bootstrap (2026-02-10)
  Escopo: remover wrappers redundantes e consolidar no `shell.py` apenas inicializacao da janela, wiring principal de sinais e persistencia minima.
  Aceite: `shell.py` vira ponto de entrada enxuto e previsivel, com baixa responsabilidade de dominio.
- [~] R7.4.1 Paridade funcional obrigatoria com a UI atual
  Escopo: validar que a GUI em PySide6 cobre 100% dos fluxos existentes hoje no Tkinter antes de considerar encerrada a migracao.
  Aceite: nenhum fluxo principal fica faltando (repositorios, commit, historico, importar, comparar e configuracoes), sem regressao funcional conhecida.
- [x] R7.4.1.1 Menus de contexto do Historico em PySide6 (2026-02-11)
  Escopo: adicionar menu de contexto em commits e arquivos da aba Historico com acoes de abrir commit no GitHub, copiar hash/URL/patch/lista de arquivos e abrir arquivo no VS Code/pasta.
  Aceite: clique direito na lista de commits e arquivos abre menu com acoes funcionais sem alterar selecao automaticamente.
- [x] R7.4.1.2 Menus de contexto de Importar e Comparar em PySide6 (2026-02-11)
  Escopo: aplicar menu de contexto nos commits da aba Importar e nos arquivos da aba Comparar com as mesmas acoes-chave da UI Tk (GitHub, copia de dados e abertura local).
  Aceite: clique direito em commit de Importar e arquivo de Comparar abre menu funcional e consistente com os fluxos equivalentes da UI Tk.
- [x] R7.4.1.3 Menus de contexto de repositorio no PySide6 (2026-02-11)
  Escopo: aplicar menu de contexto de repositorio no seletor global e na lista da aba Repositorios com acoes locais e atalhos GitHub.
  Aceite: clique direito no combo/lista de repositorios abre menu com abrir VS Code/pasta, copiar caminho e atalhos GitHub (repo/branch/commits/issues/actions/releases e copias de URL).
- [x] R7.4.1.4 Fluxo de abrir PR na aba Commit em PySide6 (2026-02-11)
  Escopo: adicionar botao "Abrir PR" na aba Commit, habilitado quando o worktree estiver limpo, abrindo compare URL do GitHub para branch atual vs branch base padrao.
  Aceite: com worktree limpo, usuario abre a pagina de criacao de PR no navegador sem montar URL manualmente.
- [x] R7.4.1.5 Acoes de Merge/Rebase/Squash na aba Comparar em PySide6 (2026-02-11)
  Escopo: adicionar na aba Comparar controles de acao de branch com validacoes de dirty state, confirmacao e execucao de merge/rebase/squash (com mensagem obrigatoria no squash).
  Aceite: usuario executa acao direto no PySide6 com feedback de erro/sucesso e atualizacao automatica de status/historico/commit/comparacao.
- [x] R7.4.1.6 Menu de contexto de commits na aba Comparar em PySide6 (2026-02-11)
  Escopo: aplicar na lista de commits da aba Comparar o mesmo padrao de menu de commit das outras abas (GitHub, hash, lista de arquivos e patch).
  Aceite: clique direito em commit da comparacao abre menu funcional sem acao manual extra de copia/abertura.
- [x] R7.4.1.7 Fluxo de conflitos em PySide6 para Importar/Comparar (2026-02-11)
  Escopo: adicionar dialogo de conflitos com lista de arquivos, abertura no VS Code e acoes de continuar/abortar para operacoes de cherry-pick, merge, rebase e squash.
  Aceite: ao detectar conflito em Importar ou Comparar, o app abre o dialogo de resolucao e permite continuar/abortar sem sair do PySide6.
- [x] R7.4.1.8 Clonagem de repositório na aba Repositorios em PySide6 (2026-02-11)
  Escopo: adicionar dialogo de clonagem com URL/SSH, pasta opcional e progresso textual, incluindo re-scan automatico e selecao do repo ao concluir.
  Aceite: usuario consegue clonar novo repositorio direto no PySide6 e o workspace e atualizado automaticamente no fim da operacao.
- [x] R7.4.1.9 Commit em PySide6 com status real, diff e stage/unstage por arquivo (2026-02-11)
  Escopo: evoluir aba Commit do PySide6 para listar estado real de stage (`[x]/[~]/[ ]`), exibir preview de diff do arquivo selecionado e permitir stage/unstage direto do arquivo selecionado.
  Aceite: usuario enxerga estado staged/unstaged por arquivo no PySide6, visualiza diff (normal/palavra) e consegue alternar stage por arquivo sem sair da aba.
- [x] R7.4.1.10 Stage/unstage por bloco (hunk) na aba Commit em PySide6 (2026-02-11)
  Escopo: adicionar acoes de stage/unstage por bloco do diff selecionado na aba Commit, com aplicacao de patch no index via `git apply --cached`.
  Aceite: com diff selecionado, usuario consegue aplicar ou reverter hunk no stage direto pelo PySide6 sem usar CLI.
- [x] R7.4.1.11 Stage/unstage por linha na aba Commit em PySide6 (2026-02-11)
  Escopo: adicionar acoes de stage/unstage por linha alterada no diff selecionado da aba Commit, com aplicacao de patch unidiff-zero por linha.
  Aceite: com uma linha de diff selecionada, usuario consegue aplicar ou reverter apenas aquela linha no stage direto pelo PySide6.
- [x] R7.4.1.12 Stash e Undo commit na aba Commit em PySide6 (2026-02-11)
  Escopo: adicionar na aba Commit as acoes de stash (com mensagem) e undo do ultimo commit por modo (`soft`, `mixed`, `hard`) com confirmacao para o modo destrutivo.
  Aceite: usuario consegue criar stash e desfazer o ultimo commit pelo PySide6 com feedback de status e atualizacao das abas dependentes.
- [ ] R7.4.2 Rodada final de testes de regressao e usabilidade
  Escopo: executar checklist de testes manuais e automatizados da migracao para confirmar estabilidade, performance e consistencia de UX.
  Aceite: migracao aprovada em testes; somente apos essa etapa a trilha de distribuicao pode iniciar.
- [ ] R7.5 Distribuicao desktop Linux (AppImage + .deb + atalho de menu)
  Escopo: empacotar versao GUI para Linux com instalacao simples, incluindo `.desktop`, icone e associacao de execucao, iniciando somente apos conclusao de R7.4.2.
  Aceite: usuario baixa e executa sem setup manual de Python, com entrada no menu de aplicativos.
- [ ] R7.6 Pipeline de release para desktop Linux
  Escopo: automatizar build e publicacao dos artefatos Linux (AppImage/.deb) na esteira de release.
  Aceite: cada release gera pacotes assinaveis/reproduziveis com checksum e notas.
- [ ] R7.7 Manter `core` em Python como padrao do projeto
  Escopo: formalizar no roadmap que somente a camada de interface muda para PySide6; dominio e automacoes permanecem em Python.
  Aceite: decisoes de arquitetura e PRs de UI seguem regra de nao reescrever o `core` em outra linguagem.

Ordem de execucao sugerida
- 1) R6.2
- 2) R6.2.1
- 3) R6.3
- 4) R6.5
- 5) R6.6
- 6) R6.4
- 7) R6.7
- 8) R6.9
- 9) R6.9.1
- 10) R6.9.2
- 11) R6.10
- 12) R6.10.1
- 13) R6.10.2
- 14) R7.1
- 15) R7.2
- 16) R7.3
- 17) R7.4
- 18) R7.4.3
- 19) R7.4.3.1
- 20) R7.4.3.2
- 21) R7.4.3.3
- 22) R7.4.3.4
- 23) R7.4.1
- 24) R7.4.2
- 25) R7.5
- 26) R7.6
- 27) R7.7

## Regras de Manutencao

- Toda entrega deve marcar o item correspondente como concluido com data.
- Mudancas relevantes devem entrar no `CHANGELOG.md`.
