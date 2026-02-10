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


def is_conflict_operation_in_progress(repo_path: str, operation: str) -> bool:
    key = operation.strip().lower()
    if key == "cherry-pick":
        return git_ref_exists(repo_path, "CHERRY_PICK_HEAD")
    if key == "rebase":
        return is_rebase_in_progress(repo_path)
    if key in {"merge", "squash_merge"}:
        return git_ref_exists(repo_path, "MERGE_HEAD")
    return False


def resolve_active_conflict_operation(repo_path: str, preferred: str = "") -> str:
    normalized_preferred = preferred.strip().lower()
    if normalized_preferred and is_conflict_operation_in_progress(repo_path, normalized_preferred):
        return normalized_preferred
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
    if key in {"merge", "squash_merge"}:
        run_git(repo_path, ["merge", "--abort"])
        return
    raise RuntimeError("Operacao de conflito invalida.")
