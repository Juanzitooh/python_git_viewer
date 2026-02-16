#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def list_branches(repo_path: str) -> list[str]:
    output = run_git(
        repo_path,
        ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"],
    )
    local_branches: list[str] = []
    local_branch_set: set[str] = set()
    remote_branches: list[str] = []
    for raw_line in output.splitlines():
        ref = raw_line.strip()
        if not ref:
            continue
        if ref.startswith("refs/heads/"):
            name = ref[len("refs/heads/") :].strip()
            if name and name not in local_branch_set:
                local_branches.append(name)
                local_branch_set.add(name)
            continue
        if not ref.startswith("refs/remotes/"):
            continue
        remote_short = ref[len("refs/remotes/") :].strip()
        if not remote_short or remote_short.endswith("/HEAD"):
            continue
        remote_name, _, branch_name = remote_short.partition("/")
        if not remote_name or not branch_name:
            continue
        if remote_name == "origin":
            if branch_name in local_branch_set:
                continue
            candidate = f"origin/{branch_name}"
        else:
            candidate = f"{remote_name}/{branch_name}"
        if candidate and candidate not in remote_branches:
            remote_branches.append(candidate)
    branches = list(local_branches)
    for candidate in remote_branches:
        if candidate not in branches:
            branches.append(candidate)
    return branches


def list_local_branches_with_upstream(repo_path: str) -> set[str]:
    output = run_git(
        repo_path,
        ["for-each-ref", "--format=%(refname:short)|%(upstream:short)", "refs/heads"],
    )
    tracked: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        local_name, _, upstream = line.partition("|")
        normalized_local = local_name.strip()
        normalized_upstream = upstream.strip()
        if normalized_local and normalized_upstream:
            tracked.add(normalized_local)
    return tracked


def get_default_branch(repo_path: str) -> str:
    try:
        output = run_git(repo_path, ["symbolic-ref", "refs/remotes/origin/HEAD"])
    except RuntimeError:
        branches = list_branches(repo_path)
        if "main" in branches:
            return "main"
        if "master" in branches:
            return "master"
        if "origin/main" in branches:
            return "main"
        if "origin/master" in branches:
            return "master"
        return ""
    ref = output.strip()
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        return ref[len(prefix) :].strip()
    return ""


def list_tags(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["tag", "--list"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def list_worktree_changed_files(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["status", "--porcelain"])
    changed_files: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        raw_path = line[3:].strip() if len(line) >= 4 else line.strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1].strip()
        if raw_path and raw_path not in changed_files:
            changed_files.append(raw_path)
    return changed_files


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
