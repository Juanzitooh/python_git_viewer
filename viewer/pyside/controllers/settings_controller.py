from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

from ...core.repo_workspace import default_repo_scan_root
from ...core.settings_store import normalize_repo_path


def load_settings_into_tab(window: object) -> None:
    if not hasattr(window, "settings_theme_combo"):
        return
    theme = str(window.settings_data.get("theme", "light"))
    theme_index = window.settings_theme_combo.findData(theme)
    if theme_index < 0:
        theme_index = window.settings_theme_combo.findData("light")
    if theme_index >= 0:
        window.settings_theme_combo.setCurrentIndex(theme_index)

    commit_limit_raw = window.settings_data.get("commit_limit", 100)
    try:
        commit_limit = int(commit_limit_raw)
    except (TypeError, ValueError):
        commit_limit = 100
    limit_index = window.settings_commit_limit_combo.findData(commit_limit)
    if limit_index < 0:
        limit_index = window.settings_commit_limit_combo.findData(100)
    if limit_index >= 0:
        window.settings_commit_limit_combo.setCurrentIndex(limit_index)

    workspace_root = str(window.settings_data.get("repo_scan_root", window.repo_scan_root)).strip()
    if workspace_root:
        workspace_root = normalize_repo_path(workspace_root)
    else:
        workspace_root = normalize_repo_path(default_repo_scan_root())
    window.settings_workspace_root_edit.setText(workspace_root)


def pick_settings_workspace_root(window: object) -> None:
    current = window.settings_workspace_root_edit.text().strip() or window.repo_scan_root
    selected = QFileDialog.getExistingDirectory(window, "Selecionar raiz do workspace", current)
    if not selected:
        return
    normalized = normalize_repo_path(selected)
    window.settings_workspace_root_edit.setText(normalized)


def save_settings_from_tab(window: object) -> None:
    theme_data = window.settings_theme_combo.currentData()
    theme = str(theme_data).strip() if theme_data is not None else "light"
    if theme not in ("light", "dark"):
        theme = "light"

    limit_data = window.settings_commit_limit_combo.currentData()
    try:
        commit_limit = int(limit_data)
    except (TypeError, ValueError):
        commit_limit = 100
    commit_limit = max(1, commit_limit)

    workspace_text = window.settings_workspace_root_edit.text().strip()
    workspace_root = (
        normalize_repo_path(workspace_text)
        if workspace_text
        else normalize_repo_path(default_repo_scan_root())
    )

    window.settings_data["theme"] = theme
    window.settings_data["commit_limit"] = commit_limit
    window.settings_data["repo_scan_root"] = workspace_root
    window.repo_scan_root = workspace_root

    window._persist_state()
    window._apply_theme_from_settings()
    window.workspace_root_edit.setText(window.repo_scan_root)
    window._scan_workspace_repos()
    window._reload_history_commits()
    window.settings_status_label.setText("Configurações salvas.")
    window._set_status("Configurações salvas.")
