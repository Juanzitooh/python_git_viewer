from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ...core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ...core.remote_ops import (
    fetch_all_prune as core_fetch_all_prune,
    pull_ff_only as core_pull_ff_only,
    push_current_branch as core_push_current_branch,
)
from ...core.repo_state import get_current_branch as core_get_current_branch


def on_branch_changed(window: object, _index: int) -> None:
    if window._setting_branch_programmatically:
        return
    if not window.repo_path:
        return
    selected = window.branch_combo.currentData()
    target = str(selected).strip() if selected is not None else ""
    if not target:
        return
    try:
        current = core_get_current_branch(window.repo_path).strip()
    except RuntimeError:
        return
    if current == target:
        return
    try:
        core_checkout_branch(window.repo_path, target)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Checkout", str(exc))
        window._refresh_repo_state_ui()
        return
    window._set_status(f"Checkout concluido: {target}")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._sync_import_target_label()
    window._persist_state()


def create_new_branch(window: object) -> None:
    if not window.repo_path:
        return
    branch_name, ok = QInputDialog.getText(window, "Nova branch", "Nome da branch:")
    if not ok:
        return
    normalized = branch_name.strip()
    if not normalized:
        return
    try:
        current = core_get_current_branch(window.repo_path).strip()
        core_create_branch(window.repo_path, normalized, current)
        core_checkout_branch(window.repo_path, normalized)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Nova branch", str(exc))
        return
    window._set_status(f"Branch local criada: {normalized} (ainda nao publicada).")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._persist_state()


def fetch_repo(window: object) -> None:
    if not window.repo_path:
        return
    window._begin_busy("Executando fetch...")
    try:
        try:
            core_fetch_all_prune(window.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Fetch", str(exc))
            return
    finally:
        window._end_busy()
    window._set_status("Fetch concluido.")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_view()
    window._persist_state()


def pull_repo(window: object) -> None:
    if not window.repo_path:
        return
    window._begin_busy("Executando pull...")
    try:
        try:
            core_pull_ff_only(window.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Pull", str(exc))
            return
    finally:
        window._end_busy()
    window._set_status("Pull concluido.")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._persist_state()


def push_repo(window: object) -> None:
    if not window.repo_path:
        return
    window._begin_busy("Executando push...")
    try:
        try:
            core_push_current_branch(window.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Push", str(exc))
            return
    finally:
        window._end_busy()
    window._set_status("Push concluido.")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_view()
    window._persist_state()
