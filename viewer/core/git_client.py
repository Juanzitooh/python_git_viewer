#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from .models import CommitFilters, CommitInfo, CommitSummary, FileStat

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
TEXT_FILTER_SCAN_MIN = 800
TEXT_FILTER_SCAN_MAX = 8000


def run_git(repo_path: str, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, *args],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "(sem detalhes)"
        raise RuntimeError(f"git falhou: {stderr}")
    return result.stdout


def is_git_repo(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", path, "rev-parse", "--git-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def parse_numstat(output: str) -> tuple[tuple[FileStat, ...], int, int]:
    file_stats: list[FileStat] = []
    total_added = 0
    total_deleted = 0
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path = parts[0], parts[1], parts[2]
        is_binary = added_raw == "-" or deleted_raw == "-"
        if is_binary:
            added = 0
            deleted = 0
        else:
            try:
                added = int(added_raw)
                deleted = int(deleted_raw)
            except ValueError:
                added = 0
                deleted = 0
        total_added += added
        total_deleted += deleted
        file_stats.append(FileStat(path=path, added=added, deleted=deleted, is_binary=is_binary))
    return tuple(file_stats), total_added, total_deleted


def build_log_args(limit: int, skip: int, filters: CommitFilters | None) -> list[str]:
    args = [
        "log",
        f"--max-count={limit}",
        f"--skip={skip}",
        "--date=iso",
        f"--pretty=format:%H{FIELD_SEP}%s{FIELD_SEP}%an{FIELD_SEP}%ad{FIELD_SEP}%ct{RECORD_SEP}",
    ]
    if not filters:
        return args
    pattern_count = 0
    if filters.text:
        pattern_count += 1
    if filters.author:
        pattern_count += 1
    if pattern_count > 1:
        args.append("--all-match")
    if filters.text:
        args.append("--regexp-ignore-case")
        args.append("--fixed-strings")
        args.append(f"--grep={filters.text}")
    if filters.author:
        args.append(f"--author={filters.author}")
    if filters.since:
        args.append(f"--since={filters.since}")
    if filters.until:
        args.append(f"--until={filters.until}")
    if filters.ref:
        args.append(filters.ref)
    if filters.path:
        args.extend(["--", filters.path])
    return args


def _build_log_scan_args(scan_limit: int, filters: CommitFilters | None) -> list[str]:
    args = [
        "log",
        f"--max-count={scan_limit}",
        "--date=iso",
        "--name-only",
        f"--pretty=format:%H{FIELD_SEP}%s{FIELD_SEP}%an{FIELD_SEP}%ad{FIELD_SEP}%ct",
    ]
    if not filters:
        return args
    if filters.author:
        args.append(f"--author={filters.author}")
    if filters.since:
        args.append(f"--since={filters.since}")
    if filters.until:
        args.append(f"--until={filters.until}")
    if filters.ref:
        args.append(filters.ref)
    if filters.path:
        args.extend(["--", filters.path])
    return args


def _is_scan_header_line(line: str) -> bool:
    if FIELD_SEP not in line:
        return False
    fields = line.split(FIELD_SEP)
    if len(fields) < 5:
        return False
    commit_hash = fields[0].strip()
    if len(commit_hash) < 7:
        return False
    lowered = commit_hash.lower()
    return all(char in "0123456789abcdef" for char in lowered)


def _parse_scan_summaries(log_output: str) -> list[tuple[CommitSummary, list[str]]]:
    parsed: list[tuple[CommitSummary, list[str]]] = []
    current_summary: CommitSummary | None = None
    current_files: list[str] = []
    for raw_line in log_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_scan_header_line(line):
            if current_summary is not None:
                parsed.append((current_summary, current_files))
            fields = line.split(FIELD_SEP)
            commit_hash = fields[0].strip()
            subject = fields[1] if len(fields) > 1 else ""
            author = fields[2] if len(fields) > 2 else ""
            date = fields[3] if len(fields) > 3 else ""
            timestamp_raw = fields[4] if len(fields) > 4 else ""
            try:
                timestamp = int(timestamp_raw)
            except ValueError:
                timestamp = 0
            current_summary = CommitSummary(
                commit_hash=commit_hash,
                subject=subject,
                author=author,
                date=date,
                timestamp=timestamp,
            )
            current_files = []
            continue
        if current_summary is None:
            continue
        if line not in current_files:
            current_files.append(line)
    if current_summary is not None:
        parsed.append((current_summary, current_files))
    return parsed


def _summary_matches_text(summary: CommitSummary, files: list[str], text: str) -> bool:
    needle = text.casefold()
    if not needle:
        return True
    if needle in summary.commit_hash.casefold():
        return True
    if needle in summary.subject.casefold():
        return True
    if needle in summary.author.casefold():
        return True
    if needle in summary.date.casefold():
        return True
    for path in files:
        if needle in path.casefold():
            return True
    return False


def load_commit_summaries(
    repo_path: str,
    limit: int,
    skip: int = 0,
    filters: CommitFilters | None = None,
) -> list[CommitSummary]:
    if filters and filters.text.strip():
        target_count = max(1, skip + limit)
        scan_limit = max(TEXT_FILTER_SCAN_MIN, target_count * 6)
        scan_limit = min(TEXT_FILTER_SCAN_MAX, scan_limit)
        log_output = run_git(repo_path, _build_log_scan_args(scan_limit, filters))
        matched: list[CommitSummary] = []
        text_value = filters.text.strip()
        for summary, files in _parse_scan_summaries(log_output):
            if not _summary_matches_text(summary, files, text_value):
                continue
            matched.append(summary)
        if skip <= 0:
            return matched[:limit]
        return matched[skip : skip + limit]

    log_output = run_git(repo_path, build_log_args(limit, skip, filters))
    summaries: list[CommitSummary] = []
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
        summaries.append(
            CommitSummary(
                commit_hash=commit_hash,
                subject=subject,
                author=author,
                date=date,
                timestamp=timestamp,
            )
        )
    return summaries


def load_commit_details(repo_path: str, commit_hash: str) -> CommitInfo:
    detail_output = run_git(
        repo_path,
        [
            "show",
            "--date=iso",
            "--no-patch",
            f"--pretty=format:%H{FIELD_SEP}%an{FIELD_SEP}%ad{FIELD_SEP}%s{FIELD_SEP}%b",
            commit_hash,
        ],
    )
    fields = detail_output.split(FIELD_SEP)
    if len(fields) < 5:
        raise RuntimeError("Falha ao obter detalhes do commit.")
    commit_hash, author, date, subject, body = fields[0], fields[1], fields[2], fields[3], fields[4]
    numstat_output = run_git(repo_path, ["show", "--numstat", "--format=", commit_hash])
    file_stats, total_added, total_deleted = parse_numstat(numstat_output)
    return CommitInfo(
        commit_hash=commit_hash,
        author=author,
        date=date,
        subject=subject,
        body=body.strip(),
        file_stats=file_stats,
        total_added=total_added,
        total_deleted=total_deleted,
    )
