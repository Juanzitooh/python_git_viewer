from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


def build_top_bar(window: object, root_layout: QVBoxLayout, parent: QWidget) -> None:
    bar = QWidget(parent)
    bar.setObjectName("TopBar")
    bar_layout = QHBoxLayout(bar)
    bar_layout.setContentsMargins(10, 8, 10, 8)
    bar_layout.setSpacing(6)

    window.repo_combo = QComboBox(bar)
    window.repo_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    window.repo_combo.currentIndexChanged.connect(window._on_repo_changed)
    window.repo_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.repo_combo.customContextMenuRequested.connect(window._on_repo_combo_context_menu)
    repo_dropdown = window.repo_combo.view()
    repo_dropdown.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    repo_dropdown.customContextMenuRequested.connect(window._on_repo_combo_dropdown_context_menu)
    bar_layout.addWidget(window.repo_combo, stretch=1)

    window.branch_combo = QComboBox(bar)
    window.branch_combo.setMinimumWidth(180)
    window.branch_combo.currentIndexChanged.connect(window._on_branch_changed)
    bar_layout.addWidget(QLabel("Branch:", bar))
    bar_layout.addWidget(window.branch_combo)

    window.new_branch_button = QPushButton("Nova branch", bar)
    window.new_branch_button.clicked.connect(window._create_new_branch)
    bar_layout.addWidget(window.new_branch_button)

    bar_layout.addStretch(1)

    window.fetch_button = QPushButton("Fetch", bar)
    window.fetch_button.clicked.connect(window._fetch_repo)
    bar_layout.addWidget(window.fetch_button)

    window.pull_button = QPushButton("Pull", bar)
    window.pull_button.setProperty("role", "primary")
    window.pull_button.clicked.connect(window._pull_repo)
    bar_layout.addWidget(window.pull_button)

    window.push_button = QPushButton("Push", bar)
    window.push_button.setProperty("role", "primary")
    window.push_button.clicked.connect(window._push_repo)
    bar_layout.addWidget(window.push_button)

    window.sync_label = QLabel("Ahead: 0 | Behind: 0", bar)
    window.sync_label.setObjectName("SyncChip")
    bar_layout.addWidget(window.sync_label)

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
