# Git Commits Viewer

Uma GUI simples em Tkinter para visualizar commits, diffs, status e executar ações básicas de Git.

## Como executar (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --repo /caminho/do/repo --limit 100
# Shell inicial PySide6 (R7.2):
python3 main_pyside6.py --repo /caminho/do/repo
```

Parâmetros:
- `--repo`: caminho do repositório (default: diretório atual).
- `--limit`: quantidade inicial de commits a carregar.
- `--perf`: habilita indicador de performance na UI e gravações em `performance.log` na raiz.

No Windows:

```bash
py -3 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
py -3 main.py --repo C:\\caminho\\do\\repo --limit 100
# Shell inicial PySide6 (R7.2):
py -3 main_pyside6.py --repo C:\\caminho\\do\\repo
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

## Estrutura

```text
.
  compile.py           # build via PyInstaller
  main.py              # entrypoint
  main_pyside6.py      # entrypoint shell PySide6
  requirements.txt     # dependências de runtime
  requirements-dev.txt # dependências de build
  README.md
  viewer/              # pacote principal
    app.py             # aplicação principal (GUI e lógica)
    core/              # git, models e utilitários
    ui/                # mixins de UI por aba
```

## Notas

- A listagem de commits usa carregamento incremental.
- Diffs grandes só são carregados quando solicitado.
- O estado do Git é atualizado automaticamente em intervalo configurável.
- `main_pyside6.py` é o shell inicial da migração; a UI completa segue em `main.py` (Tkinter) até concluir o R7.
- No estado atual do PySide6, as abas `Repositorios`, `Commit`, `Historico` e `Comparar` já têm fluxo funcional inicial; as demais abas seguem em migração.
