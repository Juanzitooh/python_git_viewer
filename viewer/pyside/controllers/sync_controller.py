from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox

from ...core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ...core.remote_ops import (
    fetch_all_prune as core_fetch_all_prune,
    publish_current_branch as core_publish_current_branch,
    pull_ff_only as core_pull_ff_only,
    push_current_branch as core_push_current_branch,
)
from ...core.repo_state import get_current_branch as core_get_current_branch, get_upstream as core_get_upstream
from ...core.repo_state import list_worktree_changed_files as core_list_worktree_changed_files


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
        changed_files = core_list_worktree_changed_files(window.repo_path)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Checkout", str(exc))
        window._refresh_repo_state_ui()
        return
    stash_before_checkout = False
    if changed_files:
        preview = "\n".join(f"- {path}" for path in changed_files[:3])
        if len(changed_files) > 3:
            preview += f"\n... +{len(changed_files) - 3} arquivo(s)"
        confirm = QMessageBox(window)
        confirm.setWindowTitle("Trocar branch")
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setText("Ha mudancas locais em aberto.")
        confirm.setInformativeText(
            (
                f"Destino: {target}\n\n"
                "Escolha como continuar:\n"
                "- Levar mudancas para a branch de destino (checkout direto)\n"
                "- Stash e trocar branch\n\n"
                f"Arquivos detectados:\n{preview}"
            )
        )
        carry_button = confirm.addButton("Levar mudancas", QMessageBox.ButtonRole.AcceptRole)
        stash_button = confirm.addButton("Stash e trocar", QMessageBox.ButtonRole.ActionRole)
        cancel_button = confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.setDefaultButton(carry_button)
        confirm.setEscapeButton(cancel_button)
        confirm.exec()
        clicked = confirm.clickedButton()
        if clicked == cancel_button or clicked is None:
            window._refresh_repo_state_ui()
            window._set_status("Checkout cancelado.")
            return
        stash_before_checkout = clicked == stash_button
    try:
        core_checkout_branch(
            window.repo_path,
            target,
            stash_before=stash_before_checkout,
            stash_message=f"git_viewer:checkout:{target}",
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Checkout", str(exc))
        window._refresh_repo_state_ui()
        return
    if stash_before_checkout:
        window._set_status(f"Checkout concluido: {target} (mudancas enviadas para stash).")
    else:
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


def publish_repo(window: object) -> None:
    if not window.repo_path:
        return
    upstream = core_get_upstream(window.repo_path)
    if upstream:
        window._set_status("Branch atual já possui upstream publicado.")
        window._refresh_repo_state_ui()
        return
    current_branch = core_get_current_branch(window.repo_path).strip()
    if not current_branch or current_branch == "HEAD":
        QMessageBox.information(window, "Publish branch", "HEAD destacado. Faça checkout de uma branch antes de publicar.")
        return
    window._begin_busy("Publicando branch...")
    try:
        try:
            core_publish_current_branch(window.repo_path, "origin")
        except RuntimeError as exc:
            QMessageBox.critical(window, "Publish branch", str(exc))
            return
    finally:
        window._end_busy()
    window._set_status(f"Branch publicada: {current_branch}")
    window._refresh_repo_state_ui()
    window._refresh_stash_tab_visibility()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_view()
    window._persist_state()
