# Guia de Profissionalizacao (Portfolio + Open Source)

Objetivo: transformar o projeto em um case forte de portfolio, com uso real, release estável e documentação profissional.

## Regra de entrada (nao iniciar antes disso)

- [ ] Todos os bugs criticos do checklist corrigidos e validados.
- [ ] Fluxos principais funcionando sem regressao:
  - [ ] Repositorios
  - [ ] Commit (incluindo diff avancado e stage/unstage)
  - [ ] Historico
  - [ ] Importar
  - [ ] Comparar
  - [ ] Configuracoes
- [ ] `checklists/CHECKLIST_FUNCIONAL_0.3.0.md` e `checklists/CHECKLIST_DISTRIBUICAO_0.3.0.md` com rodada final concluida.
- [ ] Sem crash conhecido bloqueando uso (segfault, startup failure, etc).

---

## Fase 1 - Produto (apresentacao)

- [ ] Reescrever `README.md` com foco em produto:
  - [ ] Problema que resolve
  - [ ] Publico-alvo
  - [ ] Features principais
  - [ ] Instalacao rapida (`.deb`, AppImage, source)
  - [ ] GIFs/screenshot
  - [ ] Limitacoes conhecidas (resumo)
- [ ] Padronizar linguagem e terminologia (push/pull, stage/unstage, etc).
- [ ] Adicionar badges (build, release, license).

## Fase 2 - Engenharia (prova de dominio)

- [ ] Consolidar `docs/ARCHITECTURE.md` com fluxo ponta-a-ponta:
  - [ ] Repo -> status -> diff -> stage -> commit
  - [ ] Importar/Comparar/Conflitos
- [ ] Criar `docs/DECISIONS.md` (ADRs curtos):
  - [ ] Migracao Tkinter -> PySide6
  - [ ] Modelo de diff e selecao
  - [ ] Estrategia de packaging Linux
- [ ] Criar `docs/KNOWN_ISSUES.md` para problemas abertos e workaround.
- [ ] Garantir que testes automatizados cobrem fluxos de risco.

## Fase 3 - Open Source readiness

- [ ] Adicionar/validar:
  - [ ] `LICENSE`
  - [ ] `CONTRIBUTING.md`
  - [ ] `SECURITY.md`
  - [ ] Issue templates
- [ ] Definir politica de versao (semver simples).
- [ ] Definir politica de release (changelog + tag + artefatos).
- [ ] Centralizar novos bugs em `https://github.com/Juanzitooh/python_git_viewer/issues`.

## Fase 4 - Release publica

- [ ] Criar release estavel (`v0.x` ou `v1.0.0`).
- [ ] Publicar artefatos:
  - [ ] `.deb`
  - [ ] AppImage
  - [ ] checksums
- [ ] Validar upgrade e uninstall em Linux limpo.
- [ ] Publicar notas de release objetivas.

## Fase 5 - Portfolio

- [ ] Criar `docs/CASE_STUDY.md` com:
  - [ ] Contexto
  - [ ] Decisoes
  - [ ] Problemas resolvidos
  - [ ] Resultado final
  - [ ] Proximos passos
- [ ] Incluir secao curta de uso de IA:
  - [ ] IA como acelerador de implementacao
  - [ ] Requisitos, arquitetura, validacao e qualidade sob sua responsabilidade

---

## Definition of Done (DoD) para considerar “pronto para portfolio”

- [ ] App instalavel e utilizavel sem passos manuais complexos.
- [ ] Fluxos principais estaveis em teste real.
- [ ] Documentacao principal clara e atualizada.
- [ ] Release versionada com artefatos e changelog.
- [ ] Evidencia de manutencao (issues, roadmap, correcoes recentes).

---

## Ordem recomendada de execucao

1. Fechar bugs e checklist Linux.
2. Fazer hardening tecnico (Fase 2).
3. Polir README e docs de produto (Fase 1).
4. Preparar governanca open source (Fase 3).
5. Publicar release e case study (Fases 4 e 5).
