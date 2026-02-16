from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from ..core.diff_utils import parse_diff_data, strip_word_diff_markers
from ..core.models import DiffHunk, DiffLineInfo
from .theme import get_diff_kind_color


LineMarkerResolver = Callable[[DiffLineInfo], str]
HunkMarkerResolver = Callable[[int, DiffHunk], str]
ROW_KIND_ROLE = Qt.ItemDataRole.UserRole + 41
HUNK_INDEX_ROLE = Qt.ItemDataRole.UserRole + 42
LINE_INFO_ROLE = Qt.ItemDataRole.UserRole + 43
SCOPE_ROLE = Qt.ItemDataRole.UserRole + 44
HUNK_HEADER_ROLE = Qt.ItemDataRole.UserRole + 45


class DiffColumnsView(QTreeWidget):
    def __init__(self, *, include_marker_column: bool, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("DiffColumnsView")
        self.include_marker_column = include_marker_column
        self._marker_column_width = 42
        self._line_column_width = 56
        self._content_column_width = 1200
        self._content_wrap_enabled = True
        if include_marker_column:
            self.setColumnCount(3)
            self.setHeaderLabels(["Sel", "Linha", "Conteudo"])
            self._line_column = 1
            self._old_line_column = 1
            self._new_line_column = -1
            self._marker_column = 0
            self._sign_column = -1
            self._content_column = 2
        else:
            self.setColumnCount(3)
            self.setHeaderLabels(["Ant", "Nov", "Conteudo"])
            self._line_column = 0
            self._old_line_column = 0
            self._new_line_column = 1
            self._marker_column = -1
            self._sign_column = -1
            self._content_column = 2

        self.setRootIsDecorated(False)
        self.setItemsExpandable(False)
        self.setUniformRowHeights(False)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.setAutoScroll(False)
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setIndentation(0)
        self.setSortingEnabled(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(
            self._content_column,
            QHeaderView.ResizeMode.Stretch if self._content_wrap_enabled else QHeaderView.ResizeMode.Interactive,
        )
        self.header().setSectionResizeMode(self._old_line_column, QHeaderView.ResizeMode.Fixed)
        if not self.include_marker_column:
            self.header().setSectionResizeMode(self._new_line_column, QHeaderView.ResizeMode.Fixed)
        self.header().setSectionsMovable(False)
        self.header().setSectionsClickable(False)
        self.header().setMinimumSectionSize(24)
        if self.include_marker_column:
            self.header().setSectionResizeMode(self._marker_column, QHeaderView.ResizeMode.Fixed)
        self.setFont(QFont("JetBrains Mono", 10))

        self._enforce_column_layout()

        self._internal_context_menu_enabled = True
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)
        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        self._copy_shortcut.activated.connect(self._copy_selected_content)
        self.itemSelectionChanged.connect(self._apply_selection_colors)
        self.setItemDelegate(DiffWrapDelegate(self))
        self._apply_unified_theme()

    def set_internal_context_menu_enabled(self, enabled: bool) -> None:
        self._internal_context_menu_enabled = bool(enabled)

    def _on_context_menu_requested(self, point: QPoint) -> None:
        if not self._internal_context_menu_enabled:
            return
        self._show_context_menu(point)

    def _enforce_column_layout(self) -> None:
        self.setColumnHidden(self._old_line_column, False)
        self.setColumnWidth(self._old_line_column, self._line_column_width)
        self.header().resizeSection(self._old_line_column, self._line_column_width)
        if not self.include_marker_column and self._new_line_column >= 0:
            self.setColumnHidden(self._new_line_column, False)
            self.setColumnWidth(self._new_line_column, self._line_column_width)
            self.header().resizeSection(self._new_line_column, self._line_column_width)
        if self.include_marker_column:
            self.setColumnHidden(self._marker_column, False)
            self.setColumnWidth(self._marker_column, self._marker_column_width)
            self.header().resizeSection(self._marker_column, self._marker_column_width)
        self.setColumnHidden(self._content_column, False)
        if self._content_wrap_enabled:
            self.header().setSectionResizeMode(self._content_column, QHeaderView.ResizeMode.Stretch)
        else:
            self.header().setSectionResizeMode(self._content_column, QHeaderView.ResizeMode.Interactive)
            content_width = max(self._content_column_width, self.columnWidth(self._content_column))
            self.setColumnWidth(self._content_column, content_width)

    def _refresh_wrapped_layout(self) -> None:
        if self.topLevelItemCount() <= 0:
            return
        self.doItemsLayout()
        self.viewport().update()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._enforce_column_layout()
        QTimer.singleShot(0, self._refresh_wrapped_layout)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._enforce_column_layout()
        self._refresh_wrapped_layout()

    def _apply_unified_theme(self) -> None:
        self.setStyleSheet(
            """
            QTreeView {
                gridline-color: palette(mid);
            }
            QTreeView::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QTreeView::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid palette(mid);
                border-radius: 2px;
                background: palette(base);
            }
            QTreeView::indicator:checked {
                border-color: palette(highlight);
                background: palette(highlight);
            }
            QTreeView::indicator:indeterminate {
                border-color: palette(highlight);
                background: palette(midlight);
            }
            """
        )

    @staticmethod
    def _current_theme_overrides() -> object | None:
        app = QApplication.instance()
        if app is None:
            return None
        return app.property("gv_theme_overrides")

    def _copy_selected_content(self) -> None:
        selected = self.selectedItems()
        if not selected:
            return
        ordered = sorted(selected, key=lambda item: self.indexOfTopLevelItem(item))
        payload_lines: list[str] = []
        for item in ordered:
            row_kind = item.data(0, ROW_KIND_ROLE)
            kind = str(row_kind).strip() if row_kind is not None else ""
            if kind not in {"added", "removed", "context", "modified"}:
                continue
            content = item.text(self._content_column)
            payload_lines.append(strip_word_diff_markers(content))
        if not payload_lines:
            return
        QApplication.clipboard().setText("\n".join(payload_lines))

    def _show_context_menu(self, point: QPoint) -> None:
        item = self.itemAt(point)
        if item is not None and not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
            self.setCurrentItem(item)
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar conteudo selecionado")
        copy_action.setEnabled(bool(self.selectedItems()))
        selected_action = menu.exec(self.viewport().mapToGlobal(point))
        if selected_action is copy_action:
            self._copy_selected_content()

    def _row_color_for_kind(self, kind: str) -> QColor | None:
        base = self.palette().color(QPalette.ColorRole.Base)
        is_light = int(base.lightness()) >= 128
        color_value = get_diff_kind_color(
            kind,
            is_light=is_light,
            theme_overrides=self._current_theme_overrides(),
        )
        return QColor(color_value) if color_value else None

    def _apply_selection_colors(self) -> None:
        default_color = self.palette().color(QPalette.ColorRole.Text)
        selected_color = self.palette().color(QPalette.ColorRole.HighlightedText)
        for row_index in range(self.topLevelItemCount()):
            item = self.topLevelItem(row_index)
            if item is None:
                continue
            if item.isSelected():
                color = selected_color
            else:
                kind_value = item.data(0, ROW_KIND_ROLE)
                kind = str(kind_value).strip() if kind_value is not None else ""
                color = self._row_color_for_kind(kind) or default_color
            for column in range(item.columnCount()):
                # Mantem o indicador de checkbox nativo visivel na coluna de marcador.
                if self.include_marker_column and column == self._marker_column:
                    continue
                item.setForeground(column, color)


class DiffWrapDelegate(QStyledItemDelegate):
    def __init__(self, view: DiffColumnsView) -> None:
        super().__init__(view)
        self._view = view

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideNone
        if index.column() == self._view._content_column:
            option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        else:
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.WrapText

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:  # type: ignore[override]
        base = super().sizeHint(option, index)
        if index.column() != self._view._content_column:
            return base
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if not text:
            return base
        width = int(self._view.columnWidth(self._view._content_column))
        if width <= 32:
            available = int(self._view.viewport().width())
            available -= int(self._view._line_column_width) + 8
            if not self._view.include_marker_column:
                available -= int(self._view._line_column_width)
            if self._view.include_marker_column:
                available -= int(self._view._marker_column_width)
            width = max(160, available)
        else:
            width = max(24, width - 8)
        bounds = option.fontMetrics.boundingRect(
            0,
            0,
            width,
            100_000,
            int(Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextExpandTabs),
            text,
        )
        return QSize(base.width(), max(base.height(), bounds.height() + 6))


def _make_item(values: list[str], *, bold: bool = False, kind: str = "") -> QTreeWidgetItem:
    item = QTreeWidgetItem(values)
    item.setData(0, ROW_KIND_ROLE, kind)
    if bold:
        for index in range(len(values)):
            font = item.font(index)
            font.setBold(True)
            item.setFont(index, font)
    return item


def _apply_marker_checkbox(item: QTreeWidgetItem, marker_column: int, marker: str) -> None:
    normalized = marker.strip()
    if normalized not in {"[x]", "[ ]", "[~]"}:
        item.setText(marker_column, "")
        return
    item.setText(marker_column, "")
    flags = (
        item.flags()
        | Qt.ItemFlag.ItemIsEnabled
        | Qt.ItemFlag.ItemIsSelectable
        | Qt.ItemFlag.ItemIsUserCheckable
    )
    item.setFlags(flags)
    if normalized == "[x]":
        item.setCheckState(marker_column, Qt.CheckState.Checked)
        return
    if normalized == "[~]":
        item.setCheckState(marker_column, Qt.CheckState.PartiallyChecked)
        return
    item.setCheckState(marker_column, Qt.CheckState.Unchecked)


def _is_modified_pair(removed_line: DiffLineInfo, added_line: DiffLineInfo) -> bool:
    if removed_line.line_type != "removed" or added_line.line_type != "added":
        return False
    return int(removed_line.old_line) == int(added_line.new_line)


def _hunk_context_preview(hunk: DiffHunk) -> str:
    if "@@" in hunk.header:
        parts = hunk.header.split("@@")
        if len(parts) >= 3:
            trailer = parts[2].strip()
            if trailer:
                return trailer
    for line_info in hunk.lines:
        if line_info.line_type == "context":
            value = line_info.content.strip()
            if value:
                return value
    return hunk.header


def _apply_line_color(
    item: QTreeWidgetItem,
    *,
    line_type: str,
    is_light: bool,
    theme_overrides: object | None = None,
) -> None:
    color_value = get_diff_kind_color(
        line_type,
        is_light=is_light,
        theme_overrides=theme_overrides,
    )
    if not color_value:
        return
    color = QColor(color_value)
    column_count = item.columnCount()
    for column in range(column_count):
        item.setForeground(column, color)


def _apply_line_background(
    item: QTreeWidgetItem,
    *,
    line_type: str,
    is_light: bool,
    theme_overrides: object | None = None,
) -> None:
    if line_type not in {"added", "removed", "modified", "hunk"}:
        return
    color_value = get_diff_kind_color(
        line_type,
        is_light=is_light,
        theme_overrides=theme_overrides,
    )
    if not color_value:
        return
    color = QColor(color_value)
    color.setAlpha(28 if is_light else 38)
    for column in range(item.columnCount()):
        item.setBackground(column, color)


class DiffColumnsRenderer:
    def __init__(
        self,
        view: DiffColumnsView,
        *,
        append: bool,
        scope_value: str,
        show_header_lines: bool,
        scroll_to_top: bool,
        word_diff_plain: bool,
        line_marker_resolver: LineMarkerResolver | None,
        hunk_marker_resolver: HunkMarkerResolver | None,
    ) -> None:
        self.view = view
        self.append = append
        self.scope_value = scope_value
        self.show_header_lines = show_header_lines
        self.scroll_to_top = scroll_to_top
        self.word_diff_plain = word_diff_plain
        self.line_marker_resolver = line_marker_resolver
        self.hunk_marker_resolver = hunk_marker_resolver
        base = self.view.palette().color(QPalette.ColorRole.Base)
        self._is_light_theme = int(base.lightness()) >= 128
        app = QApplication.instance()
        self._theme_overrides = app.property("gv_theme_overrides") if app is not None else None

    def _meta_row_values(self, text: str) -> list[str]:
        if self.view.include_marker_column:
            return ["", "", text]
        return ["", "", text]

    @staticmethod
    def _format_range(start: int, count: int) -> str:
        if start <= 0:
            return ""
        if count <= 1:
            return str(start)
        return f"{start}-{start + count - 1}"

    def _hunk_row_values(self, marker: str, hunk: DiffHunk) -> list[str]:
        label = f"Secao: {hunk.header}"
        if self.view.include_marker_column:
            return [marker, "", label]
        return [
            self._format_range(int(hunk.old_start), int(hunk.old_count)),
            self._format_range(int(hunk.new_start), int(hunk.new_count)),
            label,
        ]

    def _line_row_values(
        self,
        old_line_no: str,
        new_line_no: str,
        content: str,
        *,
        marker: str = "",
    ) -> list[str]:
        if self.view.include_marker_column:
            old_label = old_line_no.strip()
            new_label = new_line_no.strip()
            if old_label and not new_label:
                line_no = f"-{old_label}"
            elif new_label and not old_label:
                line_no = f"+{new_label}"
            elif old_label and new_label and old_label != new_label:
                line_no = f"~{new_label}"
            else:
                line_no = new_label or old_label
            return [marker, line_no, content]
        return [old_line_no, new_line_no, content]

    def _add_row(
        self,
        values: list[str],
        *,
        kind: str,
        hunk_index: int | None = None,
        hunk_header: str = "",
        line_info: DiffLineInfo | None = None,
        marker: str = "",
        bold: bool = False,
        tooltip: str = "",
        line_color_kind: str = "",
    ) -> QTreeWidgetItem:
        item = _make_item(values, bold=bold, kind=kind)
        item.setData(0, SCOPE_ROLE, self.scope_value)
        if hunk_index is not None:
            item.setData(0, HUNK_INDEX_ROLE, hunk_index)
        if hunk_header:
            item.setData(0, HUNK_HEADER_ROLE, hunk_header)
        if line_info is not None:
            item.setData(0, LINE_INFO_ROLE, line_info)
        if tooltip:
            for column in range(item.columnCount()):
                item.setToolTip(column, tooltip)
        if self.view.include_marker_column:
            _apply_marker_checkbox(item, self.view._marker_column, marker)
            marker_font = item.font(self.view._marker_column)
            marker_font.setBold(True)
            item.setFont(self.view._marker_column, marker_font)
        if line_color_kind:
            _apply_line_color(
                item,
                line_type=line_color_kind,
                is_light=self._is_light_theme,
                theme_overrides=self._theme_overrides,
            )
            _apply_line_background(
                item,
                line_type=line_color_kind,
                is_light=self._is_light_theme,
                theme_overrides=self._theme_overrides,
            )
        if self.view.include_marker_column:
            marker_color = self.view.palette().color(QPalette.ColorRole.Text)
            item.setForeground(self.view._marker_column, marker_color)
        self.view.addTopLevelItem(item)
        return item

    def _render_non_marker_hunk_lines(self, hunk: DiffHunk, *, hunk_index: int) -> None:
        hunk_lines = list(hunk.lines)
        index = 0
        while index < len(hunk_lines):
            line_info = hunk_lines[index]
            if line_info.line_type != "removed":
                old_no = ""
                new_no = ""
                if line_info.line_type in {"removed", "context"}:
                    old_no = str(int(line_info.old_line))
                if line_info.line_type in {"added", "context"}:
                    new_no = str(int(line_info.new_line))
                self._add_row(
                    self._line_row_values(old_no, new_no, line_info.content),
                    kind=line_info.line_type,
                    hunk_index=hunk_index,
                    hunk_header=hunk.header,
                    line_info=line_info,
                    line_color_kind=line_info.line_type,
                )
                index += 1
                continue

            removed_run: list[DiffLineInfo] = []
            while index < len(hunk_lines) and hunk_lines[index].line_type == "removed":
                removed_run.append(hunk_lines[index])
                index += 1

            added_run: list[DiffLineInfo] = []
            add_cursor = index
            while add_cursor < len(hunk_lines) and hunk_lines[add_cursor].line_type == "added":
                added_run.append(hunk_lines[add_cursor])
                add_cursor += 1

            if not added_run:
                for removed_line in removed_run:
                    self._add_row(
                        self._line_row_values(str(int(removed_line.old_line)), "", removed_line.content),
                        kind="removed",
                        hunk_index=hunk_index,
                        hunk_header=hunk.header,
                        line_info=removed_line,
                        line_color_kind="removed",
                    )
                continue

            index = add_cursor
            paired = min(len(removed_run), len(added_run))
            for pair_index in range(paired):
                removed_line = removed_run[pair_index]
                added_line = added_run[pair_index]
                if _is_modified_pair(removed_line, added_line):
                    self._add_row(
                        self._line_row_values(
                            str(int(removed_line.old_line)),
                            str(int(added_line.new_line)),
                            added_line.content,
                        ),
                        kind="modified",
                        hunk_index=hunk_index,
                        hunk_header=hunk.header,
                        line_info=added_line,
                        tooltip=f"Linha original: {removed_line.content}",
                        line_color_kind="modified",
                    )
                    continue
                self._add_row(
                    self._line_row_values(str(int(removed_line.old_line)), "", removed_line.content),
                    kind="removed",
                    hunk_index=hunk_index,
                    hunk_header=hunk.header,
                    line_info=removed_line,
                    line_color_kind="removed",
                )
                self._add_row(
                    self._line_row_values("", str(int(added_line.new_line)), added_line.content),
                    kind="added",
                    hunk_index=hunk_index,
                    hunk_header=hunk.header,
                    line_info=added_line,
                    line_color_kind="added",
                )

            for removed_line in removed_run[paired:]:
                self._add_row(
                    self._line_row_values(str(int(removed_line.old_line)), "", removed_line.content),
                    kind="removed",
                    hunk_index=hunk_index,
                    line_info=removed_line,
                    line_color_kind="removed",
                )
            for added_line in added_run[paired:]:
                self._add_row(
                    self._line_row_values("", str(int(added_line.new_line)), added_line.content),
                    kind="added",
                    hunk_index=hunk_index,
                    line_info=added_line,
                    line_color_kind="added",
                )

    def _render_hunk(self, hunk: DiffHunk, *, hunk_index: int) -> None:
        hunk_marker = ""
        if self.view.include_marker_column and self.hunk_marker_resolver is not None:
            hunk_marker = self.hunk_marker_resolver(hunk_index, hunk)
        hunk_item = self._add_row(
            self._hunk_row_values(hunk_marker, hunk),
            kind="hunk",
            hunk_index=hunk_index,
            hunk_header=hunk.header,
            marker=hunk_marker,
            bold=True,
            tooltip=_hunk_context_preview(hunk) if not self.view.include_marker_column else "",
            line_color_kind="hunk",
        )
        if not self.view.include_marker_column and hunk_item.toolTip(self.view._content_column):
            tip = hunk_item.toolTip(self.view._content_column)
            hunk_item.setToolTip(self.view._old_line_column, tip)
            if self.view._new_line_column >= 0:
                hunk_item.setToolTip(self.view._new_line_column, tip)

        if self.view.include_marker_column:
            for line_info in hunk.lines:
                marker = ""
                if self.line_marker_resolver is not None:
                    marker = self.line_marker_resolver(line_info)
                self._add_row(
                    self._line_row_values(
                        str(int(line_info.old_line)) if line_info.line_type in {"removed", "context"} else "",
                        str(int(line_info.new_line)) if line_info.line_type in {"added", "context"} else "",
                        line_info.content,
                        marker=marker,
                    ),
                    kind=line_info.line_type,
                    hunk_index=hunk_index,
                    hunk_header=hunk.header,
                    line_info=line_info,
                    marker=marker,
                    line_color_kind=line_info.line_type,
                )
            return
        self._render_non_marker_hunk_lines(hunk, hunk_index=hunk_index)

    def render(self, patch: str) -> None:
        self.view._enforce_column_layout()
        if not self.append:
            self.view.clear()
        clean_patch = patch.strip("\n")
        if not clean_patch:
            if self.append:
                return
            self._add_row(self._meta_row_values("(sem diff)"), kind="meta")
            return

        diff_data = parse_diff_data(clean_patch, word_diff_plain=self.word_diff_plain)
        if self.show_header_lines:
            for header_line in diff_data.header_lines:
                self._add_row(self._meta_row_values(header_line), kind="meta")

        for hunk_index, hunk in enumerate(diff_data.hunks):
            self._render_hunk(hunk, hunk_index=hunk_index)

        if self.view.topLevelItemCount() <= 0:
            for message_line in clean_patch.splitlines() or ["(sem diff)"]:
                self._add_row(self._meta_row_values(message_line), kind="meta")

        if self.scroll_to_top and self.view.topLevelItemCount() > 0:
            self.view.scrollToTop()
        self.view._enforce_column_layout()
        self.view._refresh_wrapped_layout()
        self.view._apply_selection_colors()


def render_diff_into_columns(
    view: DiffColumnsView,
    patch: str,
    *,
    append: bool = False,
    scope_value: str = "",
    show_header_lines: bool = True,
    scroll_to_top: bool = True,
    word_diff_plain: bool = False,
    line_marker_resolver: LineMarkerResolver | None = None,
    hunk_marker_resolver: HunkMarkerResolver | None = None,
) -> None:
    renderer = DiffColumnsRenderer(
        view,
        append=append,
        scope_value=scope_value,
        show_header_lines=show_header_lines,
        scroll_to_top=scroll_to_top,
        word_diff_plain=word_diff_plain,
        line_marker_resolver=line_marker_resolver,
        hunk_marker_resolver=hunk_marker_resolver,
    )
    renderer.render(patch)
