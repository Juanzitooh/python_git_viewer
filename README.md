# Git Commits Viewer

GUI Git em **PySide6** para visualizar commits, diffs, status e executar fluxos de commit/sync/importacao/comparacao.

![CI](https://img.shields.io/github/actions/workflow/status/Juanzitooh/python_git_viewer/ci.yml?branch=main&label=CI)
![Release](https://img.shields.io/github/v/release/Juanzitooh/python_git_viewer?label=Release)
![License](https://img.shields.io/github/license/Juanzitooh/python_git_viewer)

## Indice

- [Inicio rapido](#inicio-rapido)
- [Downloads (release v0.3.0)](#downloads-release-v030)
- [Screenshots](#screenshots)
- [Demo em video](#demo-em-video)
- [Suporte de plataforma](#suporte-de-plataforma)
- [Como executar (dev)](#como-executar-dev)
- [Build (PyInstaller)](#build-pyinstaller)
- [Pacotes Linux (.deb e AppImage)](#pacotes-linux-deb-e-appimage)
- [Limitacoes conhecidas](#limitacoes-conhecidas)
- [Contribuicao e seguranca](#contribuicao-e-seguranca)
- [Estrutura](#estrutura)
- [Notas](#notas)

## Inicio rapido

Clonar o projeto:

```bash
git clone https://github.com/Juanzitooh/python_git_viewer viewer
cd viewer
```

Rodar em modo dev (prepara ambiente automaticamente):

```bash
./setup.sh
```

Instalar no Linux Desktop (.deb + AppImage + abrir app):

```bash
./dist.sh
```

## Downloads (release v0.3.0)

- [Pagina de releases (estaveis)](https://github.com/Juanzitooh/python_git_viewer/releases)
- [Download `.deb` (Ubuntu/Debian)](https://github.com/Juanzitooh/python_git_viewer/releases/download/v0.3.0/git-viewer_0.3.0_amd64.deb)
- [Download `AppImage` (Linux portavel)](https://github.com/Juanzitooh/python_git_viewer/releases/download/v0.3.0/git-viewer-0.3.0-x86_64.AppImage)
- [Download `Linux PyInstaller` (binario)](https://github.com/Juanzitooh/python_git_viewer/releases/download/v0.3.0/git_viewer)

## Screenshots

![Screenshot 1](https://github.com/Juanzitooh/python_git_viewer/blob/main/assets/screenshot%201.png?raw=true)

![Screenshot 2](https://github.com/Juanzitooh/python_git_viewer/blob/main/assets/screenshot%202.png?raw=true)

## Demo em video

[![Demo no YouTube](https://img.youtube.com/vi/tVfZrxlHHQA/hqdefault.jpg)](https://youtu.be/tVfZrxlHHQA)

Link direto: `https://youtu.be/tVfZrxlHHQA`

## Suporte de plataforma

- Linux (Ubuntu 24.04+): suporte principal de runtime e empacotamento (`.deb`/AppImage).
- Windows: build de binario via PyInstaller no CI.
- macOS: sem pacote oficial no momento.

## Como executar (dev)

Forma recomendada (idempotente):

```bash
./setup.sh
```

Forma manual:

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

O `dist.sh` tambem:
- executa testes unitarios (`python3 -m unittest discover -s tests -p "test_*.py"`);
- gera checklists de release em `checklists/` sem sobrescrever arquivos ja existentes.

Importante:
- o `dist.sh` e voltado para build local em modo beta/iteracao;
- para versoes estaveis publicadas, use os artefatos em:
  - `https://github.com/Juanzitooh/python_git_viewer/releases`

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

## Limitacoes conhecidas

- Dependencias de runtime Qt/PySide6 podem variar por distro em ambiente headless.
- AppImage pode exigir `APPIMAGE_EXTRACT_AND_RUN=1` em sistemas sem `libfuse.so.2`.
- Integracao GitHub por SSH depende de chave cadastrada em `https://github.com/settings/ssh/new`.

Detalhes e mitigacoes:
- `docs/KNOWN_ISSUES.md`

## Contribuicao e seguranca

- Guia de contribuicao: `CONTRIBUTING.md`
- Politica de seguranca: `SECURITY.md`
- Issue tracker: `https://github.com/Juanzitooh/python_git_viewer/issues`

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
- Decisoes tecnicas (ADRs): `docs/DECISIONS.md`.
- Limitacoes conhecidas e observacoes operacionais: `docs/KNOWN_ISSUES.md`.
- Case tecnico do projeto: `docs/CASE_STUDY.md`.
- Trace detalhado de selecao/stage (UI + comandos Git + retorno): `docs/SELECTION_TRACE.md`.
