from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QListWidgetItem, QMenu, QMessageBox

from ...core.branch_ops import checkout_branch as core_checkout_branch
from ...core.branch_compare import (
    get_ahead_behind_between as core_get_ahead_behind_between,
    has_potential_conflict as core_has_potential_conflict,
    load_compare_commits as core_load_compare_commits,
    load_compare_file_patch as core_load_compare_file_patch,
    load_compare_file_stats as core_load_compare_file_stats,
)
from ...core.cherry_pick_ops import has_unmerged_conflicts as core_has_unmerged_conflicts
from ...core.commit_content import (
    get_commit_patch as core_get_commit_patch,
    list_commit_files as core_list_commit_files,
)
from ...core.commit_ops import list_modified_files as core_list_modified_files
from ...core.git_client import run_git
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
    if hasattr(window, "compare_action_status_label"):
        window.compare_action_status_label.setText("Selecione origem e destino.")
    _update_compare_action_state(window)


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
            item = QListWidgetItem(line, window.compare_commits_list)
            commit_hash = line.split(" ", 1)[0].strip() if line else ""
            item.setData(Qt.ItemDataRole.UserRole, commit_hash)

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
        _update_compare_action_state(window)
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


def _set_compare_squash_visibility(window: object) -> None:
    if not hasattr(window, "compare_action_combo"):
        return
    action_code = window.compare_action_combo.currentData()
    action = str(action_code).strip() if action_code is not None else "merge"
    show_message = action == "squash"
    if hasattr(window, "compare_squash_message_label"):
        window.compare_squash_message_label.setVisible(show_message)
    if hasattr(window, "compare_squash_message_input"):
        window.compare_squash_message_input.setVisible(show_message)


def _is_compare_worktree_dirty(window: object) -> bool:
    if not window.repo_path:
        return False
    try:
        return bool(core_list_modified_files(window.repo_path))
    except RuntimeError:
        return False


def _update_compare_action_state(window: object) -> None:
    _set_compare_squash_visibility(window)
    if not hasattr(window, "compare_run_button"):
        return
    can_run = False
    can_open_commit = False
    status_text = "Selecione origem e destino."

    if not window.repo_path:
        status_text = "Selecione um repositório."
    else:
        origin, dest = get_compare_branches(window)
        if not origin or not dest:
            status_text = "Selecione origem e destino."
        elif origin == dest:
            status_text = "Origem e destino devem ser diferentes."
        elif _is_compare_worktree_dirty(window):
            status_text = "Há mudanças locais no worktree. Finalize na aba Commit antes de executar a ação."
            can_open_commit = True
        else:
            action_code = window.compare_action_combo.currentData()
            action = str(action_code).strip() if action_code is not None else "merge"
            if action == "squash":
                message = window.compare_squash_message_input.text().strip()
                if not message:
                    status_text = "Informe a mensagem do commit squash."
                else:
                    can_run = True
                    status_text = "Pronto para executar a ação de branch."
            else:
                can_run = True
                status_text = "Pronto para executar a ação de branch."

    window.compare_run_button.setEnabled(can_run)
    if hasattr(window, "compare_open_commit_button"):
        window.compare_open_commit_button.setEnabled(can_open_commit)
    if hasattr(window, "compare_action_status_label"):
        window.compare_action_status_label.setText(status_text)


def on_compare_action_changed(window: object, _index: int) -> None:
    _update_compare_action_state(window)


def _refresh_after_compare_action(window: object) -> None:
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._refresh_commit_files()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()


def run_compare_action(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Comparar", "Selecione um repositório válido.")
        return
    origin, dest = get_compare_branches(window)
    if not origin or not dest:
        QMessageBox.warning(window, "Comparar", "Selecione origem e destino.")
        return
    if origin == dest:
        QMessageBox.warning(window, "Comparar", "Origem e destino devem ser diferentes.")
        return
    if _is_compare_worktree_dirty(window):
        QMessageBox.warning(window, "Comparar", "Há mudanças locais no worktree. Finalize na aba Commit.")
        _update_compare_action_state(window)
        return

    action_code = window.compare_action_combo.currentData()
    action = str(action_code).strip() if action_code is not None else "merge"
    action_label = window.compare_action_combo.currentText().strip() or "Merge"
    squash_message = ""
    if action == "squash":
        squash_message = window.compare_squash_message_input.text().strip()
        if not squash_message:
            QMessageBox.warning(window, "Comparar", "Mensagem obrigatória para squash merge.")
            _update_compare_action_state(window)
            return

    try:
        behind, ahead = core_get_ahead_behind_between(window.repo_path, origin, dest)
        has_conflict = core_has_potential_conflict(window.repo_path, origin, dest)
    except RuntimeError:
        behind, ahead, has_conflict = 0, 0, False
    conflict_label = "sim" if has_conflict else "não"
    confirm = QMessageBox.question(
        window,
        "Confirmar ação",
        (
            f"Ação: {action_label}\n"
            f"Origem: {origin}\n"
            f"Destino: {dest}\n"
            f"Ahead/Behind: {ahead}/{behind}\n"
            f"Conflito potencial: {conflict_label}\n\n"
            "Deseja continuar?"
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    window._begin_busy(f"Executando {action_label.lower()}...")
    try:
        current = core_get_current_branch(window.repo_path).strip()
        if current != dest:
            core_checkout_branch(window.repo_path, dest)
        if action == "merge":
            run_git(window.repo_path, ["merge", origin])
        elif action == "rebase":
            run_git(window.repo_path, ["rebase", origin])
        else:
            run_git(window.repo_path, ["merge", "--squash", origin])
            run_git(window.repo_path, ["commit", "-m", squash_message])
    except RuntimeError as exc:
        has_conflicts = False
        try:
            has_conflicts = core_has_unmerged_conflicts(window.repo_path)
        except RuntimeError:
            has_conflicts = False
        if has_conflicts:
            QMessageBox.warning(
                window,
                "Comparar",
                (
                    f"{exc}\n\nForam detectados conflitos. Resolva os arquivos e finalize com Git "
                    "(continue/abort) antes de seguir."
                ),
            )
        else:
            QMessageBox.critical(window, "Comparar", str(exc))
        _refresh_after_compare_action(window)
        _update_compare_action_state(window)
        return
    finally:
        window._end_busy()

    window._set_status(f"Ação concluída: {action_label}.")
    _refresh_after_compare_action(window)
    _update_compare_action_state(window)


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


def on_compare_commit_context_menu(window: object, pos: QPoint) -> None:
    item = window.compare_commits_list.itemAt(pos)
    if item is None:
        selected_items = window.compare_commits_list.selectedItems()
        if not selected_items:
            return
        item = selected_items[-1]
    value = item.data(Qt.ItemDataRole.UserRole)
    commit_hash = str(value).strip() if value is not None else ""
    if not commit_hash:
        return

    menu = QMenu(window.compare_commits_list)
    action_open_github = menu.addAction("Abrir commit no GitHub")
    action_copy_github = menu.addAction("Copiar URL do commit")
    menu.addSeparator()
    action_copy_hash = menu.addAction("Copiar hash completo")
    action_copy_files = menu.addAction("Copiar lista de arquivos")
    action_copy_patch = menu.addAction("Copiar patch completo")

    selected_action = menu.exec(window.compare_commits_list.mapToGlobal(pos))
    if selected_action is None:
        return
    if selected_action == action_open_github:
        window._open_commit_in_github(commit_hash, window.repo_path)
        return
    if selected_action == action_copy_github:
        window._copy_commit_github_url(commit_hash, window.repo_path)
        return
    if selected_action == action_copy_hash:
        window._copy_to_clipboard(commit_hash, status="Hash do commit copiado.")
        return
    if selected_action == action_copy_files:
        try:
            files = core_list_commit_files(window.repo_path, commit_hash)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Comparar", str(exc))
            return
        payload = "\n".join(files).strip()
        if window._copy_to_clipboard(payload, status="Lista de arquivos do commit copiada."):
            return
        QMessageBox.information(window, "Comparar", "Esse commit nao possui arquivos listaveis.")
        return
    if selected_action == action_copy_patch:
        try:
            patch = core_get_commit_patch(window.repo_path, commit_hash, path=None, word_diff=False)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Comparar", str(exc))
            return
        if window._copy_to_clipboard(patch, status="Patch completo do commit copiado."):
            return
        QMessageBox.information(window, "Comparar", "Sem patch para copiar neste commit.")
