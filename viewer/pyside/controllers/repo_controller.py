from __future__ import annotations

import os
import shutil
import time
from typing import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.branch_ops import (
    checkout_branch as core_checkout_branch,
    delete_local_branch as core_delete_local_branch,
    delete_remote_branch as core_delete_remote_branch,
    local_branch_exists as core_local_branch_exists,
    remote_branch_exists as core_remote_branch_exists,
)
from ...core.git_client import is_git_repo
from ...core.repo_state import (
    get_ahead_behind as core_get_ahead_behind,
    get_current_branch as core_get_current_branch,
    get_default_branch as core_get_default_branch,
    get_upstream as core_get_upstream,
    list_branches as core_list_branches,
    list_local_branches_with_upstream as core_list_local_branches_with_upstream,
    list_worktree_changed_files as core_list_worktree_changed_files,
)
from ...core.repo_workspace import clone_repository, default_repo_scan_root, discover_git_repositories
from ...core.settings_store import normalize_repo_path
from ..widgets import NoScrollComboBox


CONTEXT_MENU_GUARD_SECONDS = 0.35


def _is_context_menu_guard_active(window: object) -> bool:
    guard_until = getattr(window, "_context_menu_guard_until", 0.0)
    try:
        return float(guard_until) > time.monotonic()
    except (TypeError, ValueError):
        return False


def _arm_context_menu_guard(window: object, seconds: float = CONTEXT_MENU_GUARD_SECONDS) -> None:
    setattr(window, "_context_menu_guard_until", time.monotonic() + max(0.05, float(seconds)))


class WorkspaceCardFrame(QFrame):
    clicked = Signal()
    double_clicked = Signal()
    context_requested = Signal(QPoint)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def collect_repo_paths_from_settings(window: object, key: str) -> list[str]:
    items = window.settings_data.get(key, [])
    if not isinstance(items, list):
        return []
    repos: list[str] = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        normalized = normalize_repo_path(raw)
        if not os.path.isdir(normalized) or not is_git_repo(normalized):
            continue
        if normalized not in repos:
            repos.append(normalized)
    return repos


def repo_is_favorite(window: object, repo_path: str) -> bool:
    favorites = collect_repo_paths_from_settings(window, "favorite_repos")
    return normalize_repo_path(repo_path) in favorites


def format_workspace_relative_path(window: object, repo_path: str) -> str:
    normalized_repo = normalize_repo_path(repo_path)
    root = normalize_repo_path(window.repo_scan_root) if window.repo_scan_root else ""
    if root:
        try:
            relative = os.path.relpath(normalized_repo, root)
        except ValueError:
            relative = normalized_repo
        if not relative.startswith(".."):
            return f"/{relative}".replace("\\", "/")
    return normalized_repo


def format_repo_display_label(window: object, repo_path: str) -> str:
    base_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
    relative = format_workspace_relative_path(window, repo_path)
    favorite_prefix = "★ " if repo_is_favorite(window, repo_path) else ""
    return f"{favorite_prefix}{base_name} {relative}"


def format_workspace_group_label(window: object, repo_path: str) -> str:
    normalized_repo = normalize_repo_path(repo_path)
    root = normalize_repo_path(window.repo_scan_root) if window.repo_scan_root else ""
    if root:
        try:
            relative = os.path.relpath(normalized_repo, root).replace("\\", "/")
        except ValueError:
            relative = ""
        if relative and not relative.startswith(".."):
            parent = os.path.dirname(relative).replace("\\", "/").strip()
            if not parent or parent == ".":
                return "(raiz)"
            return f"/{parent}"
    parent = os.path.dirname(normalized_repo.rstrip(os.sep)).strip()
    return parent or "(raiz)"


def format_workspace_card_label(window: object, repo_path: str) -> str:
    base_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
    favorite_prefix = "★ " if repo_is_favorite(window, repo_path) else ""
    return f"{favorite_prefix}{base_name}"


def _workspace_repo_sort_key(window: object, repo_path: str) -> tuple[str, str]:
    base_name = (os.path.basename(repo_path.rstrip(os.sep)) or repo_path).casefold()
    relative_path = format_workspace_relative_path(window, repo_path).lstrip("/").casefold()
    return base_name, relative_path


def format_branch_display_label(
    branch_name: str,
    default_branch: str,
    tracked_local_branches: set[str] | None = None,
) -> str:
    payload = get_branch_display_payload(branch_name, default_branch, tracked_local_branches)
    return payload["label"]


def _branch_scope_kind(branch_name: str, tracked_local_branches: set[str] | None = None) -> str:
    normalized = str(branch_name).strip()
    if normalized == "HEAD":
        return "detached"
    if normalized.startswith("origin/"):
        return "remote"
    if "/" in normalized:
        remote, _, short_name = normalized.partition("/")
        if remote and short_name and remote in {"origin", "upstream"}:
            return "remote"
    tracked = tracked_local_branches or set()
    if normalized in tracked:
        return "tracked"
    return "local"


def _branch_display_name(branch_name: str) -> str:
    normalized = str(branch_name).strip()
    if normalized.startswith("origin/"):
        return normalized[len("origin/") :].strip()
    if "/" in normalized:
        remote, _, short_name = normalized.partition("/")
        if remote and short_name and remote in {"origin", "upstream"}:
            return short_name.strip()
    return normalized


def get_branch_display_payload(
    branch_name: str,
    default_branch: str,
    tracked_local_branches: set[str] | None = None,
) -> dict[str, str]:
    normalized = str(branch_name).strip()
    scope = _branch_scope_kind(normalized, tracked_local_branches)
    is_default = bool(
        default_branch
        and (
            normalized == default_branch
            or normalized == f"origin/{default_branch}"
        )
    )
    if scope == "detached":
        return {
            "label": "HEAD",
            "scope": scope,
            "tooltip": "HEAD detached: sem branch ativa. Faça checkout de uma branch para voltar ao fluxo normal.",
        }
    display_name = branch_name
    display_name = _branch_display_name(display_name)
    if scope == "remote":
        tooltip = "Branch remota: ainda nao existe branch local equivalente neste repositorio."
    elif scope == "tracked":
        tooltip = "Branch local com upstream remoto configurado."
    else:
        tooltip = "Branch apenas local: ainda nao publicada no remoto."
    if is_default:
        return {
            "label": f"★ {display_name}",
            "scope": scope,
            "tooltip": f"{tooltip} Branch padrao do repositorio.",
        }
    return {"label": display_name, "scope": scope, "tooltip": tooltip}


def _branch_scope_foreground_brush(window: object, scope: str) -> QBrush | None:
    if scope != "local":
        return None
    theme = str(getattr(window, "current_theme", "dark")).strip().lower()
    color_hex = "#b45309" if theme == "light" else "#fbbf24"
    return QBrush(QColor(color_hex))


def add_branch_combo_item(
    window: object,
    combo: QComboBox,
    branch_name: str,
    default_branch: str,
    tracked_local_branches: set[str] | None = None,
) -> None:
    payload = get_branch_display_payload(branch_name, default_branch, tracked_local_branches)
    combo.addItem(payload["label"], branch_name)
    index = combo.count() - 1
    combo.setItemData(index, payload["tooltip"], Qt.ItemDataRole.ToolTipRole)
    brush = _branch_scope_foreground_brush(window, payload["scope"])
    combo.setItemData(index, brush, Qt.ItemDataRole.ForegroundRole)


def sync_branch_combo_tooltip(combo: QComboBox, fallback: str = "Selecionar branch") -> None:
    index = combo.currentIndex()
    if index < 0:
        combo.setToolTip(fallback)
        return
    tooltip_value = combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
    tooltip = str(tooltip_value).strip() if tooltip_value is not None else ""
    combo.setToolTip(tooltip or fallback)


def _split_remote_branch_ref(branch_name: str) -> tuple[str, str]:
    remote, _, short_name = branch_name.partition("/")
    return remote.strip(), short_name.strip()


def _branch_target_capabilities(repo_path: str, branch_name: str) -> dict[str, str | bool]:
    normalized = str(branch_name).strip()
    local_exists = core_local_branch_exists(repo_path, normalized)
    remote_ref = ""
    remote_name = ""
    remote_branch = ""

    if core_remote_branch_exists(repo_path, normalized):
        candidate_remote, candidate_branch = _split_remote_branch_ref(normalized)
        if candidate_remote and candidate_branch:
            remote_ref = normalized
            remote_name = candidate_remote
            remote_branch = candidate_branch
    elif local_exists:
        origin_candidate = f"origin/{normalized}"
        if core_remote_branch_exists(repo_path, origin_candidate):
            remote_ref = origin_candidate
            remote_name = "origin"
            remote_branch = normalized

    return {
        "branch": normalized,
        "local_exists": local_exists,
        "remote_ref": remote_ref,
        "remote_name": remote_name,
        "remote_branch": remote_branch,
    }


def collect_known_repos(window: object) -> list[str]:
    ordered: list[str] = []
    for source in (
        collect_repo_paths_from_settings(window, "favorite_repos"),
        collect_repo_paths_from_settings(window, "recent_repos"),
        window.scanned_repos,
        [window.repo_path] if window.repo_path else [],
    ):
        for repo in source:
            normalized = normalize_repo_path(repo)
            if normalized in ordered:
                continue
            if not os.path.isdir(normalized) or not is_git_repo(normalized):
                continue
            ordered.append(normalized)
    return ordered


def load_repo_selector_items(window: object) -> None:
    selected = window.repo_path
    if not selected:
        current = window.repo_combo.currentData()
        selected = str(current).strip() if current is not None else ""
    repos = collect_known_repos(window)
    window._setting_repo_programmatically = True
    try:
        window.repo_combo.clear()
        for repo in repos:
            window.repo_combo.addItem(format_repo_display_label(window, repo), repo)
        if selected:
            index = window.repo_combo.findData(selected)
            if index >= 0:
                window.repo_combo.setCurrentIndex(index)
    finally:
        window._setting_repo_programmatically = False


def on_workspace_root_edited(window: object) -> None:
    candidate = window.workspace_root_edit.text().strip()
    normalized = normalize_repo_path(candidate) if candidate else normalize_repo_path(default_repo_scan_root())
    if normalized == window.repo_scan_root:
        return
    window.repo_scan_root = normalized
    window.workspace_root_edit.setText(window.repo_scan_root)
    scan_workspace_repos(window)
    window._persist_state()


def pick_workspace_root(window: object) -> None:
    selected = QFileDialog.getExistingDirectory(window, "Selecionar raiz do workspace", window.repo_scan_root)
    if not selected:
        return
    window.repo_scan_root = normalize_repo_path(selected)
    window.workspace_root_edit.setText(window.repo_scan_root)
    scan_workspace_repos(window)
    window._persist_state()


def scan_workspace_repos(window: object) -> None:
    window._begin_busy("Escaneando workspace...")
    try:
        root = (
            normalize_repo_path(window.repo_scan_root)
            if window.repo_scan_root
            else normalize_repo_path(default_repo_scan_root())
        )
        os.makedirs(root, exist_ok=True)
        window.repo_scan_root = root
        window.workspace_root_edit.setText(root)
        discovered = discover_git_repositories(root, max_depth=4)
        window.scanned_repos = [normalize_repo_path(path) for path in discovered]
        window.workspace_scan_status_label.setText(
            f"Scan inicial: {len(window.scanned_repos)} encontrados em {root}"
        )
        load_repo_selector_items(window)
        refresh_workspace_tree(window)
        window._refresh_import_source_repos()
    finally:
        window._end_busy()


def build_repo_status_summary(_window: object, repo_path: str) -> str:
    try:
        changed = core_list_worktree_changed_files(repo_path)
    except RuntimeError:
        return "(indisponivel)"
    if not changed:
        return "limpo"
    if len(changed) <= 2:
        suffix = "arquivo" if len(changed) == 1 else "arquivos"
        return f"{len(changed)} {suffix}: {', '.join(changed)}"
    return f"{len(changed)} arquivos: {changed[0]}, {changed[1]}, +{len(changed) - 2}"


def build_repo_snapshot(window: object, repo_path: str) -> tuple[str, int, int, str]:
    branch = "(desconhecida)"
    ahead = 0
    behind = 0
    try:
        branch = core_get_current_branch(repo_path).strip() or branch
    except RuntimeError:
        return branch, ahead, behind, "(indisponivel)"
    upstream = core_get_upstream(repo_path)
    if upstream:
        try:
            behind, ahead = core_get_ahead_behind(repo_path, upstream)
        except RuntimeError:
            behind, ahead = 0, 0
    status = build_repo_status_summary(window, repo_path)
    return branch, ahead, behind, status


def _is_current_repo(window: object, repo_path: str) -> bool:
    if not window.repo_path:
        return False
    return normalize_repo_path(window.repo_path) == normalize_repo_path(repo_path)


def _format_workspace_card_title(window: object, repo_path: str) -> str:
    title = format_workspace_card_label(window, repo_path)
    if _is_current_repo(window, repo_path):
        return f"▶ {title}"
    return title


def _clear_workspace_cards(window: object) -> QGridLayout:
    grid = window.workspace_cards_grid
    while grid.count() > 0:
        item = grid.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
    window.workspace_card_widgets = {}
    window.workspace_card_title_labels = {}
    return grid


def _workspace_card_columns(window: object) -> int:
    if not hasattr(window, "workspace_cards_scroll"):
        return 3
    viewport_width = window.workspace_cards_scroll.viewport().width()
    if viewport_width <= 0:
        return 3
    if viewport_width < 760:
        return 1
    if viewport_width < 1120:
        return 2
    if viewport_width < 1480:
        return 3
    return 4


def _checkout_branch_in_repo(window: object, repo_path: str, target_branch: str) -> bool:
    normalized_repo = normalize_repo_path(repo_path)
    normalized_target = str(target_branch).strip()
    if not normalized_target:
        return False
    try:
        current_branch = core_get_current_branch(normalized_repo).strip()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Branch", str(exc))
        refresh_workspace_tree(window)
        return False
    if current_branch == normalized_target:
        return False
    try:
        core_checkout_branch(normalized_repo, normalized_target)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Branch", str(exc))
        refresh_workspace_tree(window)
        return False

    if _is_current_repo(window, normalized_repo):
        refresh_repo_state_ui(window)
        window._refresh_commit_files()
        window._refresh_stash_tab_visibility()
        window._reload_history_commits()
        window._refresh_compare_branch_options()
        window._refresh_import_source_repos()
        window._sync_import_target_label()
    refresh_workspace_tree(window)
    window._set_status(f"Branch alterada em {os.path.basename(normalized_repo)}: {normalized_target}")
    window._persist_state()
    return True


def _on_workspace_card_branch_activated(window: object, repo_path: str, branch_combo: NoScrollComboBox) -> None:
    target_value = branch_combo.currentData()
    target_branch = str(target_value).strip() if target_value is not None else ""
    if not target_branch:
        return
    _checkout_branch_in_repo(window, repo_path, target_branch)


def _delete_local_branch_with_optional_force(window: object, repo_path: str, branch_name: str) -> bool:
    try:
        core_delete_local_branch(repo_path, branch_name, force=False)
        return True
    except RuntimeError as exc:
        lowered = str(exc).lower()
        requires_force = "not fully merged" in lowered or "não está totalmente mesclada" in lowered
        if not requires_force:
            QMessageBox.critical(window, "Excluir branch", str(exc))
            return False
    force_answer = QMessageBox.question(
        window,
        "Excluir branch",
        (
            f"A branch local `{branch_name}` não está totalmente mesclada.\n\n"
            "Deseja forçar exclusão local? (-D)"
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if force_answer != QMessageBox.StandardButton.Yes:
        return False
    try:
        core_delete_local_branch(repo_path, branch_name, force=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Excluir branch", str(exc))
        return False
    return True


def _delete_branch_with_confirmation(window: object, repo_path: str, branch_name: str) -> None:
    normalized_repo = normalize_repo_path(repo_path)
    capabilities = _branch_target_capabilities(normalized_repo, branch_name)
    normalized_branch = str(capabilities.get("branch", "")).strip()
    if not normalized_branch:
        return
    local_exists = bool(capabilities.get("local_exists", False))
    remote_name = str(capabilities.get("remote_name", "")).strip()
    remote_branch = str(capabilities.get("remote_branch", "")).strip()
    remote_exists = bool(remote_name and remote_branch)

    try:
        current_branch = core_get_current_branch(normalized_repo).strip()
    except RuntimeError:
        current_branch = ""

    can_delete_local = local_exists and normalized_branch != current_branch
    can_delete_remote = remote_exists

    if not can_delete_local and not can_delete_remote:
        if local_exists and normalized_branch == current_branch:
            QMessageBox.information(
                window,
                "Excluir branch",
                "Não é possível excluir a branch local atualmente em uso.",
            )
        return

    delete_local = False
    delete_remote = False
    if can_delete_local and can_delete_remote:
        confirm = QMessageBox(window)
        confirm.setWindowTitle("Excluir branch")
        confirm.setIcon(QMessageBox.Icon.Warning)
        confirm.setText(f"Branch selecionada: {normalized_branch}")
        confirm.setInformativeText("Escolha como excluir:")
        local_button = confirm.addButton("Excluir só local", QMessageBox.ButtonRole.AcceptRole)
        both_button = confirm.addButton("Excluir local + remota", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = confirm.addButton(QMessageBox.StandardButton.Cancel)
        confirm.setDefaultButton(cancel_button)
        confirm.exec()
        clicked = confirm.clickedButton()
        if clicked == cancel_button or clicked is None:
            return
        if clicked == local_button:
            delete_local = True
        elif clicked == both_button:
            delete_local = True
            delete_remote = True
    elif can_delete_local:
        answer = QMessageBox.question(
            window,
            "Excluir branch local",
            f"Excluir branch local `{normalized_branch}`?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        delete_local = answer == QMessageBox.StandardButton.Yes
    elif can_delete_remote:
        answer = QMessageBox.question(
            window,
            "Excluir branch remota",
            f"Excluir branch remota `{remote_name}/{remote_branch}`?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        delete_remote = answer == QMessageBox.StandardButton.Yes

    if not delete_local and not delete_remote:
        return

    performed_actions: list[str] = []
    if delete_local:
        if not _delete_local_branch_with_optional_force(window, normalized_repo, normalized_branch):
            return
        performed_actions.append(f"local `{normalized_branch}`")
    if delete_remote:
        try:
            core_delete_remote_branch(normalized_repo, remote_name, remote_branch)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Excluir branch", str(exc))
            return
        performed_actions.append(f"remota `{remote_name}/{remote_branch}`")

    if _is_current_repo(window, normalized_repo):
        refresh_repo_state_ui(window)
        window._refresh_commit_files()
        window._refresh_stash_tab_visibility()
        window._reload_history_commits()
        window._refresh_compare_branch_options()
        window._refresh_import_source_repos()
        window._sync_import_target_label()
    refresh_workspace_tree(window)
    window._persist_state()
    window._set_status(f"Branch excluída: {', '.join(performed_actions)}")


def _show_branch_context_menu(
    window: object,
    global_pos: QPoint,
    repo_path: str,
    branch_name: str,
    parent_widget: QWidget | None = None,
) -> None:
    if _is_context_menu_guard_active(window):
        return
    normalized_repo = normalize_repo_path(repo_path)
    normalized_branch = str(branch_name).strip()
    if not normalized_repo or not normalized_branch:
        return
    if not os.path.isdir(normalized_repo) or not is_git_repo(normalized_repo):
        return

    capabilities = _branch_target_capabilities(normalized_repo, normalized_branch)
    local_exists = bool(capabilities.get("local_exists", False))
    remote_name = str(capabilities.get("remote_name", "")).strip()
    remote_branch = str(capabilities.get("remote_branch", "")).strip()
    remote_exists = bool(remote_name and remote_branch)

    try:
        current_branch = core_get_current_branch(normalized_repo).strip()
    except RuntimeError:
        current_branch = ""

    can_checkout = normalized_branch != current_branch
    can_delete_local = local_exists and normalized_branch != current_branch
    can_delete_remote = remote_exists
    branch_scope = "Remota" if normalized_branch.startswith(f"{remote_name}/") and remote_exists else "Local"

    menu = QMenu(parent_widget if isinstance(parent_widget, QWidget) else window)
    title_action = menu.addAction(f"Branch: {normalized_branch}")
    title_action.setEnabled(False)
    scope_action = menu.addAction(f"Tipo: {branch_scope}")
    scope_action.setEnabled(False)
    if current_branch and normalized_branch == current_branch:
        current_action = menu.addAction("Branch atual")
        current_action.setEnabled(False)
    menu.addSeparator()
    action_checkout = menu.addAction("Fazer checkout")
    action_checkout.setEnabled(can_checkout)
    action_copy_name = menu.addAction("Copiar nome da branch")
    menu.addSeparator()
    action_delete_branch = menu.addAction("Excluir branch...")
    action_delete_branch.setEnabled(can_delete_local or can_delete_remote)

    selected_action = menu.exec(global_pos)
    if selected_action is None:
        return
    if selected_action == action_checkout:
        _checkout_branch_in_repo(window, normalized_repo, normalized_branch)
        return
    if selected_action == action_copy_name:
        window._copy_to_clipboard(normalized_branch, status="Nome da branch copiado.")
        return
    if selected_action == action_delete_branch:
        _delete_branch_with_confirmation(window, normalized_repo, normalized_branch)


def _on_workspace_card_branch_dropdown_context_menu(
    window: object,
    repo_path: str,
    branch_combo: NoScrollComboBox,
    dropdown: object,
    pos: QPoint,
) -> None:
    if not hasattr(dropdown, "indexAt") or not hasattr(dropdown, "viewport"):
        return
    index = dropdown.indexAt(pos)
    branch_name = ""
    if index.isValid():
        value = index.data(Qt.ItemDataRole.UserRole)
        branch_name = str(value).strip() if value is not None else ""
    if not branch_name:
        selected = branch_combo.currentData()
        branch_name = str(selected).strip() if selected is not None else ""
    if not branch_name:
        return
    branch_combo.hidePopup()
    _show_branch_context_menu(
        window,
        dropdown.viewport().mapToGlobal(pos),
        repo_path,
        branch_name,
        parent_widget=dropdown.viewport(),
    )


def _build_workspace_repo_card(window: object, repo_path: str) -> QWidget:
    branch, ahead, behind, status = build_repo_snapshot(window, repo_path)

    card = WorkspaceCardFrame(window.workspace_cards_container)
    card.setObjectName("WorkspaceCard")
    card.setProperty("selected", _is_current_repo(window, repo_path))
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    card.setMinimumHeight(164)

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(10, 10, 10, 10)
    card_layout.setSpacing(6)

    title_label = QLabel(_format_workspace_card_title(window, repo_path), card)
    title_label.setObjectName("WorkspaceCardTitle")
    title_label.setWordWrap(True)
    title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    card_layout.addWidget(title_label)

    path_label = QLabel(format_workspace_relative_path(window, repo_path), card)
    path_label.setObjectName("WorkspaceCardPath")
    path_label.setWordWrap(True)
    path_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    card_layout.addWidget(path_label)

    branch_row = QWidget(card)
    branch_layout = QHBoxLayout(branch_row)
    branch_layout.setContentsMargins(0, 0, 0, 0)
    branch_layout.setSpacing(6)
    branch_layout.addWidget(QLabel("Branch:", branch_row))
    branch_combo = NoScrollComboBox(branch_row)
    branch_combo.setSizeAdjustPolicy(NoScrollComboBox.SizeAdjustPolicy.AdjustToContents)
    branch_combo.setToolTip("Trocar branch deste repositorio")
    default_branch = ""
    tracked_local_branches: set[str] = set()
    try:
        branches = core_list_branches(repo_path)
        default_branch = core_get_default_branch(repo_path).strip()
        tracked_local_branches = core_list_local_branches_with_upstream(repo_path)
    except RuntimeError:
        branches = [branch]
    if branch and branch not in branches:
        branches = [branch, *branches]
    if not branches:
        branches = [branch]
    for branch_name in branches:
        add_branch_combo_item(window, branch_combo, branch_name, default_branch, tracked_local_branches)
    current_index = branch_combo.findData(branch)
    if current_index >= 0:
        branch_combo.setCurrentIndex(current_index)
    sync_branch_combo_tooltip(branch_combo, "Trocar branch deste repositorio")
    branch_combo.currentIndexChanged.connect(
        lambda _idx, combo=branch_combo: sync_branch_combo_tooltip(combo, "Trocar branch deste repositorio")
    )
    branch_combo.activated.connect(
        lambda _idx, path=repo_path, combo=branch_combo: _on_workspace_card_branch_activated(window, path, combo)
    )
    branch_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    branch_combo.customContextMenuRequested.connect(
        lambda pos, path=repo_path, combo=branch_combo: _show_branch_context_menu(
            window,
            combo.mapToGlobal(pos),
            path,
            str(combo.currentData() or "").strip(),
            parent_widget=combo,
        )
    )
    dropdown = branch_combo.view()
    dropdown.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    dropdown.customContextMenuRequested.connect(
        lambda pos, path=repo_path, combo=branch_combo, view=dropdown: _on_workspace_card_branch_dropdown_context_menu(
            window,
            path,
            combo,
            view,
            pos,
        )
    )
    branch_layout.addWidget(branch_combo, stretch=1)
    card_layout.addWidget(branch_row)

    sync_label = QLabel(f"Push {ahead} | Pull {behind}", card)
    sync_label.setObjectName("WorkspaceCardMeta")
    sync_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    card_layout.addWidget(sync_label)

    status_label = QLabel(f"Status: {status}", card)
    status_label.setObjectName("WorkspaceCardMeta")
    status_label.setWordWrap(True)
    status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    card_layout.addWidget(status_label, stretch=1)

    card.clicked.connect(lambda path=repo_path: set_repo(window, path, save=True))
    card.double_clicked.connect(
        lambda path=repo_path: (
            set_repo(window, path, save=True),
            window._open_repo_in_vscode(path),
        )
    )
    card.context_requested.connect(
        lambda global_pos, path=repo_path, widget=card: _show_repo_context_menu(
            window,
            global_pos,
            path,
            parent_widget=widget,
        )
    )

    normalized_repo = normalize_repo_path(repo_path)
    window.workspace_card_widgets[normalized_repo] = card
    window.workspace_card_title_labels[normalized_repo] = title_label
    return card


def _render_workspace_add_card(window: object) -> QWidget:
    add_card = QFrame(window.workspace_cards_container)
    add_card.setObjectName("WorkspaceCardAdd")
    add_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    add_card.setMinimumHeight(164)

    layout = QVBoxLayout(add_card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)

    title = QLabel("+ Adicionar repositorio", add_card)
    title.setObjectName("WorkspaceCardTitle")
    title.setWordWrap(True)
    layout.addWidget(title)

    description = QLabel("Abrir janela de clonagem (URL HTTPS/SSH).", add_card)
    description.setObjectName("WorkspaceCardMeta")
    description.setWordWrap(True)
    layout.addWidget(description, stretch=1)

    add_button = QPushButton("Adicionar", add_card)
    add_button.clicked.connect(window._open_clone_dialog)
    layout.addWidget(add_button)
    return add_card


def refresh_workspace_tree(window: object) -> None:
    if not hasattr(window, "workspace_cards_grid"):
        return
    grid = _clear_workspace_cards(window)
    repos = collect_known_repos(window)
    columns = _workspace_card_columns(window)
    row = 0
    column = 0

    if not repos:
        empty_label = QLabel("Nenhum repositorio encontrado no workspace.", window.workspace_cards_container)
        empty_label.setObjectName("WorkspaceCardMeta")
        grid.addWidget(empty_label, 0, 0, 1, max(columns, 1))
        row = 1
        column = 0
    else:
        favorite_repos = [repo for repo in repos if repo_is_favorite(window, repo)]
        favorite_set = {normalize_repo_path(repo) for repo in favorite_repos}
        non_favorite_repos = [repo for repo in repos if normalize_repo_path(repo) not in favorite_set]

        if favorite_repos:
            if column != 0:
                row += 1
                column = 0
            header_label = QLabel("Favoritos", window.workspace_cards_container)
            header_label.setObjectName("WorkspaceCardMeta")
            grid.addWidget(header_label, row, 0, 1, max(columns, 1))
            row += 1
            for repo in sorted(favorite_repos, key=lambda path: _workspace_repo_sort_key(window, path)):
                card = _build_workspace_repo_card(window, repo)
                grid.addWidget(card, row, column)
                column += 1
                if column >= columns:
                    column = 0
                    row += 1
            if column != 0:
                row += 1
                column = 0

        grouped_repos: dict[str, list[str]] = {}
        for repo in non_favorite_repos:
            group_label = format_workspace_group_label(window, repo)
            grouped_repos.setdefault(group_label, []).append(repo)

        for group_label in sorted(grouped_repos.keys(), key=str.casefold):
            if column != 0:
                row += 1
                column = 0
            header_label = QLabel(f"Pasta: {group_label}", window.workspace_cards_container)
            header_label.setObjectName("WorkspaceCardMeta")
            grid.addWidget(header_label, row, 0, 1, max(columns, 1))
            row += 1
            for repo in sorted(grouped_repos[group_label], key=lambda path: _workspace_repo_sort_key(window, path)):
                card = _build_workspace_repo_card(window, repo)
                grid.addWidget(card, row, column)
                column += 1
                if column >= columns:
                    column = 0
                    row += 1
            if column != 0:
                row += 1
                column = 0

    add_card = _render_workspace_add_card(window)
    grid.addWidget(add_card, row, column)
    for col in range(columns):
        grid.setColumnStretch(col, 1)
    sync_workspace_tree_selection(window)


def sync_workspace_tree_selection(window: object) -> None:
    if not hasattr(window, "workspace_card_widgets"):
        return
    for repo_path, card in window.workspace_card_widgets.items():
        selected = _is_current_repo(window, repo_path)
        card.setProperty("selected", selected)
        card.style().unpolish(card)
        card.style().polish(card)
        title_label = window.workspace_card_title_labels.get(repo_path)
        if title_label is not None:
            title_label.setText(_format_workspace_card_title(window, repo_path))
        if selected and hasattr(window, "workspace_cards_scroll"):
            window.workspace_cards_scroll.ensureWidgetVisible(card, 12, 12)


def on_workspace_selection_changed(window: object) -> None:
    # Compatibilidade com wrappers legados do shell.
    if not hasattr(window, "workspace_tree"):
        return
    selected_items = window.workspace_tree.selectedItems()
    if not selected_items:
        return
    item = selected_items[0]
    path_value = item.data(0, Qt.ItemDataRole.UserRole)
    target_repo = str(path_value).strip() if path_value is not None else ""
    if target_repo:
        set_repo(window, target_repo, save=True)


def on_workspace_item_double_clicked(window: object, item: object, _column: int) -> None:
    # Compatibilidade com wrappers legados do shell.
    if not hasattr(item, "data"):
        return
    path_value = item.data(0, Qt.ItemDataRole.UserRole)
    target_repo = str(path_value).strip() if path_value is not None else ""
    if target_repo:
        set_repo(window, target_repo, save=True)
        window._open_repo_in_vscode(target_repo)


def _show_repo_context_menu(
    window: object,
    global_pos: QPoint,
    repo_path: str,
    parent_widget: QWidget | None = None,
) -> None:
    # Evita abrir menu de branch em cascata logo apos fechar este menu.
    _arm_context_menu_guard(window)
    normalized = normalize_repo_path(repo_path)
    if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
        return
    menu = QMenu(parent_widget if isinstance(parent_widget, QWidget) else window)
    action_open_vscode = menu.addAction("Abrir repositório no VS Code")
    action_open_folder = menu.addAction("Abrir na pasta")
    action_open_terminal = menu.addAction("Abrir no terminal")
    action_copy_path = menu.addAction("Copiar caminho local")
    menu.addSeparator()
    is_favorite = repo_is_favorite(window, normalized)
    favorite_label = "Remover dos favoritos" if is_favorite else "Adicionar aos favoritos"
    action_toggle_favorite = menu.addAction(favorite_label)
    menu.addSeparator()
    github_menu = menu.addMenu("GitHub")
    action_open_repo = github_menu.addAction("Abrir repositório")
    action_open_branch = github_menu.addAction("Abrir branch atual")
    action_open_commits = github_menu.addAction("Abrir commits da branch")
    action_open_issues = github_menu.addAction("Abrir issues")
    action_open_actions = github_menu.addAction("Abrir actions")
    action_open_releases = github_menu.addAction("Abrir releases")
    github_menu.addSeparator()
    action_copy_repo_url = github_menu.addAction("Copiar URL do repositório")
    action_copy_branch_url = github_menu.addAction("Copiar URL da branch")
    menu.addSeparator()
    action_delete_repo = menu.addAction("Excluir repositório local...")

    selected_action = menu.exec(global_pos)
    _arm_context_menu_guard(window)
    if selected_action is None:
        return
    if selected_action == action_open_vscode:
        window._open_repo_in_vscode(normalized)
        return
    if selected_action == action_open_folder:
        window._open_repo_in_explorer(normalized)
        return
    if selected_action == action_open_terminal:
        window._open_repo_in_terminal(normalized)
        return
    if selected_action == action_copy_path:
        window._copy_to_clipboard(normalized, status="Caminho do repositório copiado.")
        return
    if selected_action == action_toggle_favorite:
        _set_repo_favorite(window, normalized, not is_favorite)
        return
    if selected_action == action_open_repo:
        window._open_repo_in_github(normalized)
        return
    if selected_action == action_open_branch:
        window._open_repo_branch_in_github(normalized)
        return
    if selected_action == action_open_commits:
        window._open_repo_branch_commits_in_github(normalized)
        return
    if selected_action == action_open_issues:
        window._open_repo_issues_in_github(normalized)
        return
    if selected_action == action_open_actions:
        window._open_repo_actions_in_github(normalized)
        return
    if selected_action == action_open_releases:
        window._open_repo_releases_in_github(normalized)
        return
    if selected_action == action_copy_repo_url:
        window._copy_repo_github_url(normalized)
        return
    if selected_action == action_copy_branch_url:
        window._copy_repo_branch_github_url(normalized)
        return
    if selected_action == action_delete_repo:
        _delete_local_repo(window, normalized)


def _remove_repo_from_settings(window: object, repo_path: str) -> None:
    normalized = normalize_repo_path(repo_path)
    for key in ("recent_repos", "favorite_repos"):
        current = window.settings_data.get(key, [])
        if not isinstance(current, list):
            window.settings_data[key] = []
            continue
        filtered: list[str] = []
        for raw in current:
            if not isinstance(raw, str):
                continue
            candidate = normalize_repo_path(raw)
            if candidate == normalized:
                continue
            filtered.append(candidate)
        window.settings_data[key] = filtered
    window.scanned_repos = [path for path in window.scanned_repos if normalize_repo_path(path) != normalized]


def _set_repo_favorite(window: object, repo_path: str, favorite: bool) -> None:
    normalized = normalize_repo_path(repo_path)
    current = window.settings_data.get("favorite_repos", [])
    favorites: list[str] = []
    if isinstance(current, list):
        for raw in current:
            if not isinstance(raw, str):
                continue
            candidate = normalize_repo_path(raw)
            if candidate and candidate not in favorites:
                favorites.append(candidate)
    if favorite:
        if normalized not in favorites:
            favorites.append(normalized)
    else:
        favorites = [path for path in favorites if path != normalized]
    window.settings_data["favorite_repos"] = favorites
    load_repo_selector_items(window)
    refresh_workspace_tree(window)
    window._persist_state()
    repo_name = os.path.basename(normalized.rstrip(os.sep)) or normalized
    if favorite:
        window._set_status(f"Repositorio favoritado: {repo_name}")
    else:
        window._set_status(f"Repositorio removido dos favoritos: {repo_name}")


def _delete_local_repo(window: object, repo_path: str) -> None:
    normalized = normalize_repo_path(repo_path)
    base_name = os.path.basename(normalized.rstrip(os.sep)) or normalized
    answer = QMessageBox.question(
        window,
        "Excluir repositório",
        (
            f"Excluir permanentemente a pasta local?\n\n"
            f"{normalized}\n\n"
            "Esta ação não pode ser desfeita."
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    try:
        shutil.rmtree(normalized)
    except OSError as exc:
        QMessageBox.critical(window, "Excluir repositório", f"Falha ao excluir {base_name}:\n{exc}")
        return

    was_current = _is_current_repo(window, normalized)
    _remove_repo_from_settings(window, normalized)
    load_repo_selector_items(window)
    refresh_workspace_tree(window)
    if was_current:
        fallback_repo = ""
        if window.repo_combo.count() > 0:
            value = window.repo_combo.itemData(0)
            fallback_repo = str(value).strip() if value is not None else ""
        set_repo(window, fallback_repo, save=False)
    window._persist_state()
    window._set_status(f"Repositório removido: {base_name}")


def on_repo_combo_context_menu(window: object, pos: QPoint) -> None:
    selected = window.repo_combo.currentData()
    repo_path = str(selected).strip() if selected is not None else ""
    if not repo_path:
        return
    _show_repo_context_menu(window, window.repo_combo.mapToGlobal(pos), repo_path, parent_widget=window.repo_combo)


def on_repo_combo_dropdown_context_menu(window: object, pos: QPoint) -> None:
    dropdown = window.repo_combo.view()
    index = dropdown.indexAt(pos)
    repo_path = ""
    if index.isValid():
        value = index.data(Qt.ItemDataRole.UserRole)
        repo_path = str(value).strip() if value is not None else ""
    if not repo_path:
        selected = window.repo_combo.currentData()
        repo_path = str(selected).strip() if selected is not None else ""
    if not repo_path:
        return
    window.repo_combo.hidePopup()
    _show_repo_context_menu(window, dropdown.viewport().mapToGlobal(pos), repo_path, parent_widget=dropdown.viewport())


def on_branch_combo_context_menu(window: object, pos: QPoint) -> None:
    if not window.repo_path:
        return
    selected = window.branch_combo.currentData()
    branch_name = str(selected).strip() if selected is not None else ""
    if not branch_name:
        return
    _show_branch_context_menu(
        window,
        window.branch_combo.mapToGlobal(pos),
        window.repo_path,
        branch_name,
        parent_widget=window.branch_combo,
    )


def on_branch_combo_dropdown_context_menu(window: object, pos: QPoint) -> None:
    if not window.repo_path:
        return
    dropdown = window.branch_combo.view()
    index = dropdown.indexAt(pos)
    branch_name = ""
    if index.isValid():
        value = index.data(Qt.ItemDataRole.UserRole)
        branch_name = str(value).strip() if value is not None else ""
    if not branch_name:
        selected = window.branch_combo.currentData()
        branch_name = str(selected).strip() if selected is not None else ""
    if not branch_name:
        return
    window.branch_combo.hidePopup()
    _show_branch_context_menu(
        window,
        dropdown.viewport().mapToGlobal(pos),
        window.repo_path,
        branch_name,
        parent_widget=dropdown.viewport(),
    )


def on_workspace_tree_context_menu(window: object, pos: QPoint) -> None:
    if not hasattr(window, "workspace_tree"):
        return
    item = window.workspace_tree.itemAt(pos)
    if item is None:
        return
    value = item.data(0, Qt.ItemDataRole.UserRole)
    repo_path = str(value).strip() if value is not None else ""
    if not repo_path:
        return
    _show_repo_context_menu(
        window,
        window.workspace_tree.viewport().mapToGlobal(pos),
        repo_path,
        parent_widget=window.workspace_tree.viewport(),
    )


def open_clone_dialog(
    window: object,
    *,
    activate_repo: bool = True,
    on_success: Callable[[str], None] | None = None,
) -> None:
    default_root = normalize_repo_path(window.repo_scan_root) if window.repo_scan_root else normalize_repo_path(default_repo_scan_root())

    dialog = QDialog(window)
    dialog.setWindowTitle("Adicionar repositório")
    dialog.setModal(True)
    dialog.resize(760, 480)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    root_row = QWidget(dialog)
    root_layout = QHBoxLayout(root_row)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(6)
    root_layout.addWidget(QLabel("Raiz do workspace:", root_row))
    root_input = QLineEdit(root_row)
    root_input.setText(default_root)
    root_layout.addWidget(root_input, stretch=1)
    root_pick_button = QPushButton("Pasta...", root_row)
    root_layout.addWidget(root_pick_button)
    layout.addWidget(root_row)

    url_row = QWidget(dialog)
    url_layout = QHBoxLayout(url_row)
    url_layout.setContentsMargins(0, 0, 0, 0)
    url_layout.setSpacing(6)
    url_layout.addWidget(QLabel("Clone URL/SSH:", url_row))
    url_input = QLineEdit(url_row)
    url_input.setPlaceholderText("git@github.com:owner/repo.git")
    url_layout.addWidget(url_input, stretch=1)
    layout.addWidget(url_row)

    folder_row = QWidget(dialog)
    folder_layout = QHBoxLayout(folder_row)
    folder_layout.setContentsMargins(0, 0, 0, 0)
    folder_layout.setSpacing(6)
    folder_layout.addWidget(QLabel("Pasta (opcional):", folder_row))
    folder_input = QLineEdit(folder_row)
    folder_input.setPlaceholderText("grupo/repositorio (ou vazio para nome automático)")
    folder_layout.addWidget(folder_input, stretch=1)
    layout.addWidget(folder_row)

    progress_view = QPlainTextEdit(dialog)
    progress_view.setReadOnly(True)
    progress_view.setPlaceholderText("O progresso do clone será exibido aqui.")
    layout.addWidget(progress_view, stretch=1)

    status_label = QLabel("Informe uma URL para clonar.", dialog)
    layout.addWidget(status_label)

    actions_row = QWidget(dialog)
    actions_layout = QHBoxLayout(actions_row)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(6)
    actions_layout.addStretch(1)
    cancel_button = QPushButton("Cancelar", actions_row)
    clone_button = QPushButton("Clonar", actions_row)
    clone_button.setProperty("role", "primary")
    actions_layout.addWidget(cancel_button)
    actions_layout.addWidget(clone_button)
    layout.addWidget(actions_row)

    state = {"cloning": False, "cancelled": False}

    def choose_root() -> None:
        selected = QFileDialog.getExistingDirectory(dialog, "Selecionar raiz do workspace", root_input.text().strip() or default_root)
        if selected:
            root_input.setText(normalize_repo_path(selected))

    def append_progress(text: str) -> None:
        progress_view.appendPlainText(text)
        status_label.setText(text)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def cancel_action() -> None:
        if state["cloning"]:
            state["cancelled"] = True
            status_label.setText("Cancelando clone...")
            cancel_button.setEnabled(False)
            return
        dialog.reject()

    def run_clone() -> None:
        repo_url = url_input.text().strip()
        destination_root = normalize_repo_path(root_input.text().strip())
        folder_name = folder_input.text().strip()
        if not repo_url:
            QMessageBox.warning(dialog, "Clone", "Informe a URL/SSH do repositório.")
            return
        if not destination_root:
            QMessageBox.warning(dialog, "Clone", "Informe a raiz do workspace.")
            return
        state["cloning"] = True
        state["cancelled"] = False
        clone_button.setEnabled(False)
        root_pick_button.setEnabled(False)
        url_input.setEnabled(False)
        folder_input.setEnabled(False)
        root_input.setEnabled(False)
        window.setEnabled(False)
        append_progress(f"Clonando em: {destination_root}")
        cloned_repo = ""
        try:
            cloned_repo = clone_repository(
                repo_url,
                destination_root,
                folder_name,
                on_progress=append_progress,
                is_cancelled=lambda: bool(state["cancelled"]),
            )
        except RuntimeError as exc:
            QMessageBox.critical(dialog, "Clone", str(exc))
            return
        finally:
            state["cloning"] = False
            window.setEnabled(True)
            clone_button.setEnabled(True)
            root_pick_button.setEnabled(True)
            url_input.setEnabled(True)
            folder_input.setEnabled(True)
            root_input.setEnabled(True)
            cancel_button.setEnabled(True)

        if not cloned_repo:
            return
        append_progress(f"Clone concluído: {cloned_repo}")
        window.repo_scan_root = destination_root
        window.workspace_root_edit.setText(destination_root)
        scan_workspace_repos(window)
        if activate_repo:
            set_repo(window, cloned_repo, save=True)
        if callable(on_success):
            on_success(cloned_repo)
        window._persist_state()
        QMessageBox.information(dialog, "Clone", f"Repositório clonado com sucesso:\n{cloned_repo}")
        dialog.accept()

    root_pick_button.clicked.connect(choose_root)
    cancel_button.clicked.connect(cancel_action)
    clone_button.clicked.connect(run_clone)
    dialog.exec()


def set_repo(window: object, repo_path: str, *, save: bool) -> None:
    normalized = normalize_repo_path(repo_path) if repo_path else ""
    if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
        window.repo_path = ""
        refresh_repo_state_ui(window)
        window._refresh_commit_files()
        window._refresh_stash_tab_visibility()
        window._clear_history_view()
        window._refresh_compare_branch_options()
        window._sync_import_target_label()
        sync_workspace_tree_selection(window)
        if save:
            window._persist_state()
        return
    window.repo_path = normalized
    add_recent_repo(window, normalized)
    select_repo_combo_item(window, normalized)
    refresh_repo_state_ui(window)
    window._refresh_commit_files()
    window._refresh_stash_tab_visibility()
    window._reload_history_commits()
    window._refresh_compare_branch_options()
    window._refresh_import_source_repos()
    window._sync_import_target_label()
    sync_workspace_tree_selection(window)
    window._set_status(f"Repositorio ativo: {normalized}")
    if save:
        window._persist_state()


def select_repo_combo_item(window: object, repo_path: str) -> None:
    window._setting_repo_programmatically = True
    try:
        index = window.repo_combo.findData(repo_path)
        if index < 0:
            window.repo_combo.addItem(repo_path, repo_path)
            index = window.repo_combo.findData(repo_path)
        if index >= 0:
            window.repo_combo.setCurrentIndex(index)
    finally:
        window._setting_repo_programmatically = False


def refresh_repo_state_ui(window: object) -> None:
    has_repo = bool(window.repo_path)
    window.fetch_button.setEnabled(has_repo)
    window.new_branch_button.setEnabled(has_repo)
    window.branch_combo.setEnabled(has_repo)
    if hasattr(window, "publish_button"):
        window.publish_button.setEnabled(False)
        window.publish_button.setVisible(False)
    if hasattr(window, "commit_stash_button"):
        window.commit_stash_button.setEnabled(has_repo)
    if hasattr(window, "commit_undo_button"):
        window.commit_undo_button.setEnabled(has_repo)
    if not has_repo:
        window.behind_button.setEnabled(False)
        window.ahead_button.setEnabled(False)
        window.behind_button.setVisible(False)
        window.ahead_button.setVisible(False)
        window.behind_button.setText("Pull: 0")
        window.ahead_button.setText("Push: 0")
        window.fetch_button.setText("Fetch")
        window.branch_combo.clear()
        sync_branch_combo_tooltip(window.branch_combo, "Trocar branch ativa")
        window._sync_import_target_label()
        return

    try:
        branches = core_list_branches(window.repo_path)
        current = core_get_current_branch(window.repo_path).strip()
        default_branch = core_get_default_branch(window.repo_path).strip()
        tracked_local_branches = core_list_local_branches_with_upstream(window.repo_path)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Erro", str(exc))
        window.repo_path = ""
        refresh_repo_state_ui(window)
        return
    if current and current not in branches:
        branches = [current, *branches]

    window._setting_branch_programmatically = True
    try:
        window.branch_combo.clear()
        for branch in branches:
            add_branch_combo_item(window, window.branch_combo, branch, default_branch, tracked_local_branches)
        index = window.branch_combo.findData(current)
        if index >= 0:
            window.branch_combo.setCurrentIndex(index)
    finally:
        window._setting_branch_programmatically = False
    sync_branch_combo_tooltip(window.branch_combo, "Trocar branch ativa")

    upstream = core_get_upstream(window.repo_path)
    if not upstream:
        window.behind_button.setEnabled(False)
        window.ahead_button.setEnabled(False)
        window.behind_button.setVisible(False)
        window.ahead_button.setVisible(False)
        window.behind_button.setText("Pull: 0")
        window.ahead_button.setText("Push: 0")
        window.behind_button.setToolTip("Pull indisponivel: branch sem upstream configurado.")
        window.ahead_button.setToolTip("Push indisponivel: branch sem upstream configurado.")
        window.fetch_button.setText("Fetch")
        can_publish = bool(current and current != "HEAD")
        if hasattr(window, "publish_button"):
            window.publish_button.setVisible(can_publish)
            window.publish_button.setEnabled(can_publish)
            if can_publish:
                window.publish_button.setToolTip(
                    f"Publicar branch local `{current}` no remoto origin e configurar upstream."
                )
        window._sync_import_target_label()
        return

    behind, ahead = core_get_ahead_behind(window.repo_path, upstream)
    window.behind_button.setText(f"Pull: {behind}")
    window.ahead_button.setText(f"Push: {ahead}")
    window.behind_button.setEnabled(behind > 0)
    window.ahead_button.setEnabled(ahead > 0)
    window.behind_button.setVisible(behind > 0)
    window.ahead_button.setVisible(ahead > 0)
    if behind > 0:
        window.behind_button.setToolTip(f"Pull ({behind} commit(s) remotos).")
    else:
        window.behind_button.setToolTip("Sem commits remotos pendentes para pull.")
    if ahead > 0:
        window.ahead_button.setToolTip(f"Push ({ahead} commit(s) locais).")
    else:
        window.ahead_button.setToolTip("Sem commits locais pendentes para push.")
    window.fetch_button.setText(f"Fetch ({behind})" if behind > 0 else "Fetch")
    window._sync_import_target_label()


def add_recent_repo(window: object, repo_path: str) -> None:
    normalized = normalize_repo_path(repo_path)
    current_items = window.settings_data.get("recent_repos", [])
    items: list[str] = []
    if isinstance(current_items, list):
        for raw in current_items:
            if isinstance(raw, str) and raw.strip():
                entry = normalize_repo_path(raw)
                if entry not in items and os.path.isdir(entry) and is_git_repo(entry):
                    items.append(entry)
    if normalized in items:
        items.remove(normalized)
    items.insert(0, normalized)
    window.settings_data["recent_repos"] = items[:20]
    load_repo_selector_items(window)
    refresh_workspace_tree(window)
