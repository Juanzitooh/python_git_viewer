from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...core.cherry_pick_ops import load_unmerged_conflict_files as core_load_unmerged_conflict_files
from ...core.conflict_ops import (
    abort_conflict_operation as core_abort_conflict_operation,
    abort_conflict_operation_and_restore as core_abort_conflict_operation_and_restore,
    continue_conflict_operation as core_continue_conflict_operation,
    mark_conflict_file_resolved as core_mark_conflict_file_resolved,
    resolve_conflict_file_using_side as core_resolve_conflict_file_using_side,
    resolve_active_conflict_operation as core_resolve_active_conflict_operation,
)
from ...core.git_client import run_git


ROLE_PATH = Qt.ItemDataRole.UserRole
ROLE_CONFLICT_STATE = Qt.ItemDataRole.UserRole + 1
ROLE_CONFLICT_CODE = Qt.ItemDataRole.UserRole + 2
UNMERGED_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


def _refresh_after_conflict(window: object) -> None:
    if hasattr(window, "_refresh_stash_tab_visibility"):
        window._refresh_stash_tab_visibility()
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._refresh_commit_files()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()


def _conflict_side_labels(operation: str) -> tuple[str, str]:
    normalized = operation.strip().lower()
    if normalized in {"merge", "squash_merge"}:
        return (
            "Manter versao da branch destino (atual)",
            "Manter versao da branch origem (recebida)",
        )
    if normalized == "cherry-pick":
        return (
            "Manter estado atual da branch",
            "Manter alteracoes do commit em aplicacao",
        )
    if normalized == "rebase":
        return (
            "Manter estado atual da base",
            "Manter alteracoes do commit em rebase",
        )
    return ("Manter versao atual (ours)", "Manter versao recebida (theirs)")


def _load_conflict_codes(repo_path: str) -> dict[str, str]:
    try:
        output = run_git(repo_path, ["status", "--porcelain", "-z"])
    except RuntimeError:
        return {}
    entries = output.split("\0")
    mapping: dict[str, str] = {}
    for raw_entry in entries:
        if not raw_entry:
            continue
        status_code = raw_entry[:2]
        if status_code not in UNMERGED_CODES:
            continue
        path = raw_entry[3:] if len(raw_entry) > 3 else ""
        normalized_path = path.strip()
        if normalized_path:
            mapping[normalized_path] = status_code
    return mapping


def _format_conflict_status_label(code: str) -> str:
    normalized = code.strip().upper()
    labels = {
        "UU": "ambos alteraram",
        "AA": "adicionado nos dois lados",
        "DD": "removido nos dois lados",
        "AU": "adicionado no atual, removido na origem",
        "UA": "adicionado na origem, removido no atual",
        "DU": "removido no atual, alterado na origem",
        "UD": "alterado no atual, removido na origem",
    }
    return labels.get(normalized, "conflito")


def _conflict_tab_index(window: object) -> int:
    if not hasattr(window, "tabs") or not hasattr(window, "conflict_tab"):
        return -1
    for index in range(window.tabs.count()):
        if window.tabs.widget(index) is window.conflict_tab:
            return index
    return -1


def _is_conflict_tab_visible(window: object) -> bool:
    return _conflict_tab_index(window) >= 0


def _ensure_conflict_tab_visible(window: object) -> None:
    if _is_conflict_tab_visible(window):
        return
    insert_index = window.tabs.count()
    for index in range(window.tabs.count()):
        if window.tabs.tabText(index) == "Stash":
            insert_index = index + 1
            break
    else:
        for index in range(window.tabs.count()):
            if window.tabs.tabText(index) == "Commit":
                insert_index = index + 1
                break
    window.conflict_tab.setParent(window.tabs)
    window.tabs.insertTab(insert_index, window.conflict_tab, "Conflict")


def _hide_conflict_tab(window: object) -> None:
    tab_index = _conflict_tab_index(window)
    if tab_index < 0:
        return
    if window.tabs.currentIndex() == tab_index:
        fallback = 0
        for index in range(window.tabs.count()):
            if index == tab_index:
                continue
            if window.tabs.tabText(index) == "Commit":
                fallback = index
                break
        window.tabs.setCurrentIndex(fallback)
    window.tabs.removeTab(tab_index)
    window.conflict_tab.hide()


def _set_conflict_header_labels(window: object, operation: str) -> None:
    if not hasattr(window, "conflict_repo_label"):
        return
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        window.conflict_repo_label.setText("Repositorio: (nenhum)")
        window.conflict_branch_label.setText("Branch: (nenhuma)")
        window.conflict_operation_label.setText("Operacao: (nenhuma)")
        return
    repo_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
    if hasattr(window, "_format_workspace_relative_path"):
        relative = str(window._format_workspace_relative_path(repo_path)).strip()
        if relative and relative != repo_path:
            repo_name = f"{repo_name} {relative}"
    branch_name = ""
    if hasattr(window, "_get_repo_branch_name"):
        branch_name = str(window._get_repo_branch_name(repo_path)).strip()
    normalized_operation = operation.strip().replace("_", " ")
    if not normalized_operation:
        normalized_operation = "(nenhuma)"
    window.conflict_repo_label.setText(f"Repositorio: {repo_name}")
    window.conflict_branch_label.setText(f"Branch: {branch_name or '(desconhecida)'}")
    window.conflict_operation_label.setText(f"Operacao: {normalized_operation}")


def _selected_conflict_file(window: object) -> str:
    if not hasattr(window, "conflict_files_list"):
        return ""
    selected_items = window.conflict_files_list.selectedItems()
    if not selected_items:
        return ""
    value = selected_items[0].data(ROLE_PATH)
    return str(value).strip() if value is not None else ""


def _set_conflict_actions_state(window: object, *, has_repo: bool, has_operation: bool, has_selection: bool) -> None:
    if hasattr(window, "conflict_open_file_button"):
        window.conflict_open_file_button.setEnabled(has_repo and has_selection)
    if hasattr(window, "conflict_open_resolver_button"):
        window.conflict_open_resolver_button.setEnabled(has_repo and (has_operation or has_selection))
    if hasattr(window, "conflict_refresh_button"):
        window.conflict_refresh_button.setEnabled(has_repo)


def _reload_conflict_entries(window: object, files: list[str], *, active_operation: str) -> None:
    if not hasattr(window, "conflict_files_list"):
        return
    selected = _selected_conflict_file(window)
    window.conflict_files_list.blockSignals(True)
    window.conflict_files_list.clear()
    selected_row = 0
    for index, path in enumerate(files):
        item = QListWidgetItem(path, window.conflict_files_list)
        item.setData(ROLE_PATH, path)
        if path == selected:
            selected_row = index
    window.conflict_files_list.blockSignals(False)
    if files:
        window.conflict_files_list.setCurrentRow(selected_row)
    has_selection = bool(_selected_conflict_file(window))
    _set_conflict_actions_state(
        window,
        has_repo=bool(getattr(window, "repo_path", "").strip()),
        has_operation=bool(active_operation.strip()),
        has_selection=has_selection,
    )


def refresh_conflict_tab_visibility(window: object) -> None:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        setattr(window, "conflict_active_operation", "")
        setattr(window, "conflict_abort_restore_ref", "")
        _set_conflict_header_labels(window, "")
        if hasattr(window, "conflict_files_list"):
            window.conflict_files_list.clear()
        _set_conflict_actions_state(window, has_repo=False, has_operation=False, has_selection=False)
        _hide_conflict_tab(window)
        return

    try:
        active_operation = core_resolve_active_conflict_operation(repo_path, preferred="")
        conflict_files = core_load_unmerged_conflict_files(repo_path)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Conflitos", str(exc))
        if hasattr(window, "conflict_files_list"):
            window.conflict_files_list.clear()
        _set_conflict_actions_state(window, has_repo=True, has_operation=False, has_selection=False)
        _hide_conflict_tab(window)
        return

    setattr(window, "conflict_active_operation", active_operation.strip())
    _set_conflict_header_labels(window, active_operation)
    show_tab = bool(active_operation or conflict_files)
    if not show_tab:
        setattr(window, "conflict_abort_restore_ref", "")
        if hasattr(window, "conflict_files_list"):
            window.conflict_files_list.clear()
        _set_conflict_actions_state(window, has_repo=True, has_operation=False, has_selection=False)
        _hide_conflict_tab(window)
        return

    _ensure_conflict_tab_visible(window)
    _reload_conflict_entries(window, conflict_files, active_operation=active_operation)


def on_conflict_file_selected(window: object) -> None:
    repo_path = bool(str(getattr(window, "repo_path", "")).strip())
    operation = str(getattr(window, "conflict_active_operation", "")).strip()
    has_selection = bool(_selected_conflict_file(window))
    _set_conflict_actions_state(
        window,
        has_repo=repo_path,
        has_operation=bool(operation),
        has_selection=has_selection,
    )


def open_selected_conflict_file(window: object) -> None:
    path = _selected_conflict_file(window)
    if not path:
        QMessageBox.information(window, "Conflict", "Selecione um arquivo em conflito.")
        return
    window._open_repo_file_in_vscode(path)


def open_conflict_resolver_from_tab(window: object) -> None:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        QMessageBox.information(window, "Conflict", "Selecione um repositório válido.")
        return
    operation = str(getattr(window, "conflict_active_operation", "")).strip()
    if not operation:
        try:
            operation = core_resolve_active_conflict_operation(repo_path, preferred="")
        except RuntimeError:
            operation = ""
    if not operation:
        if _selected_conflict_file(window):
            operation = "merge"
        else:
            QMessageBox.information(window, "Conflict", "Não há operação de conflito ativa.")
            return
    restore_ref = str(getattr(window, "conflict_abort_restore_ref", "")).strip()
    window._show_conflicts_dialog(
        operation=operation,
        source_label="Conflict",
        abort_restore_ref=restore_ref,
    )
    refresh_conflict_tab_visibility(window)


def show_conflicts_dialog(
    window: object,
    operation: str,
    *,
    source_label: str = "",
    continue_message: str = "",
    abort_restore_ref: str = "",
) -> None:
    repo_path = window.repo_path.strip()
    if not repo_path:
        QMessageBox.information(window, "Conflitos", "Selecione um repositório válido.")
        return
    active_operation = core_resolve_active_conflict_operation(repo_path, preferred=operation)
    if not active_operation:
        try:
            fallback_files = core_load_unmerged_conflict_files(repo_path)
        except RuntimeError:
            fallback_files = []
        preferred = operation.strip().lower()
        if fallback_files and preferred:
            active_operation = preferred
        else:
            QMessageBox.information(window, "Conflitos", "Não há operação de conflito ativa.")
            return

    dialog = QDialog(window)
    dialog.setWindowTitle("Resolver conflitos")
    dialog.setModal(True)
    dialog.resize(820, 520)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    source_prefix = f"{source_label} | " if source_label.strip() else ""
    operation_label = active_operation.replace("_", " ")
    header = QLabel(f"{source_prefix}Operação: {operation_label}", dialog)
    layout.addWidget(header)

    status_label = QLabel("Carregando conflitos...", dialog)
    layout.addWidget(status_label)

    conflicts_list = QListWidget(dialog)
    conflicts_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
    layout.addWidget(conflicts_list, stretch=1)

    side_current_label, side_incoming_label = _conflict_side_labels(active_operation)
    hints_label = QLabel(
        (
            f"Duplo clique abre no VS Code. Clique direito para ações do arquivo.\n"
            f"{side_current_label} | {side_incoming_label}"
        ),
        dialog,
    )
    hints_label.setWordWrap(True)
    layout.addWidget(hints_label)

    actions_row = QHBoxLayout()
    continue_button = QPushButton("Continuar", dialog)
    continue_button.setProperty("role", "primary")
    abort_button = QPushButton("Abortar", dialog)
    actions_row.addStretch(1)
    actions_row.addWidget(continue_button)
    actions_row.addWidget(abort_button)
    layout.addLayout(actions_row)

    normalized_restore_ref = abort_restore_ref.strip()
    if normalized_restore_ref:
        abort_button.setText("Abortar e restaurar backup")

    unresolved_paths: set[str] = set()
    resolved_paths: set[str] = set()
    active_operation_state: dict[str, str] = {"value": active_operation}
    unresolved_color = QColor("#f87171")
    resolved_color = QColor("#4ade80")
    conflicts_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def load_conflicts() -> list[str]:
        try:
            return core_load_unmerged_conflict_files(repo_path)
        except RuntimeError as exc:
            status_label.setText(f"Falha ao recarregar conflitos: {exc}")
            return []

    def selected_items_by_status(*, unresolved_only: bool = False) -> list[QListWidgetItem]:
        selected: list[QListWidgetItem] = []
        for item in conflicts_list.selectedItems():
            if not isinstance(item, QListWidgetItem):
                continue
            status_value = item.data(ROLE_CONFLICT_STATE)
            status_text = str(status_value).strip() if status_value is not None else ""
            if unresolved_only and status_text != "unresolved":
                continue
            selected.append(item)
        return selected

    def selected_unresolved_paths() -> list[str]:
        paths: list[str] = []
        for item in selected_items_by_status(unresolved_only=True):
            value = item.data(Qt.ItemDataRole.UserRole)
            path = str(value).strip() if value is not None else ""
            if path and path not in paths:
                paths.append(path)
        return paths

    def _sync_operation_ui(operation_value: str) -> None:
        operation_text = operation_value.replace("_", " ").strip() or "(nenhuma)"
        header.setText(f"{source_prefix}Operação: {operation_text}")
        ours_label, theirs_label = _conflict_side_labels(operation_value)
        hints_label.setText(
            (
                "Duplo clique abre no VS Code. Clique direito para ações do arquivo.\n"
                f"{ours_label} | {theirs_label}"
            )
        )

    def refresh_conflicts() -> list[str]:
        nonlocal unresolved_paths, resolved_paths
        files = load_conflicts()
        conflict_codes = _load_conflict_codes(repo_path)
        current_unresolved = {path.strip() for path in files if path.strip()}
        resolved_paths.update(unresolved_paths - current_unresolved)
        unresolved_paths = current_unresolved
        resolved_paths.difference_update(unresolved_paths)

        try:
            resolved_operation = core_resolve_active_conflict_operation(
                repo_path,
                preferred=active_operation_state["value"],
            )
        except RuntimeError as exc:
            status_label.setText(f"Falha ao detectar operacao de conflito: {exc}")
            resolved_operation = active_operation_state["value"]
        if resolved_operation:
            active_operation_state["value"] = resolved_operation
        elif not unresolved_paths:
            active_operation_state["value"] = ""

        _sync_operation_ui(active_operation_state["value"])

        current_item = conflicts_list.currentItem()
        current_path = ""
        if isinstance(current_item, QListWidgetItem):
            raw_current_path = current_item.data(ROLE_PATH)
            current_path = str(raw_current_path).strip() if raw_current_path is not None else ""

        conflicts_list.clear()
        for path in sorted(unresolved_paths):
            code = str(conflict_codes.get(path, "")).strip().upper()
            item = QListWidgetItem(f"● {path}")
            item.setData(ROLE_PATH, path)
            item.setData(ROLE_CONFLICT_STATE, "unresolved")
            item.setData(ROLE_CONFLICT_CODE, code)
            item.setForeground(unresolved_color)
            status_hint = _format_conflict_status_label(code)
            if code:
                item.setToolTip(
                    f"Tipo: {code} ({status_hint}).\nClique direito para escolher a ação deste conflito."
                )
            else:
                item.setToolTip("Conflito pendente.\nClique direito para escolher a ação deste conflito.")
            conflicts_list.addItem(item)
        for path in sorted(resolved_paths):
            item = QListWidgetItem(f"✔ {path} (resolvido)")
            item.setData(ROLE_PATH, path)
            item.setData(ROLE_CONFLICT_STATE, "resolved")
            item.setData(ROLE_CONFLICT_CODE, "")
            item.setForeground(resolved_color)
            item.setToolTip("Arquivo já resolvido nesta sessão.")
            conflicts_list.addItem(item)

        if current_path:
            for index in range(conflicts_list.count()):
                row_item = conflicts_list.item(index)
                row_path = row_item.data(ROLE_PATH)
                if str(row_path).strip() == current_path:
                    conflicts_list.setCurrentRow(index)
                    break

        pending = len(unresolved_paths)
        solved = len(resolved_paths)
        if pending > 0:
            status_label.setText(
                f"Conflitos: {pending} pendente(s), {solved} resolvido(s). Resolva os pendentes para liberar Continuar."
            )
        elif active_operation_state["value"]:
            status_label.setText(
                f"Conflitos: {pending} pendente(s), {solved} resolvido(s). Continuar liberado."
            )
        else:
            status_label.setText("Nenhuma operação de conflito ativa. Você pode fechar esta janela.")
        continue_button.setEnabled(pending == 0)
        abort_button.setEnabled(bool(active_operation_state["value"]))
        return files

    def open_selected() -> None:
        selected_items = selected_items_by_status(unresolved_only=False)
        if not selected_items:
            return
        for item in selected_items:
            value = item.data(Qt.ItemDataRole.UserRole)
            path = str(value).strip() if value is not None else ""
            if path:
                window._open_repo_file_in_vscode(path)

    def open_item(item: QListWidgetItem | None) -> None:
        if not isinstance(item, QListWidgetItem):
            open_selected()
            return
        value = item.data(Qt.ItemDataRole.UserRole)
        path = str(value).strip() if value is not None else ""
        if path:
            window._open_repo_file_in_vscode(path)

    def open_conflict_context_menu(pos: QPoint) -> None:
        item = conflicts_list.itemAt(pos)
        if item is not None and not item.isSelected():
            conflicts_list.clearSelection()
            item.setSelected(True)
            conflicts_list.setCurrentItem(item)

        selected_any = bool(selected_items_by_status(unresolved_only=False))
        selected_unresolved = selected_items_by_status(unresolved_only=True)
        unresolved_selected = bool(selected_unresolved)

        menu = QMenu(conflicts_list)
        open_action = menu.addAction("Abrir selecionado no VS Code")
        open_action.setEnabled(selected_any)

        keep_current_action = None
        keep_incoming_action = None
        mark_resolved_action = None
        ours_label, theirs_label = _conflict_side_labels(active_operation_state["value"])
        if unresolved_selected:
            menu.addSeparator()
            keep_current_action = menu.addAction(ours_label)
            keep_incoming_action = menu.addAction(theirs_label)
            mark_resolved_action = menu.addAction("Marcar como resolvido (git add)")

            if len(selected_unresolved) == 1:
                selected_code_value = selected_unresolved[0].data(ROLE_CONFLICT_CODE)
                selected_code = str(selected_code_value).strip().upper() if selected_code_value is not None else ""
                if selected_code:
                    menu.addSeparator()
                    info_action = menu.addAction(
                        f"Tipo: {selected_code} ({_format_conflict_status_label(selected_code)})"
                    )
                    info_action.setEnabled(False)

        menu.addSeparator()
        reload_action = menu.addAction("Recarregar conflitos")

        picked = menu.exec(conflicts_list.viewport().mapToGlobal(pos))
        if picked is None:
            return
        if picked == open_action:
            open_selected()
            return
        if picked == keep_current_action:
            apply_selected_side("ours")
            return
        if picked == keep_incoming_action:
            apply_selected_side("theirs")
            return
        if picked == mark_resolved_action:
            mark_selected_resolved()
            return
        if picked == reload_action:
            refresh_conflicts()

    def apply_selected_side(side: str) -> None:
        selected_paths = selected_unresolved_paths()
        if not selected_paths:
            return
        window._begin_busy("Aplicando resolucao de conflito...")
        try:
            for path in selected_paths:
                core_resolve_conflict_file_using_side(repo_path, path, side)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()
        _refresh_after_conflict(window)
        refresh_conflicts()
        if side == "ours":
            window._set_status("Conflito resolvido: mantida versao da branch atual.")
        else:
            window._set_status("Conflito resolvido: mantida versao recebida.")

    def mark_selected_resolved() -> None:
        selected_paths = selected_unresolved_paths()
        if not selected_paths:
            return
        window._begin_busy("Marcando arquivo como resolvido...")
        try:
            for path in selected_paths:
                core_mark_conflict_file_resolved(repo_path, path)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()
        _refresh_after_conflict(window)
        refresh_conflicts()
        window._set_status("Arquivo marcado como resolvido.")

    def continue_operation() -> None:
        remaining_before = refresh_conflicts()
        if remaining_before:
            QMessageBox.information(
                dialog,
                "Conflitos",
                "Ainda existem conflitos pendentes. Resolva/adicione os arquivos antes de continuar.",
            )
            return
        current_operation = core_resolve_active_conflict_operation(
            repo_path,
            preferred=active_operation_state["value"],
        )
        active_operation_state["value"] = current_operation
        _sync_operation_ui(current_operation)
        if not current_operation:
            _refresh_after_conflict(window)
            setattr(window, "conflict_abort_restore_ref", "")
            window._set_status("Nenhuma operação de conflito ativa.")
            dialog.accept()
            return
        operation_text = current_operation.replace("_", " ")
        squash_message = continue_message if current_operation == "squash_merge" else ""
        window._begin_busy(f"Concluindo {operation_text}...")
        try:
            core_continue_conflict_operation(repo_path, current_operation, squash_message=squash_message)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()

        _refresh_after_conflict(window)
        refresh_conflicts()
        if unresolved_paths:
            return
        next_operation = core_resolve_active_conflict_operation(repo_path, preferred=current_operation)
        if next_operation:
            active_operation_state["value"] = next_operation
            _sync_operation_ui(next_operation)
            window._set_status(f"Etapa concluida ({operation_text}).")
            return
        setattr(window, "conflict_abort_restore_ref", "")
        window._set_status(f"Operação finalizada: {operation_text}.")
        QMessageBox.information(dialog, "Conflitos", "Operação concluída sem conflitos pendentes.")
        dialog.accept()

    def abort_operation() -> None:
        current_operation = core_resolve_active_conflict_operation(
            repo_path,
            preferred=active_operation_state["value"],
        )
        active_operation_state["value"] = current_operation
        _sync_operation_ui(current_operation)
        if not current_operation:
            dialog.accept()
            return
        operation_text = current_operation.replace("_", " ")
        restore_suffix = ""
        if normalized_restore_ref:
            restore_suffix = f"\n\nO estado atual sera restaurado para: {normalized_restore_ref}"
        confirm = QMessageBox.question(
            dialog,
            "Abortar operação",
            f"Deseja abortar a operação atual ({operation_text})?{restore_suffix}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        window._begin_busy(f"Abortando {operation_text}...")
        try:
            if normalized_restore_ref:
                core_abort_conflict_operation_and_restore(
                    repo_path,
                    current_operation,
                    restore_ref=normalized_restore_ref,
                    delete_restore_ref=True,
                )
            else:
                core_abort_conflict_operation(repo_path, current_operation)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()

        _refresh_after_conflict(window)
        setattr(window, "conflict_abort_restore_ref", "")
        if normalized_restore_ref:
            window._set_status(
                f"Operação abortada: {operation_text}. Estado restaurado do backup {normalized_restore_ref}."
            )
        else:
            window._set_status(f"Operação abortada: {operation_text}.")
        dialog.accept()

    conflicts_list.itemDoubleClicked.connect(open_item)
    conflicts_list.customContextMenuRequested.connect(open_conflict_context_menu)
    continue_button.clicked.connect(continue_operation)
    abort_button.clicked.connect(abort_operation)

    poll_timer = QTimer(dialog)
    poll_timer.setInterval(1200)
    poll_timer.timeout.connect(refresh_conflicts)
    dialog.finished.connect(lambda _result: poll_timer.stop())

    refresh_conflicts()
    poll_timer.start()
    dialog.exec()
