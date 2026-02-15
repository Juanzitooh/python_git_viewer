from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QListWidget


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
