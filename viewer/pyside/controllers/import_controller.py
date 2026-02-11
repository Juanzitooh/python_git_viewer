from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem, QMenu, QMessageBox

from ...core.cherry_pick_ops import (
    cherry_pick_commit as core_cherry_pick_commit,
    has_unmerged_conflicts as core_has_unmerged_conflicts,
)
from ...core.commit_content import (
    get_commit_patch as core_get_commit_patch,
    list_commit_files as core_list_commit_files,
)
from ...core.git_client import is_git_repo, load_commit_summaries
from ...core.models import CommitFilters, CommitSummary
from ...core.repo_state import (
    get_current_branch as core_get_current_branch,
    list_branches as core_list_branches,
)
from ...core.settings_store import normalize_repo_path


def sync_import_target_label(window: object) -> None:
    if not hasattr(window, "import_target_label"):
        return
    if not window.repo_path:
        window.import_target_label.setText("Destino: (nenhum repositório selecionado)")
        return
    try:
        branch = core_get_current_branch(window.repo_path).strip()
    except RuntimeError:
        branch = "(desconhecida)"
    display = window._format_workspace_relative_path(window.repo_path)
    window.import_target_label.setText(f"Destino: {display} | Branch atual: {branch}")


def clear_import_selection(window: object, status_message: str) -> None:
    window.import_commit_summaries = []
    if hasattr(window, "import_commits_list"):
        window.import_commits_list.clear()
    window.import_status_label.setText(status_message)
    update_import_controls_state(window)


def refresh_import_source_repos(window: object) -> None:
    if not hasattr(window, "import_source_repo_combo"):
        return
    repos = window._collect_known_repos()
    source_path = normalize_repo_path(window.import_source_repo_path) if window.import_source_repo_path else ""

    labels: list[str] = []
    lookup: dict[str, str] = {}
    for repo in repos:
        label_base = window._format_repo_display_label(repo)
        label = label_base
        suffix = 2
        while label in lookup:
            label = f"{label_base} [{suffix}]"
            suffix += 1
        labels.append(label)
        lookup[label] = repo
    window.import_source_repo_lookup = lookup

    window.import_source_repo_combo.blockSignals(True)
    window.import_source_repo_combo.clear()
    for label in labels:
        window.import_source_repo_combo.addItem(label, lookup[label])
    window.import_source_repo_combo.blockSignals(False)

    if source_path and source_path in lookup.values():
        idx = window.import_source_repo_combo.findData(source_path)
        if idx >= 0:
            window.import_source_repo_combo.setCurrentIndex(idx)
    elif labels:
        window.import_source_repo_combo.setCurrentIndex(0)
    else:
        window.import_source_repo_path = ""
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Nenhum repositório disponível para origem.")

    if window.import_source_repo_combo.count() > 0:
        apply_import_source_repo_from_combo(window)
    update_import_controls_state(window)


def on_import_source_repo_changed(window: object, _index: int) -> None:
    apply_import_source_repo_from_combo(window)


def apply_import_source_repo_from_combo(window: object) -> None:
    selected = window.import_source_repo_combo.currentData()
    repo = str(selected).strip() if selected is not None else ""
    if not repo:
        window.import_source_repo_path = ""
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Selecione o repositório de origem para carregar commits.")
        return
    normalized = normalize_repo_path(repo)
    if not os.path.isdir(normalized) or not is_git_repo(normalized):
        window.import_source_repo_path = ""
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Repositório de origem inválido.")
        return
    window.import_source_repo_path = normalized
    load_import_source_branches(window)


def use_current_repo_as_import_source(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Importar", "Selecione um repositório destino válido primeiro.")
        return
    index = window.import_source_repo_combo.findData(window.repo_path)
    if index < 0:
        refresh_import_source_repos(window)
        index = window.import_source_repo_combo.findData(window.repo_path)
    if index >= 0:
        window.import_source_repo_combo.setCurrentIndex(index)
        apply_import_source_repo_from_combo(window)


def load_import_source_branches(window: object) -> None:
    source_repo = window.import_source_repo_path
    if not source_repo:
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Selecione o repositório de origem para carregar commits.")
        return
    try:
        branches = core_list_branches(source_repo)
        current = core_get_current_branch(source_repo).strip()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Importar", str(exc))
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Falha ao carregar branches da origem.")
        return
    if not branches:
        window.import_source_branch_combo.clear()
        clear_import_selection(window, "Nenhuma branch encontrada na origem.")
        return
    window.import_source_branch_combo.blockSignals(True)
    window.import_source_branch_combo.clear()
    for branch in branches:
        window.import_source_branch_combo.addItem(branch, branch)
    window.import_source_branch_combo.blockSignals(False)
    idx = window.import_source_branch_combo.findData(current)
    if idx < 0:
        idx = 0
    window.import_source_branch_combo.setCurrentIndex(idx)
    load_import_source_commits(window)


def on_import_source_branch_changed(window: object, _index: int) -> None:
    load_import_source_commits(window)


def load_import_source_commits(window: object) -> None:
    window._begin_busy("Carregando commits de origem...")
    try:
        source_repo = window.import_source_repo_path
        selected_branch = window.import_source_branch_combo.currentData()
        branch = str(selected_branch).strip() if selected_branch is not None else ""
        if not source_repo or not branch:
            clear_import_selection(window, "Selecione origem e branch para carregar commits.")
            return
        window.import_status_label.setText(f"Carregando commits de {branch}...")
        filters = CommitFilters(ref=branch)
        limit_raw = window.settings_data.get("commit_limit", 100)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, limit)
        try:
            summaries = load_commit_summaries(source_repo, limit=limit, filters=filters)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Importar", str(exc))
            clear_import_selection(window, "Falha ao carregar commits da origem.")
            return
        window.import_commit_summaries = summaries
        window.import_commits_list.clear()
        for summary in summaries:
            label = f"{summary.commit_hash[:7]} | {summary.subject}"
            item = QListWidgetItem(label, window.import_commits_list)
            item.setData(Qt.ItemDataRole.UserRole, summary.commit_hash)
        if summaries:
            window.import_status_label.setText(f"{len(summaries)} commits carregados da branch {branch}.")
        else:
            window.import_status_label.setText(f"Nenhum commit encontrado na branch {branch}.")
        update_import_controls_state(window)
    finally:
        window._end_busy()


def get_selected_import_summaries(window: object) -> list[CommitSummary]:
    selected_indexes = window.import_commits_list.selectedIndexes()
    if not selected_indexes:
        return []
    selected_hashes: list[str] = []
    for model_index in sorted(selected_indexes, key=lambda index: int(index.row())):
        item = window.import_commits_list.item(model_index.row())
        if item is None:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
        if commit_hash:
            selected_hashes.append(commit_hash)
    summaries_by_hash = {item.commit_hash: item for item in window.import_commit_summaries}
    selected: list[CommitSummary] = []
    for commit_hash in selected_hashes:
        summary = summaries_by_hash.get(commit_hash)
        if summary is not None:
            selected.append(summary)
    return selected


def copy_selected_import_hashes(window: object) -> None:
    selected = get_selected_import_summaries(window)
    if not selected:
        QMessageBox.information(window, "Importar", "Selecione commits para copiar os hashes.")
        return
    payload = "\n".join(item.commit_hash for item in selected)
    QApplication.clipboard().setText(payload)
    window._set_status("Hashes copiados.")


def _copy_import_commit_hash(window: object, commit_hash: str) -> None:
    if window._copy_to_clipboard(commit_hash, status="Hash do commit copiado."):
        return
    QMessageBox.information(window, "Importar", "Nao foi possivel copiar o hash do commit.")


def _copy_import_commit_files_list(window: object, commit_hash: str) -> None:
    source_repo = window.import_source_repo_path.strip()
    if not source_repo:
        QMessageBox.warning(window, "Importar", "Selecione repositorio e branch de origem.")
        return
    try:
        files = core_list_commit_files(source_repo, commit_hash)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Importar", str(exc))
        return
    payload = "\n".join(files).strip()
    if window._copy_to_clipboard(payload, status="Lista de arquivos do commit copiada."):
        return
    QMessageBox.information(window, "Importar", "Esse commit nao possui arquivos listaveis.")


def _copy_import_commit_patch(window: object, commit_hash: str) -> None:
    source_repo = window.import_source_repo_path.strip()
    if not source_repo:
        QMessageBox.warning(window, "Importar", "Selecione repositorio e branch de origem.")
        return
    try:
        patch = core_get_commit_patch(source_repo, commit_hash, path=None, word_diff=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Importar", str(exc))
        return
    if window._copy_to_clipboard(patch, status="Patch completo do commit copiado."):
        return
    QMessageBox.information(window, "Importar", "Sem patch para copiar neste commit.")


def on_import_commit_context_menu(window: object, pos: QPoint) -> None:
    if not window.import_source_repo_path.strip():
        return
    item = window.import_commits_list.itemAt(pos)
    if item is not None:
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
    else:
        selected_items = window.import_commits_list.selectedItems()
        if not selected_items:
            return
        value = selected_items[-1].data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
    if not commit_hash:
        return

    menu = QMenu(window.import_commits_list)
    action_open_github = menu.addAction("Abrir commit no GitHub")
    action_copy_github = menu.addAction("Copiar URL do commit")
    menu.addSeparator()
    action_copy_hash = menu.addAction("Copiar hash completo")
    action_copy_files = menu.addAction("Copiar lista de arquivos")
    action_copy_patch = menu.addAction("Copiar patch completo")

    selected_action = menu.exec(window.import_commits_list.mapToGlobal(pos))
    if selected_action is None:
        return
    if selected_action == action_open_github:
        window._open_commit_in_github(commit_hash, window.import_source_repo_path)
        return
    if selected_action == action_copy_github:
        window._copy_commit_github_url(commit_hash, window.import_source_repo_path)
        return
    if selected_action == action_copy_hash:
        _copy_import_commit_hash(window, commit_hash)
        return
    if selected_action == action_copy_files:
        _copy_import_commit_files_list(window, commit_hash)
        return
    if selected_action == action_copy_patch:
        _copy_import_commit_patch(window, commit_hash)


def import_selected_commits(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Importar", "Selecione um repositório destino válido primeiro.")
        return
    source_repo = window.import_source_repo_path
    if not source_repo:
        QMessageBox.warning(window, "Importar", "Selecione o repositório de origem.")
        return
    selected = get_selected_import_summaries(window)
    if not selected:
        QMessageBox.warning(window, "Importar", "Selecione ao menos um commit para importar.")
        return
    target_branch = window.branch_combo.currentData()
    target = str(target_branch).strip() if target_branch is not None else ""
    if not target:
        target = core_get_current_branch(window.repo_path).strip()
    source_branch_data = window.import_source_branch_combo.currentData()
    source_branch = str(source_branch_data).strip() if source_branch_data is not None else ""
    confirm = QMessageBox.question(
        window,
        "Importar commits",
        (
            f"Importar {len(selected)} commit(s)\n"
            f"Origem: {source_repo} ({source_branch or '(sem branch)'})\n"
            f"Destino: {window.repo_path} ({target or '(desconhecida)'})"
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return

    source_is_target = normalize_repo_path(source_repo) == normalize_repo_path(window.repo_path)
    ordered = list(reversed(selected))
    applied = 0
    window.import_status_label.setText("Importando commits...")
    window._begin_busy(f"Importando commits (0/{len(ordered)})...")
    try:
        for summary in ordered:
            window._set_busy_message(f"Importando commits ({applied + 1}/{len(ordered)})...")
            try:
                core_cherry_pick_commit(
                    window.repo_path,
                    summary.commit_hash,
                    source_repo=source_repo,
                    fetch_source=not source_is_target,
                )
            except RuntimeError as exc:
                has_conflicts = False
                try:
                    has_conflicts = core_has_unmerged_conflicts(window.repo_path)
                except RuntimeError:
                    has_conflicts = False
                if has_conflicts:
                    QMessageBox.warning(
                        window,
                        "Importar",
                        f"Falha ao importar {summary.commit_hash[:7]}.\n{exc}\nConflitos detectados.",
                    )
                    window._show_conflicts_dialog(
                        operation="cherry-pick",
                        source_label="Importar",
                    )
                else:
                    QMessageBox.critical(
                        window,
                        "Importar",
                        f"Falha ao importar {summary.commit_hash[:7]}.\n{exc}\nImportação interrompida.",
                    )
                window.import_status_label.setText(f"Importação interrompida após {applied} commit(s).")
                window._refresh_repo_state_ui()
                window._refresh_workspace_tree()
                window._reload_history_commits()
                window._refresh_compare_branch_options()
                window._refresh_commit_files()
                update_import_controls_state(window)
                return
            applied += 1
    finally:
        window._end_busy()

    window.import_status_label.setText(f"Importação concluída: {applied} commit(s) em {target}.")
    window._set_status(f"Importado em {target}: {applied} commit(s).")
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_commit_files()
    load_import_source_commits(window)
    update_import_controls_state(window)


def update_import_controls_state(window: object) -> None:
    if not hasattr(window, "import_run_button"):
        return
    source_ready = bool(window.import_source_repo_path and window.import_source_branch_combo.currentData())
    selected = bool(window.import_commits_list.selectedItems())
    has_source_options = window.import_source_repo_combo.count() > 0
    can_import = bool(window.repo_path and source_ready and selected)
    window.import_run_button.setEnabled(can_import)
    window.import_copy_hashes_button.setEnabled(selected)
    window.import_source_branch_combo.setEnabled(source_ready or bool(window.import_source_repo_path))
    window.import_source_branch_refresh_button.setEnabled(source_ready)
    window.import_source_repo_combo.setEnabled(has_source_options)
    window.import_source_repo_refresh_button.setEnabled(True)
