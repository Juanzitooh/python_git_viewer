from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from ..core.diff_utils import parse_diff_data, strip_word_diff_markers
from ..core.models import DiffData, DiffHunk, DiffLineInfo
from .theme import get_diff_render_color

LINE_NO_WIDTH = 6
MARKER_COL_WIDTH = 3


@dataclass
class RenderedDiff:
    text: str
    diff_data: DiffData
    line_to_hunk: dict[int, int]
    line_to_info: dict[int, DiffLineInfo]
    line_kinds: list[str]


LineMarkerResolver = Callable[[DiffLineInfo], str]
HunkMarkerResolver = Callable[[int, DiffHunk], str]


_LINE_PREFIX_WITH_MARKER_RE = re.compile(r"^\s*\d+\s+.{3}\s[+\-# ]\s")
_LINE_PREFIX_NO_MARKER_RE = re.compile(r"^\s*\d+\s+[+\-# ]\s")
_HUNK_PREFIX_WITH_MARKER_RE = re.compile(r"^\s*\d+\s+.{3}\s@\s")
_HUNK_PREFIX_NO_MARKER_RE = re.compile(r"^\s*\d+\s+@\s")
_META_PREFIX_WITH_MARKER_RE = re.compile(r"^\s*.{3}\s#\s")
_META_PREFIX_NO_MARKER_RE = re.compile(r"^\s*#\s")
_BOXED_PREFIX_RE = re.compile(r"^\[\s*\d*\s*\]\s+\[[^\]]{1,4}\]\s")


def sanitize_copied_diff_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.replace("\u2029", "\n")
    cleaned_lines: list[str] = []
    for line in normalized.split("\n"):
        clean = _BOXED_PREFIX_RE.sub("", line)
        clean = _LINE_PREFIX_WITH_MARKER_RE.sub("", clean)
        clean = _LINE_PREFIX_NO_MARKER_RE.sub("", clean)
        clean = _HUNK_PREFIX_WITH_MARKER_RE.sub("", clean)
        clean = _HUNK_PREFIX_NO_MARKER_RE.sub("", clean)
        clean = _META_PREFIX_WITH_MARKER_RE.sub("", clean)
        clean = _META_PREFIX_NO_MARKER_RE.sub("", clean)
        clean = strip_word_diff_markers(clean)
        cleaned_lines.append(clean)
    return "\n".join(cleaned_lines)


def _copy_sanitized_selection(widget: QPlainTextEdit) -> None:
    cursor = widget.textCursor()
    if not cursor.hasSelection():
        return
    payload = sanitize_copied_diff_text(cursor.selectedText())
    QApplication.clipboard().setText(payload)


def install_diff_copy_shortcut(widget: QPlainTextEdit) -> None:
    shortcut = getattr(widget, "_diff_copy_shortcut", None)
    if shortcut is None:
        shortcut = QShortcut(QKeySequence.StandardKey.Copy, widget)
        setattr(widget, "_diff_copy_shortcut", shortcut)
    if not getattr(shortcut, "_diff_copy_connected", False):
        shortcut.activated.connect(lambda: _copy_sanitized_selection(widget))
        setattr(shortcut, "_diff_copy_connected", True)


def _normalize_marker(marker: str) -> str:
    value = marker.strip()
    if not value:
        return " " * MARKER_COL_WIDTH
    if len(value) >= MARKER_COL_WIDTH:
        return value[:MARKER_COL_WIDTH]
    return value.ljust(MARKER_COL_WIDTH)


def _format_meta_line(content: str, *, include_marker_column: bool) -> str:
    if include_marker_column:
        return f"{'':>{LINE_NO_WIDTH}}  {'':<{MARKER_COL_WIDTH}} # {content}"
    return f"{'':>{LINE_NO_WIDTH}}  # {content}"


def _format_hunk_line(marker: str, header: str, *, include_marker_column: bool) -> str:
    if include_marker_column:
        return f"{'':>{LINE_NO_WIDTH}}  {_normalize_marker(marker)} @ Secao: {header}"
    return f"{'':>{LINE_NO_WIDTH}}  @ {header}"


def _format_change_line(
    marker: str,
    number: int,
    sign: str,
    content: str,
    *,
    include_marker_column: bool,
) -> str:
    if include_marker_column:
        return f"{number:>{LINE_NO_WIDTH}}  {_normalize_marker(marker)} {sign} {content}"
    return f"{number:>{LINE_NO_WIDTH}}  {sign} {content}"


def _render_sign(line_info: DiffLineInfo) -> str:
    if line_info.line_type == "removed":
        return "-"
    if line_info.line_type == "added":
        return "+"
    return " "


def build_rendered_diff(
    patch: str,
    *,
    line_marker_resolver: LineMarkerResolver | None = None,
    hunk_marker_resolver: HunkMarkerResolver | None = None,
    show_header_lines: bool = True,
    include_marker_column: bool = True,
    word_diff_plain: bool = False,
) -> RenderedDiff:
    clean_patch = patch.strip("\n")
    if not clean_patch:
        return RenderedDiff(
            text="(sem diff)",
            diff_data=DiffData(header_lines=[], hunks=[]),
            line_to_hunk={},
            line_to_info={},
            line_kinds=["meta"],
        )

    diff_data = parse_diff_data(clean_patch, word_diff_plain=word_diff_plain)
    output_lines: list[str] = []
    line_to_hunk: dict[int, int] = {}
    line_to_info: dict[int, DiffLineInfo] = {}
    line_kinds: list[str] = []
    line_no = 0

    if show_header_lines:
        for header_line in diff_data.header_lines:
            output_lines.append(_format_meta_line(header_line, include_marker_column=include_marker_column))
            line_kinds.append("meta")
            line_no += 1

    for hunk_index, hunk in enumerate(diff_data.hunks):
        hunk_lines = list(hunk.lines)
        hunk_marker = ""
        if hunk_marker_resolver is not None:
            hunk_marker = hunk_marker_resolver(hunk_index, hunk)
        if include_marker_column:
            output_lines.append(
                _format_hunk_line(hunk_marker, hunk.header, include_marker_column=include_marker_column)
            )
            line_kinds.append("hunk")
            line_no += 1
            line_to_hunk[line_no] = hunk_index

        for line_info in hunk_lines:
            marker = ""
            if line_marker_resolver is not None:
                marker = line_marker_resolver(line_info)
            if line_info.line_type == "removed":
                number = line_info.old_line
            elif line_info.line_type == "added":
                number = line_info.new_line
            else:
                number = line_info.new_line
            sign = _render_sign(line_info)
            output_lines.append(
                _format_change_line(
                    marker,
                    number,
                    sign,
                    line_info.content,
                    include_marker_column=include_marker_column,
                )
            )
            line_kinds.append(line_info.line_type)
            line_no += 1
            line_to_hunk[line_no] = hunk_index
            line_to_info[line_no] = line_info

    return RenderedDiff(
        text="\n".join(output_lines),
        diff_data=diff_data,
        line_to_hunk=line_to_hunk,
        line_to_info=line_to_info,
        line_kinds=line_kinds,
    )


class DiffSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent_document) -> None:
        super().__init__(parent_document)
        self._line_kinds: list[str] = []

        self._added_line = QTextCharFormat()
        self._removed_line = QTextCharFormat()
        self._context_line = QTextCharFormat()
        self._hunk_line = QTextCharFormat()
        self._meta_line = QTextCharFormat()
        self._added_word = QTextCharFormat()
        self._removed_word = QTextCharFormat()
        self._refresh_theme_colors()

    def _refresh_theme_colors(self) -> None:
        app = QApplication.instance()
        if app is not None:
            base = app.palette().color(QPalette.ColorRole.Base)
            is_light = int(base.lightness()) >= 128
            theme_overrides = app.property("gv_theme_overrides")
        else:
            is_light = True
            theme_overrides = None

        added_line = get_diff_render_color(
            "line_added",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#22C55E"
        removed_line = get_diff_render_color(
            "line_removed",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#EF4444"
        context_line = get_diff_render_color(
            "line_context",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#FFFFFF"
        hunk_line = get_diff_render_color(
            "line_hunk",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#60A5FA"
        meta_line = get_diff_render_color(
            "line_meta",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#9CA3AF"
        added_word_fg = get_diff_render_color(
            "word_added_fg",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#86EFAC"
        added_word_bg = get_diff_render_color(
            "word_added_bg",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#14532D"
        removed_word_fg = get_diff_render_color(
            "word_removed_fg",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#FCA5A5"
        removed_word_bg = get_diff_render_color(
            "word_removed_bg",
            is_light=is_light,
            theme_overrides=theme_overrides,
        ) or "#7F1D1D"

        self._added_line = QTextCharFormat()
        self._added_line.setForeground(QColor(added_line))

        self._removed_line = QTextCharFormat()
        self._removed_line.setForeground(QColor(removed_line))

        self._context_line = QTextCharFormat()
        self._context_line.setForeground(QColor(context_line))

        self._hunk_line = QTextCharFormat()
        self._hunk_line.setForeground(QColor(hunk_line))

        self._meta_line = QTextCharFormat()
        self._meta_line.setForeground(QColor(meta_line))

        self._added_word = QTextCharFormat()
        self._added_word.setForeground(QColor(added_word_fg))
        self._added_word.setBackground(QColor(added_word_bg))

        self._removed_word = QTextCharFormat()
        self._removed_word.setForeground(QColor(removed_word_fg))
        self._removed_word.setBackground(QColor(removed_word_bg))

    def set_line_kinds(self, line_kinds: list[str]) -> None:
        self._refresh_theme_colors()
        self._line_kinds = list(line_kinds)
        self.rehighlight()

    def _highlight_word_segments(self, text: str, opener: str, closer: str, fmt: QTextCharFormat) -> None:
        start = 0
        while True:
            left = text.find(opener, start)
            if left < 0:
                return
            right = text.find(closer, left + len(opener))
            if right < 0:
                return
            self.setFormat(left, len(opener), self._meta_line)
            inner_start = left + len(opener)
            inner_len = max(0, right - inner_start)
            if inner_len > 0:
                self.setFormat(inner_start, inner_len, fmt)
            self.setFormat(right, len(closer), self._meta_line)
            start = right + len(closer)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        block_index = self.currentBlock().blockNumber()
        line_kind = self._line_kinds[block_index] if 0 <= block_index < len(self._line_kinds) else ""
        if line_kind == "added":
            self.setFormat(0, len(text), self._added_line)
        elif line_kind == "removed":
            self.setFormat(0, len(text), self._removed_line)
        elif line_kind == "context":
            self.setFormat(0, len(text), self._context_line)
        elif line_kind == "hunk":
            self.setFormat(0, len(text), self._hunk_line)
        elif line_kind == "meta":
            self.setFormat(0, len(text), self._meta_line)

        self._highlight_word_segments(text, "{+", "+}", self._added_word)
        self._highlight_word_segments(text, "[-", "-]", self._removed_word)
        self._highlight_word_segments(text, "{-", "-}", self._removed_word)


def install_diff_highlighter(widget: QPlainTextEdit) -> DiffSyntaxHighlighter:
    current = getattr(widget, "_diff_highlighter", None)
    if current is None or current.document() is not widget.document():
        current = DiffSyntaxHighlighter(widget.document())
        widget._diff_highlighter = current
    return current


def render_diff_into_widget(
    widget: QPlainTextEdit,
    patch: str,
    *,
    line_marker_resolver: LineMarkerResolver | None = None,
    hunk_marker_resolver: HunkMarkerResolver | None = None,
    show_header_lines: bool = True,
    include_marker_column: bool = True,
    word_diff_plain: bool = False,
) -> RenderedDiff:
    install_diff_copy_shortcut(widget)
    rendered = build_rendered_diff(
        patch,
        line_marker_resolver=line_marker_resolver,
        hunk_marker_resolver=hunk_marker_resolver,
        show_header_lines=show_header_lines,
        include_marker_column=include_marker_column,
        word_diff_plain=word_diff_plain,
    )
    highlighter = install_diff_highlighter(widget)
    widget.setPlainText(rendered.text)
    highlighter.set_line_kinds(rendered.line_kinds)
    return rendered
