#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPT="${ROOT_DIR}/scripts/build_linux_packages.py"
VERSION_FILE="${ROOT_DIR}/assets/version_info.txt"
DIST_DIR="${ROOT_DIR}/dist"
CHECKLIST_DIR="${ROOT_DIR}/checklists"
CHECKLIST_FUNC_BASE="${CHECKLIST_DIR}/CHECKLIST_FUNCIONAL_BASE.md"
CHECKLIST_DIST_BASE="${CHECKLIST_DIR}/CHECKLIST_DISTRIBUICAO_BASE.md"
APP_ID="git-viewer"
ARCH="amd64"

TARGET_VERSION=""
BUILD_DEB=1
BUILD_APPIMAGE=1
DO_INSTALL=1
DO_OPEN=1
RUN_TESTS=1

usage() {
  cat <<'EOF'
Uso: ./dist.sh [opcoes]

Fluxo padrao:
1) Gera checklists da versao (sem sobrescrever arquivos existentes)
2) Executa testes unitarios
3) Gera .deb e AppImage
4) Instala (ou reinstala) o .deb
5) Abre o app com "git-viewer"

Opcoes:
  --version X.Y.Z   Forca versao do pacote no build.
  --deb-only        Gera somente .deb.
  --appimage-only   Gera somente AppImage.
  --no-install      Nao instala/reinstala .deb.
  --no-open         Nao abre o app no final.
  --skip-tests      Nao executa testes unitarios antes do build.
  -h, --help        Mostra esta ajuda.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      if [[ $# -lt 2 ]]; then
        echo "Erro: --version exige valor." >&2
        exit 1
      fi
      TARGET_VERSION="$2"
      shift 2
      ;;
    --deb-only)
      BUILD_DEB=1
      BUILD_APPIMAGE=0
      shift
      ;;
    --appimage-only)
      BUILD_DEB=0
      BUILD_APPIMAGE=1
      shift
      ;;
    --no-install)
      DO_INSTALL=0
      shift
      ;;
    --no-open)
      DO_OPEN=0
      shift
      ;;
    --skip-tests)
      RUN_TESTS=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Opcao invalida: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -f "${BUILD_SCRIPT}" ]]; then
  echo "Erro: script de build nao encontrado: ${BUILD_SCRIPT}" >&2
  exit 1
fi

if [[ "${OSTYPE:-}" != "linux-gnu"* && "${OSTYPE:-}" != "linux"* ]]; then
  echo "Erro: dist.sh suporta apenas Linux." >&2
  exit 1
fi

resolve_version() {
  if [[ -n "${TARGET_VERSION}" ]]; then
    printf '%s\n' "${TARGET_VERSION}"
    return
  fi
  python3 - "${VERSION_FILE}" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
if not path.exists():
    print("0.3.0")
    raise SystemExit(0)
content = path.read_text(encoding="utf-8", errors="ignore")
match = re.search(r"StringStruct\('ProductVersion',\s*'([^']+)'\)", content)
print(match.group(1).strip() if match else "0.3.0")
PY
}

VERSION="$(resolve_version)"
echo "Versao alvo: ${VERSION}"

ensure_checklist_templates() {
  mkdir -p "${CHECKLIST_DIR}"

  if [[ ! -f "${CHECKLIST_FUNC_BASE}" ]]; then
    cat > "${CHECKLIST_FUNC_BASE}" <<'EOF'
# Checklist Funcional - v{{VERSION}}

## Dados da rodada

- Data:
- Testador:
- Branch/commit:
- SO:

## Fluxos principais

- [ ] Repositorios
- [ ] Commit
- [ ] Historico
- [ ] Importar
- [ ] Comparar
- [ ] Configuracoes

## Observacoes

- 
EOF
  fi

  if [[ ! -f "${CHECKLIST_DIST_BASE}" ]]; then
    cat > "${CHECKLIST_DIST_BASE}" <<'EOF'
# Checklist Distribuicao Linux - v{{VERSION}}

## Dados da rodada

- Data:
- Testador:
- Branch/commit:
- Distro/kernel:
- Versao alvo: {{VERSION}}
- Pacote alvo: dist/git-viewer_{{VERSION}}_amd64.deb

## Build

- [ ] Executar `./dist.sh --version {{VERSION}}`
- [ ] Validar `.deb` em `dist/`
- [ ] Validar `.AppImage` em `dist/`

## Instalacao

- [ ] Instalar/reinstalar pacote `.deb`
- [ ] Abrir `git-viewer`
- [ ] Validar atalhos/menu

## Upgrade/Remocao

- [ ] Testar update para versao nova
- [ ] Testar uninstall

## Observacoes

- 
EOF
  fi
}

create_checklist_from_base() {
  local base_path="$1"
  local output_path="$2"
  if [[ -f "${output_path}" ]]; then
    echo "Checklist existente, mantendo: ${output_path}"
    return
  fi

  python3 - "${base_path}" "${output_path}" "${VERSION}" <<'PY'
from datetime import date
from pathlib import Path
import sys

base = Path(sys.argv[1])
target = Path(sys.argv[2])
version = sys.argv[3]

text = base.read_text(encoding="utf-8")
text = text.replace("{{VERSION}}", version)
text = text.replace("{{DATE}}", date.today().isoformat())
target.write_text(text, encoding="utf-8")
PY
  echo "Checklist criado: ${output_path}"
}

generate_checklists_for_version() {
  ensure_checklist_templates

  local functional_latest="${CHECKLIST_DIR}/CHECKLIST_FUNCIONAL.md"
  local distribution_latest="${CHECKLIST_DIR}/CHECKLIST_DISTRIBUICAO.md"
  local functional_versioned="${CHECKLIST_DIR}/CHECKLIST_FUNCIONAL_${VERSION}.md"
  local distribution_versioned="${CHECKLIST_DIR}/CHECKLIST_DISTRIBUICAO_${VERSION}.md"

  create_checklist_from_base "${CHECKLIST_FUNC_BASE}" "${functional_latest}"
  create_checklist_from_base "${CHECKLIST_DIST_BASE}" "${distribution_latest}"
  create_checklist_from_base "${CHECKLIST_FUNC_BASE}" "${functional_versioned}"
  create_checklist_from_base "${CHECKLIST_DIST_BASE}" "${distribution_versioned}"
}

run_unit_tests() {
  if [[ "${RUN_TESTS}" -ne 1 ]]; then
    echo "Testes unitarios ignorados (--skip-tests)."
    return
  fi
  local python_cmd="python3"
  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    python_cmd="${ROOT_DIR}/.venv/bin/python"
  fi
  echo "Executando testes unitarios (unittest) com: ${python_cmd}"
  (cd "${ROOT_DIR}" && "${python_cmd}" -m unittest discover -s tests -p "test_*.py")
}

generate_checklists_for_version
run_unit_tests

run_build() {
  local mode="$1"
  local -a cmd=(python3 "${BUILD_SCRIPT}" --version "${VERSION}")
  if [[ "${mode}" == "deb" ]]; then
    cmd+=(--build-binary --deb-only)
  elif [[ "${mode}" == "appimage" ]]; then
    cmd+=(--appimage-only)
  else
    echo "Modo de build invalido: ${mode}" >&2
    exit 1
  fi
  echo "+ ${cmd[*]}"
  "${cmd[@]}"
}

if [[ "${BUILD_DEB}" -eq 1 ]]; then
  run_build "deb"
fi

if [[ "${BUILD_APPIMAGE}" -eq 1 ]]; then
  if ! run_build "appimage"; then
    echo "Aviso: falha ao gerar AppImage. Seguindo com o que foi gerado." >&2
  fi
fi

DEB_PATH="${DIST_DIR}/${APP_ID}_${VERSION}_${ARCH}.deb"
if [[ "${DO_INSTALL}" -eq 1 ]]; then
  if [[ "${BUILD_DEB}" -ne 1 ]]; then
    echo "Aviso: --appimage-only usado. Instalacao de .deb foi ignorada."
  elif [[ ! -f "${DEB_PATH}" ]]; then
    echo "Erro: pacote .deb nao encontrado: ${DEB_PATH}" >&2
    exit 1
  else
    TMP_DEB="/tmp/$(basename "${DEB_PATH}")"
    cp -f "${DEB_PATH}" "${TMP_DEB}"

    installed_version="$(dpkg-query -W -f='${Version}' "${APP_ID}" 2>/dev/null || true)"
    if [[ "${installed_version}" == "${VERSION}" ]]; then
      echo "Pacote ${APP_ID} ${VERSION} ja instalado; executando reinstall..."
      sudo apt install --reinstall -y "${TMP_DEB}"
    else
      echo "Instalando ${APP_ID} ${VERSION}..."
      sudo apt install -y "${TMP_DEB}"
    fi
  fi
fi

if [[ "${DO_OPEN}" -eq 1 ]]; then
  if command -v git-viewer >/dev/null 2>&1; then
    echo "Abrindo git-viewer..."
    nohup git-viewer >/dev/null 2>&1 &
  else
    echo "Aviso: comando git-viewer nao encontrado no PATH; app nao foi aberto." >&2
  fi
fi

echo "Concluido."
