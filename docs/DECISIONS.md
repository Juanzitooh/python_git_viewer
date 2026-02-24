# Decisions (ADRs curtos)

Este documento registra decisoes tecnicas centrais do projeto.

## ADR-001 - Migracao de Tkinter para PySide6

- Data: 2026-02-21
- Status: aceito

### Contexto

A interface Tkinter atendia o fluxo inicial, mas limitava modularizacao, consistencia visual e evolucao de UX para um padrao "desktop grade".

### Decisao

Adotar PySide6 como frontend oficial, mantendo o entrypoint em `main.py` e removendo dependencia operacional do frontend antigo.

### Consequencias

- Positivas:
  - melhor controle de layout, tema e estados de UI;
  - base mais preparada para manutencao e crescimento.
- Trade-offs:
  - maior dependencia de runtime Qt/PySide6;
  - necessidade de ajustar CI para ambiente headless com GUI.

---

## ADR-002 - Core de dominio desacoplado da UI

- Data: 2026-02-21
- Status: aceito

### Contexto

Fluxos Git e regras de negocio ficaram acoplados ao frontend em fases iniciais, dificultando testes e manutencao.

### Decisao

Manter `viewer/core` como camada Python pura (sem import de toolkit grafico), com `viewer/pyside` atuando como camada de apresentacao/controladores.

### Consequencias

- Positivas:
  - testes de dominio mais simples e estaveis;
  - menor risco de regressao em mudancas de UI.
- Trade-offs:
  - aumento de disciplina arquitetural para evitar vazamento de responsabilidade entre camadas.

---

## ADR-003 - Distribuicao Linux via .deb/AppImage + scripts locais

- Data: 2026-02-21
- Status: aceito

### Contexto

Projeto precisa ser instalavel no Linux desktop com baixo atrito, mantendo fluxo rapido de iteracao local.

### Decisao

Usar:

- `setup.sh` para ambiente dev idempotente;
- `dist.sh` para fluxo local de build/test/package/install;
- `scripts/build_linux_packages.py` para geracao de `.deb` e AppImage;
- releases do GitHub para distribuicao estavel.

### Consequencias

- Positivas:
  - caminho claro para dev e para usuario final;
  - processo repetivel para empacotamento e validacao.
- Trade-offs:
  - variacao de dependencias entre distros;
  - necessidade de manter checklists e smoke tests de distribuicao.

