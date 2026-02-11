from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QMessageBox

from ...core.commit_content import (
    get_commit_patch as core_get_commit_patch,
    list_commit_files as core_list_commit_files,
)
from ...core.git_client import load_commit_details, load_commit_summaries
from ...core.models import CommitFilters


def clear_history_view(window: object) -> None:
    window.history_summaries = []
    window.history_summary_by_hash = {}
    window.history_current_commit_hash = ""
    window.history_current_file_path = ""
    if hasattr(window, "history_commits_list"):
        window.history_commits_list.clear()
    if hasattr(window, "history_files_list"):
        window.history_files_list.clear()
    if hasattr(window, "history_commit_info"):
        window.history_commit_info.setPlainText("")
    if hasattr(window, "history_patch_view"):
        window.history_patch_view.setPlainText("")


def get_history_limit_value(window: object) -> int:
    data = window.history_limit_combo.currentData()
    try:
        value = int(data)
    except (TypeError, ValueError):
        value = 100
    return max(1, value)


def reload_history_commits(window: object) -> None:
    window._begin_busy("Carregando historico...")
    try:
        if not window.repo_path:
            clear_history_view(window)
            return
        text_filter = window.history_search_input.text().strip()
        filters = CommitFilters(text=text_filter)
        limit = get_history_limit_value(window)
        try:
            summaries = load_commit_summaries(window.repo_path, limit=limit, filters=filters)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Historico", str(exc))
            clear_history_view(window)
            return

        window.history_summaries = summaries
        window.history_summary_by_hash = {item.commit_hash: item for item in summaries}
        window.history_current_commit_hash = ""
        window.history_current_file_path = ""

        window.history_commits_list.blockSignals(True)
        window.history_commits_list.clear()
        for summary in summaries:
            label = f"{summary.commit_hash[:7]} | {summary.subject}"
            item = QListWidgetItem(label, window.history_commits_list)
            item.setData(Qt.ItemDataRole.UserRole, summary.commit_hash)
        window.history_commits_list.blockSignals(False)

        if summaries:
            window.history_commits_list.setCurrentRow(0)
        else:
            window.history_files_list.clear()
            window.history_commit_info.setPlainText("Nenhum commit encontrado.")
            window.history_patch_view.setPlainText("")
    finally:
        window._end_busy()


def on_history_commit_selected(window: object) -> None:
    selected_items = window.history_commits_list.selectedItems()
    if not selected_items:
        window.history_current_commit_hash = ""
        window.history_current_file_path = ""
        window.history_files_list.clear()
        window.history_commit_info.setPlainText("")
        window.history_patch_view.setPlainText("")
        return
    item = selected_items[0]
    value = item.data(Qt.ItemDataRole.UserRole)
    commit_hash = str(value).strip() if value is not None else ""
    if not commit_hash:
        return
    window.history_current_commit_hash = commit_hash
    window.history_current_file_path = ""
    load_history_commit_content(window, commit_hash)


def load_history_commit_content(window: object, commit_hash: str) -> None:
    window._begin_busy(f"Carregando commit {commit_hash[:7]}...")
    try:
        try:
            details = load_commit_details(window.repo_path, commit_hash)
            files = core_list_commit_files(window.repo_path, commit_hash)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Historico", str(exc))
            window.history_files_list.clear()
            window.history_patch_view.setPlainText("")
            return

        info_lines = [
            f"Hash: {details.commit_hash}",
            f"Autor: {details.author}",
            f"Data: {details.date}",
            f"Titulo: {details.subject}",
            f"Arquivos: {len(details.file_stats)} | +{details.total_added} -{details.total_deleted}",
        ]
        if details.body:
            info_lines.extend(["", details.body.strip()])
        window.history_commit_info.setPlainText("\n".join(info_lines))

        window.history_files_list.blockSignals(True)
        window.history_files_list.clear()
        all_files_item = QListWidgetItem("(todos os arquivos)", window.history_files_list)
        all_files_item.setData(Qt.ItemDataRole.UserRole, "")
        for path in files:
            file_item = QListWidgetItem(path, window.history_files_list)
            file_item.setData(Qt.ItemDataRole.UserRole, path)
        window.history_files_list.blockSignals(False)
        window.history_files_list.setCurrentRow(0)
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
        window.history_patch_view.setPlainText("")
        return
    word_diff = window.history_word_diff_check.isChecked()
    path = window.history_current_file_path.strip() or None
    try:
        patch = core_get_commit_patch(
            window.repo_path,
            commit_hash,
            path=path,
            word_diff=word_diff,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Historico", str(exc))
        window.history_patch_view.setPlainText("")
        return
    window.history_patch_view.setPlainText(patch)
