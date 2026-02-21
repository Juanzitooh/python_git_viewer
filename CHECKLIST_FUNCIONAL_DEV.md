# Checklist Funcional (Dev) - Git Viewer PySide6

Objetivo:
- Validar comportamento funcional da aplicacao rodando em desenvolvimento (`python3 main.py`).
- Fechar bugs de fluxo/UX/logica antes da rodada de empacotamento.

Como usar:
- Marque `[x]` quando OK.
- Marque `[bug]` quando falhar e registre no bloco de bugs deste arquivo.
- Marque `[prox]` quando ficar para rodada seguinte.

---

## 1) Dados da rodada

- Data: 20/02/2026
- Testador: Juan Pablo
- Branch/commit: feature/r7-pyside6-linux
- OS: linux
- Modo de execucao: `python3 main.py`

## 2) Preparacao do ambiente dev

Script recomendado (idempotente):

```bash
./setup.sh --no-run
./setup.sh
```

Opcional (manual):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Checklist:
- [x] ./setup.sh inicia app direto.
- [x] App abre sem traceback.
- [x] Tabs renderizam corretamente.
- [x] `settings.json` e salvo entre reinicios.

---

## 3) Checklist funcional da GUI (dev)

### 3.1 Barra global
- [x] Troca de repositorio funciona.
- [x] Troca de branch funciona.
- [x] Nova branch cria e troca para a nova branch.
- [x] Fetch atualiza contadores.
- [x] Pull/Push obedecem estado da branch/upstream.
- [x] Publish aparece para branch local sem upstream.

### 3.2 Aba Repositorios
- [x] Workspace root carrega/salva.
- [x] Reescanear atualiza cards.
- [x] Favoritos aparecem primeiro.
- [x] Duplo clique abre no VS Code.
- [x] Menu de contexto do repo funciona.
- [x] Adicionar repositorio (clone) funciona.

### 3.3 Aba Commit
- [x] Lista por pasta + `(todos)` funciona.
- [x] Selecao arquivo/pasta/todos reflete estado parcial corretamente.
- [x] Diff principal nao reordena linhas ao marcar/desmarcar.
- [x] Stage/unstage por linha e bloco funciona.
- [x] Janela de diff avancada abre e funciona sem crash.
- [x] Janela de diff avancada: marcar/desmarcar linha NAO afeta arquivo inteiro.
- [x] reverter alterações no arquivo
- [x] Commit exige titulo.
- [x] Commit funciona normalmente.
- [bug] Stash funciona.
- [x] Undo commit (soft/mixed) funciona.
- [bug] Status Sicronizado: Arquivos e Diffs em tempo real

### 3.3.1 Aba Commit(stash)
- [bug] aplicar stash funciona
- [x] aplicar e remover stash funciona
- [x] remover stash funciona
- [bug] ao fazer uma ação a janela é ocultada ou aparece

### 3.4 Aba Historico
- [x] Lista de commits carrega.
- [x] Busca por texto filtra (case-insensitive).
- [x] Scroll progressivo carrega mais commits.
- [x] Selecionar commit atualiza metadados + arquivos + diff.
- [x] Menus de contexto (commit/arquivo) funcionam.
- [x] Exportar commits para outras branchs funciona.
- [bug] reordenar commits locais quando tem conflito, cria o backup reorder com a mudança correta pra publicar, mas dá erro na branch atual.

### 3.5 Aba Importar
- [x] Repo/branch de origem carregam.
- [x] Lista de commits carrega.
- [x] Importar commits funciona.
- [x] Fluxo de conflito abre sem popup redundante.

### 3.6 Aba Comparar
- [bug] Branch origem/destino carregam.
- [x] Botao trocar origem/destino funciona.
- [x] Commits/arquivos/diff atualizam conforme selecao.
- [x] Menus de contexto funcionam.
- [x] Merge sem conflito funciona.
- [bug] Merge com conflito abre tela de conflitos.
- [x] Rebase sem conflito funciona.
- [bug] Rebase com conflito abre tela de conflitos.
- [x] Squash sem conflito funciona.
- [bug] Squash com conflito abre tela de conflitos.

### 3.7 Aba Configuracoes
- sofrerá rework, testes adiados.

### 3.8 Aba Conflitos (situacional)
- [bug] Menu com clique direito com as opções relevantes.
- [bug] conflito sicronizado em tempo real sem impossibilitar usar a ui
- [x] abortar ação seja import, export ou merges.

---

## 4) Bugs funcionais (dev)

Use esta secao para controle dos bugs que NAO dependem de `.deb`.

# Aba Commit

- Duplo clique abre no VS Code: Dá crash e diz que tem ponteiro nulo.(resolvido)
- Menu de contexto do repo funciona: a opção abrir no terminal não abre.(resolvido)

- aba commit/ Stage/unstage por linha e bloco funciona: quando tem mais de uma seção, ao desmarcar a segunda seção pra baixo dá erro de apply patch (resolvido)

- Ao apertar stash dá crash, mas ocorre ele sim

- status quero que seja em tempo real, ou seja editei um arquivo no vscode , só de mudar a tela pra cá quero já ver os arquivos e linhas como se eu apertasse atualizar ali, atualmente preciso apertar toda vez (resolvido)

- na janela de stash, após aplicar a primeira vez, mesmo apertando no arquivo deixa de exibir a diff dele

# Janela de diff avancada: marcar/desmarcar linha NAO afeta arquivo inteiro: 
- agora quando tiro a seleção, é criada uma nova secção com a linha no final reordena no fim, queria que mantivesse na mesma seção original apenas desmarcada e marcasse o parcial certinho
- por alguma razão memso sendo linha adicionada ou excluida continua ficando na cor branca, vê se tme algum bug
- o mesmo erro de não funcionar seleção quando tem mais de uma secção ocorre aqui

# Histórico

- ao reordenar commits locais, aparece erro que teve conflito, o backup funciona normal e fica local... é assim mesmo?

# Comparar

- as combox com o nome das branchs estão pequenas, não fica facil ler (resolvido)
- quando é uma comparação grande o vscode até dá uma travada e preciso apertar pra aguardar no vscode... isso travaria no pc da pessoa?

# Janela de Conflitos

- gostaria que o menu ao invés de tanto botão ali referente ao arquivo selecionado... fosse um menu de clique direito, onde teriam as opções relativas ao arquivo 

- as opções devem levar em conta qual é o conflito ou seja de acorod com a diff ou algo assim, se é um arquivo sendo adicionado e não existia ou mudança estrutural nele

- duplo clique abre no vscode

- melhorar nomenclatura tipo pra eu entender se vou manter alterações que veio da origem ou como era no destino, e nisso dar pronto automático.

- o mesmo ao eu selecionar no vscode o head lá, atualizar e mostrar na janela de conflito que foi resolvido mesmo, já marcando pra continuar ser normal no fluxo

- ao apertar continuar memso tendo resolvido para tudo, travamento total só dando kill no processo pra continuar
---

## 5) Resultado da rodada dev

- [ ] Rodada dev aprovada sem bloqueadores.
- [ ] Bugs abertos atualizados.
- [ ] Pronto para checklist de distribuicao.

## 6) melhorias planejadas (brainstorm) -> Roadmap

- simplificar o undo commit, apertar ele é o mesmo que selecionar soft undo commit, assim fica mais simples de interagir, se não tiver nenhum local não seria possivel clicavel

-
