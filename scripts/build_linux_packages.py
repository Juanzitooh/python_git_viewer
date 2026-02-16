#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_APP_ID = "git-viewer"
DEFAULT_BINARY = ROOT_DIR / "dist" / "git_viewer"
DEFAULT_ICON = ROOT_DIR / "assets" / "icon.png"
DEFAULT_DESKTOP = ROOT_DIR / "packaging" / "linux" / "git-viewer.desktop"
DEFAULT_VERSION_FILE = ROOT_DIR / "assets" / "version_info.txt"
APPIMAGETOOL_URL = (
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"+ {printable}")
    subprocess.run(command, check=True, env=env)


def read_version(version_file: Path, fallback: str) -> str:
    if not version_file.exists():
        return fallback
    content = version_file.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"StringStruct\('ProductVersion',\s*'([^']+)'\)", content)
    if not match:
        return fallback
    candidate = match.group(1).strip()
    if not candidate:
        return fallback
    return candidate


def ensure_binary(binary_path: Path, python_exec: str, rebuild: bool) -> Path:
    if rebuild or not binary_path.exists():
        run([python_exec, str(ROOT_DIR / "compile.py")])
    if not binary_path.exists():
        raise FileNotFoundError(f"Binario nao encontrado: {binary_path}")
    binary_path.chmod(0o755)
    return binary_path


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def build_deb(
    *,
    app_id: str,
    version: str,
    arch: str,
    binary_path: Path,
    icon_path: Path,
    desktop_path: Path,
    output_dir: Path,
    work_dir: Path,
) -> Path:
    package_name = app_id
    install_root = work_dir / f"{package_name}_{version}_{arch}"
    if install_root.exists():
        shutil.rmtree(install_root)
    (install_root / "DEBIAN").mkdir(parents=True, exist_ok=True)
    (install_root / "opt" / app_id).mkdir(parents=True, exist_ok=True)
    (install_root / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (install_root / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    (install_root / "usr" / "share" / "icons" / "hicolor" / "64x64" / "apps").mkdir(
        parents=True,
        exist_ok=True,
    )

    control_content = (
        "Package: {name}\n"
        "Version: {version}\n"
        "Section: devel\n"
        "Priority: optional\n"
        "Architecture: {arch}\n"
        "Maintainer: Git Viewer Team\n"
        "Depends: libc6 (>= 2.35), libgl1, libxkbcommon0, libxcb-cursor0\n"
        "Description: Git Viewer (PySide6)\n"
        " GUI Git para Linux com commit, historico, importar e comparar.\n"
    ).format(name=package_name, version=version, arch=arch)
    write_text(install_root / "DEBIAN" / "control", control_content)

    target_binary = install_root / "opt" / app_id / "git_viewer"
    shutil.copy2(binary_path, target_binary)
    target_binary.chmod(0o755)

    launcher_script = (
        "#!/bin/sh\n"
        "exec /opt/{app_id}/git_viewer \"$@\"\n"
    ).format(app_id=app_id)
    write_text(install_root / "usr" / "bin" / app_id, launcher_script, executable=True)

    desktop_target = install_root / "usr" / "share" / "applications" / f"{app_id}.desktop"
    shutil.copy2(desktop_path, desktop_target)

    icon_target = install_root / "usr" / "share" / "icons" / "hicolor" / "64x64" / "apps" / f"{app_id}.png"
    shutil.copy2(icon_path, icon_target)

    output_dir.mkdir(parents=True, exist_ok=True)
    deb_output = output_dir / f"{package_name}_{version}_{arch}.deb"
    run(["dpkg-deb", "--build", "--root-owner-group", str(install_root), str(deb_output)])
    return deb_output


def resolve_appimagetool(work_dir: Path) -> str:
    discovered = shutil.which("appimagetool")
    if discovered:
        return discovered

    tools_dir = work_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    bundled = tools_dir / "appimagetool-x86_64.AppImage"
    if not bundled.exists():
        run(["curl", "-L", "-o", str(bundled), APPIMAGETOOL_URL])
        bundled.chmod(0o755)
    return str(bundled)


def build_appimage(
    *,
    app_id: str,
    version: str,
    binary_path: Path,
    icon_path: Path,
    desktop_path: Path,
    output_dir: Path,
    work_dir: Path,
) -> Path:
    appdir = work_dir / "appimage" / "AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr" / "bin").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "applications").mkdir(parents=True, exist_ok=True)
    (appdir / "usr" / "share" / "icons" / "hicolor" / "64x64" / "apps").mkdir(parents=True, exist_ok=True)

    shutil.copy2(binary_path, appdir / "usr" / "bin" / "git_viewer")
    (appdir / "usr" / "bin" / "git_viewer").chmod(0o755)
    shutil.copy2(desktop_path, appdir / f"{app_id}.desktop")
    shutil.copy2(desktop_path, appdir / "usr" / "share" / "applications" / f"{app_id}.desktop")
    shutil.copy2(icon_path, appdir / f"{app_id}.png")
    shutil.copy2(icon_path, appdir / "usr" / "share" / "icons" / "hicolor" / "64x64" / "apps" / f"{app_id}.png")

    apprun = (
        "#!/bin/sh\n"
        "HERE=\"$(dirname \"$(readlink -f \"$0\")\")\"\n"
        "exec \"$HERE/usr/bin/git_viewer\" \"$@\"\n"
    )
    write_text(appdir / "AppRun", apprun, executable=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{app_id}-{version}-x86_64.AppImage"
    appimagetool = resolve_appimagetool(work_dir)
    env = os.environ.copy()
    env.setdefault("ARCH", "x86_64")
    if appimagetool.endswith(".AppImage"):
        env.setdefault("APPIMAGE_EXTRACT_AND_RUN", "1")
    run([appimagetool, str(appdir), str(output)], env=env)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera pacotes Linux (.deb e AppImage) para o Git Viewer.")
    parser.add_argument("--app-id", default=DEFAULT_APP_ID, help="ID do aplicativo (nome do pacote/comando).")
    parser.add_argument("--version", default="", help="Versao do pacote (default: ProductVersion de assets/version_info.txt).")
    parser.add_argument("--arch", default="amd64", help="Arquitetura do pacote .deb (default: amd64).")
    parser.add_argument("--binary", default=str(DEFAULT_BINARY), help="Binario PyInstaller de entrada.")
    parser.add_argument("--icon", default=str(DEFAULT_ICON), help="Icone PNG para desktop/pacotes.")
    parser.add_argument("--desktop", default=str(DEFAULT_DESKTOP), help="Arquivo .desktop base.")
    parser.add_argument("--output-dir", default=str(ROOT_DIR / "dist"), help="Diretorio de saida dos pacotes.")
    parser.add_argument("--work-dir", default=str(ROOT_DIR / "build" / "linux-packaging"), help="Diretorio temporario de empacotamento.")
    parser.add_argument("--python", default=sys.executable, help="Python usado para chamar compile.py quando necessario.")
    parser.add_argument("--build-binary", action="store_true", help="Forca rebuild do binario com compile.py antes de empacotar.")
    parser.add_argument("--deb-only", action="store_true", help="Gera somente o pacote .deb.")
    parser.add_argument("--appimage-only", action="store_true", help="Gera somente o AppImage.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.deb_only and args.appimage_only:
        raise SystemExit("Use apenas uma entre --deb-only e --appimage-only.")

    version = args.version.strip() or read_version(DEFAULT_VERSION_FILE, "0.2.0")
    binary_path = ensure_binary(Path(args.binary).resolve(), args.python, args.build_binary)
    icon_path = Path(args.icon).resolve()
    desktop_path = Path(args.desktop).resolve()
    output_dir = Path(args.output_dir).resolve()
    work_dir = Path(args.work_dir).resolve()

    if not icon_path.exists():
        raise FileNotFoundError(f"Icone nao encontrado: {icon_path}")
    if not desktop_path.exists():
        raise FileNotFoundError(f"Desktop entry nao encontrado: {desktop_path}")

    generate_deb = not args.appimage_only
    generate_appimage = not args.deb_only

    outputs: list[Path] = []
    if generate_deb:
        deb_path = build_deb(
            app_id=args.app_id,
            version=version,
            arch=args.arch,
            binary_path=binary_path,
            icon_path=icon_path,
            desktop_path=desktop_path,
            output_dir=output_dir,
            work_dir=work_dir,
        )
        outputs.append(deb_path)
    if generate_appimage:
        appimage_path = build_appimage(
            app_id=args.app_id,
            version=version,
            binary_path=binary_path,
            icon_path=icon_path,
            desktop_path=desktop_path,
            output_dir=output_dir,
            work_dir=work_dir,
        )
        outputs.append(appimage_path)

    print("\nPacotes gerados:")
    for built_path in outputs:
        print(f"- {built_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
