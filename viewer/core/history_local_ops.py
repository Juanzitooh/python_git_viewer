#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
from datetime import datetime

from .git_client import run_git
from .models import CommitSummary


FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"


@dataclasses.dataclass(frozen=True)
class LocalReorderApplyResult:
    ok: bool
    backup_branch: str
    error_message: str = ""
    restore_error_message: str = ""


def load_local_only_commit_hashes(repo_path: str, upstream: str) -> set[str]:
    output = run_git(repo_path, ["rev-list", f"{upstream}..HEAD"])
    return {line.strip() for line in output.splitlines() if line.strip()}


def load_reorderable_local_commits(repo_path: str, upstream: str) -> list[CommitSummary]:
    log_output = run_git(
        repo_path,
        [
            "log",
            "--reverse",
            "--date=iso",
            f"--pretty=format:%H{FIELD_SEP}%s{FIELD_SEP}%an{FIELD_SEP}%ad{FIELD_SEP}%ct{RECORD_SEP}",
            f"{upstream}..HEAD",
        ],
    )
    commits: list[CommitSummary] = []
    for record in log_output.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        fields = record.split(FIELD_SEP)
        if len(fields) < 2:
            continue
        commit_hash = fields[0]
        subject = fields[1]
        author = fields[2] if len(fields) > 2 else ""
        date = fields[3] if len(fields) > 3 else ""
        timestamp_raw = fields[4] if len(fields) > 4 else ""
        try:
            timestamp = int(timestamp_raw)
        except ValueError:
            timestamp = 0
        commits.append(
            CommitSummary(
                commit_hash=commit_hash,
                subject=subject,
                author=author,
                date=date,
                timestamp=timestamp,
            )
        )
    return commits


def _sanitize_branch_name_for_backup(branch_name: str) -> str:
    if not branch_name.strip():
        return "branch"
    safe = []
    for char in branch_name.strip():
        if char.isalnum() or char in ("-", "_"):
            safe.append(char)
        else:
            safe.append("-")
    value = "".join(safe).strip("-")
    return value or "branch"


def build_reorder_backup_branch(repo_path: str, current_branch: str) -> str:
    safe_branch = _sanitize_branch_name_for_backup(current_branch)
    base = f"backup/reorder-{safe_branch}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    candidate = base
    counter = 2
    while True:
        try:
            run_git(repo_path, ["rev-parse", "--verify", candidate])
        except RuntimeError:
            return candidate
        candidate = f"{base}-{counter}"
        counter += 1


def apply_local_commit_reorder(
    repo_path: str,
    upstream: str,
    ordered_commits: list[CommitSummary],
    current_branch: str,
) -> LocalReorderApplyResult:
    backup_branch = build_reorder_backup_branch(repo_path, current_branch)
    try:
        run_git(repo_path, ["branch", backup_branch, "HEAD"])
    except RuntimeError as exc:
        raise RuntimeError(f"Falha ao criar branch de backup:\n{exc}") from exc

    try:
        run_git(repo_path, ["reset", "--hard", upstream])
        for summary in ordered_commits:
            run_git(repo_path, ["cherry-pick", summary.commit_hash])
        return LocalReorderApplyResult(ok=True, backup_branch=backup_branch)
    except RuntimeError as exc:
        try:
            run_git(repo_path, ["cherry-pick", "--abort"])
        except RuntimeError:
            pass
        try:
            run_git(repo_path, ["reset", "--hard", backup_branch])
        except RuntimeError as restore_exc:
            return LocalReorderApplyResult(
                ok=False,
                backup_branch=backup_branch,
                error_message=str(exc),
                restore_error_message=str(restore_exc),
            )
        return LocalReorderApplyResult(
            ok=False,
            backup_branch=backup_branch,
            error_message=str(exc),
            restore_error_message="",
        )
