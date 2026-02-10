#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def load_compare_commits(repo_path: str, origin: str, dest: str) -> list[str]:
    output = run_git(repo_path, ["log", "--oneline", f"{dest}..{origin}"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def load_compare_file_stats(repo_path: str, origin: str, dest: str) -> tuple[list[dict[str, object]], dict[str, int]]:
    output = run_git(repo_path, ["diff", "--numstat", f"{dest}...{origin}"])
    stats: list[dict[str, object]] = []
    totals = {"files": 0, "added": 0, "deleted": 0, "binary": 0}
    for raw in output.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t", 2)
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path = parts
        is_binary = added_raw == "-" or deleted_raw == "-"
        try:
            added = 0 if is_binary else int(added_raw)
            deleted = 0 if is_binary else int(deleted_raw)
        except ValueError:
            added = 0
            deleted = 0
        stats.append(
            {
                "path": path,
                "added": added,
                "deleted": deleted,
                "binary": is_binary,
            }
        )
        totals["files"] += 1
        totals["added"] += added
        totals["deleted"] += deleted
        if is_binary:
            totals["binary"] += 1
    return stats, totals


def load_compare_file_patch(
    repo_path: str,
    origin: str,
    dest: str,
    *,
    path: str = "",
    word_diff: bool = False,
    unified_zero: bool = False,
) -> str:
    args = ["diff"]
    if unified_zero:
        args.append("--unified=0")
    if word_diff:
        args.append("--word-diff=plain")
    args.append(f"{dest}...{origin}")
    relative = path.strip()
    if relative:
        args.extend(["--", relative])
    return run_git(repo_path, args)


def get_ahead_behind_between(repo_path: str, origin: str, dest: str) -> tuple[int, int]:
    try:
        output = run_git(repo_path, ["rev-list", "--left-right", "--count", f"{origin}...{dest}"])
    except RuntimeError:
        return 0, 0
    parts = output.strip().split()
    if len(parts) != 2:
        return 0, 0
    try:
        behind = int(parts[0])
        ahead = int(parts[1])
    except ValueError:
        return 0, 0
    return behind, ahead


def has_potential_conflict(repo_path: str, origin: str, dest: str) -> bool:
    try:
        base = run_git(repo_path, ["merge-base", dest, origin]).strip()
        output = run_git(repo_path, ["merge-tree", base, dest, origin])
    except RuntimeError:
        return False
    return "<<<<<<<" in output
