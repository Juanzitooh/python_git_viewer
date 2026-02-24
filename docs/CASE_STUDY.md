# Case Study - Git Viewer (PySide6)

## Contexto

O projeto nasceu para cobrir um gap pratico: um cliente Git desktop para Linux, integrado ao fluxo de GitHub e com foco em produtividade diaria.

Objetivo principal:

- centralizar fluxo de repositorio, commit, historico, importacao e comparacao em uma unica GUI.

## Problema

Os fluxos de Git no dia a dia ficavam distribuídos entre terminal, editor e navegador, com friccao para:

- revisar diff e stage por partes;
- comparar branches e executar acoes com seguranca;
- empacotar e testar distribuicao Linux de forma repetivel.

## Solucao implementada

Aplicacao em Python com frontend PySide6, organizada em camadas:

- `viewer/core`: regras de dominio e operacoes Git;
- `viewer/pyside`: apresentacao, eventos e controladores de UI.

Fluxos cobertos:

- repositorios (scan, favoritos, selecao, clone);
- commit (status, diff, stage/unstage, stash, undo);
- historico (filtro, detalhes, exportacao/reordenacao local);
- importar (cherry-pick assistido);
- comparar (merge/rebase/squash com feedback);
- configuracoes e tema.

## Decisoes tecnicas relevantes

1. Migrar frontend de Tkinter para PySide6 para melhorar modularizacao e UX.
2. Manter `core` desacoplado da UI para facilitar teste e manutencao.
3. Adotar fluxo de distribuicao Linux via `.deb` + AppImage com scripts versionados.

Detalhes formais: `docs/DECISIONS.md`.

## Qualidade e operacao

Praticas aplicadas:

- commits atomicos por tipo (`fix`, `feat`, `imp`, `docs`);
- checklists funcionais e de distribuicao por versao;
- pipeline CI com:
  - smoke de `setup.sh`,
  - testes core,
  - testes GUI com `xvfb`,
  - smoke de `dist.sh` sem install.

## Resultado atual

- release Linux com artefatos publicados;
- documentacao tecnica de arquitetura, limitacoes e operacao;
- fluxo de build e validacao repetivel para evolucao incremental.

## Trade-offs e limites

- runtime GUI depende de bibliotecas de sistema em ambientes headless;
- empacotamento principal focado em Linux desktop;
- updater automatico interno ainda fora do escopo atual.

Detalhes: `docs/KNOWN_ISSUES.md`.

## Proximos passos

- consolidar release estavel de referencia;
- ampliar documentacao visual (screenshots/GIFs);
- evoluir cobertura automatizada para cenarios de integracao mais pesados.

## Uso de IA no projeto

IA foi usada como acelerador de implementacao e refino.  
Requisitos, arquitetura, validacao de comportamento, estrategia de testes e decisoes de produto permaneceram sob responsabilidade do autor do projeto.

