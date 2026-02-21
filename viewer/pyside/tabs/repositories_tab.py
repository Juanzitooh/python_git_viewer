from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QScrollArea, QVBoxLayout, QWidget


def build_repositories_tab(window: object) -> None:
    layout = QVBoxLayout(window.repositories_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

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
