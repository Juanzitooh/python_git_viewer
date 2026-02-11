from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)


def build_repositories_tab(window: object) -> None:
    layout = QVBoxLayout(window.repositories_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    root_row = QWidget(window.repositories_tab)
    root_row_layout = QHBoxLayout(root_row)
    root_row_layout.setContentsMargins(0, 0, 0, 0)
    root_row_layout.setSpacing(6)

    root_row_layout.addWidget(QLabel("Raiz local do Workspace GitHub:", root_row))
    window.workspace_root_edit = QLineEdit(root_row)
    window.workspace_root_edit.setText(window.repo_scan_root)
    window.workspace_root_edit.editingFinished.connect(window._on_workspace_root_edited)
    root_row_layout.addWidget(window.workspace_root_edit, stretch=1)

    window.workspace_root_pick_button = QPushButton("Pasta...", root_row)
    window.workspace_root_pick_button.clicked.connect(window._pick_workspace_root)
    root_row_layout.addWidget(window.workspace_root_pick_button)

    window.workspace_rescan_button = QPushButton("Reescanear", root_row)
    window.workspace_rescan_button.clicked.connect(window._scan_workspace_repos)
    root_row_layout.addWidget(window.workspace_rescan_button)

    window.workspace_clone_button = QPushButton("Adicionar repositório", root_row)
    window.workspace_clone_button.clicked.connect(window._open_clone_dialog)
    root_row_layout.addWidget(window.workspace_clone_button)

    layout.addWidget(root_row)

    window.workspace_scan_status_label = QLabel("Aguardando scan do workspace...", window.repositories_tab)
    layout.addWidget(window.workspace_scan_status_label)

    window.workspace_tree = QTreeWidget(window.repositories_tab)
    window.workspace_tree.setRootIsDecorated(False)
    window.workspace_tree.setAlternatingRowColors(True)
    window.workspace_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
    window.workspace_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
    window.workspace_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    window.workspace_tree.customContextMenuRequested.connect(window._on_workspace_tree_context_menu)
    window.workspace_tree.setColumnCount(6)
    window.workspace_tree.setHeaderLabels(["Repositório", "Caminho", "Branch", "Ahead", "Behind", "Status"])
    window.workspace_tree.itemSelectionChanged.connect(window._on_workspace_selection_changed)
    window.workspace_tree.itemDoubleClicked.connect(window._on_workspace_item_double_clicked)
    layout.addWidget(window.workspace_tree, stretch=1)

    window._scan_workspace_repos()
