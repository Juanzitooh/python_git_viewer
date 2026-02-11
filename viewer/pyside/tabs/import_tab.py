from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.models import CommitSummary


def build_import_tab(window: object) -> None:
    window.import_source_repo_path = ""
    window.import_source_repo_lookup: dict[str, str] = {}
    window.import_commit_summaries: list[CommitSummary] = []

    layout = QVBoxLayout(window.import_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    source_row = QWidget(window.import_tab)
    source_layout = QHBoxLayout(source_row)
    source_layout.setContentsMargins(0, 0, 0, 0)
    source_layout.setSpacing(6)

    source_layout.addWidget(QLabel("Origem:", source_row))
    window.import_source_repo_combo = QComboBox(source_row)
    window.import_source_repo_combo.currentIndexChanged.connect(window._on_import_source_repo_changed)
    source_layout.addWidget(window.import_source_repo_combo, stretch=1)

    window.import_source_repo_refresh_button = QPushButton("Atualizar repos", source_row)
    window.import_source_repo_refresh_button.clicked.connect(window._refresh_import_source_repos)
    source_layout.addWidget(window.import_source_repo_refresh_button)

    window.import_source_repo_current_button = QPushButton("Usar atual", source_row)
    window.import_source_repo_current_button.clicked.connect(window._use_current_repo_as_import_source)
    source_layout.addWidget(window.import_source_repo_current_button)

    source_layout.addWidget(QLabel("Branch origem:", source_row))
    window.import_source_branch_combo = QComboBox(source_row)
    window.import_source_branch_combo.currentIndexChanged.connect(window._on_import_source_branch_changed)
    source_layout.addWidget(window.import_source_branch_combo)

    window.import_source_branch_refresh_button = QPushButton("Atualizar lista", source_row)
    window.import_source_branch_refresh_button.clicked.connect(window._load_import_source_commits)
    source_layout.addWidget(window.import_source_branch_refresh_button)

    layout.addWidget(source_row)

    window.import_target_label = QLabel("Destino: (nenhum repositório selecionado)", window.import_tab)
    layout.addWidget(window.import_target_label)

    window.import_commits_list = QListWidget(window.import_tab)
    window.import_commits_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    window.import_commits_list.itemSelectionChanged.connect(window._update_import_controls_state)
    window.import_commits_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.import_commits_list.customContextMenuRequested.connect(window._on_import_commit_context_menu)
    layout.addWidget(window.import_commits_list, stretch=1)

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
