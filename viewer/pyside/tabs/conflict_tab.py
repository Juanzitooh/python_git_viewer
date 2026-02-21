from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..widgets import UnifiedListWidget


def build_conflict_tab(window: object) -> None:
    root_layout = QVBoxLayout(window.conflict_tab)
    root_layout.setContentsMargins(12, 12, 12, 12)
    root_layout.setSpacing(8)

    info_row = QWidget(window.conflict_tab)
    info_layout = QHBoxLayout(info_row)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(8)
    window.conflict_repo_label = QLabel("Repositorio: (nenhum)", info_row)
    window.conflict_branch_label = QLabel("Branch: (nenhuma)", info_row)
    window.conflict_operation_label = QLabel("Operacao: (nenhuma)", info_row)
    info_layout.addWidget(window.conflict_repo_label, stretch=3)
    info_layout.addWidget(window.conflict_branch_label, stretch=2)
    info_layout.addWidget(window.conflict_operation_label, stretch=2)
    root_layout.addWidget(info_row)

    actions_row = QWidget(window.conflict_tab)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    window.conflict_open_file_button = QPushButton("Abrir selecionado no VS Code", actions_row)
    window.conflict_open_file_button.clicked.connect(window._open_selected_conflict_file)
    actions_layout.addWidget(window.conflict_open_file_button)
    window.conflict_open_resolver_button = QPushButton("Resolver conflitos...", actions_row)
    window.conflict_open_resolver_button.clicked.connect(window._open_conflict_resolver_from_tab)
    actions_layout.addWidget(window.conflict_open_resolver_button)
    actions_layout.addStretch(1)
    window.conflict_refresh_button = QPushButton("Atualizar", actions_row)
    window.conflict_refresh_button.clicked.connect(window._refresh_conflict_tab_visibility)
    actions_layout.addWidget(window.conflict_refresh_button)
    root_layout.addWidget(actions_row)

    root_layout.addWidget(QLabel("Arquivos em conflito:", window.conflict_tab))
    window.conflict_files_list = UnifiedListWidget(window.conflict_tab)
    window.conflict_files_list.itemSelectionChanged.connect(window._on_conflict_file_selected)
    window.conflict_files_list.itemDoubleClicked.connect(lambda _item: window._open_selected_conflict_file())
    root_layout.addWidget(window.conflict_files_list, stretch=1)

    window.conflict_hint_label = QLabel(
        "A aba aparece automaticamente quando houver conflitos em andamento.",
        window.conflict_tab,
    )
    window.conflict_hint_label.setWordWrap(True)
    window.conflict_hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    root_layout.addWidget(window.conflict_hint_label)
