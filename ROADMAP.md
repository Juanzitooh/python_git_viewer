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
- [x] R6.7 Aba Commit com stage/unstage por interacao direta (2026-02-08)
  Escopo: remover dependencia dos botoes de acao em lote e usar clique para alternar stage/unstage em arquivo, hunk e linha; preservar ordem natural dos itens e indicar visualmente selecao de hunk/linha.
  Aceite: fluxo principal de stage/unstage funciona sem combinacao de teclado e sem passos extras.

Ordem de execucao sugerida
- 1) R6.2
- 2) R6.2.1
- 3) R6.3
- 4) R6.5
- 5) R6.6
- 6) R6.4
- 7) R6.7

## Regras de Manutencao

- Toda entrega deve marcar o item correspondente como concluido com data.
- Mudancas relevantes devem entrar no `CHANGELOG.md`.
