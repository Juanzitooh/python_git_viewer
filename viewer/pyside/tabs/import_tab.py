from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.models import CommitSummary
from ..diff_columns import DiffColumnsView
from ..widgets import NoScrollComboBox, UnifiedListWidget


def build_import_tab(window: object) -> None:
    window.import_source_repo_path = ""
    window.import_source_repo_lookup: dict[str, str] = {}
    window.import_commit_summaries: list[CommitSummary] = []
    window.import_current_commit_hash = ""
    window.import_current_file_path = ""

    layout = QVBoxLayout(window.import_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    source_row = QWidget(window.import_tab)
    source_layout = QHBoxLayout(source_row)
    source_layout.setContentsMargins(0, 0, 0, 0)
    source_layout.setSpacing(6)

    source_layout.addWidget(QLabel("Origem:", source_row))
    window.import_source_repo_combo = NoScrollComboBox(source_row)
    window.import_source_repo_combo.currentIndexChanged.connect(window._on_import_source_repo_changed)
    source_layout.addWidget(window.import_source_repo_combo, stretch=1)

    window.import_source_repo_refresh_button = QPushButton("Atualizar repos", source_row)
    window.import_source_repo_refresh_button.clicked.connect(window._refresh_import_source_repos)
    source_layout.addWidget(window.import_source_repo_refresh_button)

    window.import_source_repo_clone_button = QPushButton("Clonar repo", source_row)
    window.import_source_repo_clone_button.clicked.connect(window._open_import_clone_dialog)
    source_layout.addWidget(window.import_source_repo_clone_button)

    source_layout.addWidget(QLabel("Branch origem:", source_row))
    window.import_source_branch_combo = NoScrollComboBox(source_row)
    window.import_source_branch_combo.currentIndexChanged.connect(window._on_import_source_branch_changed)
    source_layout.addWidget(window.import_source_branch_combo)

    window.import_source_branch_refresh_button = QPushButton("Atualizar lista", source_row)
    window.import_source_branch_refresh_button.clicked.connect(window._load_import_source_commits)
    source_layout.addWidget(window.import_source_branch_refresh_button)

    window.import_word_diff_check = QCheckBox("Diff por palavra", source_row)
    window.import_word_diff_check.stateChanged.connect(lambda _state: window._refresh_import_patch_view())
    window.import_word_diff_check.setChecked(False)
    source_layout.addWidget(window.import_word_diff_check)

    layout.addWidget(source_row)

    window.import_target_label = QLabel("Destino: (nenhum repositório selecionado)", window.import_tab)
    layout.addWidget(window.import_target_label)

    body_splitter = QSplitter(Qt.Orientation.Horizontal, window.import_tab)
    body_splitter.setChildrenCollapsible(False)

    window.import_commits_list = UnifiedListWidget(body_splitter)
    window.import_commits_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    window.import_commits_list.itemSelectionChanged.connect(window._on_import_commit_selected)
    window.import_commits_list.itemSelectionChanged.connect(window._update_import_controls_state)
    window.import_commits_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.import_commits_list.customContextMenuRequested.connect(window._on_import_commit_context_menu)

    right_splitter = QSplitter(Qt.Orientation.Vertical, body_splitter)
    right_splitter.setChildrenCollapsible(False)

    window.import_commit_info = QPlainTextEdit(right_splitter)
    window.import_commit_info.setReadOnly(True)

    window.import_files_list = UnifiedListWidget(right_splitter)
    window.import_files_list.itemSelectionChanged.connect(window._on_import_file_selected)
    window.import_files_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.import_files_list.customContextMenuRequested.connect(window._on_import_file_context_menu)

    window.import_patch_stack = QStackedWidget(right_splitter)
    window.import_patch_table = DiffColumnsView(include_marker_column=False, parent=window.import_patch_stack)
    window.import_patch_table.setHeaderHidden(True)
    window.import_patch_text = QPlainTextEdit(window.import_patch_stack)
    window.import_patch_text.setReadOnly(True)
    window.import_patch_text.setProperty("role", "diff")
    window.import_patch_stack.addWidget(window.import_patch_table)
    window.import_patch_stack.addWidget(window.import_patch_text)
    window.import_patch_stack.setCurrentIndex(0)
    # Compatibilidade com fluxo legado em texto.
    window.import_patch_view = window.import_patch_text

    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 4)
    right_splitter.setStretchFactor(0, 2)
    right_splitter.setStretchFactor(1, 2)
    right_splitter.setStretchFactor(2, 4)
    layout.addWidget(body_splitter, stretch=1)

    actions_row = QWidget(window.import_tab)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)

    window.import_copy_hashes_button = QPushButton("Copiar hashes", actions_row)
    window.import_copy_hashes_button.clicked.connect(window._copy_selected_import_hashes)
    actions_layout.addWidget(window.import_copy_hashes_button)

    window.import_run_button = QPushButton("Importar selecionados", actions_row)
    window.import_run_button.setProperty("role", "primary")
    window.import_run_button.clicked.connect(window._import_selected_commits)
    actions_layout.addWidget(window.import_run_button)

    actions_layout.addStretch(1)
    layout.addWidget(actions_row)

    window.import_status_label = QLabel("Selecione o repositório de origem para carregar commits.", window.import_tab)
    layout.addWidget(window.import_status_label)

    window._refresh_import_source_repos()
    window._sync_import_target_label()
    window._update_import_controls_state()
