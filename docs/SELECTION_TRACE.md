# Selection Trace (PySide6 Commit)

Este documento descreve o rastreamento completo do fluxo de selecao/stage da aba `Commit` (painel principal + janela de diff avancado).

## Objetivo

Registrar, em ordem cronologica:

- o evento visual (clique/toggle/check em arquivo, bloco e linha);
- a intencao da UI (stage/unstage, alvo, escopo e contexto);
- o comando Git enviado;
- a resposta do Git (sucesso/erro, stdout/stderr);
- o patch aplicado (resumo + preview reduzido).

Com isso, voce consegue auditar a trilha fim-a-fim: `UI -> pedido -> git -> retorno -> UI`.

## Como habilitar

### Habilitar no terminal

```bash
GIT_VIEWER_TRACE_SELECTION=1 python3 main.py
```

### Definir arquivo de saida (opcional)

```bash
GIT_VIEWER_TRACE_SELECTION=1 \
GIT_VIEWER_TRACE_FILE=/home/jp/Documentos/github/viewer/selection_trace.log \
python3 main.py
```

## Onde grava

- Arquivo padrao: `selection_trace.log` no diretorio atual.
- Formato: **JSON Lines** (1 linha JSON por evento).
- Controle por env vars:
  - `GIT_VIEWER_TRACE_SELECTION=1` ativa.
  - `GIT_VIEWER_TRACE_FILE=/caminho/arquivo.log` muda destino.

## Formato base do registro

Cada linha possui no minimo:

- `ts`: timestamp ISO com milissegundos.
- `event`: nome do evento.

Campos comuns adicionais:

- `repo_path`
- `selected_path`
- `selected_scope` (`staged`, `unstaged`, `untracked`, `mixed`)
- `selected_line`

## Fluxo rastreado

## 1) Selecao por arquivo/pasta/(todos)

Eventos UI:

- `ui.commit.files.item_changed`
- `ui.commit.files.selection.noop`
- `ui.commit.files.selection.apply.request`
- `ui.commit.files.selection.apply.done`
- `ui.commit.files.selection.apply.error`

Comandos Git associados:

- `git.unstage_paths.request` + `git.run.response` / `git.run.error`
- `git.stage_paths.request` + `git.run.response` / `git.run.error`

## 2) Diff principal da aba Commit

Eventos UI:

- `ui.commit.main.item_changed` (mudanca de check em item do diff)
- `ui.commit.main.marker_clicked` (clique direto no marcador)
- `ui.commit.main.stage_file.request` / `.error`
- `ui.commit.main.unstage_file.request` / `.error`
- `ui.commit.main.stage_hunk.request` / `.error`
- `ui.commit.main.unstage_hunk.request` / `.error`
- `ui.commit.main.stage_line.request` / `.error`
- `ui.commit.main.unstage_line.request` / `.error`
- `ui.commit.main.stage_change_ui.start`
- `ui.commit.main.stage_change_ui.done`

Comandos Git associados:

- `git.stage_paths.request` + `git.run.response` / `git.run.error`
- `git.unstage_paths.request` + `git.run.response` / `git.run.error`
- `git.apply_patch_to_index.request` + `git.apply_patch_to_index.response`

## 3) Janela de diff avancado

Eventos UI:

- `ui.commit.dialog.marker_clicked`
- `ui.commit.dialog.item_changed`
- `ui.commit.dialog.stage_change.request`
- `ui.commit.dialog.stage_change.done`
- `ui.commit.dialog.stage_change.error`

Comandos Git associados:

- `git.apply_patch_to_index.request` + `git.apply_patch_to_index.response`
- `git.apply_patch_to_worktree.request` + `git.apply_patch_to_worktree.response` (quando acao de revert no worktree)

## Campos importantes por evento

### Contexto de linha/bloco

- `line_type`: `added` ou `removed`
- `old_line`, `new_line`
- `line_content`
- `hunk_index`
- `hunk_header`

### Estado de check e toggle

- `checked_state`: estado Qt numerico (`Unchecked`, `PartiallyChecked`, `Checked`)
- `item_kind` / `row_kind`: `file`, `folder`, `all`, `hunk`, `added`, `removed`
- `item_scope` / `row_scope`: escopo no momento do clique

### Patch (quando aplicavel)

- `patch_hash`: hash curto para correlacao
- `patch_lines`: quantidade de linhas no patch enviado
- `patch_bytes`: tamanho em bytes
- `patch_preview`: preview truncado do patch

### Comando Git

- `command`: array completo (`git`, `-C`, repo, args...)
- `args`: argumentos sem prefixo binario
- `returncode` (quando chamada via `subprocess.run`)
- `stdout`
- `stderr`
- `ok` (quando via wrapper `git.run.*`)

## Relacao "pedido x resposta"

Para cada acao do usuario, a trilha esperada e:

1. evento UI `*.request` (pedido da interface);
2. evento `git.*.request` (comando enviado);
3. evento `git.*.response` ou `git.run.response`;
4. se erro: `*.error` + mensagem retornada.

Se houver desincronia visual, compare:

- evento UI inicial (`item_changed`/`marker_clicked`);
- pedido enviado (`stage_line`, `unstage_hunk`, etc.);
- resposta do Git;
- evento final `stage_change_ui.done`.

## Exemplos de leitura rapida

### Ver so eventos de erro

```bash
rg '\"event\": \".*error\"' selection_trace.log
```

### Ver so acoes de linha no diff principal

```bash
rg 'ui\\.commit\\.main\\.(stage_line|unstage_line|marker_clicked)' selection_trace.log
```

### Ver comando git + retorno

```bash
rg '\"event\": \"git\\.(run|apply_patch)' selection_trace.log
```

## Observacoes

- O trace e focado no fluxo de selecao/stage da aba Commit.
- Nao substitui `performance.log`; sao objetivos diferentes.
- O `patch_preview` e truncado para reduzir ruido no log.
