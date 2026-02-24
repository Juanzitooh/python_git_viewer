# Known Issues / Limitacoes Conhecidas

Este arquivo documenta limites atuais e observacoes operacionais.

## Estado atual

- Nao ha bugs bloqueadores abertos registrados na rodada funcional mais recente.
- Novos problemas devem ser reportados em:
  - https://github.com/Juanzitooh/python_git_viewer/issues

## Limitacoes atuais (nao bloqueadoras)

### 1) Dependencias de GUI em ambiente headless (CI/Linux)

- Sintoma:
  - erros de runtime Qt/PySide6 em runners sem bibliotecas graficas.
- Contexto:
  - testes de GUI exigem stack minima de bibliotecas do sistema e execucao com display virtual.
- Mitigacao atual:
  - pipeline separado para testes core e GUI, com `xvfb` e instalacao de libs no job GUI.

### 2) AppImage em algumas distros Linux

- Sintoma:
  - AppImage pode nao abrir em ambientes sem `libfuse.so.2`.
- Mitigacao:
  - executar com:
    - `APPIMAGE_EXTRACT_AND_RUN=1 ./dist/git-viewer-<versao>-x86_64.AppImage`

### 3) Integracao com GitHub depende de configuracao local

- Sintoma:
  - operacoes SSH falham quando a chave nao esta cadastrada no GitHub.
- Mitigacao:
  - fluxo de setup SSH integrado no app (com copy/open/test);
  - cadastro manual em:
    - https://github.com/settings/ssh/new

## Nao escopo (por enquanto)

- suporte oficial fora de Linux desktop no empacotamento principal;
- updater automatico interno do app.

## Como abrir issue de qualidade

Inclua no relato:

- versao (`git-viewer --version` ou versao do pacote);
- sistema/ambiente grafico (ex.: Ubuntu 24.04 + Wayland/X11);
- passos de reproducao;
- resultado esperado x atual;
- logs/traceback e screenshot.

