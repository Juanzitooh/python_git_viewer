from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..diff_columns import DiffColumnsView
from ..widgets import UnifiedListWidget


class CommitDiffView(QPlainTextEdit):
    markerClicked = Signal(int)

    _marker_start = 8
    _marker_end = 10

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pressed_marker_line = -1
        self._pressed_point = None
        self._press_in_marker = False

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._pressed_marker_line = -1
        self._pressed_point = event.position()
        self._press_in_marker = False
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            pos_in_block = cursor.positionInBlock()
            if self._marker_start <= pos_in_block <= self._marker_end:
                self._pressed_marker_line = cursor.blockNumber() + 1
                self._press_in_marker = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._press_in_marker
            and self._pressed_marker_line > 0
            and self._pressed_point is not None
        ):
            delta = event.position() - self._pressed_point
            if abs(delta.x()) <= 3 and abs(delta.y()) <= 3 and not self.textCursor().hasSelection():
                self.markerClicked.emit(self._pressed_marker_line)
                event.accept()
                self._pressed_marker_line = -1
                self._press_in_marker = False
                return
        self._pressed_marker_line = -1
        self._press_in_marker = False
        super().mouseReleaseEvent(event)


def build_commit_tab(window: object) -> None:
    root_layout = QVBoxLayout(window.commit_tab)
    root_layout.setContentsMargins(12, 12, 12, 12)
    root_layout.setSpacing(8)

    splitter = QSplitter(Qt.Orientation.Horizontal, window.commit_tab)
    splitter.setChildrenCollapsible(False)
    root_layout.addWidget(splitter, stretch=1)

    left_column = QWidget(splitter)
    left_layout = QVBoxLayout(left_column)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(8)

    top_row = QWidget(left_column)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)

    window.commit_refresh_button = QPushButton("Atualizar status", top_row)
    window.commit_refresh_button.clicked.connect(window._refresh_commit_files)
    top_layout.addWidget(window.commit_refresh_button)

    top_layout.addStretch(1)
    window.commit_selection_label = QLabel("Selecionados: 0/0", top_row)
    top_layout.addWidget(window.commit_selection_label)

    left_layout.addWidget(top_row)

    window.commit_files_list = UnifiedListWidget(left_column)
    window.commit_files_list.itemChanged.connect(window._on_commit_file_item_changed)
    window.commit_files_list.itemSelectionChanged.connect(window._on_commit_file_selected)
    window.commit_files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.commit_files_list.customContextMenuRequested.connect(window._on_commit_file_context_menu)
    left_layout.addWidget(window.commit_files_list, stretch=1)

    window.commit_title_input = QLineEdit(left_column)
    window.commit_title_input.setPlaceholderText("Titulo do commit (obrigatorio)")
    left_layout.addWidget(window.commit_title_input)

    window.commit_description_input = QPlainTextEdit(left_column)
    window.commit_description_input.setPlaceholderText("Descricao do commit (opcional)")
    window.commit_description_input.setFixedHeight(120)
    left_layout.addWidget(window.commit_description_input)

    action_row = QWidget(left_column)
    action_layout = QHBoxLayout(action_row)
    action_layout.setContentsMargins(0, 0, 0, 0)
    action_layout.setSpacing(6)

    window.commit_run_button = QPushButton("Commit", action_row)
    window.commit_run_button.setProperty("role", "primary")
    window.commit_run_button.clicked.connect(window._create_commit_from_selection)
    action_layout.addWidget(window.commit_run_button)

    window.commit_stash_button = QPushButton("Stash", action_row)
    window.commit_stash_button.clicked.connect(window._create_stash_from_commit_tab)
    action_layout.addWidget(window.commit_stash_button)

    window.commit_undo_button = QPushButton("Undo commit", action_row)
    window.commit_undo_button.clicked.connect(window._undo_last_commit_from_commit_tab)
    action_layout.addWidget(window.commit_undo_button)

    window.commit_open_pr_button = QPushButton("Abrir PR", action_row)
    window.commit_open_pr_button.clicked.connect(window._open_commit_pr_in_github)
    action_layout.addWidget(window.commit_open_pr_button)

    left_layout.addWidget(action_row)

    right_column = QWidget(splitter)
    right_layout = QVBoxLayout(right_column)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(8)

    diff_header = QWidget(right_column)
    diff_header_layout = QHBoxLayout(diff_header)
    diff_header_layout.setContentsMargins(0, 0, 0, 0)
    diff_header_layout.setSpacing(6)
    diff_header_layout.addWidget(QLabel("Diff do arquivo selecionado:", diff_header))
    diff_header_layout.addStretch(1)
    window.commit_open_diff_window_button = QPushButton("Abrir janela", diff_header)
    window.commit_open_diff_window_button.clicked.connect(window._open_commit_diff_window)
    diff_header_layout.addWidget(window.commit_open_diff_window_button)
    window.commit_word_diff_check = QCheckBox("Diff por palavra", diff_header)
    window.commit_word_diff_check.stateChanged.connect(lambda _state: window._refresh_commit_diff())
    diff_header_layout.addWidget(window.commit_word_diff_check)
    right_layout.addWidget(diff_header)

    window.commit_diff_view = DiffColumnsView(include_marker_column=True, parent=right_column)
    window.commit_diff_view.set_internal_context_menu_enabled(False)
    window.commit_diff_view.setHeaderHidden(True)
    window.commit_diff_view.setColumnWidth(window.commit_diff_view._marker_column, 42)
    window.commit_diff_view.setColumnWidth(window.commit_diff_view._line_column, 56)
    window.commit_diff_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    window.commit_diff_view.itemSelectionChanged.connect(window._on_commit_diff_cursor_changed)
    window.commit_diff_view.itemChanged.connect(window._on_commit_diff_item_changed)
    window.commit_diff_view.itemClicked.connect(window._on_commit_diff_item_clicked)
    window.commit_diff_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.commit_diff_view.customContextMenuRequested.connect(window._on_commit_diff_context_menu)
    right_layout.addWidget(window.commit_diff_view, stretch=1)

    splitter.addWidget(left_column)
    splitter.addWidget(right_column)
    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 3)

    window._refresh_commit_files()
