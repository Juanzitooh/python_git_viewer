# Vision

## Produto

Git Commits Viewer e uma ferramenta desktop para operacao Git diaria com foco em produtividade, seguranca de fluxo e usabilidade.

## Objetivos

- Reduzir friccao em fluxos comuns de Git (historico, commit, comparar, importar, conflitos).
- Manter o dominio Git desacoplado da UI para facilitar evolucao e testes.
- Entregar distribuicao Linux simples (`.deb` e AppImage) sem setup manual complexo.

## Principios

- Core de negocio em Python puro (`viewer/core`).
- Interface PySide6 como camada de apresentacao (`viewer/pyside`).
- Evolucao incremental com backlog rastreavel e changelog atualizado.
- Priorizar estabilidade e previsibilidade antes de novos recursos de UX.
