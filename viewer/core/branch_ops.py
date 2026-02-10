#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def create_stash(repo_path: str, message: str = "git_commits_viewer", include_untracked: bool = True) -> None:
    args = ["stash", "push"]
    if include_untracked:
        args.append("-u")
    if message.strip():
        args.extend(["-m", message.strip()])
    run_git(repo_path, args)


def checkout_branch(
    repo_path: str,
    target: str,
    *,
    stash_before: bool = False,
    stash_message: str = "git_commits_viewer",
) -> None:
    if stash_before:
        create_stash(repo_path, message=stash_message, include_untracked=True)
    run_git(repo_path, ["checkout", target.strip()])


def create_branch(repo_path: str, branch_name: str, base_branch: str = "") -> None:
    args = ["branch", branch_name.strip()]
    if base_branch.strip():
        args.append(base_branch.strip())
    run_git(repo_path, args)
