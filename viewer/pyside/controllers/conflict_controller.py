from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...core.cherry_pick_ops import load_unmerged_conflict_files as core_load_unmerged_conflict_files
from ...core.conflict_ops import (
    abort_conflict_operation as core_abort_conflict_operation,
    continue_conflict_operation as core_continue_conflict_operation,
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
    continue_button = QPushButton("Continuar", dialog)
    continue_button.setProperty("role", "primary")
    abort_button = QPushButton("Abortar", dialog)
    refresh_button = QPushButton("Recarregar", dialog)
    close_button = QPushButton("Fechar", dialog)
    actions_row.addWidget(open_button)
    actions_row.addStretch(1)
    actions_row.addWidget(refresh_button)
    actions_row.addWidget(continue_button)
    actions_row.addWidget(abort_button)
    actions_row.addWidget(close_button)
    layout.addLayout(actions_row)

    def load_conflicts() -> list[str]:
        try:
            return core_load_unmerged_conflict_files(repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Conflitos", str(exc))
            return []

    def refresh_conflicts() -> list[str]:
        files = load_conflicts()
        conflicts_list.clear()
        for path in files:
            conflicts_list.addItem(path)
        if files:
            status_label.setText(f"{len(files)} arquivo(s) em conflito.")
            continue_button.setEnabled(True)
        else:
            status_label.setText("Sem arquivos em conflito.")
            continue_button.setEnabled(False)
        open_button.setEnabled(bool(conflicts_list.selectedItems()))
        return files

    def open_selected() -> None:
        selected_items = conflicts_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            path = item.text().strip()
            if path:
                window._open_repo_file_in_vscode(path)

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
        lambda: open_button.setEnabled(bool(conflicts_list.selectedItems()))
    )
    conflicts_list.itemDoubleClicked.connect(lambda _item: open_selected())
    open_button.clicked.connect(open_selected)
    continue_button.clicked.connect(continue_operation)
    abort_button.clicked.connect(abort_operation)
    refresh_button.clicked.connect(refresh_conflicts)
    close_button.clicked.connect(dialog.reject)

    refresh_conflicts()
    dialog.exec()
