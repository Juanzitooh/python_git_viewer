# Checklist Linux - v0.2.0 (PySide6)

Objetivo:
- Validar instalacao, execucao, update e desinstalacao no Ubuntu 24.04.
- Validar fluxo funcional principal da GUI PySide6 apos instalar via `.deb`.

Como usar:
- Marque `[x]` quando OK.
- Marque `[BUG]` quando falhar e descreva no bloco final.
- Marque `[N/A]` quando nao se aplicar.
- Marque `[prox]` quando for ser testado somente após ajustes

Detalhe: após cada rodada de ajustes , ou seja zerar os bugs descritos, será testado o proximo e no fim uma rodada final de testes até aprovar
---

## 1) Dados da rodada

- Data:
- Testador:
- Branch/commit testado:
- Distro/kernel:
- Pacote testado: `dist/git-viewer_0.2.0_amd64.deb`

## 2) Caminhos importantes

- Binario CLI instalado: `/usr/bin/git-viewer`
- Atalho desktop: `/usr/share/applications/git-viewer.desktop`
- Settings (Linux):
  - padrao: `~/.config/git_commits_viewer/settings.json`
  - se `XDG_CONFIG_HOME` estiver setado: `$XDG_CONFIG_HOME/git_commits_viewer/settings.json`

---

## 3) Build e instalacao (.deb)

Executar na raiz do repo:

```bash
python3 scripts/build_linux_packages.py --build-binary --deb-only
ls -lh dist/git-viewer_0.2.0_amd64.deb
```

Instalar (evita warning de permissao do `_apt`):

```bash
cp dist/git-viewer_0.2.0_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.2.0_amd64.deb
```

Validar instalacao:

```bash
apt policy git-viewer
which git-viewer
git-viewer --help
```

Checklist:
- [x] Build do `.deb` conclui sem erro.
- [x] Instalacao via `apt` conclui sem erro.
- [x] `which git-viewer` retorna `/usr/bin/git-viewer`.
- [x] `git-viewer --help` responde.

---

## 4) Abrir o app e validar persistencia

Abrir pelo terminal:

```bash
git-viewer
```

Abrir pelo menu desktop (teste opcional):

```bash
gtk-launch git-viewer
```

Validar settings:

```bash
ls -lah ~/.config/git_commits_viewer/
cat ~/.config/git_commits_viewer/settings.json
```

Checklist:
- [x] App abre sem traceback.
- [x] Janela abre e renderiza tabs corretamente.
- [x] `settings.json` e criado no primeiro save/fechamento.
- [x] Ultimo repositorio e ultima aba persistem entre reinicios.

---

## 5) Checklist funcional da GUI

### 5.1 Barra global
- [x] Troca de repositorio funciona.
- [x] Troca de branch funciona.
- [x] Nova branch cria e troca para a nova branch.
- [x] Fetch funciona e atualiza contadores.
- [x] Pull/Push (chips) obedecem estado da branch/upstream.

### 5.2 Aba Repositorios
- [x] Workspace root carrega/salva.
- [x] Reescanear atualiza cards.
- [x] Favoritos aparecem primeiro.
- [x] Duplo clique no card abre no VS Code.
- [x] Menu de contexto do repo funciona (VS Code, pasta, copiar caminho, links GitHub).
- [x] Adicionar repositorio (clone) funciona.

### 5.3 Aba Commit
- [x] Lista de arquivos por pasta + `(todos)` funciona.
- [x] Selecao de arquivo/pasta/todos reflete estado parcial corretamente.
- [x] Diff principal carrega sem reordenar linhas ao marcar/desmarcar.
- [x] Stage/unstage por linha e bloco funciona.
- [prox] Janela de diff avancada abre e permite stage/unstage (retestar apos fix de item deletado no toggle).
- [x] Commit exige titulo.
- [x] Stash funciona.
- [prox] Undo commit (soft/mixed) funciona.
- [bug] commit funciona

### 5.4 Aba Historico
- [x] Lista de commits carrega.
- [bug] Busca por texto filtra.
- [x] Scroll progressivo carrega mais commits.
- [x] Selecionar commit atualiza metadados + arquivos + diff.
- [x] Menus de contexto (commit/arquivo) funcionam.
- [prox] Exportar commits funciona.

### 5.5 Aba Importar
- [x] Repo/branch de origem carregam.
- [x] Lista de commits carrega.
- [prox] Importar commits funciona.
- [prox] Em conflito, fluxo de resolucao abre corretamente.

### 5.6 Aba Comparar
- [x] Branch origem/destino carregam.
- [x] Botao trocar origem/destino funciona.
- [x] Commits/arquivos/diff atualizam conforme selecao.
- [x] Menus de contexto funcionam.
- [prox] merge, rebase e squash sem conflitos funcionam.
- [prox] merge, rebase e squash em conflitos funcionam, fluxo de resolucao abre corretamente.

### 5.7 Aba Configuracoes
- [x] Tema claro/escuro funciona.
- [x] Overrides de tema salvam e reaplicam.
- [bug] Perfil de atualizacao salva e reaplica.

---

## 6) Teste de update do pacote, será feito após a primeira rodada de ajustes

### 6.1 Update normal (versao maior)

Quando houver novo `.deb` (ex.: `0.2.1`):

```bash
cp dist/git-viewer_0.2.1_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.2.1_amd64.deb
apt policy git-viewer
```

Checklist:
- [prox] `apt` atualiza sem quebrar dependencias.
- [prox] Versao nova aparece em `apt policy`.
- [prox] App abre apos update.
- [prox] `settings.json` do usuario foi preservado.

### 6.2 Reinstalar mesma versao (se precisar)

```bash
cp dist/git-viewer_0.2.0_amd64.deb /tmp/
sudo apt install --reinstall /tmp/git-viewer_0.2.0_amd64.deb
```

---

## 7) Desinstalacao

Remover pacote:

```bash
sudo apt remove git-viewer -y
```

Remocao completa do pacote:

```bash
sudo apt purge git-viewer -y
sudo apt autoremove -y
```

Opcional (limpar configs do usuario):

```bash
rm -rf ~/.config/git_commits_viewer
```

Checklist:
- [x] `apt remove` remove o binario.
- [x] `which git-viewer` nao encontra comando.
- [x] `purge` conclui sem erro.
- [x] Config local removida quando solicitado.

---

## 8) Resultado final

- [prox] Rodada aprovada sem bloqueadores.
- [x] Existem bugs registrados (se sim, preencher tabela abaixo).

tivemos bugs e discordâncias em coisas descritas no fim do aruqivo como bugs, e que também foram marcados que impossibilitaram continuar legal os testes


Resumo:
- Total OK: 42
- Total BUG: 3
- Total Prox: 12
- Decisao:`MANTER EM AJUSTE`

---

## 9) Registro de bugs

| ID | Area | Severidade | Passos para reproduzir | Resultado esperado | Resultado atual | Evidencia | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 | Commit / Diff avancado | Alta | Na aba Commit, abrir diff avancado e marcar/desmarcar linhas/blocos rapidamente. | Stage/unstage sem excecao e sem crash da janela. | Excecao `RuntimeError: QTreeWidgetItem already deleted` durante toggle. | Traceback logo abaixo desta tabela. | Em reteste |
| BUG-002 | Historico / Busca | Media | Digitar no campo de busca da aba Historico. | Filtrar commits por texto em tempo real. | Filtro nao atualiza corretamente em alguns cenarios. | Marcado em 5.4 `Busca por texto filtra`. | Aberto |


bug 001 traceback ao usar seleção de stage na janela de diff avançado da aba commit

Gdk-Message: 17:43:22.050: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:22.051: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:22.051: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:22.051: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:22.052: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:22.052: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.853: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.854: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.854: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.854: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.855: Unable to load col-resize from the cursor theme
Gdk-Message: 17:43:42.855: Unable to load col-resize from the cursor theme
Traceback (most recent call last):
  File "viewer/pyside/controllers/commit_controller.py", line 3358, in <lambda>
    lambda item, column: _on_commit_diff_dialog_item_changed(window, dialog_state, item, column)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "viewer/pyside/controllers/commit_controller.py", line 3034, in _on_commit_diff_dialog_item_changed
    _apply_dialog_scope_after_toggle(
  File "viewer/pyside/controllers/commit_controller.py", line 2276, in _apply_dialog_scope_after_toggle
    _set_dialog_item_effective_scope(current_item, target_scope)
  File "viewer/pyside/controllers/commit_controller.py", line 2204, in _set_dialog_item_effective_scope
    item.setData(0, ROLE_DIALOG_EFFECTIVE_SCOPE, scope.strip())
RuntimeError: Internal C++ object (PySide6.QtWidgets.QTreeWidgetItem) already deleted.



A busca por textos faz distinção de maiuscula e minuscula, seria melhor não fazer isso, assim fica melhor a busca com mais resultados

bug 003

mesmo no perfil de atualização em tempo real, fiquei esperando e status da brnach atual escolhida, ou seja a aba commit nunca demostrou mudança , como se não fosse mais atualizada automaticamente segundo o tempo

bug 004

Quando abro uma branch nova não existe um botão de facil acesso para publica-la, seria bom ter um publish , botão pra publicar branch ao lado do fetch apenas para as que não tiverem publicadas

bug005

ao simpĺesmente subir um commit onde exclui um redme.md, algo comum, deu crash no aplicativo e precisou reiniciar 2 vezes pra voltar
