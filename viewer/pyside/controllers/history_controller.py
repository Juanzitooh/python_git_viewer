from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ...core.branch_ops import checkout_branch as core_checkout_branch
from ...core.cherry_pick_ops import (
    cherry_pick_commit as core_cherry_pick_commit,
    has_unmerged_conflicts as core_has_unmerged_conflicts,
)
from ...core.commit_content import (
    get_commit_patch as core_get_commit_patch,
    list_commit_files as core_list_commit_files,
)
from ...core.git_client import load_commit_details, load_commit_summaries
from ...core.history_local_ops import (
    apply_local_commit_reorder as core_apply_local_commit_reorder,
    load_local_only_commit_hashes as core_load_local_only_commit_hashes,
    load_reorderable_local_commits as core_load_reorderable_local_commits,
)
from ...core.models import CommitFilters
from ...core.repo_state import (
    get_current_branch as core_get_current_branch,
    get_upstream as core_get_upstream,
    list_branches as core_list_branches,
)
from ..diff_columns import render_diff_into_columns


def clear_history_view(window: object) -> None:
    window.history_summaries = []
    window.history_summary_by_hash = {}
    window.history_current_commit_hash = ""
    window.history_current_file_path = ""
    window.history_local_only_hashes = set()
    window.history_has_upstream = False
    window.history_current_skip = 0
    window.history_has_more = False
    window.history_loading_more = False
    window.history_active_filter_text = ""
    if hasattr(window, "history_commits_list"):
        window.history_commits_list.clear()
    if hasattr(window, "history_files_list"):
        window.history_files_list.clear()
    if hasattr(window, "history_commit_info"):
        window.history_commit_info.setPlainText("")
    if hasattr(window, "history_patch_table"):
        render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
    if hasattr(window, "history_patch_text"):
        window.history_patch_text.setPlainText("")
    if hasattr(window, "history_patch_stack"):
        window.history_patch_stack.setCurrentIndex(0)
    _update_history_reorder_button_visibility(window)


def get_history_limit_value(window: object) -> int:
    data = getattr(window, "history_page_size", 200)
    try:
        value = int(data)
    except (TypeError, ValueError):
        value = 200
    return max(1, value)


def on_history_search_text_changed(window: object, _text: str) -> None:
    if not window.repo_path:
        return
    reload_history_commits(window)


def _history_commit_presence(window: object, commit_hash: str) -> str:
    if not getattr(window, "history_has_upstream", False):
        return "L"
    local_only_hashes = getattr(window, "history_local_only_hashes", set())
    if commit_hash in local_only_hashes:
        return "L"
    return "L+O"


def _format_history_commit_label(window: object, commit_hash: str, subject: str) -> str:
    presence = _history_commit_presence(window, commit_hash)
    return f"[{presence}] {commit_hash[:7]} | {subject}"


def _build_history_commit_tooltip(window: object, commit_hash: str, date: str) -> str:
    marker = _history_commit_presence(window, commit_hash)
    marker_text = "Local (ainda nao enviado)" if marker == "L" else "Local + online"
    return f"{commit_hash}\n{date}\n{marker_text}".strip()


def _refresh_history_local_state(window: object) -> None:
    if not window.repo_path:
        window.history_local_only_hashes = set()
        window.history_has_upstream = False
        return
    upstream = core_get_upstream(window.repo_path)
    if not upstream:
        window.history_local_only_hashes = set()
        window.history_has_upstream = False
        return
    try:
        hashes = core_load_local_only_commit_hashes(window.repo_path, upstream)
    except RuntimeError:
        hashes = set()
    window.history_local_only_hashes = set(hashes)
    window.history_has_upstream = True


def _update_history_reorder_button_visibility(window: object) -> None:
    if not hasattr(window, "history_reorder_button"):
        return
    visible = bool(
        window.repo_path
        and getattr(window, "history_has_upstream", False)
        and len(getattr(window, "history_local_only_hashes", set())) >= 2
    )
    window.history_reorder_button.setVisible(visible)


def _selected_history_summaries_for_export(window: object) -> list[object]:
    selected_indexes = window.history_commits_list.selectedIndexes()
    if not selected_indexes:
        return []
    summaries_by_hash = getattr(window, "history_summary_by_hash", {})
    ordered_rows = sorted((int(index.row()) for index in selected_indexes), reverse=True)
    selected: list[object] = []
    for row in ordered_rows:
        item = window.history_commits_list.item(row)
        if item is None:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
        if not commit_hash:
            continue
        summary = summaries_by_hash.get(commit_hash)
        if summary is not None:
            selected.append(summary)
    return selected


def reload_history_commits(window: object) -> None:
    window._begin_busy("Carregando historico...")
    try:
        if not window.repo_path:
            clear_history_view(window)
            return
        _refresh_history_local_state(window)
        text_filter = window.history_search_input.text().strip()
        filters = CommitFilters(text=text_filter)
        page_size = get_history_limit_value(window)
        window.history_active_filter_text = text_filter
        window.history_current_skip = 0
        window.history_has_more = False
        window.history_loading_more = False
        try:
            summaries = load_commit_summaries(window.repo_path, limit=page_size, skip=0, filters=filters)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Historico", str(exc))
            clear_history_view(window)
            return

        window.history_summaries = []
        window.history_summary_by_hash = {}
        window.history_current_commit_hash = ""
        window.history_current_file_path = ""
        window.history_commits_list.blockSignals(True)
        window.history_commits_list.clear()
        window.history_commits_list.blockSignals(False)
        _append_history_page(window, summaries)
        window.history_current_skip = len(window.history_summaries)
        window.history_has_more = len(summaries) == page_size
        _update_history_reorder_button_visibility(window)

        if window.history_summaries:
            window.history_commits_list.setCurrentRow(0)
        else:
            window.history_files_list.clear()
            window.history_commit_info.setPlainText("Nenhum commit encontrado.")
            if hasattr(window, "history_patch_table"):
                render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
            if hasattr(window, "history_patch_text"):
                window.history_patch_text.setPlainText("")
    finally:
        window._end_busy()


def _append_history_page(window: object, summaries: list[object]) -> None:
    if not summaries:
        return
    existing_hashes = set(window.history_summary_by_hash.keys())
    window.history_commits_list.blockSignals(True)
    try:
        for summary in summaries:
            commit_hash = str(summary.commit_hash).strip()
            if not commit_hash or commit_hash in existing_hashes:
                continue
            existing_hashes.add(commit_hash)
            window.history_summaries.append(summary)
            window.history_summary_by_hash[commit_hash] = summary
            label = _format_history_commit_label(window, commit_hash, summary.subject)
            item = QListWidgetItem(label, window.history_commits_list)
            item.setData(Qt.ItemDataRole.UserRole, commit_hash)
            item.setToolTip(_build_history_commit_tooltip(window, commit_hash, summary.date))
    finally:
        window.history_commits_list.blockSignals(False)


def load_more_history_commits(window: object) -> None:
    if not window.repo_path:
        return
    if not getattr(window, "history_has_more", False):
        return
    if getattr(window, "history_loading_more", False):
        return
    active_filter = str(getattr(window, "history_active_filter_text", "")).strip()
    current_filter = window.history_search_input.text().strip()
    if active_filter != current_filter:
        reload_history_commits(window)
        return
    page_size = get_history_limit_value(window)
    skip = int(getattr(window, "history_current_skip", 0) or 0)
    if skip < 0:
        skip = 0
    filters = CommitFilters(text=current_filter)
    window.history_loading_more = True
    selected_hash = window.history_current_commit_hash.strip()
    try:
        try:
            summaries = load_commit_summaries(window.repo_path, limit=page_size, skip=skip, filters=filters)
        except RuntimeError:
            window.history_has_more = False
            return
        _append_history_page(window, summaries)
        window.history_current_skip = len(window.history_summaries)
        window.history_has_more = len(summaries) == page_size
    finally:
        window.history_loading_more = False
    if selected_hash:
        for row in range(window.history_commits_list.count()):
            item = window.history_commits_list.item(row)
            if item is None:
                continue
            value = item.data(Qt.ItemDataRole.UserRole)
            item_hash = str(value).strip() if value is not None else ""
            if item_hash == selected_hash:
                window.history_commits_list.setCurrentRow(row)
                break


def on_history_scroll_value_changed(window: object, value: int) -> None:
    scrollbar = window.history_commits_list.verticalScrollBar()
    remaining = int(scrollbar.maximum() - value)
    if remaining <= 2:
        load_more_history_commits(window)


def on_history_commit_selected(window: object) -> None:
    current_item = window.history_commits_list.currentItem()
    if current_item is None:
        selected_items = window.history_commits_list.selectedItems()
        current_item = selected_items[-1] if selected_items else None
    if current_item is None:
        window.history_current_commit_hash = ""
        window.history_current_file_path = ""
        window.history_files_list.clear()
        window.history_commit_info.setPlainText("")
        if hasattr(window, "history_patch_table"):
            render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
        if hasattr(window, "history_patch_text"):
            window.history_patch_text.setPlainText("")
        return
    value = current_item.data(Qt.ItemDataRole.UserRole)
    commit_hash = str(value).strip() if value is not None else ""
    if not commit_hash:
        return
    window.history_current_commit_hash = commit_hash
    window.history_current_file_path = ""
    load_history_commit_content(window, commit_hash)


def on_history_commit_hovered(window: object, item: QListWidgetItem | None) -> None:
    if item is None:
        return
    tooltip = item.toolTip().strip()
    if not tooltip:
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
        summary = getattr(window, "history_summary_by_hash", {}).get(commit_hash)
        if commit_hash and summary is not None:
            tooltip = _build_history_commit_tooltip(window, commit_hash, str(summary.date))
            item.setToolTip(tooltip)
    if tooltip:
        QToolTip.showText(QCursor.pos(), tooltip, window.history_commits_list)


def load_history_commit_content(window: object, commit_hash: str) -> None:
    window._begin_busy(f"Carregando commit {commit_hash[:7]}...")
    try:
        try:
            details = load_commit_details(window.repo_path, commit_hash)
            files = core_list_commit_files(window.repo_path, commit_hash)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Historico", str(exc))
            window.history_files_list.clear()
            if hasattr(window, "history_patch_table"):
                render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
            if hasattr(window, "history_patch_text"):
                window.history_patch_text.setPlainText("")
            return

        info_lines = [
            f"Hash: {details.commit_hash}",
            f"Autor: {details.author}",
            f"Data: {details.date}",
            f"Titulo: {details.subject}",
            f"Arquivos: {len(details.file_stats)} | +{details.total_added} -{details.total_deleted}",
        ]
        body_text = details.body.strip()
        if body_text:
            info_lines.extend(["", "Descricao:", body_text])
        else:
            info_lines.append("Descricao: (sem descricao)")
        window.history_commit_info.setPlainText("\n".join(info_lines))

        stats_by_path = {item.path: item for item in details.file_stats}
        window.history_files_list.blockSignals(True)
        window.history_files_list.clear()
        for path in files:
            stat = stats_by_path.get(path)
            if stat is None:
                label = path
            elif stat.is_binary:
                label = f"{path} [binario]"
            else:
                label = f"{path} (+{stat.added}/-{stat.deleted})"
            file_item = QListWidgetItem(label, window.history_files_list)
            file_item.setData(Qt.ItemDataRole.UserRole, path)
        window.history_files_list.blockSignals(False)
        if window.history_files_list.count() > 0:
            window.history_files_list.setCurrentRow(0)
        else:
            window.history_current_file_path = ""
            refresh_history_patch_view(window)
    finally:
        window._end_busy()


def on_history_file_selected(window: object) -> None:
    selected_items = window.history_files_list.selectedItems()
    if not selected_items:
        window.history_current_file_path = ""
        refresh_history_patch_view(window)
        return
    item = selected_items[0]
    value = item.data(Qt.ItemDataRole.UserRole)
    window.history_current_file_path = str(value).strip() if value is not None else ""
    refresh_history_patch_view(window)


def refresh_history_patch_view(window: object) -> None:
    commit_hash = window.history_current_commit_hash.strip()
    if not commit_hash:
        if hasattr(window, "history_patch_table"):
            render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
        if hasattr(window, "history_patch_text"):
            window.history_patch_text.setPlainText("")
        return
    word_diff = window.history_word_diff_check.isChecked()
    selected_path = window.history_current_file_path.strip()
    if not selected_path:
        if hasattr(window, "history_patch_table"):
            render_diff_into_columns(window.history_patch_table, "(selecione um arquivo)", show_header_lines=False)
        if hasattr(window, "history_patch_text"):
            window.history_patch_text.setPlainText("(selecione um arquivo)")
        if hasattr(window, "history_patch_stack"):
            window.history_patch_stack.setCurrentIndex(0)
        return
    path = selected_path
    try:
        patch = core_get_commit_patch(
            window.repo_path,
            commit_hash,
            path=path,
            word_diff=word_diff,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Historico", str(exc))
        if hasattr(window, "history_patch_table"):
            render_diff_into_columns(window.history_patch_table, "", show_header_lines=False)
        if hasattr(window, "history_patch_text"):
            window.history_patch_text.setPlainText("")
        return
    if hasattr(window, "history_patch_stack"):
        window.history_patch_stack.setCurrentIndex(0)
    render_diff_into_columns(
        window.history_patch_table,
        patch,
        show_header_lines=False,
        word_diff_plain=word_diff,
    )


def _get_context_commit_hash(window: object, pos: QPoint) -> str:
    item = window.history_commits_list.itemAt(pos)
    if item is not None:
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
        if commit_hash:
            return commit_hash
    return window.history_current_commit_hash.strip()


def _copy_commit_hash(window: object, commit_hash: str) -> None:
    if window._copy_to_clipboard(commit_hash, status="Hash do commit copiado."):
        return
    QMessageBox.information(window, "Historico", "Nao foi possivel copiar o hash do commit.")


def _copy_commit_files_list(window: object, commit_hash: str) -> None:
    try:
        files = core_list_commit_files(window.repo_path, commit_hash)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Historico", str(exc))
        return
    payload = "\n".join(files).strip()
    if window._copy_to_clipboard(payload, status="Lista de arquivos copiada."):
        return
    QMessageBox.information(window, "Historico", "Esse commit nao possui arquivos listaveis.")


def _copy_commit_patch(window: object, commit_hash: str) -> None:
    try:
        patch = core_get_commit_patch(window.repo_path, commit_hash, path=None, word_diff=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Historico", str(exc))
        return
    if window._copy_to_clipboard(patch, status="Patch do commit copiado."):
        return
    QMessageBox.information(window, "Historico", "Nao foi possivel copiar o patch do commit.")


def _copy_file_patch(window: object, commit_hash: str, file_path: str) -> None:
    try:
        patch = core_get_commit_patch(window.repo_path, commit_hash, path=file_path, word_diff=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Historico", str(exc))
        return
    if window._copy_to_clipboard(patch, status="Patch do arquivo copiado."):
        return
    QMessageBox.information(window, "Historico", "Nao foi possivel copiar o patch do arquivo.")


def on_history_commit_context_menu(window: object, pos: QPoint) -> None:
    previous_rows = sorted(int(index.row()) for index in window.history_commits_list.selectedIndexes())
    commit_hash = _get_context_commit_hash(window, pos)
    if not commit_hash:
        return

    menu = QMenu(window.history_commits_list)
    action_copy_hash = menu.addAction("Copiar hash")
    action_copy_patch = menu.addAction("Copiar patch completo")
    action_copy_files = menu.addAction("Copiar lista de arquivos")
    menu.addSeparator()
    action_open_github = menu.addAction("Abrir commit no GitHub")
    action_copy_github = menu.addAction("Copiar URL do commit")

    selected_action = menu.exec(window.history_commits_list.viewport().mapToGlobal(pos))
    _restore_history_commit_selection(window, previous_rows)
    if selected_action is None:
        return
    if selected_action == action_copy_hash:
        _copy_commit_hash(window, commit_hash)
        return
    if selected_action == action_copy_patch:
        _copy_commit_patch(window, commit_hash)
        return
    if selected_action == action_copy_files:
        _copy_commit_files_list(window, commit_hash)
        return
    if selected_action == action_open_github:
        window._open_commit_in_github(commit_hash)
        return
    if selected_action == action_copy_github:
        window._copy_commit_github_url(commit_hash)


def on_history_file_context_menu(window: object, pos: QPoint) -> None:
    commit_hash = window.history_current_commit_hash.strip()
    if not commit_hash:
        return
    item = window.history_files_list.itemAt(pos)
    if item is not None:
        value = item.data(Qt.ItemDataRole.UserRole)
        file_path = str(value).strip() if value is not None else ""
    else:
        selected_items = window.history_files_list.selectedItems()
        if selected_items:
            value = selected_items[-1].data(Qt.ItemDataRole.UserRole)
            file_path = str(value).strip() if value is not None else ""
        else:
            file_path = window.history_current_file_path.strip()

    menu = QMenu(window.history_files_list)
    action_open_vscode = menu.addAction("Abrir arquivo no VS Code")
    action_open_folder = menu.addAction("Abrir na pasta")
    action_copy_relative = menu.addAction("Copiar caminho relativo")
    menu.addSeparator()
    action_copy_file_patch = menu.addAction("Copiar patch do arquivo")
    action_copy_commit_patch = menu.addAction("Copiar patch completo")

    has_file = bool(file_path)
    action_open_vscode.setEnabled(has_file)
    action_open_folder.setEnabled(has_file)
    action_copy_relative.setEnabled(has_file)
    action_copy_file_patch.setEnabled(has_file)

    selected_action = menu.exec(window.history_files_list.viewport().mapToGlobal(pos))
    if selected_action is None:
        return
    if selected_action == action_open_vscode:
        window._open_repo_file_in_vscode(file_path)
        return
    if selected_action == action_open_folder:
        window._open_repo_file_in_explorer(file_path)
        return
    if selected_action == action_copy_relative:
        window._copy_to_clipboard(file_path, status="Caminho relativo copiado.")
        return
    if selected_action == action_copy_file_patch:
        _copy_file_patch(window, commit_hash, file_path)
        return
    if selected_action == action_copy_commit_patch:
        _copy_commit_patch(window, commit_hash)


def _restore_history_commit_selection(window: object, rows: list[int]) -> None:
    if not rows:
        return
    window.history_commits_list.blockSignals(True)
    try:
        window.history_commits_list.clearSelection()
        for row in rows:
            item = window.history_commits_list.item(row)
            if item is not None:
                item.setSelected(True)
        window.history_commits_list.setCurrentRow(rows[0])
    finally:
        window.history_commits_list.blockSignals(False)


def _refresh_after_history_export(window: object) -> None:
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._refresh_commit_files()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()


def open_history_export_dialog(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Exportar", "Selecione um repositorio valido primeiro.")
        return
    selected = _selected_history_summaries_for_export(window)
    if not selected:
        QMessageBox.information(window, "Exportar", "Selecione commits na aba Historico.")
        return
    try:
        branches = core_list_branches(window.repo_path)
        current = core_get_current_branch(window.repo_path).strip()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Exportar", str(exc))
        return
    target_options = [branch for branch in branches if branch != current]
    if not target_options:
        QMessageBox.information(
            window,
            "Exportar",
            "E necessario ter pelo menos duas branches para exportar commits.",
        )
        return

    dialog = QDialog(window)
    dialog.setWindowTitle("Exportar commits")
    dialog.setModal(True)
    dialog.resize(760, 520)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    layout.addWidget(QLabel(f"Origem: {current}", dialog))

    commits_list = QListWidget(dialog)
    for summary in selected:
        commits_list.addItem(f"{summary.commit_hash[:7]} | {summary.subject}")
    layout.addWidget(commits_list, stretch=1)

    target_row = QWidget(dialog)
    target_layout = QHBoxLayout(target_row)
    target_layout.setContentsMargins(0, 0, 0, 0)
    target_layout.setSpacing(6)
    target_layout.addWidget(QLabel("Destino:", target_row))
    target_combo = QComboBox(target_row)
    for branch in target_options:
        target_combo.addItem(branch, branch)
    target_layout.addWidget(target_combo, stretch=1)
    layout.addWidget(target_row)

    status_label = QLabel("", dialog)
    layout.addWidget(status_label)

    actions_row = QWidget(dialog)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    actions_layout.addStretch(1)
    copy_button = QPushButton("Copiar hashes", actions_row)
    confirm_button = QPushButton("Confirmar exportacao", actions_row)
    confirm_button.setProperty("role", "primary")
    cancel_button = QPushButton("Cancelar", actions_row)
    actions_layout.addWidget(copy_button)
    actions_layout.addWidget(confirm_button)
    actions_layout.addWidget(cancel_button)
    layout.addWidget(actions_row)

    def sync_status() -> None:
        target = str(target_combo.currentData() or "").strip()
        if not target:
            status_label.setText("Destino nao definido.")
            confirm_button.setEnabled(False)
            return
        status_label.setText(f"Destino atual: {target}")
        confirm_button.setEnabled(True)

    def copy_hashes() -> None:
        payload = "\n".join(summary.commit_hash for summary in selected)
        QApplication.clipboard().setText(payload)
        window._set_status("Hashes copiados.")

    def confirm_export() -> None:
        target = str(target_combo.currentData() or "").strip()
        if not target:
            QMessageBox.warning(dialog, "Exportar", "Selecione a branch de destino.")
            return
        question = QMessageBox.question(
            dialog,
            "Confirmar exportacao",
            (
                f"Exportar {len(selected)} commit(s)\n"
                f"Origem: {current}\n"
                f"Destino: {target}\n\n"
                "Deseja continuar?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if question != QMessageBox.StandardButton.Yes:
            return

        dialog.setEnabled(False)
        window._begin_busy("Exportando commits...")
        applied = 0
        try:
            core_checkout_branch(window.repo_path, target)
            for summary in selected:
                try:
                    core_cherry_pick_commit(window.repo_path, summary.commit_hash)
                except RuntimeError as exc:
                    has_conflicts = False
                    try:
                        has_conflicts = core_has_unmerged_conflicts(window.repo_path)
                    except RuntimeError:
                        has_conflicts = False
                    if has_conflicts:
                        QMessageBox.warning(
                            dialog,
                            "Exportar",
                            (
                                f"Falha ao exportar {summary.commit_hash[:7]}.\n{exc}\n\n"
                                "Conflitos detectados."
                            ),
                        )
                        window._show_conflicts_dialog(
                            operation="cherry-pick",
                            source_label="Exportar",
                        )
                    else:
                        QMessageBox.critical(
                            dialog,
                            "Exportar",
                            f"Falha ao exportar {summary.commit_hash[:7]}.\n{exc}",
                        )
                    _refresh_after_history_export(window)
                    dialog.setEnabled(True)
                    return
                applied += 1
        finally:
            window._end_busy()
            dialog.setEnabled(True)

        window._set_status(f"Exportacao concluida em {target}: {applied} commit(s).")
        _refresh_after_history_export(window)
        dialog.accept()

    target_combo.currentIndexChanged.connect(sync_status)
    copy_button.clicked.connect(copy_hashes)
    confirm_button.clicked.connect(confirm_export)
    cancel_button.clicked.connect(dialog.reject)
    sync_status()
    dialog.exec()


def open_history_reorder_dialog(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Reordenar commits", "Selecione um repositorio valido primeiro.")
        return
    if not getattr(window, "history_has_upstream", False):
        QMessageBox.information(
            window,
            "Reordenar commits",
            "A branch atual nao possui upstream configurado.",
        )
        return
    try:
        upstream = core_get_upstream(window.repo_path) or ""
        current = core_get_current_branch(window.repo_path).strip()
        commits = core_load_reorderable_local_commits(window.repo_path, upstream)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Reordenar commits", str(exc))
        return
    if len(commits) < 2:
        QMessageBox.information(
            window,
            "Reordenar commits",
            "E necessario ao menos 2 commits locais [L] para reordenar.",
        )
        return

    commit_rows = list(commits)
    dialog = QDialog(window)
    dialog.setWindowTitle("Reordenar commits locais")
    dialog.setModal(True)
    dialog.resize(900, 560)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    layout.addWidget(
        QLabel(
            (
                f"Branch atual: {current}\n"
                f"Upstream: {upstream}\n"
                "Lista em ordem de aplicacao (mais antigo -> mais novo)."
            ),
            dialog,
        )
    )

    list_widget = QListWidget(dialog)
    layout.addWidget(list_widget, stretch=1)

    actions_row = QWidget(dialog)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    move_up_button = QPushButton("Subir", actions_row)
    move_down_button = QPushButton("Descer", actions_row)
    copy_hashes_button = QPushButton("Copiar hashes", actions_row)
    apply_button = QPushButton("Aplicar ordem", actions_row)
    apply_button.setProperty("role", "primary")
    close_button = QPushButton("Fechar", actions_row)
    actions_layout.addWidget(move_up_button)
    actions_layout.addWidget(move_down_button)
    actions_layout.addWidget(copy_hashes_button)
    actions_layout.addWidget(apply_button)
    actions_layout.addStretch(1)
    actions_layout.addWidget(close_button)
    layout.addWidget(actions_row)

    def render_list(selected_index: int | None = None) -> None:
        list_widget.clear()
        for index, summary in enumerate(commit_rows, start=1):
            list_widget.addItem(f"{index:>2}. {summary.commit_hash[:7]} | {summary.subject}")
        if selected_index is None:
            return
        if 0 <= selected_index < len(commit_rows):
            list_widget.setCurrentRow(selected_index)

    def move_selected(delta: int) -> None:
        current_row = list_widget.currentRow()
        if current_row < 0:
            return
        new_row = current_row + delta
        if new_row < 0 or new_row >= len(commit_rows):
            return
        commit_rows[current_row], commit_rows[new_row] = commit_rows[new_row], commit_rows[current_row]
        render_list(new_row)

    def copy_hashes() -> None:
        payload = "\n".join(summary.commit_hash for summary in commit_rows)
        QApplication.clipboard().setText(payload)
        window._set_status("Hashes copiados.")

    def apply_reorder() -> None:
        original_order = [summary.commit_hash for summary in commits]
        new_order = [summary.commit_hash for summary in commit_rows]
        if new_order == original_order:
            QMessageBox.information(dialog, "Reordenar commits", "A ordem nao foi alterada.")
            return
        question = QMessageBox.question(
            dialog,
            "Confirmar reordenacao",
            (
                "Isto vai reescrever o historico local [L] da branch atual.\n"
                "Pode exigir push com --force-with-lease.\n\n"
                "Deseja continuar?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if question != QMessageBox.StandardButton.Yes:
            return

        dialog.setEnabled(False)
        window._begin_busy("Reordenando commits locais...")
        try:
            result = core_apply_local_commit_reorder(
                window.repo_path,
                upstream,
                commit_rows,
                current_branch=current,
            )
        except RuntimeError as exc:
            window._end_busy()
            dialog.setEnabled(True)
            QMessageBox.critical(dialog, "Reordenar commits", str(exc))
            return
        finally:
            if getattr(window, "_busy_depth", 0) > 0:
                window._end_busy()
        dialog.setEnabled(True)

        if not result.ok:
            if result.restore_error_message:
                QMessageBox.critical(
                    dialog,
                    "Reordenar commits",
                    (
                        f"Falha ao reordenar commits:\n{result.error_message}\n\n"
                        f"Tambem falhou ao restaurar backup automaticamente:\n"
                        f"{result.restore_error_message}\n\n"
                        f"Backup disponivel em: {result.backup_branch}"
                    ),
                )
            else:
                QMessageBox.critical(
                    dialog,
                    "Reordenar commits",
                    (
                        f"Falha ao reordenar commits:\n{result.error_message}\n\n"
                        f"Estado restaurado com backup: {result.backup_branch}"
                    ),
                )
            _refresh_after_history_export(window)
            return

        QMessageBox.information(
            dialog,
            "Reordenar commits",
            f"Reordenacao concluida com sucesso.\nBackup criado em: {result.backup_branch}",
        )
        window._set_status(f"Commits locais reordenados. Backup: {result.backup_branch}")
        _refresh_after_history_export(window)
        dialog.accept()

    move_up_button.clicked.connect(lambda: move_selected(-1))
    move_down_button.clicked.connect(lambda: move_selected(1))
    copy_hashes_button.clicked.connect(copy_hashes)
    apply_button.clicked.connect(apply_reorder)
    close_button.clicked.connect(dialog.reject)
    render_list(0)
    dialog.exec()
