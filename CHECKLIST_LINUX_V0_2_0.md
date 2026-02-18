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
ls -lh dist/git-viewer_0.2.1_amd64.deb
```

Instalar (evita warning de permissao do `_apt`):

```bash
cp dist/git-viewer_0.2.1_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.2.1_amd64.deb
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
- [x] Publish aparece para branch local sem upstream e publica com `-u origin HEAD`.

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
- [x] Undo commit (soft/mixed) funciona.
- [prox] Commit funciona (incluindo cenarios com arquivo deletado).

### 5.4 Aba Historico
- [x] Lista de commits carrega.
- [x] Busca por texto filtra (case-insensitive).
- [x] Scroll progressivo carrega mais commits.
- [x] Selecionar commit atualiza metadados + arquivos + diff.
- [x] Menus de contexto (commit/arquivo) funcionam.
- [x] Exportar commits funciona.

### 5.5 Aba Importar
- [x] Repo/branch de origem carregam.
- [x] Lista de commits carrega.
- [x] Importar commits funciona.
- [prox] Conflito: fluxo de resolucao abre corretamente (sem popup de erro redundante).

### 5.6 Aba Comparar
- [x] Branch origem/destino carregam.
- [x] Botao trocar origem/destino funciona.
- [x] Commits/arquivos/diff atualizam conforme selecao.
- [x] Menus de contexto funcionam.
- [prox] Merge, rebase e squash sem conflitos funcionam.
- [prox] Merge, rebase e squash em conflitos funcionam com abertura da tela de conflitos.

### 5.7 Aba Configuracoes
- [x] Tema claro/escuro funciona.
- [x] Overrides de tema salvam e reaplicam.
- [prox] Perfil de atualizacao salva e reaplica.

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
- [x] `apt` atualiza sem quebrar dependencias.
- [x] Versao nova aparece em `apt policy`.
- [bug] App abre apos update.
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

- [bug] Rodada aprovada sem bloqueadores.
- [x] Existem bugs registrados (se sim, preencher tabela abaixo).

tivemos bugs e discordâncias em coisas descritas no fim do aruqivo como bugs, e que também foram marcados que impossibilitaram continuar legal os testes


Resumo:
- Total OK: 47
- Total BUG: 1
- Total Prox: 10
- Decisao:`MANTER EM AJUSTE`

---

## 9) Registro de bugs

| ID | Area | Severidade | Passos para reproduzir | Resultado esperado | Resultado atual | Evidencia | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 | Commit / Diff avancado | Alta | Na aba Commit, abrir diff avancado e marcar/desmarcar linhas/blocos rapidamente. | Stage/unstage sem excecao e sem crash da janela. | Excecao `RuntimeError: QTreeWidgetItem already deleted` durante toggle. | Traceback da rodada anterior. | Em reteste (prox) |
| BUG-002 | Historico / Busca | Media | Digitar no campo de busca da aba Historico. | Filtrar commits por texto sem diferenciar caixa. | Filtro falhava com case-sensitive. | Teste manual anterior. | Em reteste (prox) |
| BUG-003 | Auto update / Commit | Media | Perfil Tempo real + aba Commit aberta. | Status/worktree atualiza automaticamente. | Aba Commit nao refletia mudancas sem acao manual. | Relato do checklist. | Em reteste (prox) |
| BUG-004 | Barra global / Branch | Media | Criar branch local sem upstream. | Exibir acao direta para publicar branch. | Nao havia botao para publish rapido. | Relato do checklist. | Em reteste (prox) |
| BUG-005 | Commit / Estabilidade | Alta | Commit contendo remocao de arquivo (ex.: `README.md`). | Commit conclui e UI atualiza sem crash. | App encerrava durante/apos commit com remocao. | Relato manual. | Em reteste (prox) |
| BUG-006 | Importar / Conflitos | Alta | Importar commit que gera conflito. | Abrir tela de conflitos direto, sem popup redundante de erro, e permitir resolver arquivos. | Exibia popup de erro do git antes da tela de conflitos e faltavam acoes por arquivo. | Relato manual + screenshot. | Corrigido, validar (prox) |
| BUG-007 | Commit / Auto-stage | Alta | Editar arquivo no VS Code com aba Commit aberta. | Novas mudancas aparecem e entram no fluxo auto-stage sem quebrar selecao. | Auto-stage global nao cobria edicoes incrementais apos carga inicial e podia desalinhar com selecao manual. | Relato manual recorrente. | Corrigido, validar (prox) |
| BUG-008 | Commit / Sincronia diff | Alta | Fazer multiplas edicoes incrementais no mesmo arquivo. | Diff manter secoes incrementais coerentes com estado atual. | Com auto-stage incremental ausente, acoes manuais no arquivo podiam convergir para estado final inesperado no diff. | Relato manual recorrente. | Corrigido, validar (prox) |
| BUG-009 | Commit / Menu arquivo | Media | Clique direito em arquivo modificado (aba Commit). | Opcao para reverter alteracoes do arquivo individualmente. | Opcao nao existia. | Relato manual. | Corrigido, validar (prox) |
| BUG-010 | Repositorios / Menu contexto | Media | Clique direito em card/combo de repositorio. | Acao de favoritar/desfavoritar e abrir terminal no repo. | Acoes nao existiam. | Relato manual. | Corrigido, validar (prox) |
| BUG-011 | Comparar / Squash conflito | Alta | Executar squash com conflito. | Abrir tela de conflitos corretamente para squash. | Fluxo podia nao abrir dialogo por deteccao incompleta da operacao. | Relato manual. | Corrigido, validar (prox) |
| BUG-012 | Tela de conflitos | Media | Abrir tela de conflitos e resolver parcialmente. | Mostrar contagem pendente/resolvido, cor por estado e acoes por arquivo; atualizar em tempo real. | Tela anterior era basica e sem opcoes de resolucao guiada. | Relato manual. | Corrigido, validar (prox) |
| BUG-013 | Fluxo conflito UX | Media | Gerar conflito em merge/rebase/squash/importar/exportar. | Ir direto para tela de conflitos (sem popup extra de erro esperado). | Exibia popup de erro antes do dialogo de conflitos. | Relato manual. | Corrigido, validar (prox) |
| BUG-014 | Configuracoes / Perfil de atualizacao | Media | Alterar perfil em Configuracoes e validar timers ativos/apos salvar. | Perfil aplicado na hora e persistido apos salvar/reabrir. | Aplicacao imediata do perfil nao estava clara e revalidacao de persistencia ficou pendente. | Relato no checklist 5.7. | Corrigido, validar (prox) |
| BUG-015 | Pacote Linux (.deb) / Inicializacao Qt | Alta | Atualizar pacote para nova versao e executar `git-viewer`. | Aplicativo inicia normalmente apos update. | Falha no boot com erro de plugin Qt (`wayland`/`xcb`) e aborta antes da UI. | Log do terminal no checklist (rodada v0.2.1). | Corrigido, validar (prox) |
