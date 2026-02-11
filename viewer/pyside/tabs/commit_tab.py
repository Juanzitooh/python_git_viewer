from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def build_commit_tab(window: object) -> None:
    layout = QVBoxLayout(window.commit_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top_row = QWidget(window.commit_tab)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)

    window.commit_refresh_button = QPushButton("Atualizar status", top_row)
    window.commit_refresh_button.clicked.connect(window._refresh_commit_files)
    top_layout.addWidget(window.commit_refresh_button)

    window.commit_select_all_button = QPushButton("Selecionar tudo", top_row)
    window.commit_select_all_button.clicked.connect(window._select_all_commit_files)
    top_layout.addWidget(window.commit_select_all_button)

    window.commit_clear_selection_button = QPushButton("Limpar selecao", top_row)
    window.commit_clear_selection_button.clicked.connect(window._clear_commit_file_selection)
    top_layout.addWidget(window.commit_clear_selection_button)

    top_layout.addStretch(1)
    window.commit_selection_label = QLabel("Selecionados: 0/0", top_row)
    top_layout.addWidget(window.commit_selection_label)

    layout.addWidget(top_row)

    window.commit_files_list = QListWidget(window.commit_tab)
    window.commit_files_list.itemChanged.connect(window._on_commit_file_item_changed)
    layout.addWidget(window.commit_files_list, stretch=1)

    window.commit_title_input = QLineEdit(window.commit_tab)
    window.commit_title_input.setPlaceholderText("Titulo do commit (obrigatorio)")
    layout.addWidget(window.commit_title_input)

    window.commit_description_input = QPlainTextEdit(window.commit_tab)
    window.commit_description_input.setPlaceholderText("Descricao do commit (opcional)")
    window.commit_description_input.setFixedHeight(120)
    layout.addWidget(window.commit_description_input)

    action_row = QWidget(window.commit_tab)
    action_layout = QHBoxLayout(action_row)
    action_layout.setContentsMargins(0, 0, 0, 0)
    action_layout.setSpacing(6)

    window.commit_run_button = QPushButton("Commit", action_row)
    window.commit_run_button.setProperty("role", "primary")
    window.commit_run_button.clicked.connect(window._create_commit_from_selection)
    action_layout.addWidget(window.commit_run_button)

    window.commit_open_pr_button = QPushButton("Abrir PR", action_row)
    window.commit_open_pr_button.clicked.connect(window._open_commit_pr_in_github)
    action_layout.addWidget(window.commit_open_pr_button)

    layout.addWidget(action_row)
    window._refresh_commit_files()
