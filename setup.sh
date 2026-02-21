#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
REQ_FILE="${ROOT_DIR}/requirements.txt"
STAMP_FILE="${VENV_DIR}/.requirements.sha256"

RUN_APP=1
FORCE_INSTALL=0
APP_ARGS=()

usage() {
  cat <<'EOF'
Uso: ./setup.sh [opcoes] [-- <args do main.py>]

Opcoes:
  --no-run         Prepara ambiente, mas nao inicia o app.
  --force-install  Reinstala dependencias mesmo sem mudanca em requirements.txt.
  -h, --help       Mostra esta ajuda.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-run)
      RUN_APP=0
      shift
      ;;
    --force-install)
      FORCE_INSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      APP_ARGS+=("$@")
      break
      ;;
    *)
      APP_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "Erro: requirements.txt nao encontrado em ${ROOT_DIR}" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Criando ambiente virtual em ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

python -m ensurepip --upgrade >/dev/null 2>&1 || true

current_hash="$(python - "${REQ_FILE}" <<'PY'
import hashlib
import pathlib
import sys

req_path = pathlib.Path(sys.argv[1])
print(hashlib.sha256(req_path.read_bytes()).hexdigest())
PY
)"

installed_hash=""
if [[ -f "${STAMP_FILE}" ]]; then
  installed_hash="$(<"${STAMP_FILE}")"
fi

if [[ "${FORCE_INSTALL}" -eq 1 || "${current_hash}" != "${installed_hash}" ]]; then
  echo "Instalando dependencias..."
  python -m pip install -r "${REQ_FILE}"
  printf '%s\n' "${current_hash}" > "${STAMP_FILE}"
else
  echo "Dependencias ja estao atualizadas."
fi

if [[ "${RUN_APP}" -eq 0 ]]; then
  echo "Ambiente pronto. Execucao do app ignorada (--no-run)."
  exit 0
fi

cd "${ROOT_DIR}"
exec python main.py "${APP_ARGS[@]}"
