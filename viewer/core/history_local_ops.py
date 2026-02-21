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
    conflict_in_progress: bool = False


@dataclasses.dataclass(frozen=True)
class ReorderDependencyIssue:
    path: str
    reason: str
    first_commit: str
    second_commit: str


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
        commit_hashes = [summary.commit_hash.strip() for summary in ordered_commits if summary.commit_hash.strip()]
        if commit_hashes:
            run_git(repo_path, ["cherry-pick", *commit_hashes])
        return LocalReorderApplyResult(ok=True, backup_branch=backup_branch)
    except RuntimeError as exc:
        has_conflicts = (
            _has_unmerged_conflicts(repo_path)
            or _is_cherry_pick_in_progress(repo_path)
            or _is_cherry_pick_conflict_error(str(exc))
        )
        if has_conflicts:
            return LocalReorderApplyResult(
                ok=False,
                backup_branch=backup_branch,
                error_message=str(exc),
                conflict_in_progress=True,
            )
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


def _has_unmerged_conflicts(repo_path: str) -> bool:
    try:
        output = run_git(repo_path, ["diff", "--name-only", "--diff-filter=U"])
    except RuntimeError:
        return False
    return bool(output.strip())


def _is_cherry_pick_in_progress(repo_path: str) -> bool:
    try:
        output = run_git(repo_path, ["rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD"])
    except RuntimeError:
        return False
    return bool(output.strip())


def _is_cherry_pick_conflict_error(error_message: str) -> bool:
    lowered = error_message.casefold()
    markers = (
        "could not apply",
        "after resolving the conflicts",
        "git cherry-pick --continue",
        "após resolver os conflitos",
        "apos resolver os conflitos",
        "cherry-pick --continue",
    )
    return any(marker in lowered for marker in markers)


def analyze_local_reorder_dependencies(repo_path: str, ordered_commits: list[CommitSummary]) -> list[ReorderDependencyIssue]:
    ops_by_path: dict[str, list[tuple[int, str, str]]] = {}
    renames: list[tuple[int, str, str, str]] = []

    for index, summary in enumerate(ordered_commits):
        commit_hash = summary.commit_hash.strip()
        if not commit_hash:
            continue
        for status, old_path, new_path in _load_commit_name_status(repo_path, commit_hash):
            if status == "R":
                if old_path and new_path:
                    renames.append((index, old_path, new_path, commit_hash))
                    ops_by_path.setdefault(new_path, []).append((index, "A", commit_hash))
                    ops_by_path.setdefault(old_path, []).append((index, "D", commit_hash))
                continue
            path = new_path or old_path
            if not path:
                continue
            ops_by_path.setdefault(path, []).append((index, status, commit_hash))

    issues: list[ReorderDependencyIssue] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for path, ops in ops_by_path.items():
        add_indexes = [(idx, commit) for idx, status, commit in ops if status == "A"]
        mod_indexes = [(idx, commit) for idx, status, commit in ops if status == "M"]
        del_indexes = [(idx, commit) for idx, status, commit in ops if status == "D"]
        if add_indexes:
            first_add_idx, first_add_commit = min(add_indexes, key=lambda item: item[0])
            for mod_idx, mod_commit in [*mod_indexes, *del_indexes]:
                if mod_idx < first_add_idx:
                    _append_reorder_issue(
                        issues,
                        seen_keys,
                        path=path,
                        reason="modify_before_add",
                        first_commit=mod_commit,
                        second_commit=first_add_commit,
                    )
        if del_indexes:
            first_delete_idx, first_delete_commit = min(del_indexes, key=lambda item: item[0])
            for mod_idx, mod_commit in mod_indexes:
                if mod_idx > first_delete_idx:
                    _append_reorder_issue(
                        issues,
                        seen_keys,
                        path=path,
                        reason="modify_after_delete",
                        first_commit=first_delete_commit,
                        second_commit=mod_commit,
                    )

    for rename_index, old_path, new_path, rename_commit in renames:
        for idx, status, commit_hash in ops_by_path.get(new_path, []):
            if status in {"M", "D"} and idx < rename_index:
                _append_reorder_issue(
                    issues,
                    seen_keys,
                    path=new_path,
                    reason="modify_before_rename",
                    first_commit=commit_hash,
                    second_commit=rename_commit,
                )
        for idx, status, commit_hash in ops_by_path.get(old_path, []):
            if status == "M" and idx > rename_index:
                _append_reorder_issue(
                    issues,
                    seen_keys,
                    path=old_path,
                    reason="modify_after_rename",
                    first_commit=rename_commit,
                    second_commit=commit_hash,
                )

    return issues


def _append_reorder_issue(
    issues: list[ReorderDependencyIssue],
    seen_keys: set[tuple[str, str, str, str]],
    *,
    path: str,
    reason: str,
    first_commit: str,
    second_commit: str,
) -> None:
    key = (path, reason, first_commit, second_commit)
    if key in seen_keys:
        return
    seen_keys.add(key)
    issues.append(
        ReorderDependencyIssue(
            path=path,
            reason=reason,
            first_commit=first_commit,
            second_commit=second_commit,
        )
    )


def _load_commit_name_status(repo_path: str, commit_hash: str) -> list[tuple[str, str, str]]:
    output = run_git(repo_path, ["show", "--name-status", "--pretty=", commit_hash])
    entries: list[tuple[str, str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if not parts:
            continue
        status_raw = parts[0].strip().upper()
        status = status_raw[:1]
        if status == "R":
            if len(parts) < 3:
                continue
            old_path = parts[1].strip()
            new_path = parts[2].strip()
            if old_path and new_path:
                entries.append(("R", old_path, new_path))
            continue
        if status not in {"A", "M", "D"}:
            continue
        if len(parts) < 2:
            continue
        path = parts[1].strip()
        if not path:
            continue
        entries.append((status, path, path))
    return entries
