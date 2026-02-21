#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def fetch_all_prune(repo_path: str) -> None:
    run_git(repo_path, ["fetch", "--all", "--prune"])


def pull_ff_only(repo_path: str) -> None:
    run_git(repo_path, ["pull", "--ff-only"])


def push_current_branch(repo_path: str) -> None:
    run_git(repo_path, ["push"])


def publish_current_branch(repo_path: str, remote_name: str = "origin") -> None:
    remote = remote_name.strip() or "origin"
    run_git(repo_path, ["push", "-u", remote, "HEAD"])


def list_outgoing_commit_titles(repo_path: str, upstream: str) -> list[str]:
    upstream_ref = upstream.strip()
    if not upstream_ref:
        return []
    output = run_git(repo_path, ["log", "--pretty=format:%h %s", f"{upstream_ref}..HEAD"])
    return [line.strip() for line in output.splitlines() if line.strip()]
