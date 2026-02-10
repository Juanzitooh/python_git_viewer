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
- Corrigido entrypoint do app e import ausente na aba de commit.
- Janela principal abre maximizada e painel de patch no Historico fica redimensionavel com abertura em janela.
- Barra global com titulo dinamico e acao de copiar caminho/abrir no VS Code.
- Barra global simplificada sem campo editavel de caminho e sem seletores redundantes de branch/origem/destino.
- Workspace GitHub na aba Repositorios com pasta base configuravel, scan de repos locais, preparo + checagem de chave SSH em Python e clone por URL/SSH.
- Scan automatico da pasta base de workspace na inicializacao para popular repositorios recentes.
- Remocao do bloco redundante de status da aba Repositorios para reduzir ruido visual.
- Removida a seção inferior de listas de favoritos/recentes da aba Repositórios.
- Aba Repositórios ajustada para "Raiz local do Workspace GitHub" com ação de "Reescanear".
- Botão "Preparar chave SSH" passa a aparecer somente quando a chave SSH local nao existe.
- Corrigida troca de repositório para evitar erro de branch ambígua na aba Comparar durante estado transitório entre repos.
- Aba Repositórios ganhou painel de cards (2x4) com visão geral de favoritos/recentes, branch atual e ahead/behind por repositório.
- Combobox de repositório voltou para a barra superior com visibilidade contextual: aparece fora da aba Repositórios e fica oculto dentro dela.
- Barra superior reorganizada com ações de repositório no lado esquerdo e ações globais (Fetch/Pull/Push, Ahead/Behind e Perf) ancoradas à direita.
- Ações de repositório migradas para menu de contexto (clique direito) no combobox global e nos cards da aba Repositórios, com abrir no VS Code, copiar caminho, abrir pasta e abrir no GitHub.
- Cards da aba Repositórios agora incluem opção de excluir repositório local via menu de contexto, com confirmação explícita antes da remoção física da pasta.
- Cards da aba Repositórios agora têm rolagem contínua (sem limite fixo de 8) e card final "+1" para adicionar repositório.
- Fluxo de clonagem saiu da barra superior e foi para modal aberto pelo card de adicionar repositório.
- Janela de clonagem agora mostra progresso detalhado em tempo real (`git clone --progress`), com log textual, hint de percentual e cancelamento durante a operação.
- Durante a clonagem, a UI principal fica bloqueada para evitar interações concorrentes e no diálogo apenas a ação de cancelar permanece ativa.
- Ao finalizar clone com sucesso, a barra de progresso da janela de clonagem pisca brevemente para sinalizar conclusão antes de fechar.
- Cada card agora exibe status local do repositório com arquivos modificados quando houver alterações.
- Log de performance em `performance.log` na raiz com timestamp, repositório e duração das operações monitoradas.
- Novo argumento `--perf`: quando ativo, mostra bloco de performance na UI e grava métricas no `performance.log`; em execução padrão o bloco fica oculto e sem logging.
- Log de performance agora inclui `trigger=` para indicar origem da ação (ex.: `status:auto_timer`, `status:repo_switch`) e passou a registrar também o `fetch` automático e o `fetch` de pré-commit+push.
- Cobertura de performance ampliada para ações síncronas de usuário: stage/unstage (arquivo, linha, hunk), commit/undo, stash (rápido e janela), checkout/criação de branch, cherry-pick/reordenação no histórico, importação de commits e ação de merge/rebase/squash na aba Comparar.
- Taxonomia de `trigger` padronizada para facilitar leitura no log: eventos principais em `area:acao` e recargas derivadas em `post_*`.
- Otimizado painel de cards do workspace com cache e atualização leve de seleção para evitar recálculo completo a cada troca de repositório.
- Cards do workspace agora têm combobox de branch por repositório para checkout rápido, clique simples para selecionar no app e duplo clique para selecionar + abrir no VS Code.
- Nova barra fina de atividade no rodapé (fio azul) durante operações assíncronas para indicar carregamento em andamento.
- Abas Histórico e Commit agora têm seletor rápido de branch local com botão "Nova branch" para criar branch a partir da base selecionada e opcionalmente já fazer checkout.
- Ajustado layout da aba Commit: controles de branch/atualização ficam em linha separada para liberar largura da lista de arquivos e melhorar leitura/scroll.
- Cache do estado SSH do GitHub persistido em `settings.json` para evitar novo teste remoto no startup quando a chave local não mudou.
- Persistência da última aba ativa em `settings.json` e restauração automática no próximo start.
- Janela principal inicia oculta e só é exibida após estabilizar a carga inicial assíncrona (cards/status/branches/commits).
- Nova aba dedicada "Importar" com repositório origem, branch origem e lista de commits selecionáveis para importação no repositório/branch atual via cherry-pick.
- Aba Historico compactada com filtro em modal "Busca filtrada", botao "Tirar filtro" apenas quando ativo, linha de commit com data relativa e tooltip com data/hora completa, alem de acao para copiar hash completo.
- Aba Historico agora marca cada commit com `[L]` (apenas local, ainda nao enviado) ou `[L+O]` (presente local e remoto/upstream), incluindo legenda e tooltip com esse estado.
- Aba Importar agora usa combobox de repositorios vindos do scan (favoritos/recentes/workspace), sem entrada manual de caminho, e carrega as branches da origem selecionada.
- Aba Commit ganhou fluxo de `Undo commit` com modos `soft`, `mixed` e `hard`, com confirmações reforçadas para o modo destrutivo.
- Aba Historico ganhou ferramenta de reordenacao de commits locais `[L]` com mover para cima/baixo e aplicacao segura via backup automatico antes da reescrita.
- Fluxo legado de "Abrir recente" agora abre repositorio, executa fetch e navega automaticamente para a aba Historico.
- Aba Comparar reorganizada com bloco de acao no rodape, botao Executar alinhado a direita, campo de mensagem visivel apenas em "Squash merge" e CTA para ir direto a aba Commit quando houver alteracoes locais.
- Aba Commit agora usa interacao direta por clique para stage/unstage: clique simples no arquivo alterna stage, clique no diff alterna linha e duplo clique no diff alterna hunk, sem depender dos quatro botoes de acao.

## [0.1.0] - 2026-02-05

- Build com PyInstaller via `compile.py`.
- Criacao de `.venv` automatica no build.
- `requirements.txt` e `requirements-dev.txt` iniciais.
- `.gitignore` para artefatos e caches.
- README com instrucoes de build e execucao.
