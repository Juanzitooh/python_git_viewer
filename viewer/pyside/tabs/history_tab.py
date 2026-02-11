from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core.models import CommitSummary


def build_history_tab(window: object) -> None:
    window.history_summaries: list[CommitSummary] = []
    window.history_summary_by_hash: dict[str, CommitSummary] = {}
    window.history_current_commit_hash = ""
    window.history_current_file_path = ""
    window.history_local_only_hashes: set[str] = set()
    window.history_has_upstream = False

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
    top_layout.addWidget(window.history_search_input, stretch=1)

    top_layout.addWidget(QLabel("Limite:", top_row))
    window.history_limit_combo = QComboBox(top_row)
    window.history_limit_combo.addItem("50", 50)
    window.history_limit_combo.addItem("100", 100)
    window.history_limit_combo.addItem("200", 200)
    window.history_limit_combo.setCurrentIndex(1)
    window.history_limit_combo.currentIndexChanged.connect(window._reload_history_commits)
    top_layout.addWidget(window.history_limit_combo)

    window.history_word_diff_check = QCheckBox("Diff por palavra", top_row)
    window.history_word_diff_check.stateChanged.connect(window._refresh_history_patch_view)
    top_layout.addWidget(window.history_word_diff_check)

    top_layout.addStretch(1)
    window.history_legend_label = QLabel("Legenda: [L] local | [L+O] local+online", top_row)
    top_layout.addWidget(window.history_legend_label)

    layout.addWidget(top_row)

    body_splitter = QSplitter(Qt.Orientation.Horizontal, window.history_tab)
    body_splitter.setChildrenCollapsible(False)

    window.history_commits_list = QListWidget(body_splitter)
    window.history_commits_list.itemSelectionChanged.connect(window._on_history_commit_selected)
    window.history_commits_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history_commits_list.customContextMenuRequested.connect(window._on_history_commit_context_menu)

    right_splitter = QSplitter(Qt.Orientation.Vertical, body_splitter)
    right_splitter.setChildrenCollapsible(False)

    window.history_commit_info = QPlainTextEdit(right_splitter)
    window.history_commit_info.setReadOnly(True)

    window.history_files_list = QListWidget(right_splitter)
    window.history_files_list.itemSelectionChanged.connect(window._on_history_file_selected)
    window.history_files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.history_files_list.customContextMenuRequested.connect(window._on_history_file_context_menu)

    window.history_patch_view = QPlainTextEdit(right_splitter)
    window.history_patch_view.setReadOnly(True)

    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 4)
    right_splitter.setStretchFactor(0, 2)
    right_splitter.setStretchFactor(1, 2)
    right_splitter.setStretchFactor(2, 4)
    layout.addWidget(body_splitter, stretch=1)

    window._clear_history_view()
