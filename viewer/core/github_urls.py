#!/usr/bin/env python3
from __future__ import annotations

from urllib.parse import quote

from .git_client import run_git


def normalize_remote_url_for_browser(remote_url: str) -> str:
    value = remote_url.strip()
    if not value:
        return ""
    if value.startswith("git@"):
        prefix, sep, path = value.partition(":")
        if not sep or "@" not in prefix:
            return ""
        host = prefix.split("@", 1)[1]
        clean_path = path.removesuffix(".git").strip("/")
        if not host or not clean_path:
            return ""
        return f"https://{host}/{clean_path}"
    if value.startswith("ssh://"):
        payload = value[len("ssh://") :]
        if "@" in payload:
            payload = payload.split("@", 1)[1]
        host, sep, path = payload.partition("/")
        clean_path = path.removesuffix(".git").strip("/")
        if not sep or not host or not clean_path:
            return ""
        return f"https://{host}/{clean_path}"
    if value.startswith("http://") or value.startswith("https://"):
        return value.removesuffix(".git")
    return ""


def get_repo_origin_url(repo_path: str) -> str:
    return run_git(repo_path, ["remote", "get-url", "origin"]).strip()


def get_repo_github_base_url(repo_path: str) -> str:
    remote_url_raw = get_repo_origin_url(repo_path)
    remote_url = normalize_remote_url_for_browser(remote_url_raw)
    if not remote_url or "github.com/" not in remote_url:
        raise RuntimeError(f"Remote origin nao aponta para GitHub:\n{remote_url_raw}")
    return remote_url.rstrip("/")


def get_default_base_branch_for_pr(repo_path: str) -> str:
    try:
        ref = run_git(repo_path, ["symbolic-ref", "refs/remotes/origin/HEAD"]).strip()
    except RuntimeError:
        return "main"
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        branch = ref[len(prefix) :].strip()
        if branch:
            return branch
    return "main"


def get_current_branch_for_pr(repo_path: str) -> str:
    try:
        current = run_git(repo_path, ["branch", "--show-current"]).strip()
        if current:
            return current
    except RuntimeError:
        pass
    try:
        current = run_git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    except RuntimeError:
        return ""
    if current == "HEAD":
        return ""
    return current


def build_repo_branch_url(repo_base_url: str, branch: str) -> str:
    branch_enc = quote(branch, safe="")
    return f"{repo_base_url.rstrip('/')}/tree/{branch_enc}"


def build_repo_branch_commits_url(repo_base_url: str, branch: str) -> str:
    branch_enc = quote(branch, safe="")
    return f"{repo_base_url.rstrip('/')}/commits/{branch_enc}"


def build_repo_issues_url(repo_base_url: str) -> str:
    return f"{repo_base_url.rstrip('/')}/issues"


def build_repo_actions_url(repo_base_url: str) -> str:
    return f"{repo_base_url.rstrip('/')}/actions"


def build_repo_releases_url(repo_base_url: str) -> str:
    return f"{repo_base_url.rstrip('/')}/releases"


def build_pr_compare_url(repo_base_url: str, base_branch: str, head_branch: str) -> str:
    base_enc = quote(base_branch, safe="")
    head_enc = quote(head_branch, safe="")
    return f"{repo_base_url.rstrip('/')}/compare/{base_enc}...{head_enc}"


def build_commit_url(repo_base_url: str, commit_hash: str) -> str:
    return f"{repo_base_url.rstrip('/')}/commit/{commit_hash.strip()}"
