from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QListWidgetItem, QMenu, QMessageBox

from ...core.branch_compare import (
    get_ahead_behind_between as core_get_ahead_behind_between,
    has_potential_conflict as core_has_potential_conflict,
    load_compare_commits as core_load_compare_commits,
    load_compare_file_patch as core_load_compare_file_patch,
    load_compare_file_stats as core_load_compare_file_stats,
)
from ...core.repo_state import (
    get_current_branch as core_get_current_branch,
    list_branches as core_list_branches,
)


def clear_compare_view(window: object) -> None:
    window.compare_file_entries = []
    window.compare_current_file_path = ""
    if hasattr(window, "compare_commits_list"):
        window.compare_commits_list.clear()
    if hasattr(window, "compare_files_list"):
        window.compare_files_list.clear()
    if hasattr(window, "compare_patch_view"):
        window.compare_patch_view.setPlainText("")
    if hasattr(window, "compare_status_label"):
        window.compare_status_label.setText("Selecione origem e destino para comparar.")


def refresh_compare_branch_options(window: object) -> None:
    if not hasattr(window, "compare_origin_combo"):
        return
    if not window.repo_path:
        window._setting_compare_branches_programmatically = True
        try:
            window.compare_origin_combo.clear()
            window.compare_dest_combo.clear()
        finally:
            window._setting_compare_branches_programmatically = False
        clear_compare_view(window)
        return
    try:
        branches = core_list_branches(window.repo_path)
        current = core_get_current_branch(window.repo_path).strip()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Comparar", str(exc))
        clear_compare_view(window)
        return

    origin_value = window.compare_origin_combo.currentData()
    dest_value = window.compare_dest_combo.currentData()
    origin_selected = str(origin_value).strip() if origin_value is not None else ""
    dest_selected = str(dest_value).strip() if dest_value is not None else ""

    if origin_selected not in branches:
        origin_selected = current or (branches[0] if branches else "")
    if dest_selected not in branches or dest_selected == origin_selected:
        dest_selected = ""
        for branch in branches:
            if branch != origin_selected:
                dest_selected = branch
                break
        if not dest_selected and branches:
            dest_selected = branches[0]

    window._setting_compare_branches_programmatically = True
    try:
        window.compare_origin_combo.clear()
        window.compare_dest_combo.clear()
        for branch in branches:
            window.compare_origin_combo.addItem(branch, branch)
            window.compare_dest_combo.addItem(branch, branch)
        origin_index = window.compare_origin_combo.findData(origin_selected)
        if origin_index >= 0:
            window.compare_origin_combo.setCurrentIndex(origin_index)
        dest_index = window.compare_dest_combo.findData(dest_selected)
        if dest_index >= 0:
            window.compare_dest_combo.setCurrentIndex(dest_index)
    finally:
        window._setting_compare_branches_programmatically = False
    refresh_compare_view(window)


def get_compare_branches(window: object) -> tuple[str, str]:
    origin_value = window.compare_origin_combo.currentData()
    dest_value = window.compare_dest_combo.currentData()
    origin = str(origin_value).strip() if origin_value is not None else ""
    dest = str(dest_value).strip() if dest_value is not None else ""
    return origin, dest


def on_compare_branches_changed(window: object, _index: int) -> None:
    if window._setting_compare_branches_programmatically:
        return
    refresh_compare_view(window)


def swap_compare_branches(window: object) -> None:
    origin, dest = get_compare_branches(window)
    if not origin and not dest:
        return
    window._setting_compare_branches_programmatically = True
    try:
        origin_index = window.compare_origin_combo.findData(dest)
        dest_index = window.compare_dest_combo.findData(origin)
        if origin_index >= 0:
            window.compare_origin_combo.setCurrentIndex(origin_index)
        if dest_index >= 0:
            window.compare_dest_combo.setCurrentIndex(dest_index)
    finally:
        window._setting_compare_branches_programmatically = False
    refresh_compare_view(window)


def refresh_compare_view(window: object) -> None:
    window._begin_busy("Atualizando comparacao...")
    try:
        if not window.repo_path:
            clear_compare_view(window)
            return
        origin, dest = get_compare_branches(window)
        if not origin or not dest:
            clear_compare_view(window)
            return
        if origin == dest:
            clear_compare_view(window)
            window.compare_status_label.setText("Origem e destino devem ser diferentes.")
            return

        try:
            commits = core_load_compare_commits(window.repo_path, origin, dest)
            file_stats, totals = core_load_compare_file_stats(window.repo_path, origin, dest)
            behind, ahead = core_get_ahead_behind_between(window.repo_path, origin, dest)
            has_conflict = core_has_potential_conflict(window.repo_path, origin, dest)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Comparar", str(exc))
            clear_compare_view(window)
            return

        window.compare_file_entries = file_stats
        window.compare_current_file_path = ""

        window.compare_commits_list.clear()
        for line in commits:
            window.compare_commits_list.addItem(line)

        window.compare_files_list.blockSignals(True)
        window.compare_files_list.clear()
        for entry in file_stats:
            path = str(entry.get("path", "")).strip()
            if not path:
                continue
            added = int(entry.get("added", 0) or 0)
            deleted = int(entry.get("deleted", 0) or 0)
            binary = bool(entry.get("binary", False))
            if binary:
                label = f"{path} [binario]"
            else:
                label = f"{path} (+{added}/-{deleted})"
            item = QListWidgetItem(label, window.compare_files_list)
            item.setData(Qt.ItemDataRole.UserRole, path)
        window.compare_files_list.blockSignals(False)

        conflict_label = "possivel conflito" if has_conflict else "sem conflito aparente"
        window.compare_status_label.setText(
            (
                f"{origin} -> {dest} | commits: {len(commits)} | arquivos: {totals.get('files', 0)} "
                f"| +{totals.get('added', 0)} -{totals.get('deleted', 0)} | "
                f"ahead/behind: {ahead}/{behind} | {conflict_label}"
            )
        )

        if window.compare_files_list.count() > 0:
            window.compare_files_list.setCurrentRow(0)
        else:
            window.compare_patch_view.setPlainText("(nenhuma diferença)")
    finally:
        window._end_busy()


def on_compare_file_selected(window: object) -> None:
    selected_items = window.compare_files_list.selectedItems()
    if not selected_items:
        window.compare_current_file_path = ""
        refresh_compare_patch(window)
        return
    item = selected_items[0]
    value = item.data(Qt.ItemDataRole.UserRole)
    window.compare_current_file_path = str(value).strip() if value is not None else ""
    refresh_compare_patch(window)


def refresh_compare_patch(window: object) -> None:
    if not window.repo_path:
        window.compare_patch_view.setPlainText("")
        return
    origin, dest = get_compare_branches(window)
    if not origin or not dest or origin == dest:
        window.compare_patch_view.setPlainText("")
        return
    selected_path = window.compare_current_file_path.strip()
    if not selected_path:
        window.compare_patch_view.setPlainText("(selecione um arquivo)")
        return
    word_diff = window.compare_word_diff_check.isChecked()
    try:
        patch = core_load_compare_file_patch(
            window.repo_path,
            origin,
            dest,
            path=selected_path,
            word_diff=word_diff,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Comparar", str(exc))
        window.compare_patch_view.setPlainText("")
        return
    window.compare_patch_view.setPlainText(patch or "(sem diff para este arquivo)")


def _is_compare_file_binary(window: object, selected_path: str) -> bool:
    for entry in window.compare_file_entries:
        path = str(entry.get("path", "")).strip()
        if path != selected_path:
            continue
        return bool(entry.get("binary", False))
    return False


def _copy_compare_file_patch(window: object, path: str) -> None:
    origin, dest = get_compare_branches(window)
    if not origin or not dest or origin == dest:
        QMessageBox.information(window, "Comparar", "Selecione origem e destino validos para copiar o patch.")
        return
    try:
        patch = core_load_compare_file_patch(
            window.repo_path,
            origin,
            dest,
            path=path,
            word_diff=False,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Comparar", str(exc))
        return
    if window._copy_to_clipboard(patch, status=f"Patch do arquivo copiado: {path}"):
        return
    QMessageBox.information(window, "Comparar", "Sem diff textual para copiar neste arquivo.")


def on_compare_file_context_menu(window: object, pos: QPoint) -> None:
    item = window.compare_files_list.itemAt(pos)
    if item is not None:
        value = item.data(Qt.ItemDataRole.UserRole)
        selected_path = str(value).strip() if value is not None else ""
    else:
        selected_path = window.compare_current_file_path.strip()
    if not selected_path:
        return

    is_binary = _is_compare_file_binary(window, selected_path)
    menu = QMenu(window.compare_files_list)
    action_open_vscode = menu.addAction("Abrir arquivo no VS Code")
    action_open_folder = menu.addAction("Abrir na pasta")
    action_copy_relative = menu.addAction("Copiar caminho relativo")
    menu.addSeparator()
    action_copy_patch = menu.addAction("Copiar patch do arquivo")
    action_copy_patch.setEnabled(not is_binary)

    selected_action = menu.exec(window.compare_files_list.mapToGlobal(pos))
    if selected_action is None:
        return
    if selected_action == action_open_vscode:
        window._open_repo_file_in_vscode(selected_path)
        return
    if selected_action == action_open_folder:
        window._open_repo_file_in_explorer(selected_path)
        return
    if selected_action == action_copy_relative:
        window._copy_to_clipboard(selected_path, status="Caminho relativo copiado.")
        return
    if selected_action == action_copy_patch:
        _copy_compare_file_patch(window, selected_path)
