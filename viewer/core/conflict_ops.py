#!/usr/bin/env python3
from __future__ import annotations

import os

from .git_client import run_git


VALID_CONFLICT_OPERATIONS = {"cherry-pick", "rebase", "merge", "squash_merge"}


def git_ref_exists(repo_path: str, ref_name: str) -> bool:
    try:
        output = run_git(repo_path, ["rev-parse", "-q", "--verify", ref_name]).strip()
    except RuntimeError:
        return False
    return bool(output)


def is_rebase_in_progress(repo_path: str) -> bool:
    try:
        git_dir_output = run_git(repo_path, ["rev-parse", "--git-dir"]).strip()
    except RuntimeError:
        return False
    if not git_dir_output:
        return False
    git_dir = git_dir_output
    if not os.path.isabs(git_dir):
        git_dir = os.path.normpath(os.path.join(repo_path, git_dir))
    return os.path.isdir(os.path.join(git_dir, "rebase-merge")) or os.path.isdir(os.path.join(git_dir, "rebase-apply"))


def _resolve_git_dir_path(repo_path: str) -> str:
    git_dir_output = run_git(repo_path, ["rev-parse", "--git-dir"]).strip()
    if not git_dir_output:
        return ""
    if os.path.isabs(git_dir_output):
        return git_dir_output
    return os.path.normpath(os.path.join(repo_path, git_dir_output))


def _git_dir_file_exists(repo_path: str, file_name: str) -> bool:
    try:
        git_dir = _resolve_git_dir_path(repo_path)
    except RuntimeError:
        return False
    if not git_dir:
        return False
    return os.path.exists(os.path.join(git_dir, file_name))


def has_unmerged_conflicts(repo_path: str) -> bool:
    try:
        output = run_git(repo_path, ["diff", "--name-only", "--diff-filter=U"])
    except RuntimeError:
        return False
    return bool(output.strip())


def is_conflict_operation_in_progress(repo_path: str, operation: str) -> bool:
    key = operation.strip().lower()
    if key == "cherry-pick":
        return git_ref_exists(repo_path, "CHERRY_PICK_HEAD")
    if key == "rebase":
        return is_rebase_in_progress(repo_path)
    if key == "merge":
        return git_ref_exists(repo_path, "MERGE_HEAD")
    if key == "squash_merge":
        return git_ref_exists(repo_path, "MERGE_HEAD") or _git_dir_file_exists(repo_path, "SQUASH_MSG")
    return False


def resolve_active_conflict_operation(repo_path: str, preferred: str = "") -> str:
    normalized_preferred = preferred.strip().lower()
    if normalized_preferred and is_conflict_operation_in_progress(repo_path, normalized_preferred):
        return normalized_preferred
    if normalized_preferred == "squash_merge" and has_unmerged_conflicts(repo_path):
        return "squash_merge"
    for candidate in ("cherry-pick", "rebase", "merge"):
        if not is_conflict_operation_in_progress(repo_path, candidate):
            continue
        if candidate == "merge" and normalized_preferred == "squash_merge":
            return "squash_merge"
        return candidate
    return ""


def continue_conflict_operation(repo_path: str, operation: str, squash_message: str = "") -> None:
    key = operation.strip().lower()
    if key not in VALID_CONFLICT_OPERATIONS:
        raise RuntimeError("Operacao de conflito invalida.")
    if key == "cherry-pick":
        run_git(repo_path, ["cherry-pick", "--continue"])
        return
    if key == "rebase":
        run_git(repo_path, ["rebase", "--continue"])
        return
    if key == "merge":
        try:
            run_git(repo_path, ["merge", "--continue"])
        except RuntimeError:
            run_git(repo_path, ["commit", "--no-edit"])
        return
    message = squash_message.strip()
    if not message:
        raise RuntimeError("Informe a mensagem do commit de squash.")
    run_git(repo_path, ["commit", "-m", message])


def abort_conflict_operation(repo_path: str, operation: str) -> None:
    key = operation.strip().lower()
    if key == "cherry-pick":
        run_git(repo_path, ["cherry-pick", "--abort"])
        return
    if key == "rebase":
        run_git(repo_path, ["rebase", "--abort"])
        return
    if key == "merge":
        run_git(repo_path, ["merge", "--abort"])
        return
    if key == "squash_merge":
        try:
            run_git(repo_path, ["merge", "--abort"])
        except RuntimeError:
            run_git(repo_path, ["reset", "--merge"])
        return
    raise RuntimeError("Operacao de conflito invalida.")


def resolve_conflict_file_using_side(repo_path: str, path_for_git: str, side: str) -> None:
    normalized_path = path_for_git.strip()
    normalized_side = side.strip().lower()
    if not normalized_path:
        raise RuntimeError("Arquivo de conflito inválido.")
    if normalized_side not in {"ours", "theirs"}:
        raise RuntimeError("Lado de resolução inválido.")
    run_git(repo_path, ["checkout", f"--{normalized_side}", "--", normalized_path])
    run_git(repo_path, ["add", "--", normalized_path])


def mark_conflict_file_resolved(repo_path: str, path_for_git: str) -> None:
    normalized_path = path_for_git.strip()
    if not normalized_path:
        raise RuntimeError("Arquivo de conflito inválido.")
    run_git(repo_path, ["add", "--", normalized_path])
