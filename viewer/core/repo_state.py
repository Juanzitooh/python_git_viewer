#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def list_branches(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["branch", "--format=%(refname:short)"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def list_tags(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["tag", "--list"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_current_branch(repo_path: str) -> str:
    output = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    return output.strip()


def is_dirty(repo_path: str) -> bool:
    output = run_git(repo_path, ["status", "--porcelain"])
    return bool(output.strip())


def get_upstream(repo_path: str) -> str | None:
    try:
        output = run_git(repo_path, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except RuntimeError:
        return None
    upstream = output.strip()
    return upstream if upstream else None


def get_ahead_behind(repo_path: str, upstream: str | None = None) -> tuple[int, int]:
    upstream_ref = upstream or get_upstream(repo_path)
    if not upstream_ref:
        return 0, 0
    output = run_git(repo_path, ["rev-list", "--left-right", "--count", f"{upstream_ref}...HEAD"])
    parts = output.strip().split()
    if len(parts) != 2:
        return 0, 0
    try:
        behind = int(parts[0])
        ahead = int(parts[1])
    except ValueError:
        return 0, 0
    return behind, ahead
