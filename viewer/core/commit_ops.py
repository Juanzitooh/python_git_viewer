#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from dataclasses import dataclass

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


def create_stash(
    repo_path: str,
    message: str = "git_viewer",
    include_untracked: bool = True,
    paths: list[str] | None = None,
) -> None:
    args = ["stash", "push"]
    if include_untracked:
        args.append("-u")
    text = message.strip()
    if text:
        args.extend(["-m", text])
    cleaned_paths = [item.strip() for item in (paths or []) if item.strip()]
    if cleaned_paths:
        args.extend(["--", *cleaned_paths])
    run_git(repo_path, args)


@dataclass(frozen=True)
class StashEntry:
    ref: str
    description: str


def list_stashes(repo_path: str) -> list[StashEntry]:
    output = run_git(repo_path, ["stash", "list"])
    entries: list[StashEntry] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        ref, separator, description = line.partition(":")
        if not separator:
            continue
        normalized_ref = ref.strip()
        if not normalized_ref:
            continue
        entries.append(StashEntry(ref=normalized_ref, description=description.strip()))
    return entries


def get_stash_patch(
    repo_path: str,
    ref: str,
    *,
    word_diff: bool = False,
    path_for_git: str = "",
) -> str:
    selected_ref = ref.strip()
    if not selected_ref:
        return ""
    selected_path = path_for_git.strip()
    if selected_path:
        args = ["show", "--pretty=format:", "-p", selected_ref]
        if word_diff:
            args.append("--word-diff=plain")
        args.extend(["--", selected_path])
        return run_git(repo_path, args)
    args = ["stash", "show", "-p", selected_ref]
    if word_diff:
        args.append("--word-diff=plain")
    return run_git(repo_path, args)


def list_stash_files_from_patch(patch: str) -> list[str]:
    files: list[str] = []
    for line in patch.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        old_path = parts[2].strip()
        new_path = parts[3].strip()
        candidate = new_path if new_path.startswith("b/") else old_path
        normalized = candidate[2:] if candidate.startswith(("a/", "b/")) else candidate
        normalized = normalized.strip()
        if normalized and normalized not in files:
            files.append(normalized)
    return files


def apply_stash(repo_path: str, ref: str, *, pop: bool = False) -> None:
    selected_ref = ref.strip()
    if not selected_ref:
        raise RuntimeError("Stash inválido.")
    action = "pop" if pop else "apply"
    run_git(repo_path, ["stash", action, selected_ref])


def drop_stash(repo_path: str, ref: str) -> None:
    selected_ref = ref.strip()
    if not selected_ref:
        raise RuntimeError("Stash inválido.")
    run_git(repo_path, ["stash", "drop", selected_ref])


def undo_last_commit(repo_path: str, mode: str = "mixed") -> None:
    normalized = mode.strip().lower()
    if normalized not in {"soft", "mixed", "hard"}:
        raise RuntimeError("Modo de undo inválido. Use: soft, mixed ou hard.")
    run_git(repo_path, ["reset", f"--{normalized}", "HEAD~1"])


def get_last_commit_subject(repo_path: str) -> str:
    output = run_git(repo_path, ["log", "-1", "--pretty=%s"])
    return output.strip()


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


def apply_patch_to_worktree(repo_path: str, patch: str, *, reverse: bool = False) -> None:
    payload = patch.strip()
    if not payload:
        return
    cmd = ["git", "-C", repo_path, "apply", "--recount", "--unidiff-zero"]
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
    stderr = result.stderr.strip() or "falha ao aplicar patch no arquivo"
    raise RuntimeError(stderr)
