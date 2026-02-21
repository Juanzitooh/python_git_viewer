from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..widgets import NoScrollComboBox


def build_top_bar(window: object, root_layout: QVBoxLayout, parent: QWidget) -> None:
    bar = QWidget(parent)
    bar.setObjectName("TopBar")
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(10, 8, 10, 8)
    bar_layout.setSpacing(6)

    window.top_bar_normal_controls = QWidget(bar)
    normal_layout = QHBoxLayout(window.top_bar_normal_controls)
    normal_layout.setContentsMargins(0, 0, 0, 0)
    normal_layout.setSpacing(6)

    window.repo_combo = NoScrollComboBox(window.top_bar_normal_controls)
    window.repo_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    window.repo_combo.currentIndexChanged.connect(window._on_repo_changed)
    window.repo_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.repo_combo.customContextMenuRequested.connect(window._on_repo_combo_context_menu)
    repo_dropdown = window.repo_combo.view()
    repo_dropdown.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    repo_dropdown.customContextMenuRequested.connect(window._on_repo_combo_dropdown_context_menu)
    normal_layout.addWidget(QLabel("Repositório:", window.top_bar_normal_controls))
    normal_layout.addWidget(window.repo_combo, stretch=1)

    window.branch_combo = NoScrollComboBox(window.top_bar_normal_controls)
    window.branch_combo.setMinimumWidth(120)
    window.branch_combo.currentIndexChanged.connect(window._on_branch_changed)
    window.branch_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.branch_combo.customContextMenuRequested.connect(window._on_branch_combo_context_menu)
    branch_dropdown = window.branch_combo.view()
    branch_dropdown.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    branch_dropdown.customContextMenuRequested.connect(window._on_branch_combo_dropdown_context_menu)
    normal_layout.addWidget(QLabel("Branch:", window.top_bar_normal_controls))
    normal_layout.addWidget(window.branch_combo)

    window.new_branch_button = QPushButton("Nova branch", window.top_bar_normal_controls)
    window.new_branch_button.clicked.connect(window._create_new_branch)
    normal_layout.addWidget(window.new_branch_button)

    normal_layout.addStretch(1)

    window.fetch_button = QPushButton("Fetch", window.top_bar_normal_controls)
    window.fetch_button.clicked.connect(window._fetch_repo)
    normal_layout.addWidget(window.fetch_button)

    window.publish_button = QPushButton("Publish", window.top_bar_normal_controls)
    window.publish_button.clicked.connect(window._publish_repo)
    window.publish_button.setToolTip("Publicar branch local no remoto (origin) e configurar upstream.")
    window.publish_button.setVisible(False)
    window.publish_button.setEnabled(False)
    normal_layout.addWidget(window.publish_button)

    window.behind_button = QPushButton("Pull: 0", window.top_bar_normal_controls)
    window.behind_button.setObjectName("SyncChip")
    window.behind_button.clicked.connect(window._pull_repo)
    window.behind_button.setToolTip("Pull: buscar commits remotos pendentes (behind > 0).")
    normal_layout.addWidget(window.behind_button)

    window.ahead_button = QPushButton("Push: 0", window.top_bar_normal_controls)
    window.ahead_button.setObjectName("SyncChip")
    window.ahead_button.clicked.connect(window._push_repo)
    window.ahead_button.setToolTip("Push: enviar commits locais pendentes (ahead > 0).")
    normal_layout.addWidget(window.ahead_button)

    window.top_bar_workspace_controls = QWidget(bar)
    workspace_layout = QHBoxLayout(window.top_bar_workspace_controls)
    workspace_layout.setContentsMargins(0, 0, 0, 0)
    workspace_layout.setSpacing(6)
    workspace_layout.addWidget(QLabel("Raiz local do Workspace GitHub:", window.top_bar_workspace_controls))
    window.workspace_root_edit = QLineEdit(window.top_bar_workspace_controls)
    window.workspace_root_edit.setText(window.repo_scan_root)
    window.workspace_root_edit.editingFinished.connect(window._on_workspace_root_edited)
    workspace_layout.addWidget(window.workspace_root_edit, stretch=1)

    window.workspace_root_pick_button = QPushButton("Pasta...", window.top_bar_workspace_controls)
    window.workspace_root_pick_button.clicked.connect(window._pick_workspace_root)
    workspace_layout.addWidget(window.workspace_root_pick_button)

    window.workspace_rescan_button = QPushButton("Reescanear", window.top_bar_workspace_controls)
    window.workspace_rescan_button.clicked.connect(window._scan_workspace_repos)
    workspace_layout.addWidget(window.workspace_rescan_button)

    window.workspace_clone_button = QPushButton("Adicionar repositório", window.top_bar_workspace_controls)
    window.workspace_clone_button.clicked.connect(window._open_clone_dialog)
    workspace_layout.addWidget(window.workspace_clone_button)

    bar_layout.addWidget(window.top_bar_normal_controls, stretch=1)
    bar_layout.addWidget(window.top_bar_workspace_controls, stretch=1)
    window.top_bar_workspace_controls.setVisible(False)

    root_layout.addWidget(bar)


def build_status_bar(window: object, parent: QWidget) -> None:
    window.status = QStatusBar(parent)
    window.setStatusBar(window.status)
    window.status_busy_label = QLabel("Pronto", window.status)
    window.status_busy_label.setObjectName("BusyBadge")
    window.status_busy_progress = QProgressBar(window.status)
    window.status_busy_progress.setObjectName("BusyBar")
    window.status_busy_progress.setMaximum(0)
    window.status_busy_progress.setFixedWidth(120)
    window.status_busy_progress.setTextVisible(False)
    window.status_busy_progress.setVisible(False)
    window.status.addPermanentWidget(window.status_busy_label)
    window.status.addPermanentWidget(window.status_busy_progress)
