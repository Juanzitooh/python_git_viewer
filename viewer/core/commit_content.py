#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def resolve_commit_hash(repo_path: str, token: str) -> str:
    candidate = token.strip()
    if not candidate:
        return ""
    try:
        return run_git(repo_path, ["rev-parse", candidate]).strip()
    except RuntimeError:
        return candidate


def list_commit_files(repo_path: str, commit_hash: str) -> list[str]:
    output = run_git(repo_path, ["show", "--pretty=format:", "--name-only", commit_hash])
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_commit_patch(
    repo_path: str,
    commit_hash: str,
    *,
    path: str | None = None,
    word_diff: bool = False,
    unified_zero: bool = False,
) -> str:
    args = ["show"]
    if unified_zero:
        args.append("--unified=0")
    args.append("--format=")
    if word_diff:
        args.append("--word-diff=plain")
    args.append(commit_hash)
    if path:
        args.extend(["--", path])
    return run_git(repo_path, args)
