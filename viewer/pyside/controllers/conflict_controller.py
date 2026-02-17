from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...core.cherry_pick_ops import load_unmerged_conflict_files as core_load_unmerged_conflict_files
from ...core.conflict_ops import (
    abort_conflict_operation as core_abort_conflict_operation,
    continue_conflict_operation as core_continue_conflict_operation,
    mark_conflict_file_resolved as core_mark_conflict_file_resolved,
    resolve_conflict_file_using_side as core_resolve_conflict_file_using_side,
    resolve_active_conflict_operation as core_resolve_active_conflict_operation,
)


def _refresh_after_conflict(window: object) -> None:
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._refresh_commit_files()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()


def show_conflicts_dialog(
    window: object,
    operation: str,
    *,
    source_label: str = "",
    continue_message: str = "",
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

    actions_row = QHBoxLayout()
    open_button = QPushButton("Abrir selecionado no VS Code", dialog)
    keep_current_button = QPushButton("Manter atual", dialog)
    keep_incoming_button = QPushButton("Manter origem", dialog)
    mark_resolved_button = QPushButton("Marcar resolvido", dialog)
    continue_button = QPushButton("Continuar", dialog)
    continue_button.setProperty("role", "primary")
    abort_button = QPushButton("Abortar", dialog)
    refresh_button = QPushButton("Recarregar", dialog)
    close_button = QPushButton("Fechar", dialog)
    actions_row.addWidget(open_button)
    actions_row.addWidget(keep_current_button)
    actions_row.addWidget(keep_incoming_button)
    actions_row.addWidget(mark_resolved_button)
    actions_row.addStretch(1)
    actions_row.addWidget(refresh_button)
    actions_row.addWidget(continue_button)
    actions_row.addWidget(abort_button)
    actions_row.addWidget(close_button)
    layout.addLayout(actions_row)

    unresolved_paths: set[str] = set()
    resolved_paths: set[str] = set()
    unresolved_color = QColor("#f87171")
    resolved_color = QColor("#4ade80")
    status_role = int(Qt.ItemDataRole.UserRole + 1)

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
            status_value = item.data(status_role)
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

    def refresh_conflicts() -> list[str]:
        nonlocal unresolved_paths, resolved_paths
        files = load_conflicts()
        current_unresolved = {path.strip() for path in files if path.strip()}
        resolved_paths.update(unresolved_paths - current_unresolved)
        unresolved_paths = current_unresolved
        resolved_paths.difference_update(unresolved_paths)

        conflicts_list.clear()
        for path in sorted(unresolved_paths):
            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(status_role, "unresolved")
            item.setForeground(unresolved_color)
            item.setToolTip("Em conflito: resolva e marque como resolvido.")
            conflicts_list.addItem(item)
        for path in sorted(resolved_paths):
            item = QListWidgetItem(f"{path} (resolvido)")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(status_role, "resolved")
            item.setForeground(resolved_color)
            item.setToolTip("Arquivo já resolvido nesta sessão.")
            conflicts_list.addItem(item)
        status_label.setText(
            f"Conflitos: {len(unresolved_paths)} pendente(s), {len(resolved_paths)} resolvido(s)."
        )
        continue_button.setEnabled(True)
        _sync_action_buttons()
        return files

    def _sync_action_buttons() -> None:
        has_selection = bool(conflicts_list.selectedItems())
        has_unresolved_selection = bool(selected_items_by_status(unresolved_only=True))
        open_button.setEnabled(has_selection)
        keep_current_button.setEnabled(has_unresolved_selection)
        keep_incoming_button.setEnabled(has_unresolved_selection)
        mark_resolved_button.setEnabled(has_unresolved_selection)

    def open_selected() -> None:
        selected_items = selected_items_by_status(unresolved_only=False)
        if not selected_items:
            return
        for item in selected_items:
            value = item.data(Qt.ItemDataRole.UserRole)
            path = str(value).strip() if value is not None else ""
            if path:
                window._open_repo_file_in_vscode(path)

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
            window._set_status("Conflito resolvido: mantidas alteracoes locais.")
        else:
            window._set_status("Conflito resolvido: mantidas alteracoes da origem.")

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
        squash_message = continue_message if active_operation == "squash_merge" else ""
        window._begin_busy(f"Concluindo {operation_label}...")
        try:
            core_continue_conflict_operation(repo_path, active_operation, squash_message=squash_message)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()

        remaining = refresh_conflicts()
        _refresh_after_conflict(window)
        if remaining:
            return
        window._set_status(f"Operação finalizada: {operation_label}.")
        QMessageBox.information(dialog, "Conflitos", "Operação concluída sem conflitos pendentes.")
        dialog.accept()

    def abort_operation() -> None:
        confirm = QMessageBox.question(
            dialog,
            "Abortar operação",
            f"Deseja abortar a operação atual ({operation_label})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        window._begin_busy(f"Abortando {operation_label}...")
        try:
            core_abort_conflict_operation(repo_path, active_operation)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return
        finally:
            window._end_busy()

        _refresh_after_conflict(window)
        window._set_status(f"Operação abortada: {operation_label}.")
        dialog.accept()

    conflicts_list.itemSelectionChanged.connect(
        _sync_action_buttons
    )
    conflicts_list.itemDoubleClicked.connect(lambda _item: open_selected())
    open_button.clicked.connect(open_selected)
    keep_current_button.clicked.connect(lambda: apply_selected_side("ours"))
    keep_incoming_button.clicked.connect(lambda: apply_selected_side("theirs"))
    mark_resolved_button.clicked.connect(mark_selected_resolved)
    continue_button.clicked.connect(continue_operation)
    abort_button.clicked.connect(abort_operation)
    refresh_button.clicked.connect(refresh_conflicts)
    close_button.clicked.connect(dialog.reject)

    poll_timer = QTimer(dialog)
    poll_timer.setInterval(1500)
    poll_timer.timeout.connect(refresh_conflicts)
    dialog.finished.connect(lambda _result: poll_timer.stop())

    refresh_conflicts()
    poll_timer.start()
    dialog.exec()
