from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..diff_columns import DiffColumnsView
from ..widgets import UnifiedListWidget


def build_stash_tab(window: object) -> None:
    root_layout = QVBoxLayout(window.stash_tab)
    root_layout.setContentsMargins(12, 12, 12, 12)
    root_layout.setSpacing(8)

    info_row = QWidget(window.stash_tab)
    info_layout = QHBoxLayout(info_row)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(8)
    window.stash_repo_label = QLabel("Repositorio: (nenhum)", info_row)
    window.stash_branch_label = QLabel("Branch: (nenhuma)", info_row)
    info_layout.addWidget(window.stash_repo_label, stretch=3)
    info_layout.addWidget(window.stash_branch_label, stretch=1)
    root_layout.addWidget(info_row)

    create_row = QWidget(window.stash_tab)
    create_layout = QHBoxLayout(create_row)
    create_layout.setContentsMargins(0, 0, 0, 0)
    create_layout.setSpacing(6)
    create_layout.addWidget(QLabel("Mensagem fixa: git_viewer", create_row))
    create_layout.addStretch(1)
    window.stash_create_button = QPushButton("Criar stash (selecionados)", create_row)
    window.stash_create_button.clicked.connect(window._create_stash_from_commit_tab)
    create_layout.addWidget(window.stash_create_button)
    window.stash_refresh_button = QPushButton("Atualizar", create_row)
    window.stash_refresh_button.clicked.connect(lambda: window._refresh_stash_tab_visibility())
    create_layout.addWidget(window.stash_refresh_button)
    root_layout.addWidget(create_row)

    splitter = QSplitter(Qt.Orientation.Horizontal, window.stash_tab)
    splitter.setChildrenCollapsible(False)
    root_layout.addWidget(splitter, stretch=1)

    left_panel = QWidget(splitter)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(6)
    left_layout.addWidget(QLabel("Stashes:", left_panel))
    window.stash_entries_list = UnifiedListWidget(left_panel)
    window.stash_entries_list.itemSelectionChanged.connect(window._on_stash_entry_selected)
    window.stash_entries_list.itemDoubleClicked.connect(lambda _item: window._pop_selected_stash())
    window.stash_entries_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.stash_entries_list.customContextMenuRequested.connect(window._on_stash_entry_context_menu)
    left_layout.addWidget(window.stash_entries_list, stretch=1)

    right_splitter = QSplitter(Qt.Orientation.Vertical, splitter)
    right_splitter.setChildrenCollapsible(False)

    files_panel = QWidget(right_splitter)
    files_layout = QVBoxLayout(files_panel)
    files_layout.setContentsMargins(0, 0, 0, 0)
    files_layout.setSpacing(6)
    files_layout.addWidget(QLabel("Arquivos do stash:", files_panel))
    window.stash_files_list = UnifiedListWidget(files_panel)
    window.stash_files_list.itemSelectionChanged.connect(window._on_stash_file_selected)
    files_layout.addWidget(window.stash_files_list, stretch=1)

    diff_panel = QWidget(right_splitter)
    diff_layout = QVBoxLayout(diff_panel)
    diff_layout.setContentsMargins(0, 0, 0, 0)
    diff_layout.setSpacing(6)
    diff_header = QWidget(diff_panel)
    diff_header_layout = QHBoxLayout(diff_header)
    diff_header_layout.setContentsMargins(0, 0, 0, 0)
    diff_header_layout.setSpacing(6)
    diff_header_layout.addWidget(QLabel("Diff do stash:", diff_header))
    diff_header_layout.addStretch(1)
    window.stash_word_diff_check = QCheckBox("Diff por palavra", diff_header)
    window.stash_word_diff_check.stateChanged.connect(lambda _state: window._refresh_stash_patch_view())
    window.stash_word_diff_check.setChecked(False)
    diff_header_layout.addWidget(window.stash_word_diff_check)
    diff_layout.addWidget(diff_header)
    window.stash_patch_stack = QStackedWidget(diff_panel)
    window.stash_patch_table = DiffColumnsView(include_marker_column=False, parent=window.stash_patch_stack)
    window.stash_patch_table.setHeaderHidden(True)
    window.stash_patch_text = QPlainTextEdit(window.stash_patch_stack)
    window.stash_patch_text.setReadOnly(True)
    window.stash_patch_text.setProperty("role", "diff")
    window.stash_patch_text.setPlaceholderText("Selecione um stash para visualizar o diff.")
    window.stash_patch_stack.addWidget(window.stash_patch_table)
    window.stash_patch_stack.addWidget(window.stash_patch_text)
    window.stash_patch_stack.setCurrentIndex(0)
    # Compatibilidade com fluxo legado de render em texto.
    window.stash_patch_view = window.stash_patch_text
    diff_layout.addWidget(window.stash_patch_stack, stretch=1)

    splitter.addWidget(left_panel)
    splitter.addWidget(right_splitter)
    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 4)
    right_splitter.setStretchFactor(0, 1)
    right_splitter.setStretchFactor(1, 3)
