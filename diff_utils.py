#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk

from models import DiffData, DiffHunk, DiffLineInfo


def parse_hunk_header(header: str) -> tuple[int, int]:
    # Example: @@ -77,4 +77,4 @@
    try:
        parts = header.split()
        old_part = parts[1]
        new_part = parts[2]
        old_line = int(old_part.split(",")[0].lstrip("-"))
        new_line = int(new_part.split(",")[0].lstrip("+"))
        return old_line, new_line
    except (IndexError, ValueError):
        return 0, 0


def parse_hunk_header_full(header: str) -> tuple[int, int, int, int]:
    parts = header.split()
    if len(parts) < 3:
        return 0, 0, 0, 0

    def parse_range(value: str) -> tuple[int, int]:
        if "," in value:
            start, count = value.split(",", 1)
            return int(start), int(count)
        return int(value), 1

    try:
        old_start, old_count = parse_range(parts[1].lstrip("-"))
        new_start, new_count = parse_range(parts[2].lstrip("+"))
    except ValueError:
        return 0, 0, 0, 0
    return old_start, old_count, new_start, new_count


def parse_diff_data(diff_text: str) -> DiffData:
    header_lines: list[str] = []
    hunks: list[DiffHunk] = []
    current: DiffHunk | None = None
    old_line = 0
    new_line = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git") or line.startswith("index ") or line.startswith("---") or line.startswith("+++"):
            header_lines.append(line)
            continue
        if line.startswith("@@"):
            old_start, old_count, new_start, new_count = parse_hunk_header_full(line)
            current = DiffHunk(
                header=line,
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=[],
                raw_lines=[line],
            )
            hunks.append(current)
            old_line = old_start
            new_line = new_start
            continue
        if not current:
            continue
        if line.startswith("\\ No newline at end of file"):
            continue
        if line.startswith("-"):
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="removed",
                old_line=old_line,
                new_line=new_line,
                content=line[1:],
                raw=line,
            )
            old_line += 1
        elif line.startswith("+"):
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="added",
                old_line=old_line,
                new_line=new_line,
                content=line[1:],
                raw=line,
            )
            new_line += 1
        elif line.startswith(" "):
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="context",
                old_line=old_line,
                new_line=new_line,
                content=line[1:],
                raw=line,
            )
            old_line += 1
            new_line += 1
        else:
            continue
        current.lines.append(info)
        current.raw_lines.append(line)

    return DiffData(header_lines=header_lines, hunks=hunks)


def build_line_map(diff_data: DiffData) -> dict[int, DiffLineInfo]:
    line_map: dict[int, DiffLineInfo] = {}
    line_index = 1
    for hunk in diff_data.hunks:
        for info in hunk.lines:
            line_map[line_index] = info
            line_index += 1
    return line_map


def build_patch_for_hunk(diff_data: DiffData, hunk_index: int) -> str | None:
    if hunk_index < 0 or hunk_index >= len(diff_data.hunks):
        return None
    hunk = diff_data.hunks[hunk_index]
    lines = [*diff_data.header_lines, *hunk.raw_lines]
    return "\n".join(lines) + "\n"


def build_patch_for_line(diff_data: DiffData, line_info: DiffLineInfo) -> str | None:
    if line_info.line_type not in ("added", "removed"):
        return None
    if line_info.line_type == "added":
        old_start = line_info.old_line
        new_start = line_info.new_line
        old_count = 0
        new_count = 1
        line = f"+{line_info.content}"
    else:
        old_start = line_info.old_line
        new_start = line_info.new_line
        old_count = 1
        new_count = 0
        line = f"-{line_info.content}"
    header = f"@@ -{old_start},{old_count} +{new_start},{new_count} @@"
    lines = [*diff_data.header_lines, header, line]
    return "\n".join(lines) + "\n"


def line_has_word_markers(line: str) -> bool:
    return "{+" in line or "+}" in line or "[-" in line or "-]" in line or "{-" in line or "-}" in line


def insert_line_with_word_diff(
    widget: tk.Text,
    prefix: str,
    content: str,
    base_tag: str,
    word_diff: bool,
) -> None:
    if not word_diff:
        if base_tag:
            widget.insert(tk.END, f"{prefix}{content}\n", base_tag)
        else:
            widget.insert(tk.END, f"{prefix}{content}\n")
        return
    if base_tag:
        widget.insert(tk.END, prefix, base_tag)
    else:
        widget.insert(tk.END, prefix)
    insert_word_diff_content(widget, content, base_tag)
    widget.insert(tk.END, "\n")


def insert_word_diff_content(widget: tk.Text, content: str, base_tag: str) -> None:
    markers = [
        ("{+", "+}", "added_word"),
        ("[-", "-]", "removed_word"),
        ("{-", "-}", "removed_word"),
    ]
    index = 0
    while index < len(content):
        next_marker = None
        for opener, closer, tag in markers:
            pos = content.find(opener, index)
            if pos == -1:
                continue
            if next_marker is None or pos < next_marker[0]:
                next_marker = (pos, opener, closer, tag)
        if next_marker is None:
            text = content[index:]
            if text:
                if base_tag:
                    widget.insert(tk.END, text, base_tag)
                else:
                    widget.insert(tk.END, text)
            break
        pos, opener, closer, tag = next_marker
        if pos > index:
            if base_tag:
                widget.insert(tk.END, content[index:pos], base_tag)
            else:
                widget.insert(tk.END, content[index:pos])
        end = content.find(closer, pos + len(opener))
        if end == -1:
            if base_tag:
                widget.insert(tk.END, content[pos:], base_tag)
            else:
                widget.insert(tk.END, content[pos:])
            break
        word = content[pos + len(opener) : end]
        tags = (tag, base_tag) if base_tag else (tag,)
        widget.insert(tk.END, word, tags)
        index = end + len(closer)


def render_patch_to_widget(
    widget: tk.Text,
    patch: str,
    read_only: bool,
    show_file_headers: bool,
    word_diff: bool,
) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)

    if not patch.strip():
        widget.insert(tk.END, "(sem diff)")
        if read_only:
            widget.configure(state="disabled")
        return

    old_line = 0
    new_line = 0
    in_hunk = False

    for raw_line in patch.splitlines():
        if raw_line.startswith("diff --git"):
            in_hunk = False
            if show_file_headers:
                try:
                    parts = raw_line.split()
                    path = parts[2][2:]
                except IndexError:
                    path = raw_line
                widget.insert(tk.END, f"\n=== {path} ===\n", "meta")
            continue
        if raw_line.startswith("index ") or raw_line.startswith("---") or raw_line.startswith("+++"):
            continue
        if raw_line.startswith("@@"):
            old_line, new_line = parse_hunk_header(raw_line)
            in_hunk = True
            continue
        if raw_line.startswith("\\ No newline at end of file"):
            continue

        if raw_line.startswith("-"):
            content = raw_line[1:]
            insert_line_with_word_diff(
                widget,
                f"{old_line:>6} - ",
                content,
                base_tag="removed",
                word_diff=word_diff,
            )
            old_line += 1
            continue
        if raw_line.startswith("+"):
            content = raw_line[1:]
            insert_line_with_word_diff(
                widget,
                f"{new_line:>6} + ",
                content,
                base_tag="added",
                word_diff=word_diff,
            )
            new_line += 1
            continue
        if raw_line.startswith(" "):
            content = raw_line[1:]
            insert_line_with_word_diff(
                widget,
                f"{old_line:>6}   ",
                content,
                base_tag="",
                word_diff=word_diff,
            )
            old_line += 1
            new_line += 1
            continue

        if word_diff and in_hunk and line_has_word_markers(raw_line):
            insert_line_with_word_diff(
                widget,
                f"{old_line:>6}   ",
                raw_line,
                base_tag="",
                word_diff=True,
            )
            old_line += 1
            new_line += 1
            continue

        widget.insert(tk.END, raw_line + "\n")

    if read_only:
        widget.configure(state="disabled")
