#!/usr/bin/env python3
from __future__ import annotations

from .models import DiffData, DiffHunk, DiffLineInfo


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


def _unwrap_word_diff_plain_line(line: str) -> str:
    # `git diff --word-diff=plain` pode encapsular linhas inteiras.
    # Exemplos: `{+linha nova+}`, `[-linha antiga-]`, `{-linha antiga-}`
    if line.startswith("{+") and line.endswith("+}"):
        return line[2:-2]
    if line.startswith("[-") and line.endswith("-]"):
        return line[2:-2]
    if line.startswith("{-") and line.endswith("-}"):
        return line[2:-2]
    return line


def _contains_word_diff_markers(line: str) -> bool:
    return "{+" in line or "[-" in line or "{-" in line


def _split_word_diff_plain_line(line: str) -> tuple[str, str, bool]:
    old_parts: list[str] = []
    new_parts: list[str] = []
    index = 0
    changed = False
    length = len(line)
    while index < length:
        if line.startswith("{+", index):
            end = line.find("+}", index + 2)
            if end < 0:
                text = line[index:]
                old_parts.append(text)
                new_parts.append(text)
                break
            new_parts.append(line[index + 2 : end])
            index = end + 2
            changed = True
            continue
        if line.startswith("[-", index):
            end = line.find("-]", index + 2)
            if end < 0:
                text = line[index:]
                old_parts.append(text)
                new_parts.append(text)
                break
            old_parts.append(line[index + 2 : end])
            index = end + 2
            changed = True
            continue
        if line.startswith("{-", index):
            end = line.find("-}", index + 2)
            if end < 0:
                text = line[index:]
                old_parts.append(text)
                new_parts.append(text)
                break
            old_parts.append(line[index + 2 : end])
            index = end + 2
            changed = True
            continue
        char = line[index]
        old_parts.append(char)
        new_parts.append(char)
        index += 1
    return "".join(old_parts), "".join(new_parts), changed


def strip_word_diff_markers(text: str) -> str:
    """Remove marcadores de --word-diff=plain preservando apenas o conteudo."""
    if not text:
        return ""
    cleaned = text
    cleaned = cleaned.replace("{+", "")
    cleaned = cleaned.replace("+}", "")
    cleaned = cleaned.replace("[-", "")
    cleaned = cleaned.replace("-]", "")
    cleaned = cleaned.replace("{-", "")
    cleaned = cleaned.replace("-}", "")
    return cleaned


def parse_diff_data(diff_text: str, *, word_diff_plain: bool = False) -> DiffData:
    header_lines: list[str] = []
    hunks: list[DiffHunk] = []
    current: DiffHunk | None = None
    old_line = 0
    new_line = 0
    word_diff_plain_mode = bool(word_diff_plain)

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
        if word_diff_plain_mode:
            prefix = ""
            payload = line
            if payload and payload[0] in {"+", "-", " "}:
                prefix = payload[0]
                payload = payload[1:]
            if payload.startswith("{+") and payload.endswith("+}"):
                content = payload[2:-2]
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="added",
                    old_line=old_line,
                    new_line=new_line,
                    content=content,
                    raw=line,
                )
                current.lines.append(info)
                current.raw_lines.append(line)
                new_line += 1
                continue
            if (payload.startswith("[-") and payload.endswith("-]")) or (
                payload.startswith("{-") and payload.endswith("-}")
            ):
                content = payload[2:-2]
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="removed",
                    old_line=old_line,
                    new_line=new_line,
                    content=content,
                    raw=line,
                )
                current.lines.append(info)
                current.raw_lines.append(line)
                old_line += 1
                continue
            old_content, new_content, changed = _split_word_diff_plain_line(payload)
            if changed and old_content != new_content:
                if prefix in {"+", "-"} and payload.startswith(" "):
                    old_content = f"{prefix}{old_content}"
                    new_content = f"{prefix}{new_content}"
                base_old_line = old_line
                base_new_line = new_line
                removed = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="removed",
                    old_line=base_old_line,
                    new_line=base_new_line,
                    content=old_content,
                    raw=f"-{old_content}",
                )
                current.lines.append(removed)
                current.raw_lines.append(f"-{old_content}")
                added = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="added",
                    old_line=base_old_line,
                    new_line=base_new_line,
                    content=new_content,
                    raw=f"+{new_content}",
                )
                current.lines.append(added)
                current.raw_lines.append(f"+{new_content}")
                old_line += 1
                new_line += 1
                continue
            normalized_content = strip_word_diff_markers(payload)
            if prefix == "+":
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="added",
                    old_line=old_line,
                    new_line=new_line,
                    content=normalized_content,
                    raw=line,
                )
                current.lines.append(info)
                current.raw_lines.append(line)
                new_line += 1
                continue
            if prefix == "-":
                info = DiffLineInfo(
                    hunk_index=len(hunks) - 1,
                    line_type="removed",
                    old_line=old_line,
                    new_line=new_line,
                    content=normalized_content,
                    raw=line,
                )
                current.lines.append(info)
                current.raw_lines.append(line)
                old_line += 1
                continue
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="context",
                old_line=old_line,
                new_line=new_line,
                content=normalized_content,
                raw=line,
            )
            current.lines.append(info)
            current.raw_lines.append(line)
            old_line += 1
            new_line += 1
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
        elif line.startswith("{+") or line.startswith("{-"):
            # `git diff --word-diff=plain` pode gerar linhas sem prefixo `+/-`,
            # por exemplo `{+texto+}` para adicao de linha inteira.
            content = _unwrap_word_diff_plain_line(line)
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="added" if line.startswith("{+") else "removed",
                old_line=old_line,
                new_line=new_line,
                content=content,
                raw=line,
            )
            if line.startswith("{+"):
                new_line += 1
            else:
                old_line += 1
        elif line.startswith("[-"):
            content = _unwrap_word_diff_plain_line(line)
            info = DiffLineInfo(
                hunk_index=len(hunks) - 1,
                line_type="removed",
                old_line=old_line,
                new_line=new_line,
                content=content,
                raw=line,
            )
            old_line += 1
        else:
            continue
        current.lines.append(info)
        current.raw_lines.append(line)

    return DiffData(header_lines=header_lines, hunks=hunks)


def build_line_map(diff_data: DiffData, include_hunk_headers: bool = False) -> dict[int, DiffLineInfo]:
    line_map: dict[int, DiffLineInfo] = {}
    line_index = 1
    for hunk in diff_data.hunks:
        if include_hunk_headers:
            line_index += 1
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


def build_read_mode_diff(diff_text: str, *, threshold: int, max_lines: int) -> tuple[str, bool]:
    lines = diff_text.splitlines()
    total = len(lines)
    if total <= threshold:
        return diff_text, False
    if max_lines <= 0:
        return diff_text, False
    head = max_lines // 2
    tail = max_lines - head
    if head + tail >= total:
        return diff_text, False
    omitted = total - head - tail
    marker = f"... ({omitted} linhas omitidas no modo leitura) ..."
    preview = lines[:head] + [marker] + lines[-tail:]
    return "\n".join(preview) + "\n", True
