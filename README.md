# Git Commits Viewer

Uma GUI simples em Tkinter para visualizar commits, diffs, status e executar ações básicas de Git.

## Como executar

```bash
python3 tools/viewer/main.py --repo /caminho/do/repo --limit 100
```

Parâmetros:
- `--repo`: caminho do repositório (default: diretório atual).
- `--limit`: quantidade inicial de commits a carregar.

## Estrutura

```text
tools/viewer/
  app.py        # aplicação principal (GUI e lógica)
  main.py       # entrypoint
  README.md
  AGENTS.global.md
```

## Notas

- A listagem de commits usa carregamento incremental.
- Diffs grandes só são carregados quando solicitado.
- O estado do Git é atualizado automaticamente em intervalo configurável.
