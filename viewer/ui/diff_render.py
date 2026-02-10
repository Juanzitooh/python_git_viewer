#!/usr/bin/env python3
from __future__ import annotations

import tkinter as tk

from ..core.diff_utils import parse_hunk_header


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
    line_marker: str = "",
    show_hunk_headers: bool = False,
    hunk_marker: str = "",
    hunk_markers: list[str] | None = None,
    append: bool = False,
) -> None:
    widget.configure(state="normal")
    if not append:
        widget.delete("1.0", tk.END)

    if not patch.strip():
        widget.insert(tk.END, "(sem diff)")
        if read_only:
            widget.configure(state="disabled")
        return

    old_line = 0
    new_line = 0
    in_hunk = False

    marker_prefix = f"{line_marker} " if line_marker else ""
    marker_padding = " " * len(marker_prefix)
    fallback_hunk_prefix = f"{hunk_marker} " if hunk_marker else marker_padding
    hunk_index = 0

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
            if show_hunk_headers:
                current_hunk_marker = hunk_marker
                if hunk_markers is not None and hunk_index < len(hunk_markers):
                    current_hunk_marker = hunk_markers[hunk_index]
                if current_hunk_marker:
                    hunk_prefix = f"{current_hunk_marker} "
                else:
                    hunk_prefix = fallback_hunk_prefix
                widget.insert(tk.END, f"{hunk_prefix}\n", "meta")
            hunk_index += 1
            continue
        if raw_line.startswith("\\ No newline at end of file"):
            continue

        if raw_line.startswith("-"):
            content = raw_line[1:]
            insert_line_with_word_diff(
                widget,
                f"{marker_prefix}{old_line:>6} - ",
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
                f"{marker_prefix}{new_line:>6} + ",
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
                f"{marker_padding}{old_line:>6}   ",
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
                f"{marker_padding}{old_line:>6}   ",
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
