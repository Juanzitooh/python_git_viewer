from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.models import CommitSummary
from ..diff_columns import DiffColumnsView
from ..widgets import UnifiedListWidget


def build_history_tab(window: object) -> None:
    window.history_summaries: list[CommitSummary] = []
    window.history_summary_by_hash: dict[str, CommitSummary] = {}
    window.history_current_commit_hash = ""
    window.history_current_file_path = ""
    window.history_local_only_hashes: set[str] = set()
    window.history_has_upstream = False
    window.history_page_size = 200
    window.history_current_skip = 0
    window.history_has_more = False
    window.history_loading_more = False
    window.history_active_filter_text = ""

    layout = QVBoxLayout(window.history_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top_row = QWidget(window.history_tab)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)

    window.history_refresh_button = QPushButton("Atualizar", top_row)
    window.history_refresh_button.clicked.connect(window._reload_history_commits)
    top_layout.addWidget(window.history_refresh_button)

    window.history_export_button = QPushButton("Exportar", top_row)
    window.history_export_button.clicked.connect(window._open_history_export_dialog)
    top_layout.addWidget(window.history_export_button)

    window.history_reorder_button = QPushButton("Reordenar locais", top_row)
    window.history_reorder_button.clicked.connect(window._open_history_reorder_dialog)
    top_layout.addWidget(window.history_reorder_button)
    window.history_reorder_button.setVisible(False)

    top_layout.addWidget(QLabel("Buscar:", top_row))
    window.history_search_input = QLineEdit(top_row)
    window.history_search_input.setPlaceholderText("Filtrar por texto no commit")
    window.history_search_input.returnPressed.connect(window._reload_history_commits)
    window.history_search_input.textChanged.connect(window._on_history_search_text_changed)
    top_layout.addWidget(window.history_search_input, stretch=1)

    window.history_word_diff_check = QCheckBox("Diff por palavra", top_row)
    window.history_word_diff_check.stateChanged.connect(window._refresh_history_patch_view)
    window.history_word_diff_check.setChecked(False)
    top_layout.addWidget(window.history_word_diff_check)

    top_layout.addStretch(1)
    layout.addWidget(top_row)

    body_splitter = QSplitter(Qt.Orientation.Horizontal, window.history_tab)
    body_splitter.setChildrenCollapsible(False)

    window.history_commits_list = UnifiedListWidget(body_splitter)
    window.history_commits_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    window.history_commits_list.setMouseTracking(True)
    window.history_commits_list.itemSelectionChanged.connect(window._on_history_commit_selected)
    window.history_commits_list.itemEntered.connect(window._on_history_commit_hovered)
    window.history_commits_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history_commits_list.customContextMenuRequested.connect(window._on_history_commit_context_menu)
    window.history_commits_list.verticalScrollBar().valueChanged.connect(window._on_history_scroll_value_changed)

    right_splitter = QSplitter(Qt.Orientation.Vertical, body_splitter)
    right_splitter.setChildrenCollapsible(False)

    window.history_commit_info = QPlainTextEdit(right_splitter)
    window.history_commit_info.setReadOnly(True)

    window.history_files_list = UnifiedListWidget(right_splitter)
    window.history_files_list.itemSelectionChanged.connect(window._on_history_file_selected)
    window.history_files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history_files_list.customContextMenuRequested.connect(window._on_history_file_context_menu)

    window.history_patch_stack = QStackedWidget(right_splitter)
    window.history_patch_table = DiffColumnsView(include_marker_column=False, parent=window.history_patch_stack)
    window.history_patch_table.setHeaderHidden(True)
    window.history_patch_text = QPlainTextEdit(window.history_patch_stack)
    window.history_patch_text.setReadOnly(True)
    window.history_patch_text.setProperty("role", "diff")
    window.history_patch_stack.addWidget(window.history_patch_table)
    window.history_patch_stack.addWidget(window.history_patch_text)
    window.history_patch_stack.setCurrentIndex(0)
    # Compatibilidade com fluxo legado de render em texto.
    window.history_patch_view = window.history_patch_text

    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 4)
    right_splitter.setStretchFactor(0, 2)
    right_splitter.setStretchFactor(1, 2)
    right_splitter.setStretchFactor(2, 4)
    layout.addWidget(body_splitter, stretch=1)

    window._clear_history_view()
