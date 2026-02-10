#!/usr/bin/env python3
from __future__ import annotations

from .git_client import run_git


def list_modified_files(repo_path: str) -> list[str]:
    output = run_git(repo_path, ["status", "--porcelain", "-z"])
    if not output:
        return []
    entries: list[str] = []
    raw_items = output.split("\0")
    index = 0
    while index < len(raw_items):
        raw_entry = raw_items[index]
        index += 1
        if not raw_entry:
            continue
        if len(raw_entry) < 3:
            continue
        status = raw_entry[:2]
        path = raw_entry[3:].strip() if len(raw_entry) > 3 else ""
        if not path:
            continue
        if status.startswith("R") or status.startswith("C"):
            if index >= len(raw_items):
                continue
            renamed_path = raw_items[index].strip()
            index += 1
            if renamed_path:
                path = renamed_path
        if path not in entries:
            entries.append(path)
    return entries


def stage_paths(repo_path: str, paths: list[str]) -> None:
    cleaned = [item.strip() for item in paths if item.strip()]
    if not cleaned:
        return
    run_git(repo_path, ["add", "--", *cleaned])


def stage_all(repo_path: str) -> None:
    run_git(repo_path, ["add", "-A"])


def unstage_all(repo_path: str) -> None:
    run_git(repo_path, ["reset"])


def has_staged_changes(repo_path: str) -> bool:
    output = run_git(repo_path, ["diff", "--cached", "--name-only"])
    return bool(output.strip())


def create_commit(repo_path: str, title: str, description: str = "") -> None:
    subject = title.strip()
    if not subject:
        raise RuntimeError("Titulo do commit e obrigatorio.")
    body = description.strip()
    if body:
        run_git(repo_path, ["commit", "-m", subject, "-m", body])
        return
    run_git(repo_path, ["commit", "-m", subject])

