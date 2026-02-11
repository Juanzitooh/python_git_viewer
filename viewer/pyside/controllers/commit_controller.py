from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from ...core.commit_ops import (
    create_commit as core_create_commit,
    get_file_patch as core_get_file_patch,
    has_staged_changes as core_has_staged_changes,
    list_status_entries as core_list_status_entries,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
    unstage_paths as core_unstage_paths,
)


def _sync_commit_pr_button_state(window: object, file_count: int) -> None:
    if not hasattr(window, "commit_open_pr_button"):
        return
    can_open_pr = bool(window.repo_path and file_count == 0)
    window.commit_open_pr_button.setEnabled(can_open_pr)


def _entry_stage_marker(entry: dict[str, str | bool]) -> str:
    staged = bool(entry.get("staged", False))
    unstaged = bool(entry.get("unstaged", False))
    if staged and unstaged:
        return "[~]"
    if staged:
        return "[x]"
    return "[ ]"


def _entry_status_label(entry: dict[str, str | bool]) -> str:
    status = str(entry.get("status", "")).strip()
    path = str(entry.get("path", "")).strip()
    return f"{_entry_stage_marker(entry)} {status:>2} {path}"


def _current_commit_file_path(window: object) -> str:
    selected_items = window.commit_files_list.selectedItems()
    if not selected_items:
        return ""
    value = selected_items[0].data(Qt.ItemDataRole.UserRole)
    return str(value).strip() if value is not None else ""


def _sync_commit_stage_buttons(window: object) -> None:
    if not hasattr(window, "commit_stage_selected_button") or not hasattr(window, "commit_unstage_selected_button"):
        return
    path = _current_commit_file_path(window)
    if not path:
        window.commit_stage_selected_button.setEnabled(False)
        window.commit_unstage_selected_button.setEnabled(False)
        return
    entry = window.commit_status_entries_by_path.get(path, {})
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    window.commit_stage_selected_button.setEnabled(has_unstaged)
    window.commit_unstage_selected_button.setEnabled(has_staged)


def _restore_commit_selection(window: object, preferred_path: str) -> None:
    target = preferred_path.strip()
    if not target:
        if window.commit_files_list.count() > 0:
            window.commit_files_list.setCurrentRow(0)
        return
    for index in range(window.commit_files_list.count()):
        item = window.commit_files_list.item(index)
        if item is None:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        candidate = str(value).strip() if value is not None else ""
        if candidate != target:
            continue
        window.commit_files_list.setCurrentRow(index)
        return
    if window.commit_files_list.count() > 0:
        window.commit_files_list.setCurrentRow(0)


def refresh_commit_files(window: object) -> None:
    previous_checked_paths: set[str] = set()
    had_items = window.commit_files_list.count() > 0
    for item in iter_commit_items(window):
        if item.checkState() != Qt.CheckState.Checked:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        path = str(value).strip() if value is not None else ""
        if path:
            previous_checked_paths.add(path)
    preferred_path = str(getattr(window, "commit_selected_path", "")).strip()

    window.commit_files_list.blockSignals(True)
    window.commit_files_list.clear()
    window.commit_status_entries_by_path = {}
    if not window.repo_path:
        window.commit_files_list.blockSignals(False)
        window.commit_selected_path = ""
        if hasattr(window, "commit_diff_view"):
            window.commit_diff_view.setPlainText("")
        _sync_commit_pr_button_state(window, 0)
        _sync_commit_stage_buttons(window)
        update_commit_selection_label(window)
        return
    try:
        status_entries = core_list_status_entries(window.repo_path)
    except RuntimeError as exc:
        window.commit_files_list.blockSignals(False)
        window.commit_selected_path = ""
        if hasattr(window, "commit_diff_view"):
            window.commit_diff_view.setPlainText("")
        _sync_commit_pr_button_state(window, 0)
        _sync_commit_stage_buttons(window)
        QMessageBox.critical(window, "Commit", str(exc))
        update_commit_selection_label(window)
        return
    for entry in status_entries:
        path_for_git = str(entry.get("path_for_git", "")).strip()
        if not path_for_git:
            continue
        window.commit_status_entries_by_path[path_for_git] = entry
        item = QListWidgetItem(_entry_status_label(entry), window.commit_files_list)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
        item.setData(Qt.ItemDataRole.UserRole, path_for_git)
        if had_items:
            checked = path_for_git in previous_checked_paths
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        else:
            item.setCheckState(Qt.CheckState.Checked)
    window.commit_files_list.blockSignals(False)
    _sync_commit_pr_button_state(window, len(status_entries))
    _restore_commit_selection(window, preferred_path)
    refresh_commit_diff(window)
    _sync_commit_stage_buttons(window)
    update_commit_selection_label(window)


def iter_commit_items(window: object) -> list[QListWidgetItem]:
    items: list[QListWidgetItem] = []
    for index in range(window.commit_files_list.count()):
        item = window.commit_files_list.item(index)
        if item is not None:
            items.append(item)
    return items


def update_commit_selection_label(window: object) -> None:
    items = iter_commit_items(window)
    selected = 0
    for item in items:
        if item.checkState() == Qt.CheckState.Checked:
            selected += 1
    window.commit_selection_label.setText(f"Selecionados: {selected}/{len(items)}")


def on_commit_file_item_changed(window: object, _item: QListWidgetItem) -> None:
    update_commit_selection_label(window)


def on_commit_file_selected(window: object) -> None:
    window.commit_selected_path = _current_commit_file_path(window)
    refresh_commit_diff(window)
    _sync_commit_stage_buttons(window)


def refresh_commit_diff(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    if not window.repo_path:
        window.commit_diff_view.setPlainText("")
        return
    path = _current_commit_file_path(window)
    if not path:
        window.commit_diff_view.setPlainText("(selecione um arquivo)")
        return
    entry = window.commit_status_entries_by_path.get(path)
    if entry is None:
        window.commit_diff_view.setPlainText("(arquivo não encontrado no status atual)")
        return
    word_diff = bool(getattr(window, "commit_word_diff_check", None) and window.commit_word_diff_check.isChecked())
    status_code = str(entry.get("status", "")).strip()
    untracked = status_code == "??"
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    try:
        patch = ""
        if untracked or has_unstaged:
            patch = core_get_file_patch(
                window.repo_path,
                path,
                word_diff=word_diff,
                cached=False,
                untracked=untracked,
            )
        if not patch and has_staged:
            patch = core_get_file_patch(
                window.repo_path,
                path,
                word_diff=word_diff,
                cached=True,
            )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        window.commit_diff_view.setPlainText("")
        return
    window.commit_diff_view.setPlainText(patch or "(sem diff para este arquivo)")


def stage_selected_commit_file(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para stage.")
        return
    try:
        core_stage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    window._set_status(f"Arquivo adicionado ao stage: {path}")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_file(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para unstage.")
        return
    try:
        core_unstage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    window._set_status(f"Arquivo removido do stage: {path}")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def select_all_commit_files(window: object) -> None:
    window.commit_files_list.blockSignals(True)
    for item in iter_commit_items(window):
        item.setCheckState(Qt.CheckState.Checked)
    window.commit_files_list.blockSignals(False)
    update_commit_selection_label(window)


def clear_commit_file_selection(window: object) -> None:
    window.commit_files_list.blockSignals(True)
    for item in iter_commit_items(window):
        item.setCheckState(Qt.CheckState.Unchecked)
    window.commit_files_list.blockSignals(False)
    update_commit_selection_label(window)


def get_selected_commit_paths(window: object) -> list[str]:
    selected: list[str] = []
    for item in iter_commit_items(window):
        if item.checkState() != Qt.CheckState.Checked:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        path = str(value).strip() if value is not None else ""
        if path:
            selected.append(path)
    return selected


def create_commit_from_selection(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositorio valido primeiro.")
        return
    title = window.commit_title_input.text().strip()
    if not title:
        QMessageBox.warning(window, "Commit", "Titulo do commit e obrigatorio.")
        return
    selected_paths = get_selected_commit_paths(window)
    if not selected_paths:
        QMessageBox.warning(window, "Commit", "Selecione ao menos um arquivo para commit.")
        return
    description = window.commit_description_input.toPlainText().strip()
    try:
        core_unstage_all(window.repo_path)
        core_stage_paths(window.repo_path, selected_paths)
        if not core_has_staged_changes(window.repo_path):
            QMessageBox.warning(window, "Commit", "Nenhuma alteracao ficou staged para commit.")
            return
        core_create_commit(window.repo_path, title, description)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        refresh_commit_files(window)
        window._refresh_repo_state_ui()
        window._refresh_workspace_tree()
        return
    window.commit_title_input.clear()
    window.commit_description_input.clear()
    window._set_status("Commit concluido.")
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()
