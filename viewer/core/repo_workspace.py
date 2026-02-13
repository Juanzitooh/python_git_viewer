#!/usr/bin/env python3
from __future__ import annotations

import getpass
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


def default_repo_scan_root() -> str:
    if os.name == "nt":
        return str(Path.home() / "Documents" / "github")
    return str(Path.home() / "Documentos" / "github")


def discover_git_repositories(root_path: str, max_depth: int = 4) -> list[str]:
    root = Path(root_path).expanduser()
    if not root.is_dir():
        return []
    root = root.resolve()
    base_depth = len(root.parts)
    found: list[str] = []
    seen: set[str] = set()
    for current, dirs, _files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.parts) - base_depth
        if ".git" in dirs:
            normalized = str(current_path)
            if normalized not in seen:
                found.append(normalized)
                seen.add(normalized)
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        if depth >= max_depth:
            dirs[:] = []
    found.sort()
    return found


def _derive_repo_name_from_url(repo_url: str) -> str:
    candidate = repo_url.strip()
    if "://" in candidate:
        parsed = urlparse(candidate)
        path = parsed.path
    elif "@" in candidate and ":" in candidate.split("@", 1)[1]:
        path = candidate.split(":", 1)[1]
    else:
        path = candidate
    name = path.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    name = name.strip()
    if not name:
        raise RuntimeError("Nao foi possivel identificar o nome do repositorio pela URL.")
    invalid = set('\\/:*?"<>|')
    cleaned = "".join(ch for ch in name if ch not in invalid).strip()
    if not cleaned:
        raise RuntimeError("Nome de diretorio invalido para clone.")
    return cleaned


def _parse_clone_target_path(
    repo_url: str,
    root: Path,
    directory_name: str,
) -> Path:
    repo_name = _derive_repo_name_from_url(repo_url)
    raw_target = directory_name.strip()
    if not raw_target:
        return (root / repo_name).resolve()

    ends_with_separator = raw_target.endswith(("/", "\\"))
    normalized_target = raw_target.rstrip("/\\")
    if not normalized_target:
        raise RuntimeError("Pasta de destino inválida.")

    relative_target = Path(normalized_target.replace("\\", "/"))
    if relative_target.is_absolute():
        raise RuntimeError("Informe a pasta de destino como caminho relativo ao workspace.")
    if any(part in ("", ".", "..") for part in relative_target.parts):
        raise RuntimeError("Pasta de destino inválida.")

    # Interpreta o campo "Pasta" como namespace por padrao:
    # - "grupo" -> root/grupo/<repo>
    # - "grupo/repo" -> root/grupo/repo
    # - "repo" (igual ao nome do repo) -> root/repo
    if relative_target.name == repo_name:
        target_path = (root / relative_target).resolve()
    else:
        target_path = (root / relative_target / repo_name).resolve()
    try:
        target_path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Pasta de destino fora da raiz do workspace.") from exc

    if ends_with_separator:
        return target_path
    return target_path


def clone_repository(
    repo_url: str,
    destination_root: str,
    directory_name: str = "",
    on_progress: Callable[[str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> str:
    root = Path(destination_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    target_path = _parse_clone_target_path(repo_url, root, directory_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise RuntimeError(f"Destino ja existe: {target_path}")
    command = ["git", "clone", "--progress", repo_url, str(target_path)]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        bufsize=1,
    )

    def cancel_clone() -> None:
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        shutil.rmtree(target_path, ignore_errors=True)
        raise RuntimeError("Clone cancelado pelo usuario.")

    stderr_buffer = ""
    try:
        if process.stderr is not None:
            while True:
                chunk = process.stderr.read(1)
                if chunk == "":
                    break
                if chunk in ("\r", "\n"):
                    line = stderr_buffer.strip().replace("\x1b[K", "")
                    stderr_buffer = ""
                    if line:
                        if line.startswith("remote: "):
                            line = line[8:].strip()
                        if on_progress:
                            on_progress(line)
                    if is_cancelled and is_cancelled():
                        cancel_clone()
                    continue
                stderr_buffer += chunk
                if is_cancelled and is_cancelled():
                    cancel_clone()
        result_code = process.wait()
    except RuntimeError:
        raise
    except Exception:
        process.kill()
        process.wait(timeout=5)
        raise
    if stderr_buffer.strip() and on_progress:
        line = stderr_buffer.strip().replace("\x1b[K", "")
        if line.startswith("remote: "):
            line = line[8:].strip()
        on_progress(line)
    if result_code != 0:
        shutil.rmtree(target_path, ignore_errors=True)
        raise RuntimeError("Falha no clone: verifique URL/SSH e permissões.")
    return str(target_path.resolve())


def _resolve_github_ssh_key_paths(key_path: str = "") -> tuple[Path, Path]:
    key_file = Path(key_path).expanduser() if key_path.strip() else Path.home() / ".ssh" / "id_ed25519"
    pub_file = Path(f"{key_file}.pub")
    return key_file, pub_file


def github_ssh_key_exists(key_path: str = "") -> tuple[bool, str]:
    key_file, pub_file = _resolve_github_ssh_key_paths(key_path)
    exists = key_file.exists() and pub_file.exists()
    return exists, str(key_file)


def ensure_github_ssh_key(key_path: str = "") -> tuple[bool, str, str]:
    key_file, pub_file = _resolve_github_ssh_key_paths(key_path)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(key_file.parent, 0o700)
    created = False
    if not key_file.exists():
        comment = f"{getpass.getuser()}@{socket.gethostname()}"
        result = subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(key_file),
                "-N",
                "",
                "-C",
                comment,
            ],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or "(sem detalhes)"
            raise RuntimeError(f"Falha ao criar chave SSH: {stderr}")
        created = True
    if not pub_file.exists():
        raise RuntimeError(f"Chave publica nao encontrada: {pub_file}")
    if os.name != "nt":
        try:
            os.chmod(key_file, 0o600)
            os.chmod(pub_file, 0o644)
        except OSError:
            pass
    pub_key = pub_file.read_text(encoding="utf-8").strip()
    return created, str(key_file), pub_key


def check_github_ssh_auth(key_path: str, timeout_sec: int = 12) -> tuple[bool, str]:
    result = subprocess.run(
        [
            "ssh",
            "-i",
            key_path,
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-T",
            "git@github.com",
        ],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout_sec,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    authenticated = "successfully authenticated" in output.lower()
    return authenticated, output
