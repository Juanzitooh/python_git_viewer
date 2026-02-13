from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..theme import THEME_COLOR_FIELDS


def build_settings_tab(window: object) -> None:
    layout = QVBoxLayout(window.settings_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    scroll = QScrollArea(window.settings_tab)
    scroll.setObjectName("SettingsScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_content = QWidget(scroll)
    scroll_content.setObjectName("SettingsScrollContent")
    content_layout = QVBoxLayout(scroll_content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(8)
    scroll.setWidget(scroll_content)
    layout.addWidget(scroll, stretch=1)

    theme_row = QWidget(scroll_content)
    theme_layout = QHBoxLayout(theme_row)
    theme_layout.setContentsMargins(0, 0, 0, 0)
    theme_layout.setSpacing(6)
    theme_layout.addWidget(QLabel("Tema:", theme_row))
    window.settings_theme_combo = QComboBox(theme_row)
    window.settings_theme_combo.addItem("Claro", "light")
    window.settings_theme_combo.addItem("Escuro", "dark")
    window.settings_theme_combo.currentIndexChanged.connect(
        lambda _index: window._on_settings_theme_changed()
    )
    theme_layout.addWidget(window.settings_theme_combo)
    window.settings_theme_reset_button = QPushButton("Resetar cores do tema", theme_row)
    window.settings_theme_reset_button.clicked.connect(window._reset_settings_theme_colors)
    theme_layout.addWidget(window.settings_theme_reset_button)
    theme_layout.addStretch(1)
    content_layout.addWidget(theme_row)

    colors_row = QWidget(scroll_content)
    colors_layout = QVBoxLayout(colors_row)
    colors_layout.setContentsMargins(0, 0, 0, 0)
    colors_layout.setSpacing(6)
    colors_layout.addWidget(QLabel("Paleta do tema atual (preview ao mudar):", colors_row))

    colors_grid = QGridLayout()
    colors_grid.setContentsMargins(0, 0, 0, 0)
    colors_grid.setHorizontalSpacing(8)
    colors_grid.setVerticalSpacing(6)
    window.settings_theme_color_inputs = {}
    window.settings_theme_color_previews = {}
    for row_index, (color_key, color_label) in enumerate(THEME_COLOR_FIELDS):
        label = QLabel(f"{color_label}:", colors_row)
        colors_grid.addWidget(label, row_index, 0)

        color_input = QLineEdit(colors_row)
        color_input.setPlaceholderText("#RRGGBB")
        color_input.setMaxLength(7)
        color_input.editingFinished.connect(
            lambda key=color_key: window._on_settings_theme_color_edited(key)
        )
        colors_grid.addWidget(color_input, row_index, 1)

        color_preview = QLabel("", colors_row)
        color_preview.setFixedWidth(30)
        color_preview.setMinimumHeight(18)
        colors_grid.addWidget(color_preview, row_index, 2)

        pick_button = QPushButton("Cor...", colors_row)
        pick_button.clicked.connect(lambda _=False, key=color_key: window._pick_settings_theme_color(key))
        colors_grid.addWidget(pick_button, row_index, 3)

        window.settings_theme_color_inputs[color_key] = color_input
        window.settings_theme_color_previews[color_key] = color_preview

    colors_layout.addLayout(colors_grid)
    content_layout.addWidget(colors_row)

    workspace_row = QWidget(scroll_content)
    workspace_layout = QHBoxLayout(workspace_row)
    workspace_layout.setContentsMargins(0, 0, 0, 0)
    workspace_layout.setSpacing(6)
    workspace_layout.addWidget(QLabel("Raiz do workspace:", workspace_row))
    window.settings_workspace_root_edit = QLineEdit(workspace_row)
    workspace_layout.addWidget(window.settings_workspace_root_edit, stretch=1)
    window.settings_workspace_root_pick_button = QPushButton("Pasta...", workspace_row)
    window.settings_workspace_root_pick_button.clicked.connect(window._pick_settings_workspace_root)
    workspace_layout.addWidget(window.settings_workspace_root_pick_button)
    content_layout.addWidget(workspace_row)

    actions_row = QWidget(scroll_content)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    window.settings_save_button = QPushButton("Salvar configurações", actions_row)
    window.settings_save_button.setProperty("role", "primary")
    window.settings_save_button.clicked.connect(window._save_settings_from_tab)
    actions_layout.addWidget(window.settings_save_button)
    actions_layout.addStretch(1)
    content_layout.addWidget(actions_row)

    content_layout.addStretch(1)

    window.settings_status_label = QLabel("Ajuste e salve as configurações.", window.settings_tab)
    layout.addWidget(window.settings_status_label)

    window._load_settings_into_tab()
