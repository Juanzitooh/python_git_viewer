# Checklist Manual - R7.4.2 (PySide6)

Objetivo:
- Validar regressao funcional e usabilidade final do shell PySide6 antes de iniciar distribuicao Linux (R7.5).

Como usar:
- Marque cada item com `[x]` quando OK.
- Se falhar, marque `[BUG]` e registre no bloco "Registro de Bugs" no final.
- Se item nao se aplica no seu ambiente, marque `[N/A]`.

## 1. Dados da rodada

- Data:
- Testador:
- Branch:
- Commit (hash curto):
- OS:
- Python usado:
- Execucao: `python3 main_pyside6.py` ou `.venv/bin/python main_pyside6.py`

## 2. Pre-check rapido

- [X] App abre sem traceback no terminal.
- [BUG] Janela abre maximizada.
- [X] Tabs aparecem na ordem correta: Repositorios, Commit, Historico, Importar, Comparar, Configuracoes.
- [X] Status bar mostra estado sem travar UI.

## 3. Barra global (topo)

- [X] Combobox de repositorio carrega repos validos.
- [X] Trocar repo atualiza branch/status sem erro.
- [X] Combobox de branch faz checkout sem erro.
- [X] Botao Nova branch cria branch e troca para ela.
- [X] Fetch executa e atualiza ahead/behind.
- [BUG] Pull habilita/desabilita corretamente conforme behind.- atualiza informação, mas gostaria que se não tiver, ou seja for zero, não apareça.
- [BUG] Push habilita/desabilita corretamente conforme ahead.- atualiza informação, mas gostaria que se não tiver, ou seja for zero, não apareça.
- [X] Menus de contexto de repositorio funcionam:
  - [x] Abrir no VS Code
  - [x] Abrir na pasta
  - [x] Copiar caminho
  - [x] GitHub: abrir repo/branch/commits/issues/actions/releases
  - [x] GitHub: copiar URL repo/branch

## 4. Aba Repositorios

- [X] Campo raiz workspace aceita edicao e persiste.
- [X] Botao Pasta seleciona raiz corretamente.
- [X] Reescanear atualiza lista sem travar.
- [BUG] Lista mostra colunas (repo, caminho, branch, ahead, behind, status). - deveriam ser cards com essas informações, algo mais moderno não listas sabe
- [X] Clique simples seleciona repo ativo.
- [BUG] Duplo clique seleciona repo sem erro. - isso é um erro, deveria abrir no vscode
- [X] Menu de contexto na lista funciona (mesmas acoes da barra global).
- [X] Adicionar repositorio abre dialogo de clone.
- [BUG] Clone URL/SSH com pasta opcional funciona. - ele salva numa pasta com o exato nome que coloquei lá.. por exemplo era pra ser pasta/repo não salvar em pasta
- [X] Progresso de clone aparece.
- [X] Ao concluir clone: re-scan acontece e repo novo aparece selecionavel.

## 5. Aba Commit

- [BUG] Lista de arquivos modificados carrega. - carrega mas com er - carrega, mas incompleta cade a linha todos ou a linha com o nome de cada pasta pra selecionar várias de uma vez? como no tkinter?
- [BUG] Marcadores de status aparecem (`[x]`, `[~]`, `[ ]`). - aparece sim, mas tem um checkbox marcador, qunado marco ele não muda nada ai, tem coisa errada nessa legenda
- [BUG] Selecao por checkbox funciona. - escesso de botão checar aba no tkinter e comparar
- [BUG] Selecionar tudo funciona.- escesso de botão checar aba no tkinter e comparar
- [ ] Limpar selecao funciona. - escesso de botão checar aba no tkinter e comparar
- [bug] Diff do arquivo selecionado carrega.
- [bug] Diff por palavra alterna visualizacao. olha lá no tkinter como era a diff de arquivos era bem mais visual com inha, cor vermelha pra deletado e verde para adicionado, tá muito ruim vizualizar
- [x] Stage selecionado (arquivo) funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Unstage selecionado (arquivo) funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Stage bloco funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Unstage bloco funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Stage linha funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Unstage linha funciona. - escesso de botão checar aba no tkinter e comparar
- [x] Commit exige titulo (obrigatorio).
- [x] Commit com titulo e descricao opcional funciona.
- [ ] Stash funciona e atualiza tela.
- [bug] Undo commit (soft/mixed/hard) funciona. deixa só o soft e mixed por favor
- [ ] Botao Abrir PR so habilita com worktree limpo.
- [bug] Abrir PR abre dialogo base/head e abre URL correta no navegador. não ta abrindo o dialogo para selecionar quais serão as branchs

## 6. Aba Historico

- [X] Lista de commits carrega.
- [bug] Busca por texto filtra resultados. - não ta filtrando nada, gostaria que de escrever algo ali já filtrasse dizendo nada encontrado caso não tenha
- [bug] Limite de commits funciona (50/100/200). - deveria ser scroll infinito
- [bug] Diff por palavra atualiza patch. revê como era exibido o path pelo tkinter os path utils que deixavam facil de ler as coiss com filtros em verde e vermelho para linahs adicionadas e tal, tá tudo confuso
- [x] Selecionar commit atualiza metadados.
- [x] Selecionar arquivo atualiza patch do arquivo.
- [x] Marcadores `[L]` e `[L+O]` aparecem conforme estado.
- [bug] Tooltip/infos do commit estao coerentes. - nãoi vi uma tooltip na pagina
- [bug] Menu de contexto de commit funciona: - ap abrir menu tá selecionadndo commit, atrapalha o fluxo
  - [ ] Copiar hash
  - [ ] Copiar patch completo
  - [ ] Copiar lista de arquivos
  - [ ] Abrir commit no GitHub
  - [ ] Copiar URL do commit
- [bug] Menu de contexto de arquivo funciona:
tudo bugado no menu, ele aparece mas somente a ultima opção é possivel clicar nela
  - [ ] Abrir no VS Code
  - [ ] Abrir na pasta
  - [ ] Copiar caminho relativo
  - [ ] Copiar patch do arquivo
  - [ ] Copiar patch completo
- [bug] Botao Exportar funciona (copiar hashes + confirmar exportacao). ao apertar ctrl e apertar em outro commit não é possivel adicionar mais um a seleção e isso faz o exportar só funcionar unitariamente
- [ ] Exportar trata conflito abrindo dialogo de conflitos.
- [ ] Botao Reordenar locais aparece so quando ha >=2 commits locais com upstream.
- [ ] Reordenar locais funciona com backup e atualiza historico.

## 7. Aba Importar

- [x] Combobox de repo origem carrega lista do scan.
- [bug] Usar atual funciona. qual sentido de usar atual se e importar de outro repositório o intuito da pagina?
- [x] Combobox de branch origem carrega.
- [x] Lista de commits da origem carrega.
- [x] Botao Copiar hashes funciona.
- [ ] Importar selecionados funciona.
- [ ] Em conflito, dialogo de conflitos abre corretamente.
- [X] Menu de contexto de commit funciona (GitHub/hash/lista/patch).

## 8. Aba Comparar

- [X] Origem/destino carregam branches validas.
- [X] Botao Trocar inverte origem/destino.
- [X] Atualizar recarrega comparacao.
- [bug] Diff por palavra funciona no patch. - todo bugado a forma de ver o patch consulta uo tkinter, antiga ui pra entende como era lá
- [x] Lista de commits carrega.
- [x] Lista de arquivos carrega.
- [x] Selecionar arquivo mostra patch.
- [x] Menu de contexto de commit funciona.
- [x] Menu de contexto de arquivo funciona.
- [ ] Acao Merge funciona.
- [ ] Acao Rebase funciona.
- [X] Acao Squash exige mensagem.
- [ ] Em conflito, dialogo de conflitos abre corretamente.
- [x] Botao Ir para Commit funciona quando worktree esta sujo.

## 9. Aba Configuracoes

- [X] Troca de tema Claro/Escuro funciona.
- [bug] Limite padrao de commits salva e aplica. - não deveria ter limite de commits aqui, deveria ser scrool infinito caso tenha o que carregar
- [x] Raiz do workspace salva e aplica.
- [x] Reiniciar app preserva configuracoes salvas.

## 10. Dialogo de conflitos (geral)

- [ ] Lista arquivos em conflito.
- [ ] Abrir no VS Code funciona.
- [ ] Atualizar recarrega estado.
- [ ] Continuar funciona quando conflito resolvido.
- [ ] Abortar funciona.

## 11. Persistencia entre reinicios

- [X] Ultimo repositorio ativo e restaurado.
- [bug] Ultima aba ativa e restaurada.
- [?] Preferencias mantidas em `settings.json`.

## 12. Resultado final da rodada

- [ ] Rodada aprovada sem bloqueios.
- [ ] Existem bugs registrados (se sim, listar abaixo).

Resumo rapido:
- Total itens OK:
- Total itens BUG:
- Total itens N/A:
- Decisao: `APROVAR R7.4.2` / `MANTER EM AJUSTE`

---

## Registro de Bugs

Use 1 linha por bug.

| ID | Area | Severidade (Alta/Media/Baixa) | Passos para reproduzir | Resultado esperado | Resultado atual | Evidencia (print/log) | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 |  |  |  |  |  |  | Aberto |

