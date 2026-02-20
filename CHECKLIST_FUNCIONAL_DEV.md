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

- Data:
- Testador:
- Branch/commit:
- OS:
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
- [ ] Janela de diff avancada abre e funciona sem crash.
- [ ] Janela de diff avancada: marcar/desmarcar linha NAO afeta arquivo inteiro.
- [ ] Commit exige titulo.
- [ ] Commit com arquivo removido funciona.
- [ ] Stash funciona.
- [ ] Undo commit (soft/mixed) funciona.

### 3.4 Aba Historico
- [ ] Lista de commits carrega.
- [ ] Busca por texto filtra (case-insensitive).
- [ ] Scroll progressivo carrega mais commits.
- [ ] Selecionar commit atualiza metadados + arquivos + diff.
- [ ] Menus de contexto (commit/arquivo) funcionam.
- [ ] Exportar commits funciona.

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
- [ ] Merge/rebase/squash sem conflito funcionam.
- [ ] Merge/rebase/squash com conflito abrem tela de conflitos.

### 3.7 Aba Configuracoes
- [ ] Tema claro/escuro funciona.
- [ ] Overrides de tema salvam e reaplicam.
- [ ] Perfil de atualizacao salva e reaplica.

---

## 4) Bugs funcionais (dev)

Use esta secao para controle dos bugs que NAO dependem de `.deb`.

| ID | Area | Severidade | Status atual |
|---|---|---|---|
| BUG-001 | Commit / Diff avancado | Alta | Em reteste (prox) |
| BUG-002 | Historico / Busca | Media | Em reteste (prox) |
| BUG-003 | Auto update / Commit | Media | Em reteste (prox) |
| BUG-004 | Barra global / Branch | Media | Em reteste (prox) |
| BUG-005 | Commit / Estabilidade | Alta | Em reteste (prox) |
| BUG-006 | Importar / Conflitos | Alta | Corrigido, validar (prox) |
| BUG-007 | Commit / Auto-stage | Alta | Corrigido, validar (prox) |
| BUG-008 | Commit / Sincronia diff | Alta | Corrigido, validar (prox) |
| BUG-009 | Commit / Menu arquivo | Media | Corrigido, validar (prox) |
| BUG-010 | Repositorios / Menu contexto | Media | Corrigido, validar (prox) |
| BUG-011 | Comparar / Squash conflito | Alta | Corrigido, validar (prox) |
| BUG-012 | Tela de conflitos | Media | Corrigido, validar (prox) |
| BUG-013 | Fluxo conflito UX | Media | Corrigido, validar (prox) |
| BUG-014 | Configuracoes / Perfil de atualizacao | Media | Corrigido, validar (prox) |

---

## 5) Resultado da rodada dev

- [ ] Rodada dev aprovada sem bloqueadores.
- [ ] Bugs abertos atualizados.
- [ ] Pronto para checklist de distribuicao.
