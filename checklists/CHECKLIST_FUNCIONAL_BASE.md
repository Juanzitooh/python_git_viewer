# Checklist Funcional (Dev) - Git Viewer v{{VERSION}}

Objetivo:
- Validar comportamento funcional da aplicacao rodando em desenvolvimento (`python3 main.py`).
- Fechar bugs de fluxo/UX/logica antes da rodada de empacotamento.

Como usar:
- Marque `[x]` quando OK.
- Marque `[bug]` quando falhar e registre no bloco de bugs deste arquivo.
- Marque `[prox]` quando ficar para rodada seguinte.

---

## 1) Dados da rodada

- Data: {{DATE}}
- Testador: {{TESTER}}
- Branch/commit: {{BRANCH_COMMIT}}
- OS: {{OS_INFO}}
- Modo de execucao: `python3 main.py`

## 2) Preparacao do ambiente dev

Script recomendado (idempotente):

```bash
./setup.sh --no-run
./setup.sh
```

Checklist:
- [ ] setup executa sem erro.
- [ ] App abre sem traceback.
- [ ] Tabs renderizam corretamente.
- [ ] `settings.json` e salvo entre reinicios.

---

## 3) Checklist funcional da GUI (dev)

### 3.1 Barra global
- [ ] Troca de repositorio funciona.
- [ ] Troca de branch funciona.
- [ ] Nova branch cria e troca para a nova branch.
- [ ] Fetch atualiza contadores.
- [ ] Pull/Push obedecem estado da branch/upstream.
- [ ] Publish aparece para branch local sem upstream.

### 3.2 Aba Repositorios
- [ ] Workspace root carrega/salva.
- [ ] Reescanear atualiza cards.
- [ ] Favoritos aparecem primeiro.
- [ ] Duplo clique abre no VS Code.
- [ ] Menu de contexto do repo funciona.
- [ ] Adicionar repositorio (clone) funciona.

### 3.3 Aba Commit
- [ ] Lista por pasta + `(todos)` funciona.
- [ ] Selecao arquivo/pasta/todos reflete estado parcial corretamente.
- [ ] Diff principal nao reordena linhas ao marcar/desmarcar.
- [ ] Stage/unstage por linha e bloco funciona.
- [ ] Commit exige titulo.
- [ ] Commit funciona normalmente.
- [ ] Stash funciona.
- [ ] Undo commit funciona.
- [ ] Status sincronizado em tempo real.

### 3.3.1 Aba Commit (stash)
- [ ] Aplicar stash funciona.
- [ ] Aplicar e remover stash funciona.
- [ ] Remover stash funciona.
- [ ] A aba stash aparece/some conforme existencia de stash.

### 3.4 Aba Historico
- [ ] Lista de commits carrega.
- [ ] Busca por texto filtra (case-insensitive).
- [ ] Scroll progressivo carrega mais commits.
- [ ] Selecionar commit atualiza metadados + arquivos + diff.
- [ ] Menus de contexto (commit/arquivo) funcionam.
- [ ] Exportar commits para outras branchs funciona.
- [ ] Reordenar commits locais funciona (com e sem conflito).

### 3.5 Aba Importar
- [ ] Repo/branch de origem carregam.
- [ ] Lista de commits carrega.
- [ ] Importar commits funciona.
- [ ] Fluxo de conflito abre sem popup redundante.

### 3.6 Aba Comparar
- [ ] Branch origem/destino carregam.
- [ ] Botao trocar origem/destino funciona.
- [ ] Commits/arquivos/diff atualizam conforme selecao.
- [ ] Menus de contexto funcionam.
- [ ] Merge sem conflito funciona.
- [ ] Merge com conflito abre tela de conflitos.
- [ ] Rebase sem conflito funciona.
- [ ] Rebase com conflito abre tela de conflitos.
- [ ] Squash merge sem conflito funciona.
- [ ] Squash merge com conflito abre tela de conflitos.

### 3.7 Aba Configuracoes
- [ ] Tema e configuracoes gerais salvam e reaplicam.

### 3.8 Aba Conflitos (situacional)
- [ ] Resolver conflito por menu de contexto funciona.
- [ ] Estado de conflito atualiza em tempo real.
- [ ] Continuar/abortar fluxo funciona.

---

## 4) Bugs funcionais (dev)

Registre aqui apenas bugs de funcionalidade (nao empacotamento).

| ID | Area | Severidade | Status atual |
|---|---|---|---|

---

## 5) Resultado da rodada dev

- [ ] Rodada dev aprovada sem bloqueadores.
- [ ] Bugs abertos atualizados.
- [ ] Pronto para checklist de distribuicao.
