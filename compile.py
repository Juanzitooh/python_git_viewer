#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_ENTRY = "main.py"
DEFAULT_NAME = "git_viewer"


def run(cmd: list[str]) -> None:
    display = " ".join(shlex.quote(part) for part in cmd)
    print(f"+ {display}")
    subprocess.run(cmd, check=True)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_venv(venv_dir: Path) -> Path:
    python_path = venv_python(venv_dir)
    if python_path.exists():
        return python_path
    run([sys.executable, "-m", "venv", str(venv_dir)])
    if not python_path.exists():
        raise RuntimeError("Falha ao criar a .venv.")
    return python_path


def has_requirements(requirements_file: Path) -> bool:
    if not requirements_file.exists():
        return False
    for line in requirements_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return True
    return False


def install_requirements(python_path: Path, requirements_file: Path) -> None:
    if not has_requirements(requirements_file):
        return
    run([str(python_path), "-m", "pip", "install", "-r", str(requirements_file)])


def build_pyinstaller(python_path: Path, entry: Path, name: str, console: bool) -> None:
    cmd = [
        str(python_path),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
    ]
    if not console:
        cmd.append("--windowed")
    cmd.append(str(entry))
    run(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Builda o executavel via PyInstaller.")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Nome do executavel")
    parser.add_argument("--entry", default=DEFAULT_ENTRY, help="Arquivo de entrada")
    parser.add_argument(
        "--console",
        action="store_true",
        help="Mantem a janela de console (bom para debug)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entry_path = (ROOT_DIR / args.entry).resolve()
    if not entry_path.exists():
        raise FileNotFoundError(f"Entrada nao encontrada: {entry_path}")

    venv_dir = ROOT_DIR / ".venv"
    python_path = ensure_venv(venv_dir)

    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    install_requirements(python_path, ROOT_DIR / "requirements.txt")
    install_requirements(python_path, ROOT_DIR / "requirements-dev.txt")
    build_pyinstaller(python_path, entry_path, args.name, args.console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
