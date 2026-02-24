# Contributing

Obrigado por contribuir com o Git Viewer.

## Como contribuir

1. Abra uma issue descrevendo bug, melhoria ou proposta.
2. Crie um branch a partir de `main`.
3. Faça mudancas pequenas e objetivas.
4. Rode testes antes de abrir PR.
5. Abra Pull Request com contexto e evidencias de teste.

## Ambiente de desenvolvimento

Setup recomendado:

```bash
./setup.sh --no-run
./setup.sh
```

Ou manual:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python3 main.py
```

## Padrao de commits

Este projeto usa commits atomicos com prefixo:

- `fix:` correcao de bug
- `feat:` nova funcionalidade
- `imp:` melhoria/refactor sem feature nova
- `docs:` documentacao
- `codex:` ajustes de agents/overrides e arquivos de suporte do agente

## Testes

Antes de abrir PR:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Se alterar fluxo de distribuicao Linux, rode tambem:

```bash
./dist.sh --deb-only --no-install --no-open --skip-tests
```

## Pull Request checklist

- [ ] Mudanca tem escopo claro e pequeno.
- [ ] Commits seguem prefixo e sao atomicos.
- [ ] Testes relevantes executados localmente.
- [ ] Documentacao atualizada (quando aplicavel).
- [ ] CHANGELOG/ROADMAP atualizados (quando aplicavel).

