#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from .git_client import run_git


def list_modified_files(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["status", "--porcelain", "-z"])
    if not output:
        return []
    entries: list[str] = []
    raw_items = output.split("\0")
    index = 0
    while index < len(raw_items):
        raw_entry = raw_items[index]
        index += 1
        if not raw_entry:
            continue
        if len(raw_entry) < 3:
            continue
        status = raw_entry[:2]
        path = raw_entry[3:].strip() if len(raw_entry) > 3 else ""
        if not path:
            continue
        if status.startswith("R") or status.startswith("C"):
            if index >= len(raw_items):
                continue
            renamed_path = raw_items[index].strip()
            index += 1
            if renamed_path:
                path = renamed_path
        if path not in entries:
            entries.append(path)
    return entries


def stage_paths(repo_path: str, paths: list[str]) -> None:
    cleaned = [item.strip() for item in paths if item.strip()]
    if not cleaned:
        return
    run_git(repo_path, ["add", "--", *cleaned])


def stage_all(repo_path: str) -> None:
    run_git(repo_path, ["add", "-A"])


def unstage_all(repo_path: str) -> None:
    run_git(repo_path, ["reset"])


def unstage_paths(repo_path: str, paths: list[str]) -> None:
    cleaned = [item.strip() for item in paths if item.strip()]
    if not cleaned:
        return
    run_git(repo_path, ["reset", "HEAD", "--", *cleaned])


def has_staged_changes(repo_path: str) -> bool:
    output = run_git(repo_path, ["diff", "--cached", "--name-only"])
    return bool(output.strip())


def create_commit(repo_path: str, title: str, description: str = "") -> None:
    subject = title.strip()
    if not subject:
        raise RuntimeError("Titulo do commit e obrigatorio.")
    body = description.strip()
    if body:
        run_git(repo_path, ["commit", "-m", subject, "-m", body])
        return
    run_git(repo_path, ["commit", "-m", subject])


def list_status_entries(repo_path: str) -> list[dict[str, str | bool]]:
    output = run_git(repo_path, ["status", "--porcelain", "-z"])
    entries: list[dict[str, str | bool]] = []
    chunks = [chunk for chunk in output.split("\0") if chunk]
    index = 0
    while index < len(chunks):
        raw = chunks[index]
        if len(raw) < 3:
            index += 1
            continue
        status = raw[:2]
        path = raw[3:]
        path_for_git = path
        if status[0] in ("R", "C") and index + 1 < len(chunks):
            new_path = chunks[index + 1]
            path = f"{path} -> {new_path}"
            path_for_git = new_path
            index += 1
        staged = status[0] not in (" ", "?")
        unstaged = status[1] != " "
        entries.append(
            {
                "status": status,
                "path": path,
                "path_for_git": path_for_git,
                "staged": staged,
                "unstaged": unstaged,
            }
        )
        index += 1
    return entries


def get_file_patch(
    repo_path: str,
    path_for_git: str,
    *,
    word_diff: bool = False,
    cached: bool = False,
    untracked: bool = False,
) -> str:
    path = path_for_git.strip()
    if not path:
        return ""
    if untracked:
        cmd = ["git", "-C", repo_path, "diff", "--no-index", "--unified=0"]
        if word_diff:
            cmd.append("--word-diff=plain")
        cmd.extend(["/dev/null", path])
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
        )
        return result.stdout
    args = ["diff", "--unified=0"]
    if cached:
        args.append("--cached")
    if word_diff:
        args.append("--word-diff=plain")
    args.extend(["--", path])
    return run_git(repo_path, args)


def apply_patch_to_index(repo_path: str, patch: str, *, reverse: bool = False) -> None:
    payload = patch.strip()
    if not payload:
        return
    cmd = ["git", "-C", repo_path, "apply", "--recount", "--unidiff-zero", "--cached"]
    if reverse:
        cmd.append("-R")
    result = subprocess.run(
        cmd,
        input=payload + "\n",
        text=True,
        capture_output=True,
        errors="replace",
    )
    if result.returncode == 0:
        return
    stderr = result.stderr.strip() or "falha ao aplicar patch"
    raise RuntimeError(stderr)
