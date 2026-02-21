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

from ..diff_columns import DiffColumnsView
from ..widgets import NoScrollComboBox, UnifiedListWidget


def build_compare_tab(window: object) -> None:
    window.compare_file_entries: list[dict[str, object]] = []
    window.compare_current_file_path = ""
    window.compare_current_commit_hash = ""
    window._setting_compare_branches_programmatically = False

    layout = QVBoxLayout(window.compare_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top_row = QWidget(window.compare_tab)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)

    top_layout.addWidget(QLabel("Origem:", top_row))
    window.compare_origin_combo = NoScrollComboBox(top_row)
    window.compare_origin_combo.setMinimumWidth(260)
    window.compare_origin_combo.setSizeAdjustPolicy(NoScrollComboBox.SizeAdjustPolicy.AdjustToContents)
    window.compare_origin_combo.currentIndexChanged.connect(window._on_compare_branches_changed)
    top_layout.addWidget(window.compare_origin_combo, stretch=1)

    window.compare_swap_button = QPushButton("Trocar", top_row)
    window.compare_swap_button.clicked.connect(window._swap_compare_branches)
    top_layout.addWidget(window.compare_swap_button)

    top_layout.addWidget(QLabel("Destino:", top_row))
    window.compare_dest_combo = NoScrollComboBox(top_row)
    window.compare_dest_combo.setMinimumWidth(260)
    window.compare_dest_combo.setSizeAdjustPolicy(NoScrollComboBox.SizeAdjustPolicy.AdjustToContents)
    window.compare_dest_combo.currentIndexChanged.connect(window._on_compare_branches_changed)
    top_layout.addWidget(window.compare_dest_combo, stretch=1)

    window.compare_refresh_button = QPushButton("Atualizar", top_row)
    window.compare_refresh_button.clicked.connect(window._refresh_compare_view)
    top_layout.addWidget(window.compare_refresh_button)

    window.compare_word_diff_check = QCheckBox("Diff por palavra", top_row)
    window.compare_word_diff_check.stateChanged.connect(window._refresh_compare_patch)
    window.compare_word_diff_check.setChecked(False)
    top_layout.addWidget(window.compare_word_diff_check)

    layout.addWidget(top_row)

    window.compare_status_label = QLabel("Selecione origem e destino para comparar.", window.compare_tab)
    layout.addWidget(window.compare_status_label)

    action_row = QWidget(window.compare_tab)
    action_layout = QHBoxLayout(action_row)
    action_layout.setContentsMargins(0, 0, 0, 0)
    action_layout.setSpacing(6)

    action_layout.addWidget(QLabel("Ação:", action_row))
    window.compare_action_combo = NoScrollComboBox(action_row)
    window.compare_action_combo.addItem("Merge", "merge")
    window.compare_action_combo.addItem("Rebase", "rebase")
    window.compare_action_combo.addItem("Squash merge", "squash")
    window.compare_action_combo.currentIndexChanged.connect(window._on_compare_action_changed)
    action_layout.addWidget(window.compare_action_combo)

    window.compare_squash_message_label = QLabel("Mensagem (squash):", action_row)
    action_layout.addWidget(window.compare_squash_message_label)

    window.compare_squash_message_input = QLineEdit(action_row)
    window.compare_squash_message_input.setPlaceholderText("Mensagem do commit squash")
    window.compare_squash_message_input.textChanged.connect(window._on_compare_action_changed)
    action_layout.addWidget(window.compare_squash_message_input, stretch=1)

    window.compare_run_button = QPushButton("Executar", action_row)
    window.compare_run_button.setProperty("role", "primary")
    window.compare_run_button.clicked.connect(window._run_compare_action)
    action_layout.addWidget(window.compare_run_button)

    window.compare_open_commit_button = QPushButton("Ir para Commit", action_row)
    window.compare_open_commit_button.clicked.connect(window._open_commit_tab_from_compare)
    action_layout.addWidget(window.compare_open_commit_button)

    layout.addWidget(action_row)

    window.compare_action_status_label = QLabel("Selecione origem e destino.", window.compare_tab)
    layout.addWidget(window.compare_action_status_label)

    body_splitter = QSplitter(Qt.Orientation.Horizontal, window.compare_tab)
    body_splitter.setChildrenCollapsible(False)

    window.compare_commits_list = UnifiedListWidget(body_splitter)
    window.compare_commits_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    window.compare_commits_list.itemSelectionChanged.connect(window._on_compare_commit_selected)
    window.compare_commits_list.itemDoubleClicked.connect(window._on_compare_commit_double_clicked)
    window.compare_commits_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.compare_commits_list.customContextMenuRequested.connect(window._on_compare_commit_context_menu)

    right_splitter = QSplitter(Qt.Orientation.Vertical, body_splitter)
    right_splitter.setChildrenCollapsible(False)

    window.compare_commit_info = QPlainTextEdit(right_splitter)
    window.compare_commit_info.setReadOnly(True)

    window.compare_files_list = UnifiedListWidget(right_splitter)
    window.compare_files_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    window.compare_files_list.itemSelectionChanged.connect(window._on_compare_file_selected)
    window.compare_files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.compare_files_list.customContextMenuRequested.connect(window._on_compare_file_context_menu)

    window.compare_patch_stack = QStackedWidget(right_splitter)
    window.compare_patch_table = DiffColumnsView(include_marker_column=False, parent=window.compare_patch_stack)
    window.compare_patch_table.setHeaderHidden(True)
    window.compare_patch_text = QPlainTextEdit(window.compare_patch_stack)
    window.compare_patch_text.setReadOnly(True)
    window.compare_patch_text.setProperty("role", "diff")
    window.compare_patch_stack.addWidget(window.compare_patch_table)
    window.compare_patch_stack.addWidget(window.compare_patch_text)
    window.compare_patch_stack.setCurrentIndex(0)
    # Compatibilidade com fluxo legado de render em texto.
    window.compare_patch_view = window.compare_patch_text

    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 4)
    right_splitter.setStretchFactor(0, 2)
    right_splitter.setStretchFactor(1, 2)
    right_splitter.setStretchFactor(2, 4)
    layout.addWidget(body_splitter, stretch=1)
    window._clear_compare_view()
    window._on_compare_action_changed(-1)
