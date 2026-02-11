from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def build_compare_tab(window: object) -> None:
    window.compare_file_entries: list[dict[str, object]] = []
    window.compare_current_file_path = ""
    window._setting_compare_branches_programmatically = False

    layout = QVBoxLayout(window.compare_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top_row = QWidget(window.compare_tab)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)

    top_layout.addWidget(QLabel("Origem:", top_row))
    window.compare_origin_combo = QComboBox(top_row)
    window.compare_origin_combo.currentIndexChanged.connect(window._on_compare_branches_changed)
    top_layout.addWidget(window.compare_origin_combo)

    window.compare_swap_button = QPushButton("Trocar", top_row)
    window.compare_swap_button.clicked.connect(window._swap_compare_branches)
    top_layout.addWidget(window.compare_swap_button)

    top_layout.addWidget(QLabel("Destino:", top_row))
    window.compare_dest_combo = QComboBox(top_row)
    window.compare_dest_combo.currentIndexChanged.connect(window._on_compare_branches_changed)
    top_layout.addWidget(window.compare_dest_combo)

    window.compare_refresh_button = QPushButton("Atualizar", top_row)
    window.compare_refresh_button.clicked.connect(window._refresh_compare_view)
    top_layout.addWidget(window.compare_refresh_button)

    window.compare_word_diff_check = QCheckBox("Diff por palavra", top_row)
    window.compare_word_diff_check.stateChanged.connect(window._refresh_compare_patch)
    top_layout.addWidget(window.compare_word_diff_check)

    top_layout.addStretch(1)
    layout.addWidget(top_row)

    window.compare_status_label = QLabel("Selecione origem e destino para comparar.", window.compare_tab)
    layout.addWidget(window.compare_status_label)

    body_splitter = QSplitter(Qt.Orientation.Horizontal, window.compare_tab)
    body_splitter.setChildrenCollapsible(False)

    window.compare_commits_list = QListWidget(body_splitter)
    window.compare_files_list = QListWidget(body_splitter)
    window.compare_files_list.itemSelectionChanged.connect(window._on_compare_file_selected)
    window.compare_patch_view = QPlainTextEdit(body_splitter)
    window.compare_patch_view.setReadOnly(True)

    body_splitter.setStretchFactor(0, 2)
    body_splitter.setStretchFactor(1, 2)
    body_splitter.setStretchFactor(2, 4)
    layout.addWidget(body_splitter, stretch=1)
    window._clear_compare_view()
