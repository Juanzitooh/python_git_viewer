# Checklist Distribuicao Linux (.deb/AppImage) - Git Viewer

Objetivo:
- Validar empacotamento, instalacao, update e desinstalacao em Ubuntu 24.04.
- Confirmar que build distribuivel se comporta igual ao dev nos fluxos essenciais.
- Priorizar o fluxo automatico (`dist.sh`) e usar o fluxo manual apenas como fallback/debug.

Pre-condicao:
- Execute este checklist somente apos aprovacao do `CHECKLIST_FUNCIONAL_DEV.md`.
- Tenha `sudo` disponivel para instalacao/reinstalacao do `.deb`.

Como usar:
- Marque `[x]` quando OK.
- Marque `[bug]` quando falhar e registre no bloco de bugs deste arquivo.
- Marque `[prox]` quando ficar para rodada seguinte.

---

## 1) Dados da rodada

- Data: 21/02/2026
- Testador: Juan Pablo
- Branch/commit: feature/r7-pyside6-linux
- Distro/kernel: linux desktop 24.04 lts
- Versao alvo: 0.3.x
- Pacote alvo: `dist/git-viewer_0.3.0_amd64.deb`

## 2) Caminhos importantes

- Binario CLI instalado: `/usr/bin/git-viewer`
- Atalho desktop: `/usr/share/applications/git-viewer.desktop`
- Settings (Linux):
  - padrao: `~/.config/git_commits_viewer/settings.json`
  - com XDG: `$XDG_CONFIG_HOME/git_commits_viewer/settings.json`

---

## 3) Build de distribuicao

Fluxo rapido (recomendado):

```bash
./dist.sh --version 0.3.0
```

Isso faz:
- build `.deb`
- build AppImage (quando possivel)
- install/reinstall do `.deb`
- abre `git-viewer`

Onde mudar versao base do projeto:
- `assets/version_info.txt`:
  - `filevers=(X, Y, Z, 0)`
  - `prodvers=(X, Y, Z, 0)`
  - `StringStruct('FileVersion', 'X.Y.Z')`
  - `StringStruct('ProductVersion', 'X.Y.Z')`

Checklist (fluxo automatico):
- [x] `dist.sh` conclui sem erro.
- [x] `.deb` foi gerado em `dist/`.
- [x] AppImage foi gerado em `dist/` (quando aplicavel).
- [x] Instalacao/reinstalacao do `.deb` foi executada.
- [x] App abriu ao final do script.

Fluxo manual (fallback/debug):

```bash
python3 scripts/build_linux_packages.py --build-binary --deb-only
ls -lh dist/git-viewer_0.3.0_amd64.deb
```

Opcional AppImage:

```bash
python3 scripts/build_linux_packages.py --build-binary --appimage-only
ls -lh dist/git-viewer-0.3.0-x86_64.AppImage
```

Checklist:
- [ ] Build manual `.deb` conclui sem erro.
- [ ] Build manual AppImage conclui sem erro (quando aplicavel).

---

## 4) Instalacao `.deb`

Se voce usou `dist.sh`, este passo ja foi executado automaticamente.

```bash
cp dist/git-viewer_0.3.0_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.3.0_amd64.deb
```

Validar:

```bash
apt policy git-viewer
which git-viewer
git-viewer --help
```

Checklist:
- [ ] Instalacao via `apt` conclui sem erro.
- [ ] `which git-viewer` retorna `/usr/bin/git-viewer`.
- [ ] `git-viewer --help` responde.
- [ ] App abre via terminal (`git-viewer`).
- [ ] App abre via menu desktop (`gtk-launch git-viewer`).

---

## 5) Smoke funcional no pacote instalado

Teste rapido no app instalado (nao repetir checklist funcional completo):
- [x] Troca de repositorio/branch.
- [x] Commit diff carrega.
- [x] Historico carrega.
- [x] Importar/Comparar abrem sem erro.
- [x] Configuracoes salvam e reaplicam.

---

## 6) Update de versao

Fluxo recomendado:

```bash
./dist.sh --version 0.3.0
```

Fluxo manual:

```bash
cp dist/git-viewer_0.3.0_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_0.3.0_amd64.deb
apt policy git-viewer
git-viewer
```

Checklist:
- [ ] `apt` atualiza sem quebrar dependencias.
- [ ] Nova versao aparece no `apt policy`.
- [ ] App abre apos update.
- [ ] `settings.json` do usuario foi preservado.

---

## 7) Reinstall da mesma versao

Fluxo recomendado:

```bash
./dist.sh --version 0.3.0
```

Fluxo manual:

```bash
sudo apt install --reinstall /tmp/git-viewer_0.3.0_amd64.deb
```

Checklist:
- [ ] Reinstall conclui sem erro.
- [ ] App continua abrindo.

---

## 8) Desinstalacao

```bash
sudo apt remove git-viewer -y
sudo apt purge git-viewer -y
sudo apt autoremove -y
```

Opcional limpar config local:

```bash
rm -rf ~/.config/git_commits_viewer
```

Checklist:
- [ ] `apt remove` remove binario.
- [ ] `which git-viewer` nao encontra comando.
- [ ] `purge` conclui sem erro.
- [ ] Config local removida quando solicitado.

---

## 9) Bugs de distribuicao

Use esta secao para bugs que existem somente no pacote distribuivel.

| ID | Area | Severidade | Status atual |
|---|---|---|---|
| BUG-015 | Pacote Linux (.deb) / Inicializacao Qt | Alta | Corrigido, validar (prox) |

---

## 10) Resultado final da rodada de distribuicao

- [ ] Rodada de distribuicao aprovada sem bloqueadores.
- [ ] Bugs de distribuicao atualizados.
- [ ] Pronto para release publica.
