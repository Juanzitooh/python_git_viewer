from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox, QTreeWidgetItem

from ...core.git_client import is_git_repo
from ...core.repo_state import (
    get_ahead_behind as core_get_ahead_behind,
    get_current_branch as core_get_current_branch,
    get_upstream as core_get_upstream,
    list_branches as core_list_branches,
    list_worktree_changed_files as core_list_worktree_changed_files,
)
from ...core.repo_workspace import default_repo_scan_root, discover_git_repositories
from ...core.settings_store import normalize_repo_path


def collect_repo_paths_from_settings(window: object, key: str) -> list[str]:
    items = window.settings_data.get(key, [])
    if not isinstance(items, list):
        return []
    repos: list[str] = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        normalized = normalize_repo_path(raw)
        if not os.path.isdir(normalized) or not is_git_repo(normalized):
            continue
        if normalized not in repos:
            repos.append(normalized)
    return repos


def repo_is_favorite(window: object, repo_path: str) -> bool:
    favorites = collect_repo_paths_from_settings(window, "favorite_repos")
    return normalize_repo_path(repo_path) in favorites


def format_workspace_relative_path(window: object, repo_path: str) -> str:
    normalized_repo = normalize_repo_path(repo_path)
    root = normalize_repo_path(window.repo_scan_root) if window.repo_scan_root else ""
    if root:
        try:
            relative = os.path.relpath(normalized_repo, root)
        except ValueError:
            relative = normalized_repo
        if not relative.startswith(".."):
            return f"/{relative}".replace("\\", "/")
    return normalized_repo


def format_repo_display_label(window: object, repo_path: str) -> str:
    base_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
    relative = format_workspace_relative_path(window, repo_path)
    favorite_prefix = "★ " if repo_is_favorite(window, repo_path) else ""
    return f"{favorite_prefix}{base_name} {relative}"


def collect_known_repos(window: object) -> list[str]:
    ordered: list[str] = []
    for source in (
        collect_repo_paths_from_settings(window, "favorite_repos"),
        collect_repo_paths_from_settings(window, "recent_repos"),
        window.scanned_repos,
        [window.repo_path] if window.repo_path else [],
    ):
        for repo in source:
            normalized = normalize_repo_path(repo)
            if normalized in ordered:
                continue
            if not os.path.isdir(normalized) or not is_git_repo(normalized):
                continue
            ordered.append(normalized)
    return ordered


def load_repo_selector_items(window: object) -> None:
    selected = window.repo_path
    if not selected:
        current = window.repo_combo.currentData()
        selected = str(current).strip() if current is not None else ""
    repos = collect_known_repos(window)
    window._setting_repo_programmatically = True
    try:
        window.repo_combo.clear()
        for repo in repos:
            window.repo_combo.addItem(format_repo_display_label(window, repo), repo)
        if selected:
            index = window.repo_combo.findData(selected)
            if index >= 0:
                window.repo_combo.setCurrentIndex(index)
    finally:
        window._setting_repo_programmatically = False


def on_workspace_root_edited(window: object) -> None:
    candidate = window.workspace_root_edit.text().strip()
    normalized = normalize_repo_path(candidate) if candidate else normalize_repo_path(default_repo_scan_root())
    if normalized == window.repo_scan_root:
        return
    window.repo_scan_root = normalized
    window.workspace_root_edit.setText(window.repo_scan_root)
    scan_workspace_repos(window)
    window._persist_state()


def pick_workspace_root(window: object) -> None:
    selected = QFileDialog.getExistingDirectory(window, "Selecionar raiz do workspace", window.repo_scan_root)
    if not selected:
        return
    window.repo_scan_root = normalize_repo_path(selected)
    window.workspace_root_edit.setText(window.repo_scan_root)
    scan_workspace_repos(window)
    window._persist_state()


def scan_workspace_repos(window: object) -> None:
    window._begin_busy("Escaneando workspace...")
    try:
        root = (
            normalize_repo_path(window.repo_scan_root)
            if window.repo_scan_root
            else normalize_repo_path(default_repo_scan_root())
        )
        os.makedirs(root, exist_ok=True)
        window.repo_scan_root = root
        window.workspace_root_edit.setText(root)
        discovered = discover_git_repositories(root, max_depth=4)
        window.scanned_repos = [normalize_repo_path(path) for path in discovered]
        window.workspace_scan_status_label.setText(
            f"Scan inicial: {len(window.scanned_repos)} encontrados em {root}"
        )
        load_repo_selector_items(window)
        refresh_workspace_tree(window)
        window._refresh_import_source_repos()
    finally:
        window._end_busy()


def build_repo_status_summary(_window: object, repo_path: str) -> str:
    try:
        changed = core_list_worktree_changed_files(repo_path)
    except RuntimeError:
        return "(indisponivel)"
    if not changed:
        return "limpo"
    if len(changed) <= 2:
        suffix = "arquivo" if len(changed) == 1 else "arquivos"
        return f"{len(changed)} {suffix}: {', '.join(changed)}"
    return f"{len(changed)} arquivos: {changed[0]}, {changed[1]}, +{len(changed) - 2}"


def build_repo_snapshot(window: object, repo_path: str) -> tuple[str, int, int, str]:
    branch = "(desconhecida)"
    ahead = 0
    behind = 0
    try:
        branch = core_get_current_branch(repo_path).strip() or branch
    except RuntimeError:
        return branch, ahead, behind, "(indisponivel)"
    upstream = core_get_upstream(repo_path)
    if upstream:
        try:
            behind, ahead = core_get_ahead_behind(repo_path, upstream)
        except RuntimeError:
            behind, ahead = 0, 0
    status = build_repo_status_summary(window, repo_path)
    return branch, ahead, behind, status


def refresh_workspace_tree(window: object) -> None:
    window.workspace_tree.clear()
    repos = collect_known_repos(window)
    if not repos:
        placeholder = QTreeWidgetItem(["(sem repositorios)", "", "", "", "", ""])
        placeholder.setData(0, Qt.ItemDataRole.UserRole, "")
        window.workspace_tree.addTopLevelItem(placeholder)
        window.workspace_tree.resizeColumnToContents(0)
        window.workspace_tree.resizeColumnToContents(2)
        window.workspace_tree.resizeColumnToContents(3)
        window.workspace_tree.resizeColumnToContents(4)
        return
    for repo in repos:
        branch, ahead, behind, status = build_repo_snapshot(window, repo)
        item = QTreeWidgetItem(
            [
                format_repo_display_label(window, repo),
                format_workspace_relative_path(window, repo),
                branch,
                str(ahead),
                str(behind),
                status,
            ]
        )
        item.setData(0, Qt.ItemDataRole.UserRole, repo)
        window.workspace_tree.addTopLevelItem(item)
    window.workspace_tree.resizeColumnToContents(0)
    window.workspace_tree.resizeColumnToContents(2)
    window.workspace_tree.resizeColumnToContents(3)
    window.workspace_tree.resizeColumnToContents(4)
    sync_workspace_tree_selection(window)


def sync_workspace_tree_selection(window: object) -> None:
    window._setting_workspace_selection = True
    try:
        for index in range(window.workspace_tree.topLevelItemCount()):
            item = window.workspace_tree.topLevelItem(index)
            path_value = item.data(0, Qt.ItemDataRole.UserRole)
            repo = str(path_value).strip() if path_value is not None else ""
            should_select = bool(window.repo_path and repo == window.repo_path)
            item.setSelected(should_select)
            if should_select:
                window.workspace_tree.scrollToItem(item)
    finally:
        window._setting_workspace_selection = False


def on_workspace_selection_changed(window: object) -> None:
    if window._setting_workspace_selection:
        return
    selected_items = window.workspace_tree.selectedItems()
    if not selected_items:
        return
    item = selected_items[0]
    path_value = item.data(0, Qt.ItemDataRole.UserRole)
    target_repo = str(path_value).strip() if path_value is not None else ""
    if not target_repo:
        return
    if window.repo_path and normalize_repo_path(window.repo_path) == normalize_repo_path(target_repo):
        return
    set_repo(window, target_repo, save=True)


def on_workspace_item_double_clicked(window: object, item: QTreeWidgetItem, _column: int) -> None:
    path_value = item.data(0, Qt.ItemDataRole.UserRole)
    target_repo = str(path_value).strip() if path_value is not None else ""
    if not target_repo:
        return
    set_repo(window, target_repo, save=True)


def _show_repo_context_menu(window: object, global_pos: QPoint, repo_path: str) -> None:
    normalized = normalize_repo_path(repo_path)
    if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
        return
    menu = QMenu(window)
    action_open_vscode = menu.addAction("Abrir repositório no VS Code")
    action_open_folder = menu.addAction("Abrir na pasta")
    action_copy_path = menu.addAction("Copiar caminho local")
    menu.addSeparator()
    github_menu = menu.addMenu("GitHub")
    action_open_repo = github_menu.addAction("Abrir repositório")
    action_open_branch = github_menu.addAction("Abrir branch atual")
    action_open_commits = github_menu.addAction("Abrir commits da branch")
    action_open_issues = github_menu.addAction("Abrir issues")
    action_open_actions = github_menu.addAction("Abrir actions")
    action_open_releases = github_menu.addAction("Abrir releases")
    github_menu.addSeparator()
    action_copy_repo_url = github_menu.addAction("Copiar URL do repositório")
    action_copy_branch_url = github_menu.addAction("Copiar URL da branch")

    selected_action = menu.exec(global_pos)
    if selected_action is None:
        return
    if selected_action == action_open_vscode:
        window._open_repo_in_vscode(normalized)
        return
    if selected_action == action_open_folder:
        window._open_repo_in_explorer(normalized)
        return
    if selected_action == action_copy_path:
        window._copy_to_clipboard(normalized, status="Caminho do repositório copiado.")
        return
    if selected_action == action_open_repo:
        window._open_repo_in_github(normalized)
        return
    if selected_action == action_open_branch:
        window._open_repo_branch_in_github(normalized)
        return
    if selected_action == action_open_commits:
        window._open_repo_branch_commits_in_github(normalized)
        return
    if selected_action == action_open_issues:
        window._open_repo_issues_in_github(normalized)
        return
    if selected_action == action_open_actions:
        window._open_repo_actions_in_github(normalized)
        return
    if selected_action == action_open_releases:
        window._open_repo_releases_in_github(normalized)
        return
    if selected_action == action_copy_repo_url:
        window._copy_repo_github_url(normalized)
        return
    if selected_action == action_copy_branch_url:
        window._copy_repo_branch_github_url(normalized)


def on_repo_combo_context_menu(window: object, pos: QPoint) -> None:
    selected = window.repo_combo.currentData()
    repo_path = str(selected).strip() if selected is not None else ""
    if not repo_path:
        return
    _show_repo_context_menu(window, window.repo_combo.mapToGlobal(pos), repo_path)


def on_repo_combo_dropdown_context_menu(window: object, pos: QPoint) -> None:
    dropdown = window.repo_combo.view()
    index = dropdown.indexAt(pos)
    repo_path = ""
    if index.isValid():
        value = index.data(Qt.ItemDataRole.UserRole)
        repo_path = str(value).strip() if value is not None else ""
    if not repo_path:
        selected = window.repo_combo.currentData()
        repo_path = str(selected).strip() if selected is not None else ""
    if not repo_path:
        return
    _show_repo_context_menu(window, dropdown.viewport().mapToGlobal(pos), repo_path)


def on_workspace_tree_context_menu(window: object, pos: QPoint) -> None:
    item = window.workspace_tree.itemAt(pos)
    if item is None:
        return
    value = item.data(0, Qt.ItemDataRole.UserRole)
    repo_path = str(value).strip() if value is not None else ""
    if not repo_path:
        return
    _show_repo_context_menu(window, window.workspace_tree.viewport().mapToGlobal(pos), repo_path)


def set_repo(window: object, repo_path: str, *, save: bool) -> None:
    normalized = normalize_repo_path(repo_path) if repo_path else ""
    if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
        window.repo_path = ""
        refresh_repo_state_ui(window)
        window._refresh_commit_files()
        window._clear_history_view()
        window._refresh_compare_branch_options()
        window._sync_import_target_label()
        sync_workspace_tree_selection(window)
        if save:
            window._persist_state()
        return
    window.repo_path = normalized
    add_recent_repo(window, normalized)
    select_repo_combo_item(window, normalized)
    refresh_repo_state_ui(window)
    window._refresh_commit_files()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()
    window._sync_import_target_label()
    sync_workspace_tree_selection(window)
    window._set_status(f"Repositorio ativo: {normalized}")
    if save:
        window._persist_state()


def select_repo_combo_item(window: object, repo_path: str) -> None:
    window._setting_repo_programmatically = True
    try:
        index = window.repo_combo.findData(repo_path)
        if index < 0:
            window.repo_combo.addItem(repo_path, repo_path)
            index = window.repo_combo.findData(repo_path)
        if index >= 0:
            window.repo_combo.setCurrentIndex(index)
    finally:
        window._setting_repo_programmatically = False


def refresh_repo_state_ui(window: object) -> None:
    has_repo = bool(window.repo_path)
    window.fetch_button.setEnabled(has_repo)
    window.new_branch_button.setEnabled(has_repo)
    window.branch_combo.setEnabled(has_repo)
    if not has_repo:
        window.pull_button.setEnabled(False)
        window.push_button.setEnabled(False)
        window.sync_label.setText("Ahead: 0 | Behind: 0")
        window.branch_combo.clear()
        window._sync_import_target_label()
        return

    try:
        branches = core_list_branches(window.repo_path)
        current = core_get_current_branch(window.repo_path).strip()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Erro", str(exc))
        window.repo_path = ""
        refresh_repo_state_ui(window)
        return

    window._setting_branch_programmatically = True
    try:
        window.branch_combo.clear()
        for branch in branches:
            window.branch_combo.addItem(branch, branch)
        index = window.branch_combo.findData(current)
        if index >= 0:
            window.branch_combo.setCurrentIndex(index)
    finally:
        window._setting_branch_programmatically = False

    upstream = core_get_upstream(window.repo_path)
    if not upstream:
        window.pull_button.setEnabled(False)
        window.push_button.setEnabled(False)
        window.sync_label.setText("Ahead: 0 | Behind: 0 (sem upstream)")
        window.fetch_button.setText("Fetch")
        window._sync_import_target_label()
        return

    behind, ahead = core_get_ahead_behind(window.repo_path, upstream)
    window.sync_label.setText(f"Ahead: {ahead} | Behind: {behind}")
    window.pull_button.setEnabled(behind > 0)
    window.push_button.setEnabled(ahead > 0)
    window.fetch_button.setText(f"Fetch ({behind})" if behind > 0 else "Fetch")
    window.pull_button.setText(f"Pull ({behind})" if behind > 0 else "Pull")
    window.push_button.setText(f"Push ({ahead})" if ahead > 0 else "Push")
    window._sync_import_target_label()


def add_recent_repo(window: object, repo_path: str) -> None:
    normalized = normalize_repo_path(repo_path)
    current_items = window.settings_data.get("recent_repos", [])
    items: list[str] = []
    if isinstance(current_items, list):
        for raw in current_items:
            if isinstance(raw, str) and raw.strip():
                entry = normalize_repo_path(raw)
                if entry not in items and os.path.isdir(entry) and is_git_repo(entry):
                    items.append(entry)
    if normalized in items:
        items.remove(normalized)
    items.insert(0, normalized)
    window.settings_data["recent_repos"] = items[:20]
    load_repo_selector_items(window)
    refresh_workspace_tree(window)
