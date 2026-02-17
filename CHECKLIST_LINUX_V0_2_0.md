# Checklist Linux - v0.2.0 (PySide6)

Objetivo:
- Validar instalacao, execucao, update e desinstalacao no Ubuntu 24.04.
- Validar fluxo funcional principal da GUI PySide6 apos instalar via `.deb`.

Como usar:
- Marque `[x]` quando OK.
- Marque `[BUG]` quando falhar e descreva no bloco final.
- Marque `[N/A]` quando nao se aplicar.

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
- [ ] Build do `.deb` conclui sem erro.
- [ ] Instalacao via `apt` conclui sem erro.
- [ ] `which git-viewer` retorna `/usr/bin/git-viewer`.
- [ ] `git-viewer --help` responde.

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
- [ ] App abre sem traceback.
- [ ] Janela abre e renderiza tabs corretamente.
- [ ] `settings.json` e criado no primeiro save/fechamento.
- [ ] Ultimo repositorio e ultima aba persistem entre reinicios.

---

## 5) Checklist funcional da GUI

### 5.1 Barra global
- [ ] Troca de repositorio funciona.
- [ ] Troca de branch funciona.
- [ ] Nova branch cria e troca para a nova branch.
- [ ] Fetch funciona e atualiza contadores.
- [ ] Pull/Push (chips) obedecem estado da branch/upstream.

### 5.2 Aba Repositorios
- [ ] Workspace root carrega/salva.
- [ ] Reescanear atualiza cards.
- [ ] Favoritos aparecem primeiro.
- [ ] Duplo clique no card abre no VS Code.
- [ ] Menu de contexto do repo funciona (VS Code, pasta, copiar caminho, links GitHub).
- [ ] Adicionar repositorio (clone) funciona.

### 5.3 Aba Commit
- [ ] Lista de arquivos por pasta + `(todos)` funciona.
- [ ] Selecao de arquivo/pasta/todos reflete estado parcial corretamente.
- [ ] Diff principal carrega sem reordenar linhas ao marcar/desmarcar.
- [ ] Stage/unstage por linha e bloco funciona.
- [ ] Janela de diff avancada abre e permite stage/unstage.
- [ ] Commit exige titulo.
- [ ] Stash funciona.
- [ ] Undo commit (soft/mixed) funciona.

### 5.4 Aba Historico
- [ ] Lista de commits carrega.
- [ ] Busca por texto filtra.
- [ ] Scroll progressivo carrega mais commits.
- [ ] Selecionar commit atualiza metadados + arquivos + diff.
- [ ] Menus de contexto (commit/arquivo) funcionam.

### 5.5 Aba Importar
- [ ] Repo/branch de origem carregam.
- [ ] Lista de commits carrega.
- [ ] Importar commits funciona.
- [ ] Em conflito, fluxo de resolucao abre corretamente.

### 5.6 Aba Comparar
- [ ] Branch origem/destino carregam.
- [ ] Botao trocar origem/destino funciona.
- [ ] Commits/arquivos/diff atualizam conforme selecao.
- [ ] Menus de contexto funcionam.

### 5.7 Aba Configuracoes
- [ ] Tema claro/escuro funciona.
- [ ] Overrides de tema salvam e reaplicam.
- [ ] Perfil de atualizacao salva e reaplica.

---

## 6) Teste de update do pacote

### 6.1 Update normal (versao maior)

Quando houver novo `.deb` (ex.: `0.2.1`):

```bash
cp dist/git-viewer_0.2.1_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.2.1_amd64.deb
apt policy git-viewer
```

Checklist:
- [ ] `apt` atualiza sem quebrar dependencias.
- [ ] Versao nova aparece em `apt policy`.
- [ ] App abre apos update.
- [ ] `settings.json` do usuario foi preservado.

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
- [ ] `apt remove` remove o binario.
- [ ] `which git-viewer` nao encontra comando.
- [ ] `purge` conclui sem erro.
- [ ] Config local removida quando solicitado.

---

## 8) Resultado final

- [ ] Rodada aprovada sem bloqueadores.
- [ ] Existem bugs registrados (se sim, preencher tabela abaixo).

Resumo:
- Total OK:
- Total BUG:
- Total N/A:
- Decisao: `APROVAR` / `MANTER EM AJUSTE`

---

## 9) Registro de bugs

| ID | Area | Severidade | Passos para reproduzir | Resultado esperado | Resultado atual | Evidencia | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 |  | Alta/Media/Baixa |  |  |  |  | Aberto |
