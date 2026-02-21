# Checklist Distribuicao Linux (.deb/AppImage) - Git Viewer v{{VERSION}}

Objetivo:
- Validar empacotamento, instalacao, update e desinstalacao em Ubuntu 24.04.
- Confirmar que build distribuivel se comporta igual ao dev nos fluxos essenciais.

Como usar:
- Marque `[x]` quando OK.
- Marque `[bug]` quando falhar e registre no bloco de bugs deste arquivo.
- Marque `[prox]` quando ficar para rodada seguinte.

---

## 1) Dados da rodada

- Data: {{DATE}}
- Testador: {{TESTER}}
- Branch/commit: {{BRANCH_COMMIT}}
- Distro/kernel: {{DISTRO_KERNEL}}
- Versao alvo: {{VERSION}}
- Pacote alvo: `dist/git-viewer_{{VERSION}}_amd64.deb`

## 2) Build de distribuicao

Fluxo rapido (recomendado):

```bash
./dist.sh --version {{VERSION}}
```

Checklist:
- [ ] `dist.sh` conclui sem erro.
- [ ] `.deb` foi gerado em `dist/`.
- [ ] AppImage foi gerado em `dist/` (quando aplicavel).
- [ ] Instalacao/reinstalacao do `.deb` foi executada.
- [ ] App abriu ao final do script.

Fluxo manual (fallback/debug):

```bash
python3 scripts/build_linux_packages.py --version {{VERSION}} --build-binary --deb-only
python3 scripts/build_linux_packages.py --version {{VERSION}} --appimage-only
```

Checklist:
- [ ] Build manual `.deb` conclui sem erro.
- [ ] Build manual AppImage conclui sem erro (quando aplicavel).

---

## 3) Instalacao `.deb`

```bash
cp dist/git-viewer_{{VERSION}}_amd64.deb /tmp/
sudo apt install /tmp/git-viewer_{{VERSION}}_amd64.deb
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

## 4) Smoke funcional no pacote instalado

- [ ] Troca de repositorio/branch.
- [ ] Commit diff carrega.
- [ ] Historico carrega.
- [ ] Importar/Comparar abrem sem erro.
- [ ] Configuracoes salvam e reaplicam.

---

## 5) Update de versao

Checklist:
- [ ] `apt` atualiza sem quebrar dependencias.
- [ ] Nova versao aparece no `apt policy`.
- [ ] App abre apos update.
- [ ] `settings.json` do usuario foi preservado.

---

## 6) Reinstall da mesma versao

Checklist:
- [ ] Reinstall conclui sem erro.
- [ ] App continua abrindo.

---

## 7) Desinstalacao

```bash
sudo apt remove git-viewer -y
sudo apt purge git-viewer -y
sudo apt autoremove -y
```

Checklist:
- [ ] `apt remove` remove binario.
- [ ] `which git-viewer` nao encontra comando.
- [ ] `purge` conclui sem erro.

---

## 8) Bugs de distribuicao

Registre aqui apenas bugs que aparecem no pacote distribuivel.

| ID | Area | Severidade | Status atual |
|---|---|---|---|

---

## 9) Resultado final da rodada de distribuicao

- [ ] Rodada de distribuicao aprovada sem bloqueadores.
- [ ] Bugs de distribuicao atualizados.
- [ ] Pronto para release publica.
