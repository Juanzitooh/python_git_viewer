#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def fetch_commit_from_source(repo_path: str, source_repo: str, commit_hash: str) -> None:
    source = source_repo.strip()
    commit = commit_hash.strip()
    if not source:
        raise RuntimeError("Repositório de origem não informado para fetch.")
    if not commit:
        raise RuntimeError("Hash de commit inválido para fetch.")
    run_git(repo_path, ["fetch", source, commit])


def cherry_pick_commit(
    repo_path: str,
    commit_hash: str,
    *,
    source_repo: str = "",
    fetch_source: bool = False,
) -> None:
    commit = commit_hash.strip()
    if not commit:
        raise RuntimeError("Hash de commit inválido para cherry-pick.")
    if fetch_source:
        fetch_commit_from_source(repo_path, source_repo, commit)
    run_git(repo_path, ["cherry-pick", commit])


def load_unmerged_conflict_files(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["diff", "--name-only", "--diff-filter=U"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def has_unmerged_conflicts(repo_path: str) -> bool:
    return bool(load_unmerged_conflict_files(repo_path))
