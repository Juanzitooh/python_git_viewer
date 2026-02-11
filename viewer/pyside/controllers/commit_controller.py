from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from ...core.commit_ops import (
    create_commit as core_create_commit,
    has_staged_changes as core_has_staged_changes,
    list_modified_files as core_list_modified_files,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
)


def refresh_commit_files(window: object) -> None:
    window.commit_files_list.blockSignals(True)
    window.commit_files_list.clear()
    if not window.repo_path:
        window.commit_files_list.blockSignals(False)
        update_commit_selection_label(window)
        return
    try:
        files = core_list_modified_files(window.repo_path)
    except RuntimeError as exc:
        window.commit_files_list.blockSignals(False)
        QMessageBox.critical(window, "Commit", str(exc))
        update_commit_selection_label(window)
        return
    for path in files:
        item = QListWidgetItem(path, window.commit_files_list)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
        item.setCheckState(Qt.CheckState.Checked)
    window.commit_files_list.blockSignals(False)
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
        path = item.text().strip()
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
