# Git Commits Viewer

GUI Git em **PySide6** para visualizar commits, diffs, status e executar fluxos de commit/sync/importacao/comparacao.

## Como executar (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --repo /caminho/do/repo
```

Parâmetros:
- `--repo`: caminho do repositório (default: diretório atual).
- `GIT_VIEWER_TRACE_SELECTION=1`: habilita trace detalhado do fluxo de selecao/stage na aba Commit, gravando em `selection_trace.log` (ou caminho definido em `GIT_VIEWER_TRACE_FILE`).

No Windows:

```bash
py -3 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
py -3 main.py --repo C:\\caminho\\do\\repo
```

## Build (PyInstaller)

O script `compile.py` cria `.venv`, instala dependências (incluindo PyInstaller) e gera o executável.

```bash
python3 compile.py
```

No Windows:

```bash
py -3 compile.py
```

Saída:
- Linux/macOS: `dist/git_viewer`
- Windows: `dist\\git_viewer.exe`

Opcional: `python3 compile.py --console` para manter a janela de console (útil para debug).
Opcional: `python3 compile.py --icon assets/icon.ico --version-file assets/version_info.txt` para personalizar o executável (Windows usa metadata do version file).

## Pacotes Linux (.deb e AppImage)

Script de empacotamento Linux:

```bash
python3 scripts/build_linux_packages.py --build-binary
```

Atalho completo (build + install/reinstall + abrir app):

```bash
./dist.sh
```

Exemplo para gerar versão `0.3.0`:

```bash
./dist.sh --version 0.3.0
```

Somente `.deb`:

```bash
python3 scripts/build_linux_packages.py --build-binary --deb-only
```

Somente AppImage:

```bash
python3 scripts/build_linux_packages.py --build-binary --appimage-only
```

Saídas padrão:
- `dist/git-viewer_<versao>_amd64.deb`
- `dist/git-viewer-<versao>-x86_64.AppImage`

Observações:
- Em sistemas sem `libfuse.so.2`, rode AppImage com `APPIMAGE_EXTRACT_AND_RUN=1`.
- Checklist de validacao Linux: `docs/LINUX_PACKAGING_VALIDATION.md`.
- Versao padrao do pacote vem de `assets/version_info.txt` (`ProductVersion`).

## Estrutura

```text
.
  compile.py           # build via PyInstaller
  main.py              # entrypoint oficial (PySide6)
  requirements.txt     # dependências de runtime
  requirements-dev.txt # dependências de build
  README.md
  viewer/              # pacote principal
    core/              # git, models e utilitários
    pyside/            # interface PySide6
```

## Notas

- A listagem de commits usa carregamento incremental.
- Diffs grandes só são carregados quando solicitado.
- O estado do Git é atualizado automaticamente em intervalo configurável.
- As abas `Repositorios`, `Commit`, `Historico`, `Importar`, `Comparar` e `Configuracoes` rodam no frontend PySide6.
- Contrato de arquitetura (core Python + UI desacoplada): `docs/ARCHITECTURE.md`.
- Trace detalhado de selecao/stage (UI + comandos Git + retorno): `docs/SELECTION_TRACE.md`.
