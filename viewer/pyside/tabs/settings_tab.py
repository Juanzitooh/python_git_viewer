from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def build_settings_tab(window: object) -> None:
    layout = QVBoxLayout(window.settings_tab)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    theme_row = QWidget(window.settings_tab)
    theme_layout = QHBoxLayout(theme_row)
    theme_layout.setContentsMargins(0, 0, 0, 0)
    theme_layout.setSpacing(6)
    theme_layout.addWidget(QLabel("Tema:", theme_row))
    window.settings_theme_combo = QComboBox(theme_row)
    window.settings_theme_combo.addItem("Claro", "light")
    window.settings_theme_combo.addItem("Escuro", "dark")
    theme_layout.addWidget(window.settings_theme_combo)
    theme_layout.addStretch(1)
    layout.addWidget(theme_row)

    limit_row = QWidget(window.settings_tab)
    limit_layout = QHBoxLayout(limit_row)
    limit_layout.setContentsMargins(0, 0, 0, 0)
    limit_layout.setSpacing(6)
    limit_layout.addWidget(QLabel("Limite padrão de commits:", limit_row))
    window.settings_commit_limit_combo = QComboBox(limit_row)
    for value in (50, 100, 200, 500, 1000):
        window.settings_commit_limit_combo.addItem(str(value), value)
    limit_layout.addWidget(window.settings_commit_limit_combo)
    limit_layout.addStretch(1)
    layout.addWidget(limit_row)

    workspace_row = QWidget(window.settings_tab)
    workspace_layout = QHBoxLayout(workspace_row)
    workspace_layout.setContentsMargins(0, 0, 0, 0)
    workspace_layout.setSpacing(6)
    workspace_layout.addWidget(QLabel("Raiz do workspace:", workspace_row))
    window.settings_workspace_root_edit = QLineEdit(workspace_row)
    workspace_layout.addWidget(window.settings_workspace_root_edit, stretch=1)
    window.settings_workspace_root_pick_button = QPushButton("Pasta...", workspace_row)
    window.settings_workspace_root_pick_button.clicked.connect(window._pick_settings_workspace_root)
    workspace_layout.addWidget(window.settings_workspace_root_pick_button)
    layout.addWidget(workspace_row)

    actions_row = QWidget(window.settings_tab)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    window.settings_save_button = QPushButton("Salvar configurações", actions_row)
    window.settings_save_button.setProperty("role", "primary")
    window.settings_save_button.clicked.connect(window._save_settings_from_tab)
    actions_layout.addWidget(window.settings_save_button)
    actions_layout.addStretch(1)
    layout.addWidget(actions_row)

    window.settings_status_label = QLabel("Ajuste e salve as configurações.", window.settings_tab)
    layout.addWidget(window.settings_status_label)
    layout.addStretch(1)

    window._load_settings_into_tab()
