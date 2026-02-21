from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QFont, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QListWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)


class KeepForegroundOnSelectionDelegate(QStyledItemDelegate):
    """Mantem a cor de foreground do item ao selecionar (muda apenas o fundo)."""

    def paint(self, painter, option, index) -> None:  # type: ignore[override]
        draw_option = QStyleOptionViewItem(option)
        if draw_option.state & QStyle.StateFlag.State_Selected:
            brush_data = index.data(Qt.ItemDataRole.ForegroundRole)
            if isinstance(brush_data, QBrush) and brush_data.color().isValid():
                draw_option.palette.setBrush(QPalette.ColorRole.HighlightedText, brush_data)
        super().paint(painter, draw_option, index)


class NoScrollComboBox(QComboBox):
    """Evita troca de valor por scroll acidental quando o dropdown esta fechado."""

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        event.ignore()


class UnifiedListWidget(QListWidget):
    """Lista padronizada para manter o mesmo visual/comportamento nas abas."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAutoScroll(False)
        self.setFont(QFont("JetBrains Mono", 10))
        self.setItemDelegate(KeepForegroundOnSelectionDelegate(self))
