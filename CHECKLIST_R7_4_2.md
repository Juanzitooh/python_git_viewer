# Checklist Manual - R7.4.2 (PySide6)

Objetivo:
- Validar regressao funcional e usabilidade final do shell PySide6 antes de iniciar distribuicao Linux (R7.5).

Como usar:
- Marque cada item com `[x]` quando OK.
- Se falhar, marque `[BUG]` e registre no bloco "Registro de Bugs" no final.
- Se item nao se aplica no seu ambiente, marque `[N/A]`.

## 1. Dados da rodada

- Data:
- Testador:
- Branch:
- Commit (hash curto):
- OS:
- Python usado:
- Execucao: `python3 main_pyside6.py` ou `.venv/bin/python main_pyside6.py`

## 2. Pre-check rapido

- [ ] App abre sem traceback no terminal.
- [ ] Janela abre maximizada.
- [ ] Tabs aparecem na ordem correta: Repositorios, Commit, Historico, Importar, Comparar, Configuracoes.
- [ ] Status bar mostra estado sem travar UI.

## 3. Barra global (topo)

- [ ] Combobox de repositorio carrega repos validos.
- [ ] Trocar repo atualiza branch/status sem erro.
- [ ] Combobox de branch faz checkout sem erro.
- [ ] Botao Nova branch cria branch e troca para ela.
- [ ] Fetch executa e atualiza ahead/behind.
- [ ] Pull habilita/desabilita corretamente conforme behind.
- [ ] Push habilita/desabilita corretamente conforme ahead.
- [ ] Menus de contexto de repositorio funcionam:
  - [ ] Abrir no VS Code
  - [ ] Abrir na pasta
  - [ ] Copiar caminho
  - [ ] GitHub: abrir repo/branch/commits/issues/actions/releases
  - [ ] GitHub: copiar URL repo/branch

## 4. Aba Repositorios

- [ ] Campo raiz workspace aceita edicao e persiste.
- [ ] Botao Pasta seleciona raiz corretamente.
- [ ] Reescanear atualiza lista sem travar.
- [ ] Lista mostra colunas (repo, caminho, branch, ahead, behind, status).
- [ ] Clique simples seleciona repo ativo.
- [ ] Duplo clique seleciona repo sem erro.
- [ ] Menu de contexto na lista funciona (mesmas acoes da barra global).
- [ ] Adicionar repositorio abre dialogo de clone.
- [ ] Clone URL/SSH com pasta opcional funciona.
- [ ] Progresso de clone aparece.
- [ ] Ao concluir clone: re-scan acontece e repo novo aparece selecionavel.

## 5. Aba Commit

- [ ] Lista de arquivos modificados carrega.
- [ ] Marcadores de status aparecem (`[x]`, `[~]`, `[ ]`).
- [ ] Selecao por checkbox funciona.
- [ ] Selecionar tudo funciona.
- [ ] Limpar selecao funciona.
- [ ] Diff do arquivo selecionado carrega.
- [ ] Diff por palavra alterna visualizacao.
- [ ] Stage selecionado (arquivo) funciona.
- [ ] Unstage selecionado (arquivo) funciona.
- [ ] Stage bloco funciona.
- [ ] Unstage bloco funciona.
- [ ] Stage linha funciona.
- [ ] Unstage linha funciona.
- [ ] Commit exige titulo (obrigatorio).
- [ ] Commit com titulo e descricao opcional funciona.
- [ ] Stash funciona e atualiza tela.
- [ ] Undo commit (soft/mixed/hard) funciona.
- [ ] Botao Abrir PR so habilita com worktree limpo.
- [ ] Abrir PR abre dialogo base/head e abre URL correta no navegador.

## 6. Aba Historico

- [ ] Lista de commits carrega.
- [ ] Busca por texto filtra resultados.
- [ ] Limite de commits funciona (50/100/200).
- [ ] Diff por palavra atualiza patch.
- [ ] Selecionar commit atualiza metadados.
- [ ] Selecionar arquivo atualiza patch do arquivo.
- [ ] Marcadores `[L]` e `[L+O]` aparecem conforme estado.
- [ ] Tooltip/infos do commit estao coerentes.
- [ ] Menu de contexto de commit funciona:
  - [ ] Copiar hash
  - [ ] Copiar patch completo
  - [ ] Copiar lista de arquivos
  - [ ] Abrir commit no GitHub
  - [ ] Copiar URL do commit
- [ ] Menu de contexto de arquivo funciona:
  - [ ] Abrir no VS Code
  - [ ] Abrir na pasta
  - [ ] Copiar caminho relativo
  - [ ] Copiar patch do arquivo
  - [ ] Copiar patch completo
- [ ] Botao Exportar funciona (copiar hashes + confirmar exportacao).
- [ ] Exportar trata conflito abrindo dialogo de conflitos.
- [ ] Botao Reordenar locais aparece so quando ha >=2 commits locais com upstream.
- [ ] Reordenar locais funciona com backup e atualiza historico.

## 7. Aba Importar

- [ ] Combobox de repo origem carrega lista do scan.
- [ ] Usar atual funciona.
- [ ] Combobox de branch origem carrega.
- [ ] Lista de commits da origem carrega.
- [ ] Botao Copiar hashes funciona.
- [ ] Importar selecionados funciona.
- [ ] Em conflito, dialogo de conflitos abre corretamente.
- [ ] Menu de contexto de commit funciona (GitHub/hash/lista/patch).

## 8. Aba Comparar

- [ ] Origem/destino carregam branches validas.
- [ ] Botao Trocar inverte origem/destino.
- [ ] Atualizar recarrega comparacao.
- [ ] Diff por palavra funciona no patch.
- [ ] Lista de commits carrega.
- [ ] Lista de arquivos carrega.
- [ ] Selecionar arquivo mostra patch.
- [ ] Menu de contexto de commit funciona.
- [ ] Menu de contexto de arquivo funciona.
- [ ] Acao Merge funciona.
- [ ] Acao Rebase funciona.
- [ ] Acao Squash exige mensagem.
- [ ] Em conflito, dialogo de conflitos abre corretamente.
- [ ] Botao Ir para Commit funciona quando worktree esta sujo.

## 9. Aba Configuracoes

- [ ] Troca de tema Claro/Escuro funciona.
- [ ] Limite padrao de commits salva e aplica.
- [ ] Raiz do workspace salva e aplica.
- [ ] Reiniciar app preserva configuracoes salvas.

## 10. Dialogo de conflitos (geral)

- [ ] Lista arquivos em conflito.
- [ ] Abrir no VS Code funciona.
- [ ] Atualizar recarrega estado.
- [ ] Continuar funciona quando conflito resolvido.
- [ ] Abortar funciona.

## 11. Persistencia entre reinicios

- [ ] Ultimo repositorio ativo e restaurado.
- [ ] Ultima aba ativa e restaurada.
- [ ] Preferencias mantidas em `settings.json`.

## 12. Resultado final da rodada

- [ ] Rodada aprovada sem bloqueios.
- [ ] Existem bugs registrados (se sim, listar abaixo).

Resumo rapido:
- Total itens OK:
- Total itens BUG:
- Total itens N/A:
- Decisao: `APROVAR R7.4.2` / `MANTER EM AJUSTE`

---

## Registro de Bugs

Use 1 linha por bug.

| ID | Area | Severidade (Alta/Media/Baixa) | Passos para reproduzir | Resultado esperado | Resultado atual | Evidencia (print/log) | Status |
|---|---|---|---|---|---|---|---|
| BUG-001 |  |  |  |  |  |  | Aberto |

