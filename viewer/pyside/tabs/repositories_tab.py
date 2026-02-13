from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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

    cards_header = QLabel("Visao Geral do Workspace", window.repositories_tab)
    layout.addWidget(cards_header)

    window.workspace_cards_scroll = QScrollArea(window.repositories_tab)
    window.workspace_cards_scroll.setObjectName("WorkspaceCardsScroll")
    window.workspace_cards_scroll.setWidgetResizable(True)
    window.workspace_cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
    window.workspace_cards_scroll.viewport().setObjectName("WorkspaceCardsViewport")

    window.workspace_cards_container = QWidget(window.workspace_cards_scroll)
    window.workspace_cards_container.setObjectName("WorkspaceCardsContainer")
    window.workspace_cards_grid = QGridLayout(window.workspace_cards_container)
    window.workspace_cards_grid.setContentsMargins(0, 0, 0, 0)
    window.workspace_cards_grid.setHorizontalSpacing(8)
    window.workspace_cards_grid.setVerticalSpacing(8)
    window.workspace_cards_scroll.setWidget(window.workspace_cards_container)
    layout.addWidget(window.workspace_cards_scroll, stretch=1)

    window._scan_workspace_repos()
