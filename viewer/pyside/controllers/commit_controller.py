from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QListWidgetItem, QMessageBox

from ...core.commit_ops import (
    apply_patch_to_index as core_apply_patch_to_index,
    create_stash as core_create_stash,
    create_commit as core_create_commit,
    get_file_patch as core_get_file_patch,
    get_last_commit_subject as core_get_last_commit_subject,
    has_staged_changes as core_has_staged_changes,
    list_status_entries as core_list_status_entries,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
    unstage_paths as core_unstage_paths,
    undo_last_commit as core_undo_last_commit,
)
from ...core.diff_utils import build_patch_for_hunk, build_patch_for_line, parse_diff_data


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
        if hasattr(window, "commit_stage_hunk_button"):
            window.commit_stage_hunk_button.setEnabled(False)
        if hasattr(window, "commit_unstage_hunk_button"):
            window.commit_unstage_hunk_button.setEnabled(False)
        if hasattr(window, "commit_stage_line_button"):
            window.commit_stage_line_button.setEnabled(False)
        if hasattr(window, "commit_unstage_line_button"):
            window.commit_unstage_line_button.setEnabled(False)
        return
    entry = window.commit_status_entries_by_path.get(path, {})
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    window.commit_stage_selected_button.setEnabled(has_unstaged)
    window.commit_unstage_selected_button.setEnabled(has_staged)
    selected_hunk = _selected_commit_hunk_index(window)
    has_hunk = selected_hunk is not None
    scope = str(getattr(window, "commit_diff_scope", "")).strip()
    if hasattr(window, "commit_stage_hunk_button"):
        window.commit_stage_hunk_button.setEnabled(has_hunk and scope == "unstaged")
    if hasattr(window, "commit_unstage_hunk_button"):
        window.commit_unstage_hunk_button.setEnabled(has_hunk and scope == "staged")
    line_info = _selected_commit_line_info(window)
    is_changed_line = bool(line_info and line_info.line_type in ("added", "removed"))
    if hasattr(window, "commit_stage_line_button"):
        window.commit_stage_line_button.setEnabled(is_changed_line and scope == "unstaged")
    if hasattr(window, "commit_unstage_line_button"):
        window.commit_unstage_line_button.setEnabled(is_changed_line and scope == "staged")


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
    window.commit_diff_scope = ""
    if not window.repo_path:
        window.commit_files_list.blockSignals(False)
        window.commit_selected_path = ""
        if hasattr(window, "commit_diff_view"):
            window.commit_diff_view.setPlainText("")
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
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
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
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
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        return
    path = _current_commit_file_path(window)
    if not path:
        window.commit_diff_view.setPlainText("(selecione um arquivo)")
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        _sync_commit_stage_buttons(window)
        return
    entry = window.commit_status_entries_by_path.get(path)
    if entry is None:
        window.commit_diff_view.setPlainText("(arquivo não encontrado no status atual)")
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        _sync_commit_stage_buttons(window)
        return
    word_diff = bool(getattr(window, "commit_word_diff_check", None) and window.commit_word_diff_check.isChecked())
    status_code = str(entry.get("status", "")).strip()
    untracked = status_code == "??"
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    try:
        patch = ""
        if untracked or has_unstaged:
            window.commit_diff_scope = "unstaged"
            patch = core_get_file_patch(
                window.repo_path,
                path,
                word_diff=word_diff,
                cached=False,
                untracked=untracked,
            )
        if not patch and has_staged:
            window.commit_diff_scope = "staged"
            patch = core_get_file_patch(
                window.repo_path,
                path,
                word_diff=word_diff,
                cached=True,
            )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        window.commit_diff_view.setPlainText("")
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        _sync_commit_stage_buttons(window)
        return
    display_patch = patch or "(sem diff para este arquivo)"
    window.commit_diff_view.setPlainText(display_patch)
    if patch:
        _build_commit_diff_maps(window, patch)
    else:
        window.commit_diff_data = None
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
    _sync_commit_stage_buttons(window)


def _build_commit_diff_maps(window: object, patch: str) -> None:
    diff_data = parse_diff_data(patch)
    line_to_hunk: dict[int, int] = {}
    line_to_info: dict[int, object] = {}
    line_no = 1
    for _ in diff_data.header_lines:
        line_no += 1
    for hunk_index, hunk in enumerate(diff_data.hunks):
        line_to_hunk[line_no] = hunk_index
        line_no += 1
        for line_info in hunk.lines:
            line_to_hunk[line_no] = hunk_index
            line_to_info[line_no] = line_info
            line_no += 1
    window.commit_diff_data = diff_data
    window.commit_diff_hunk_by_line = line_to_hunk
    window.commit_diff_info_by_line = line_to_info
    if line_to_hunk:
        window.commit_diff_selected_line = min(line_to_hunk.keys())


def _selected_commit_hunk_index(window: object) -> int | None:
    line_to_hunk = getattr(window, "commit_diff_hunk_by_line", {})
    if not line_to_hunk:
        return None
    selected_line = int(getattr(window, "commit_diff_selected_line", 0) or 0)
    if selected_line in line_to_hunk:
        return int(line_to_hunk[selected_line])
    smaller = [line for line in line_to_hunk if line <= selected_line]
    if not smaller:
        return None
    nearest = max(smaller)
    return int(line_to_hunk[nearest])


def _selected_commit_line_info(window: object) -> object | None:
    line_to_info = getattr(window, "commit_diff_info_by_line", {})
    if not line_to_info:
        return None
    selected_line = int(getattr(window, "commit_diff_selected_line", 0) or 0)
    return line_to_info.get(selected_line)


def on_commit_diff_cursor_changed(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    cursor = window.commit_diff_view.textCursor()
    window.commit_diff_selected_line = cursor.blockNumber() + 1
    _sync_commit_stage_buttons(window)


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


def stage_selected_commit_hunk(window: object) -> None:
    if not window.repo_path:
        return
    if str(getattr(window, "commit_diff_scope", "")).strip() != "unstaged":
        QMessageBox.information(window, "Commit", "Selecione um diff unstaged para stage do bloco.")
        return
    diff_data = getattr(window, "commit_diff_data", None)
    if diff_data is None:
        QMessageBox.information(window, "Commit", "Selecione um arquivo com diff disponível.")
        return
    hunk_index = _selected_commit_hunk_index(window)
    if hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    patch = build_patch_for_hunk(diff_data, hunk_index)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Bloco adicionado ao stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_hunk(window: object) -> None:
    if not window.repo_path:
        return
    if str(getattr(window, "commit_diff_scope", "")).strip() != "staged":
        QMessageBox.information(window, "Commit", "Selecione um diff staged para unstage do bloco.")
        return
    diff_data = getattr(window, "commit_diff_data", None)
    if diff_data is None:
        QMessageBox.information(window, "Commit", "Selecione um arquivo com diff disponível.")
        return
    hunk_index = _selected_commit_hunk_index(window)
    if hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    patch = build_patch_for_hunk(diff_data, hunk_index)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Bloco removido do stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def stage_selected_commit_line(window: object) -> None:
    if not window.repo_path:
        return
    if str(getattr(window, "commit_diff_scope", "")).strip() != "unstaged":
        QMessageBox.information(window, "Commit", "Selecione um diff unstaged para stage da linha.")
        return
    diff_data = getattr(window, "commit_diff_data", None)
    line_info = _selected_commit_line_info(window)
    if diff_data is None or line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Linha adicionada ao stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_line(window: object) -> None:
    if not window.repo_path:
        return
    if str(getattr(window, "commit_diff_scope", "")).strip() != "staged":
        QMessageBox.information(window, "Commit", "Selecione um diff staged para unstage da linha.")
        return
    diff_data = getattr(window, "commit_diff_data", None)
    line_info = _selected_commit_line_info(window)
    if diff_data is None or line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Linha removida do stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def create_stash_from_commit_tab(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Stash", "Selecione um repositório válido primeiro.")
        return
    message, accepted = QInputDialog.getText(
        window,
        "Criar stash",
        "Mensagem do stash:",
        text="git_viewer",
    )
    if not accepted:
        return
    stash_message = message.strip() or "git_viewer"
    try:
        core_create_stash(window.repo_path, message=stash_message, include_untracked=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    window._set_status("Stash criado com sucesso.")
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()


def undo_last_commit_from_commit_tab(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Undo commit", "Selecione um repositório válido primeiro.")
        return
    try:
        subject = core_get_last_commit_subject(window.repo_path)
    except RuntimeError as exc:
        QMessageBox.warning(window, "Undo commit", str(exc))
        return
    if not subject:
        QMessageBox.information(window, "Undo commit", "Nenhum commit encontrado para desfazer.")
        return
    modes = ["soft", "mixed", "hard"]
    selected_mode, accepted = QInputDialog.getItem(
        window,
        "Undo commit",
        f"Commit alvo: {subject}\nModo de reset:",
        modes,
        current=1,
        editable=False,
    )
    if not accepted or not selected_mode:
        return
    mode = str(selected_mode).strip().lower()
    if mode == "hard":
        confirm = QMessageBox.question(
            window,
            "Confirmar reset --hard",
            "Modo hard descarta alterações locais. Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
    try:
        core_undo_last_commit(window.repo_path, mode=mode)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Undo commit", str(exc))
        return
    window._set_status(f"Último commit desfeito ({mode}).")
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()


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
