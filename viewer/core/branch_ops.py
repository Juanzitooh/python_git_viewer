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
    normalized_target = target.strip()
    if not normalized_target:
        raise RuntimeError("Branch de destino invalida.")
    if stash_before:
        create_stash(repo_path, message=stash_message, include_untracked=True)
    checkout_error: RuntimeError | None = None
    try:
        run_git(repo_path, ["checkout", normalized_target])
        return
    except RuntimeError as exc:
        checkout_error = exc
        lowered = str(exc).lower()
        lookup_failure = (
            "did not match any file(s) known to git" in lowered
            or "unknown revision" in lowered
            or "invalid reference" in lowered
            or "pathspec" in lowered
        )
        if not lookup_failure:
            raise

    remote_ref = _resolve_remote_branch_ref(repo_path, normalized_target)
    if not remote_ref:
        if checkout_error is not None:
            raise checkout_error
        raise RuntimeError("Falha ao trocar de branch.")
    local_branch = _derive_local_branch_name(normalized_target, remote_ref)
    run_git(repo_path, ["checkout", "-b", local_branch, "--track", remote_ref])


def _resolve_remote_branch_ref(repo_path: str, target: str) -> str:
    if _remote_ref_exists(repo_path, target):
        return target
    origin_candidate = f"origin/{target}"
    if _remote_ref_exists(repo_path, origin_candidate):
        return origin_candidate
    return ""


def _remote_ref_exists(repo_path: str, remote_ref: str) -> bool:
    try:
        run_git(repo_path, ["show-ref", "--verify", "--quiet", f"refs/remotes/{remote_ref}"])
    except RuntimeError:
        return False
    return True


def _derive_local_branch_name(target: str, remote_ref: str) -> str:
    if remote_ref == target and "/" in target:
        _, _, branch_name = target.partition("/")
        if branch_name:
            return branch_name
    return target


def create_branch(repo_path: str, branch_name: str, base_branch: str = "") -> None:
    args = ["branch", branch_name.strip()]
    if base_branch.strip():
        args.append(base_branch.strip())
    run_git(repo_path, args)
