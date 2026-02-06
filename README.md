# Git Commits Viewer

Uma GUI simples em Tkinter para visualizar commits, diffs, status e executar ações básicas de Git.

## Como executar (dev)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --repo /caminho/do/repo --limit 100
```

Parâmetros:
- `--repo`: caminho do repositório (default: diretório atual).
- `--limit`: quantidade inicial de commits a carregar.

No Windows:

```bash
py -3 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
py -3 main.py --repo C:\\caminho\\do\\repo --limit 100
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
