from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def build_commit_tab(window: object) -> None:
    root_layout = QVBoxLayout(window.commit_tab)
    root_layout.setContentsMargins(12, 12, 12, 12)
    root_layout.setSpacing(8)

    splitter = QSplitter(Qt.Orientation.Horizontal, window.commit_tab)
    splitter.setChildrenCollapsible(False)
    root_layout.addWidget(splitter, stretch=1)

    left_column = QWidget(splitter)
    left_layout = QVBoxLayout(left_column)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(8)

    top_row = QWidget(left_column)
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

    window.commit_stage_selected_button = QPushButton("Stage selecionado", top_row)
    window.commit_stage_selected_button.clicked.connect(window._stage_selected_commit_file)
    top_layout.addWidget(window.commit_stage_selected_button)

    window.commit_unstage_selected_button = QPushButton("Unstage selecionado", top_row)
    window.commit_unstage_selected_button.clicked.connect(window._unstage_selected_commit_file)
    top_layout.addWidget(window.commit_unstage_selected_button)

    window.commit_stage_hunk_button = QPushButton("Stage bloco", top_row)
    window.commit_stage_hunk_button.clicked.connect(window._stage_selected_commit_hunk)
    top_layout.addWidget(window.commit_stage_hunk_button)

    window.commit_unstage_hunk_button = QPushButton("Unstage bloco", top_row)
    window.commit_unstage_hunk_button.clicked.connect(window._unstage_selected_commit_hunk)
    top_layout.addWidget(window.commit_unstage_hunk_button)

    window.commit_stage_line_button = QPushButton("Stage linha", top_row)
    window.commit_stage_line_button.clicked.connect(window._stage_selected_commit_line)
    top_layout.addWidget(window.commit_stage_line_button)

    window.commit_unstage_line_button = QPushButton("Unstage linha", top_row)
    window.commit_unstage_line_button.clicked.connect(window._unstage_selected_commit_line)
    top_layout.addWidget(window.commit_unstage_line_button)

    top_layout.addStretch(1)
    window.commit_selection_label = QLabel("Selecionados: 0/0", top_row)
    top_layout.addWidget(window.commit_selection_label)

    left_layout.addWidget(top_row)

    window.commit_files_list = QListWidget(left_column)
    window.commit_files_list.itemChanged.connect(window._on_commit_file_item_changed)
    window.commit_files_list.itemSelectionChanged.connect(window._on_commit_file_selected)
    left_layout.addWidget(window.commit_files_list, stretch=1)

    window.commit_title_input = QLineEdit(left_column)
    window.commit_title_input.setPlaceholderText("Titulo do commit (obrigatorio)")
    left_layout.addWidget(window.commit_title_input)

    window.commit_description_input = QPlainTextEdit(left_column)
    window.commit_description_input.setPlaceholderText("Descricao do commit (opcional)")
    window.commit_description_input.setFixedHeight(120)
    left_layout.addWidget(window.commit_description_input)

    action_row = QWidget(left_column)
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

    left_layout.addWidget(action_row)

    right_column = QWidget(splitter)
    right_layout = QVBoxLayout(right_column)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(8)

    diff_header = QWidget(right_column)
    diff_header_layout = QHBoxLayout(diff_header)
    diff_header_layout.setContentsMargins(0, 0, 0, 0)
    diff_header_layout.setSpacing(6)
    diff_header_layout.addWidget(QLabel("Diff do arquivo selecionado:", diff_header))
    diff_header_layout.addStretch(1)
    window.commit_word_diff_check = QCheckBox("Diff por palavra", diff_header)
    window.commit_word_diff_check.stateChanged.connect(lambda _state: window._refresh_commit_diff())
    diff_header_layout.addWidget(window.commit_word_diff_check)
    right_layout.addWidget(diff_header)

    window.commit_diff_view = QPlainTextEdit(right_column)
    window.commit_diff_view.setReadOnly(True)
    window.commit_diff_view.setPlaceholderText("Selecione um arquivo para visualizar o diff.")
    window.commit_diff_view.cursorPositionChanged.connect(window._on_commit_diff_cursor_changed)
    right_layout.addWidget(window.commit_diff_view, stretch=1)

    splitter.addWidget(left_column)
    splitter.addWidget(right_column)
    splitter.setStretchFactor(0, 2)
    splitter.setStretchFactor(1, 3)

    window._refresh_commit_files()
