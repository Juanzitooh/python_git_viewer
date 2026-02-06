#!/usr/bin/env python3
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class FileStat:
    path: str
    added: int
    deleted: int
    is_binary: bool


@dataclasses.dataclass(frozen=True)
class CommitInfo:
    commit_hash: str
    author: str
    date: str
    subject: str
    body: str
    file_stats: tuple[FileStat, ...]
    total_added: int
    total_deleted: int


@dataclasses.dataclass(frozen=True)
class CommitSummary:
    commit_hash: str
    subject: str


@dataclasses.dataclass
class CommitFilters:
    text: str = ""
    author: str = ""
    path: str = ""
    since: str = ""
    until: str = ""
    ref: str = ""
    repo_status: str = ""

    def is_active(self) -> bool:
        return any([self.text, self.author, self.path, self.since, self.until, self.ref, self.repo_status])


@dataclasses.dataclass(frozen=True)
class DiffLineInfo:
    hunk_index: int
    line_type: str
    old_line: int
    new_line: int
    content: str
    raw: str


@dataclasses.dataclass
class DiffHunk:
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLineInfo]
    raw_lines: list[str]


@dataclasses.dataclass
class DiffData:
    header_lines: list[str]
    hunks: list[DiffHunk]
