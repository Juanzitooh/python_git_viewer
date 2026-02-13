from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.models import DiffData, DiffHunk, DiffLineInfo
from ...core.commit_ops import (
    apply_stash as core_apply_stash,
    apply_patch_to_index as core_apply_patch_to_index,
    apply_patch_to_worktree as core_apply_patch_to_worktree,
    create_stash as core_create_stash,
    create_commit as core_create_commit,
    drop_stash as core_drop_stash,
    get_file_patch as core_get_file_patch,
    get_last_commit_subject as core_get_last_commit_subject,
    get_stash_patch as core_get_stash_patch,
    has_staged_changes as core_has_staged_changes,
    list_stash_files_from_patch as core_list_stash_files_from_patch,
    list_stashes as core_list_stashes,
    list_status_entries as core_list_status_entries,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
    unstage_paths as core_unstage_paths,
    undo_last_commit as core_undo_last_commit,
)
from ...core.diff_utils import build_patch_for_hunk, build_patch_for_line, parse_diff_data
from ..diff_columns import HUNK_INDEX_ROLE, LINE_INFO_ROLE, ROW_KIND_ROLE, SCOPE_ROLE, render_diff_into_columns
from ..diff_render import install_diff_copy_shortcut, install_diff_highlighter, render_diff_into_widget
from ..tabs.commit_tab import CommitDiffView
from ..theme import get_commit_status_color, get_diff_kind_color

ROLE_PATH = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_FOLDER = Qt.ItemDataRole.UserRole + 2
ROLE_DIALOG_KIND = Qt.ItemDataRole.UserRole + 101
ROLE_DIALOG_LINE_NO = Qt.ItemDataRole.UserRole + 102
ROLE_DIALOG_HUNK = Qt.ItemDataRole.UserRole + 103
ROLE_DIALOG_LINE_INFO = Qt.ItemDataRole.UserRole + 104
ROLE_DIALOG_OLD_RAW = Qt.ItemDataRole.UserRole + 105
ROLE_DIALOG_NEW_RAW = Qt.ItemDataRole.UserRole + 106
ROLE_DIALOG_OLD_LINE_INFO = Qt.ItemDataRole.UserRole + 107
ROLE_DIALOG_NEW_LINE_INFO = Qt.ItemDataRole.UserRole + 108

KIND_ALL = "all"
KIND_FOLDER = "folder"
KIND_FILE = "file"
STASH_MESSAGE_DEFAULT = "git_viewer"


def _entry_has_staged(entry: dict[str, str | bool]) -> bool:
    return bool(entry.get("staged", False))


def _entry_has_unstaged(entry: dict[str, str | bool]) -> bool:
    return bool(entry.get("unstaged", False))


def _entry_is_fully_staged(entry: dict[str, str | bool]) -> bool:
    return _entry_has_staged(entry) and not _entry_has_unstaged(entry)


def _sync_commit_pr_button_state(window: object, file_count: int) -> None:
    if not hasattr(window, "commit_open_pr_button"):
        return
    can_open_pr = bool(window.repo_path and file_count == 0)
    window.commit_open_pr_button.setEnabled(can_open_pr)


def _entry_status_label(entry: dict[str, str | bool]) -> str:
    path = str(entry.get("path", "")).strip()
    if " -> " in path:
        display_path = path
    else:
        display_path = os.path.basename(path) or path
    return display_path


def _entry_status_color(entry: dict[str, str | bool]) -> QColor | None:
    status = str(entry.get("status", "")).strip()
    staged_status = status[0] if len(status) >= 1 else " "
    unstaged_status = status[1] if len(status) >= 2 else " "
    status_flags = {staged_status, unstaged_status}
    app = QApplication.instance()
    if app is not None:
        base = app.palette().color(QPalette.ColorRole.Base)
        is_light = int(base.lightness()) >= 128
        theme_overrides = app.property("gv_theme_overrides")
    else:
        is_light = True
        theme_overrides = None
    if "R" in status_flags:
        color_value = get_commit_status_color(
            "renamed",
            is_light=is_light,
            theme_overrides=theme_overrides,
        )
        return QColor(color_value) if color_value else None
    if "D" in status_flags:
        color_value = get_commit_status_color(
            "deleted",
            is_light=is_light,
            theme_overrides=theme_overrides,
        )
        return QColor(color_value) if color_value else None
    if "A" in status_flags or "?" in status_flags:
        color_value = get_commit_status_color(
            "added",
            is_light=is_light,
            theme_overrides=theme_overrides,
        )
        return QColor(color_value) if color_value else None
    if "M" in status_flags:
        color_value = get_commit_status_color(
            "modified",
            is_light=is_light,
            theme_overrides=theme_overrides,
        )
        return QColor(color_value) if color_value else None
    return None


def _commit_item_kind(item: QListWidgetItem | None) -> str:
    if item is None:
        return ""
    value = item.data(ROLE_KIND)
    return str(value).strip() if value is not None else ""


def _is_commit_file_item(item: QListWidgetItem | None) -> bool:
    return _commit_item_kind(item) == KIND_FILE


def _folder_display_label(folder: str) -> str:
    return f"{folder}/" if folder else "(root)"


def _iter_commit_file_items(window: object) -> list[QListWidgetItem]:
    return [item for item in iter_commit_items(window) if _is_commit_file_item(item)]


def _set_commit_header_style(item: QListWidgetItem) -> None:
    font = item.font()
    font.setBold(True)
    item.setFont(font)


def _set_commit_item_check_state(window: object, item: QListWidgetItem, state: Qt.CheckState) -> None:
    if item.checkState() == state:
        return
    previous = bool(getattr(window, "commit_syncing_checks", False))
    window.commit_syncing_checks = True
    try:
        item.setCheckState(state)
    finally:
        window.commit_syncing_checks = previous


def _set_commit_paths_checked(window: object, paths: list[str], checked: bool) -> None:
    state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    previous = bool(getattr(window, "commit_syncing_checks", False))
    window.commit_syncing_checks = True
    try:
        for path in paths:
            item = file_item_by_path.get(path)
            if item is not None:
                item.setCheckState(state)
    finally:
        window.commit_syncing_checks = previous


def _checked_state_for_paths(window: object, paths: list[str]) -> Qt.CheckState:
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    if not paths:
        return Qt.CheckState.Unchecked
    checked_count = 0
    partial_count = 0
    for path in paths:
        item = file_item_by_path.get(path)
        if item is None:
            continue
        state = item.checkState()
        if state == Qt.CheckState.Checked:
            checked_count += 1
        elif state == Qt.CheckState.PartiallyChecked:
            partial_count += 1
    if partial_count > 0:
        return Qt.CheckState.PartiallyChecked
    if checked_count <= 0:
        return Qt.CheckState.Unchecked
    if checked_count >= len(paths):
        return Qt.CheckState.Checked
    return Qt.CheckState.PartiallyChecked


def _apply_stage_state_from_selection(window: object, paths: list[str]) -> bool:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        return False
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    status_entries_by_path = getattr(window, "commit_status_entries_by_path", {})
    stage_paths: list[str] = []
    unstage_paths: list[str] = []
    for path in paths:
        normalized_path = str(path).strip()
        if not normalized_path:
            continue
        item = file_item_by_path.get(normalized_path)
        if item is None:
            continue
        state = item.checkState()
        if state == Qt.CheckState.PartiallyChecked:
            continue
        selected = state == Qt.CheckState.Checked
        entry = status_entries_by_path.get(normalized_path, {})
        if selected:
            if not _entry_is_fully_staged(entry):
                stage_paths.append(normalized_path)
            continue
        if _entry_has_staged(entry):
            unstage_paths.append(normalized_path)
    if not stage_paths and not unstage_paths:
        return False
    try:
        if unstage_paths:
            core_unstage_paths(repo_path, unstage_paths)
        if stage_paths:
            core_stage_paths(repo_path, stage_paths)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return False
    return True


def _sync_commit_group_check_states(window: object) -> None:
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    folder_paths = getattr(window, "commit_folder_paths", {})
    folder_item_by_name = getattr(window, "commit_folder_item_by_name", {})
    all_paths = list(file_item_by_path.keys())
    if getattr(window, "commit_all_item", None) is not None:
        all_state = _checked_state_for_paths(window, all_paths)
        _set_commit_item_check_state(window, window.commit_all_item, all_state)
    for folder, paths in folder_paths.items():
        item = folder_item_by_name.get(folder)
        if item is None:
            continue
        folder_state = _checked_state_for_paths(window, paths)
        _set_commit_item_check_state(window, item, folder_state)


def _current_commit_file_path(window: object) -> str:
    selected_items = window.commit_files_list.selectedItems()
    for selected_item in selected_items:
        if not _is_commit_file_item(selected_item):
            continue
        value = selected_item.data(ROLE_PATH)
        return str(value).strip() if value is not None else ""
    return ""


def _sync_commit_stage_buttons(window: object) -> None:
    if not hasattr(window, "commit_stage_selected_button") or not hasattr(window, "commit_unstage_selected_button"):
        return
    path = _current_commit_file_path(window)
    if not path:
        window.commit_stage_selected_button.setEnabled(False)
        window.commit_unstage_selected_button.setEnabled(False)
        if hasattr(window, "commit_stage_hunk_button"):
            window.commit_stage_hunk_button.setEnabled(False)
        if hasattr(window, "commit_unstage_hunk_button"):
            window.commit_unstage_hunk_button.setEnabled(False)
        if hasattr(window, "commit_stage_line_button"):
            window.commit_stage_line_button.setEnabled(False)
        if hasattr(window, "commit_unstage_line_button"):
            window.commit_unstage_line_button.setEnabled(False)
        return
    entry = window.commit_status_entries_by_path.get(path, {})
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    window.commit_stage_selected_button.setEnabled(has_unstaged)
    window.commit_unstage_selected_button.setEnabled(has_staged)
    selected_hunk = _selected_commit_hunk_index(window)
    has_hunk = selected_hunk is not None
    scope = str(getattr(window, "commit_diff_scope", "")).strip()
    if hasattr(window, "commit_stage_hunk_button"):
        window.commit_stage_hunk_button.setEnabled(has_hunk and scope == "unstaged")
    if hasattr(window, "commit_unstage_hunk_button"):
        window.commit_unstage_hunk_button.setEnabled(has_hunk and scope == "staged")
    line_info = _selected_commit_line_info(window)
    is_changed_line = bool(line_info and line_info.line_type in ("added", "removed"))
    if hasattr(window, "commit_stage_line_button"):
        window.commit_stage_line_button.setEnabled(is_changed_line and scope == "unstaged")
    if hasattr(window, "commit_unstage_line_button"):
        window.commit_unstage_line_button.setEnabled(is_changed_line and scope == "staged")


def _commit_diff_line_marker_for_scope(scope: str, line_info: DiffLineInfo) -> str:
    if line_info.line_type not in ("added", "removed"):
        return ""
    if scope == "staged":
        return "[x]"
    if scope in {"unstaged", "untracked"}:
        return "[ ]"
    return "[~]"


def _commit_diff_hunk_marker_for_scope(scope: str, _hunk_index: int, hunk: DiffHunk) -> str:
    has_changes = any(line.line_type in ("added", "removed") for line in hunk.lines)
    if not has_changes:
        return ""
    if scope == "staged":
        return "[x]"
    if scope in {"unstaged", "untracked"}:
        return "[ ]"
    return "[~]"


def _selected_commit_scope(window: object) -> str:
    if not hasattr(window, "commit_diff_view"):
        return ""
    current_item = window.commit_diff_view.currentItem()
    if current_item is None:
        return ""
    value = current_item.data(0, SCOPE_ROLE)
    return str(value).strip() if value is not None else ""


def _get_commit_diff_data_for_scope(window: object, scope: str) -> DiffData | None:
    by_scope = getattr(window, "commit_diff_data_by_scope", None)
    if isinstance(by_scope, dict):
        candidate = by_scope.get(scope)
        if isinstance(candidate, DiffData):
            return candidate
    fallback = getattr(window, "commit_diff_data", None)
    return fallback if isinstance(fallback, DiffData) else None


def _sync_active_commit_diff_data(window: object) -> None:
    scope = _selected_commit_scope(window)
    if not scope:
        scope = str(getattr(window, "commit_diff_scope", "")).strip()
    data = _get_commit_diff_data_for_scope(window, scope)
    window.commit_diff_data = data


def _restore_commit_selection(window: object, preferred_path: str) -> None:
    target = preferred_path.strip()
    first_file_index: int | None = None
    if not target:
        for index in range(window.commit_files_list.count()):
            item = window.commit_files_list.item(index)
            if not _is_commit_file_item(item):
                continue
            first_file_index = index
            break
        if first_file_index is not None:
            window.commit_files_list.setCurrentRow(first_file_index)
        return
    for index in range(window.commit_files_list.count()):
        item = window.commit_files_list.item(index)
        if not _is_commit_file_item(item):
            continue
        if first_file_index is None:
            first_file_index = index
        value = item.data(ROLE_PATH)
        candidate = str(value).strip() if value is not None else ""
        if candidate != target:
            continue
        window.commit_files_list.setCurrentRow(index)
        return
    if first_file_index is not None:
        window.commit_files_list.setCurrentRow(first_file_index)


def refresh_commit_files(window: object) -> None:
    had_items = window.commit_files_list.count() > 0
    previous_scroll_value = window.commit_files_list.verticalScrollBar().value()
    preferred_path = str(getattr(window, "commit_selected_path", "")).strip()
    if not hasattr(window, "commit_diff_scope_by_path"):
        window.commit_diff_scope_by_path = {}
    if not hasattr(window, "commit_last_diff_path"):
        window.commit_last_diff_path = ""

    window.commit_files_list.blockSignals(True)
    window.commit_files_list.clear()
    window.commit_status_entries_by_path = {}
    window.commit_file_item_by_path = {}
    window.commit_folder_paths = {}
    window.commit_folder_item_by_name = {}
    window.commit_all_item = None
    window.commit_syncing_checks = False
    window.commit_diff_scope = ""
    window.commit_diff_data_by_scope = {}
    previous_repo = str(getattr(window, "commit_auto_stage_repo", "")).strip()
    current_repo = str(getattr(window, "repo_path", "")).strip()
    repo_switched = bool(current_repo and current_repo != previous_repo)
    if repo_switched:
        window.commit_auto_stage_disabled = False
        window.commit_diff_scope_by_path = {}
        window.commit_last_diff_path = ""
    window.commit_auto_stage_repo = current_repo
    if not window.repo_path:
        window.commit_files_list.blockSignals(False)
        window.commit_selected_path = ""
        window.commit_diff_scope_by_path = {}
        window.commit_last_diff_path = ""
        if hasattr(window, "commit_diff_view"):
            render_diff_into_columns(window.commit_diff_view, "", show_header_lines=False)
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        _sync_commit_pr_button_state(window, 0)
        _sync_commit_stage_buttons(window)
        window.commit_auto_stage_disabled = False
        update_commit_selection_label(window)
        return
    try:
        status_entries = core_list_status_entries(window.repo_path)
    except RuntimeError as exc:
        window.commit_files_list.blockSignals(False)
        window.commit_selected_path = ""
        if hasattr(window, "commit_diff_view"):
            render_diff_into_columns(window.commit_diff_view, "", show_header_lines=False)
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        _sync_commit_pr_button_state(window, 0)
        _sync_commit_stage_buttons(window)
        QMessageBox.critical(window, "Commit", str(exc))
        update_commit_selection_label(window)
        return
    grouped_entries: dict[str, list[dict[str, str | bool]]] = {}
    for entry in status_entries:
        path_for_git = str(entry.get("path_for_git", "")).strip()
        if not path_for_git:
            continue
        window.commit_status_entries_by_path[path_for_git] = entry
        folder = os.path.dirname(path_for_git) if path_for_git else ""
        grouped_entries.setdefault(folder, []).append(entry)

    should_auto_stage = (
        bool(window.commit_status_entries_by_path)
        and not bool(getattr(window, "commit_auto_stage_disabled", False))
        and (repo_switched or not had_items)
        and any(not _entry_is_fully_staged(entry) for entry in window.commit_status_entries_by_path.values())
    )
    if should_auto_stage:
        try:
            core_stage_paths(window.repo_path, list(window.commit_status_entries_by_path.keys()))
        except RuntimeError as exc:
            window.commit_files_list.blockSignals(False)
            QMessageBox.critical(window, "Commit", str(exc))
            return
        window.commit_files_list.blockSignals(False)
        window._set_status("Arquivos modificados foram stageados automaticamente.")
        refresh_commit_files(window)
        return

    if grouped_entries:
        all_item = QListWidgetItem("(todos)", window.commit_files_list)
        _set_commit_header_style(all_item)
        all_item.setFlags(all_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
        all_item.setData(ROLE_KIND, KIND_ALL)
        all_item.setData(ROLE_PATH, "")
        all_item.setData(ROLE_FOLDER, "")
        all_item.setCheckState(Qt.CheckState.Unchecked)
        window.commit_all_item = all_item

        for folder in sorted(grouped_entries.keys()):
            folder_item = QListWidgetItem(_folder_display_label(folder), window.commit_files_list)
            _set_commit_header_style(folder_item)
            folder_item.setFlags(folder_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            folder_item.setData(ROLE_KIND, KIND_FOLDER)
            folder_item.setData(ROLE_PATH, "")
            folder_item.setData(ROLE_FOLDER, folder)
            folder_item.setCheckState(Qt.CheckState.Unchecked)
            window.commit_folder_item_by_name[folder] = folder_item
            window.commit_folder_paths[folder] = []

            folder_entries = sorted(grouped_entries[folder], key=lambda entry: str(entry.get("path_for_git", "")))
            for entry in folder_entries:
                path_for_git = str(entry.get("path_for_git", "")).strip()
                if not path_for_git:
                    continue
                item = QListWidgetItem(_entry_status_label(entry), window.commit_files_list)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
                item.setData(ROLE_KIND, KIND_FILE)
                item.setData(ROLE_PATH, path_for_git)
                item.setData(ROLE_FOLDER, folder)
                color = _entry_status_color(entry)
                if color is not None:
                    item.setForeground(color)
                if _entry_has_staged(entry) and _entry_has_unstaged(entry):
                    item.setCheckState(Qt.CheckState.PartiallyChecked)
                elif _entry_has_staged(entry):
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
                window.commit_file_item_by_path[path_for_git] = item
                window.commit_folder_paths[folder].append(path_for_git)

    _sync_commit_group_check_states(window)
    window.commit_files_list.blockSignals(False)
    _sync_commit_pr_button_state(window, len(window.commit_file_item_by_path))
    _restore_commit_selection(window, preferred_path)
    scroll_bar = window.commit_files_list.verticalScrollBar()
    scroll_bar.setValue(min(previous_scroll_value, scroll_bar.maximum()))
    refresh_commit_diff(window)
    _sync_commit_stage_buttons(window)
    update_commit_selection_label(window)


def iter_commit_items(window: object) -> list[QListWidgetItem]:
    items: list[QListWidgetItem] = []
    for index in range(window.commit_files_list.count()):
        item = window.commit_files_list.item(index)
        if item is not None:
            items.append(item)
    return items


def update_commit_selection_label(window: object) -> None:
    items = _iter_commit_file_items(window)
    selected = 0
    for item in items:
        if item.checkState() == Qt.CheckState.Checked:
            selected += 1
    window.commit_selection_label.setText(f"Selecionados: {selected}/{len(items)}")


def on_commit_file_item_changed(window: object, item: QListWidgetItem) -> None:
    if bool(getattr(window, "commit_syncing_checks", False)):
        return
    window.commit_auto_stage_disabled = True
    kind = _commit_item_kind(item)
    changed = False
    affected_paths: list[str] = []
    selected_path = _current_commit_file_path(window)
    if kind == KIND_ALL:
        affected_paths = list(window.commit_file_item_by_path.keys())
        should_check = item.checkState() == Qt.CheckState.Checked
        _set_commit_paths_checked(window, affected_paths, should_check)
    elif kind == KIND_FOLDER:
        folder_value = item.data(ROLE_FOLDER)
        folder = str(folder_value).strip() if folder_value is not None else ""
        affected_paths = list(window.commit_folder_paths.get(folder, []))
        should_check = item.checkState() == Qt.CheckState.Checked
        _set_commit_paths_checked(window, affected_paths, should_check)
    elif kind == KIND_FILE:
        path_value = item.data(ROLE_PATH)
        file_path = str(path_value).strip() if path_value is not None else ""
        if file_path:
            affected_paths = [file_path]
    _sync_commit_group_check_states(window)
    if affected_paths:
        changed = _apply_stage_state_from_selection(window, affected_paths)
    update_commit_selection_label(window)
    if not changed:
        return
    if selected_path:
        window.commit_selected_path = selected_path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def on_commit_file_selected(window: object) -> None:
    window.commit_selected_path = _current_commit_file_path(window)
    refresh_commit_diff(window)
    _sync_commit_stage_buttons(window)


def _load_commit_patch_for_path(
    window: object,
    path: str,
    *,
    word_diff: bool,
    preferred_scope: str = "",
    allow_scope_fallback: bool = True,
) -> tuple[str, str]:
    entry = window.commit_status_entries_by_path.get(path)
    if entry is None:
        return "", ""
    status_code = str(entry.get("status", "")).strip()
    untracked = status_code == "??"
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    available_scopes: list[str] = []
    if untracked or has_unstaged:
        available_scopes.append("unstaged")
    if has_staged:
        available_scopes.append("staged")
    if not available_scopes:
        return "", ""

    normalized_scope = preferred_scope.strip()
    candidate_scopes: list[str] = []
    if normalized_scope in available_scopes:
        candidate_scopes.append(normalized_scope)
    if allow_scope_fallback:
        for scope in available_scopes:
            if scope in candidate_scopes:
                continue
            candidate_scopes.append(scope)
    if not candidate_scopes:
        return "", ""

    for scope in candidate_scopes:
        patch = core_get_file_patch(
            window.repo_path,
            path,
            word_diff=word_diff,
            cached=(scope == "staged"),
            untracked=(scope == "unstaged" and untracked),
        )
        if patch:
            return patch, scope
    return "", (candidate_scopes[0] if candidate_scopes else "")


def _load_commit_patches_by_scope(
    window: object,
    path: str,
    *,
    word_diff: bool,
    preferred_scope: str = "",
) -> list[tuple[str, str]]:
    entry = window.commit_status_entries_by_path.get(path)
    if entry is None:
        return []
    status_code = str(entry.get("status", "")).strip()
    untracked = status_code == "??"
    has_unstaged = bool(entry.get("unstaged", False)) or untracked
    has_staged = bool(entry.get("staged", False))
    scope_order: list[str] = []
    normalized_scope = preferred_scope.strip()
    if normalized_scope in {"staged", "unstaged"}:
        scope_order.append(normalized_scope)
    for candidate in ("staged", "unstaged"):
        if candidate in scope_order:
            continue
        scope_order.append(candidate)
    scopes_available: list[str] = []
    if has_staged:
        scopes_available.append("staged")
    if has_unstaged:
        scopes_available.append("unstaged")

    patches: list[tuple[str, str]] = []
    for scope in scope_order:
        if scope not in scopes_available:
            continue
        patch = core_get_file_patch(
            window.repo_path,
            path,
            word_diff=word_diff,
            cached=(scope == "staged"),
            untracked=(scope == "unstaged" and untracked),
        )
        if not patch.strip():
            continue
        patches.append((scope, patch))
    return patches


def _same_diff_line_info(left: DiffLineInfo, right: DiffLineInfo) -> bool:
    return (
        left.line_type == right.line_type
        and int(left.old_line) == int(right.old_line)
        and int(left.new_line) == int(right.new_line)
        and left.content == right.content
    )


def _find_commit_diff_target_row(
    window: object,
    *,
    previous_line_info: DiffLineInfo | None,
    previous_hunk_index: int | None,
    previous_scope: str,
    previous_row_index: int,
    first_selectable_index: int,
) -> int:
    if previous_line_info is not None:
        for row_index in range(window.commit_diff_view.topLevelItemCount()):
            item = window.commit_diff_view.topLevelItem(row_index)
            if item is None:
                continue
            scope_value = item.data(0, SCOPE_ROLE)
            scope = str(scope_value).strip() if scope_value is not None else ""
            if previous_scope and scope and scope != previous_scope:
                continue
            info_value = item.data(0, LINE_INFO_ROLE)
            if not isinstance(info_value, DiffLineInfo):
                continue
            if _same_diff_line_info(previous_line_info, info_value):
                return row_index
    if previous_hunk_index is not None:
        for row_index in range(window.commit_diff_view.topLevelItemCount()):
            item = window.commit_diff_view.topLevelItem(row_index)
            if item is None:
                continue
            scope_value = item.data(0, SCOPE_ROLE)
            scope = str(scope_value).strip() if scope_value is not None else ""
            if previous_scope and scope and scope != previous_scope:
                continue
            hunk_value = item.data(0, HUNK_INDEX_ROLE)
            kind_value = item.data(0, ROW_KIND_ROLE)
            kind = str(kind_value).strip() if kind_value is not None else ""
            if isinstance(hunk_value, int) and hunk_value == previous_hunk_index and kind == "hunk":
                return row_index
    if 0 <= previous_row_index < window.commit_diff_view.topLevelItemCount():
        return previous_row_index
    return first_selectable_index


def refresh_commit_diff(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    if not hasattr(window, "commit_diff_scope_by_path"):
        window.commit_diff_scope_by_path = {}
    if not hasattr(window, "commit_last_diff_path"):
        window.commit_last_diff_path = ""
    if not hasattr(window, "commit_diff_data_by_scope"):
        window.commit_diff_data_by_scope = {}
    if not window.repo_path:
        render_diff_into_columns(window.commit_diff_view, "", show_header_lines=False)
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        window.commit_last_diff_path = ""
        return
    path = _current_commit_file_path(window)
    if not path:
        render_diff_into_columns(window.commit_diff_view, "(selecione um arquivo)", show_header_lines=False)
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        window.commit_last_diff_path = ""
        _sync_commit_stage_buttons(window)
        return
    if path not in window.commit_status_entries_by_path:
        render_diff_into_columns(window.commit_diff_view, "(arquivo nao encontrado no status atual)", show_header_lines=False)
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        window.commit_last_diff_path = path
        _sync_commit_stage_buttons(window)
        return
    previous_scope_by_path = str(window.commit_diff_scope_by_path.get(path, "")).strip()
    previous_scope = previous_scope_by_path or str(getattr(window, "commit_diff_scope", "")).strip()

    current_item = window.commit_diff_view.currentItem()
    previous_row_index = -1
    previous_hunk_index: int | None = None
    previous_line_info: DiffLineInfo | None = None
    previous_row_scope = ""
    if current_item is not None:
        previous_row_index = window.commit_diff_view.indexOfTopLevelItem(current_item)
        hunk_value = current_item.data(0, HUNK_INDEX_ROLE)
        if isinstance(hunk_value, int):
            previous_hunk_index = hunk_value
        info_value = current_item.data(0, LINE_INFO_ROLE)
        if isinstance(info_value, DiffLineInfo):
            previous_line_info = info_value
        scope_value = current_item.data(0, SCOPE_ROLE)
        previous_row_scope = str(scope_value).strip() if scope_value is not None else ""
    previous_scroll_value = window.commit_diff_view.verticalScrollBar().value()

    word_diff = bool(getattr(window, "commit_word_diff_check", None) and window.commit_word_diff_check.isChecked())
    try:
        patches_by_scope = _load_commit_patches_by_scope(
            window,
            path,
            word_diff=word_diff,
            preferred_scope=previous_scope,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        render_diff_into_columns(window.commit_diff_view, "", show_header_lines=False)
        window.commit_diff_scope = ""
        window.commit_diff_data = None
        window.commit_diff_data_by_scope = {}
        window.commit_diff_hunk_by_line = {}
        window.commit_diff_info_by_line = {}
        window.commit_diff_selected_line = 0
        window.commit_last_diff_path = path
        _sync_commit_stage_buttons(window)
        return

    window.commit_last_diff_path = path
    window.commit_diff_hunk_by_line = {}
    window.commit_diff_info_by_line = {}
    window.commit_diff_data_by_scope = {}
    if not patches_by_scope:
        render_diff_into_columns(window.commit_diff_view, "(sem diff para este arquivo)", show_header_lines=False)
        window.commit_diff_data = None
        window.commit_diff_selected_line = 0
        window.commit_diff_scope = ""
        window.commit_current_patch = ""
        _sync_commit_stage_buttons(window)
        return

    only_scope = patches_by_scope[0][0] if len(patches_by_scope) == 1 else ""
    window.commit_diff_scope = only_scope if only_scope else "mixed"
    window.commit_diff_scope_by_path[path] = window.commit_diff_scope

    first_selectable_index = -1
    window.commit_diff_rendering = True
    try:
        for scope_index, (scope, patch) in enumerate(patches_by_scope):
            window.commit_diff_data_by_scope[scope] = parse_diff_data(patch, word_diff_plain=word_diff)
            render_diff_into_columns(
                window.commit_diff_view,
                patch,
                append=(scope_index > 0),
                scope_value=scope,
                line_marker_resolver=lambda info, current_scope=scope: _commit_diff_line_marker_for_scope(
                    current_scope, info
                ),
                hunk_marker_resolver=lambda idx, hunk, current_scope=scope: _commit_diff_hunk_marker_for_scope(
                    current_scope, idx, hunk
                ),
                show_header_lines=False,
                scroll_to_top=False,
                word_diff_plain=word_diff,
            )
    finally:
        window.commit_diff_rendering = False

    for row_index in range(window.commit_diff_view.topLevelItemCount()):
        item = window.commit_diff_view.topLevelItem(row_index)
        if item is None:
            continue
        hunk_value = item.data(0, HUNK_INDEX_ROLE)
        if isinstance(hunk_value, int):
            window.commit_diff_hunk_by_line[row_index + 1] = hunk_value
        info_value = item.data(0, LINE_INFO_ROLE)
        if isinstance(info_value, DiffLineInfo):
            window.commit_diff_info_by_line[row_index + 1] = info_value
        kind_value = item.data(0, ROW_KIND_ROLE)
        kind = str(kind_value).strip() if kind_value is not None else ""
        if first_selectable_index < 0 and kind in {"hunk", "added", "removed", "context"}:
            first_selectable_index = row_index

    target_row_index = _find_commit_diff_target_row(
        window,
        previous_line_info=previous_line_info,
        previous_hunk_index=previous_hunk_index,
        previous_scope=previous_row_scope,
        previous_row_index=previous_row_index,
        first_selectable_index=first_selectable_index,
    )
    if target_row_index >= 0:
        first_item = window.commit_diff_view.topLevelItem(target_row_index)
        if first_item is not None:
            window.commit_diff_view.setCurrentItem(first_item)
            window.commit_diff_selected_line = target_row_index + 1
            vertical_scroll_bar = window.commit_diff_view.verticalScrollBar()
            vertical_scroll_bar.setValue(min(previous_scroll_value, vertical_scroll_bar.maximum()))
    else:
        window.commit_diff_selected_line = 0
    _sync_active_commit_diff_data(window)
    window.commit_current_patch = "\n".join(section_patch for _scope, section_patch in patches_by_scope)
    _sync_commit_stage_buttons(window)


def _set_diff_text_with_kinds(widget: QPlainTextEdit, text: str, line_kinds: list[str]) -> None:
    install_diff_copy_shortcut(widget)
    highlighter = install_diff_highlighter(widget)
    widget.setPlainText(text)
    highlighter.set_line_kinds(line_kinds)


def _dialog_tree_current_item(dialog_state: dict[str, object]) -> QTreeWidgetItem | None:
    tree = dialog_state.get("side_tree")
    if not isinstance(tree, QTreeWidget):
        return None
    return tree.currentItem()


def _dialog_tree_item_key(item: QTreeWidgetItem) -> tuple[str, int, int, str, str]:
    kind_value = item.data(0, ROLE_DIALOG_KIND)
    hunk_value = item.data(0, ROLE_DIALOG_HUNK)
    line_no_value = item.data(0, ROLE_DIALOG_LINE_NO)
    old_text = item.text(0)
    new_text = item.text(4)
    kind = str(kind_value).strip() if kind_value is not None else ""
    hunk_index = int(hunk_value) if isinstance(hunk_value, int) else -1
    line_no = int(line_no_value) if isinstance(line_no_value, int) else 0
    return (kind, hunk_index, line_no, old_text, new_text)


def _dialog_apply_marker_to_item(item: QTreeWidgetItem, marker: str) -> None:
    normalized = marker.strip()
    item.setText(2, "")
    item.setTextAlignment(2, int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
    if normalized not in {"[x]", "[ ]", "[~]"}:
        return
    flags = (
        item.flags()
        | Qt.ItemFlag.ItemIsEnabled
        | Qt.ItemFlag.ItemIsSelectable
        | Qt.ItemFlag.ItemIsUserCheckable
    )
    item.setFlags(flags)
    if normalized == "[x]":
        item.setCheckState(2, Qt.CheckState.Checked)
        return
    if normalized == "[~]":
        item.setCheckState(2, Qt.CheckState.PartiallyChecked)
        return
    item.setCheckState(2, Qt.CheckState.Unchecked)


def _dialog_apply_row_color(
    item: QTreeWidgetItem,
    *,
    line_type: str,
    target_columns: tuple[int, ...],
) -> None:
    app = QApplication.instance()
    if app is None:
        return
    base = app.palette().color(QPalette.ColorRole.Base)
    is_light = int(base.lightness()) >= 128
    color_value = get_diff_kind_color(
        line_type,
        is_light=is_light,
        theme_overrides=app.property("gv_theme_overrides"),
    )
    if not color_value:
        return
    color = QColor(color_value)
    for column in target_columns:
        item.setForeground(column, color)


def _dialog_apply_real_line_tooltips(
    item: QTreeWidgetItem,
    *,
    old_real_line: int | None,
    new_real_line: int | None,
) -> None:
    old_label = str(int(old_real_line)) if isinstance(old_real_line, int) and old_real_line > 0 else "-"
    new_label = str(int(new_real_line)) if isinstance(new_real_line, int) and new_real_line > 0 else "-"
    row_tooltip = f"Linha real: removida={old_label}, adicionada={new_label}"
    item.setToolTip(1, f"Linha real removida: {old_label}")
    item.setToolTip(3, f"Linha real adicionada: {new_label}")
    for column in (0, 2, 4):
        item.setToolTip(column, row_tooltip)


def _dialog_selected_hunk_index(dialog_state: dict[str, object]) -> int | None:
    current_item = _dialog_tree_current_item(dialog_state)
    if current_item is not None:
        value = current_item.data(0, ROLE_DIALOG_HUNK)
        if isinstance(value, int):
            return value
    line_to_hunk = dialog_state.get("line_to_hunk")
    if not isinstance(line_to_hunk, dict) or not line_to_hunk:
        return None
    selected_line = int(dialog_state.get("selected_line", 0) or 0)
    if selected_line in line_to_hunk:
        return int(line_to_hunk[selected_line])
    smaller = [line for line in line_to_hunk if line <= selected_line]
    if not smaller:
        return None
    nearest = max(smaller)
    return int(line_to_hunk[nearest])


def _dialog_selected_line_info(dialog_state: dict[str, object]) -> DiffLineInfo | None:
    current_item = _dialog_tree_current_item(dialog_state)
    if current_item is not None:
        value = current_item.data(0, ROLE_DIALOG_LINE_INFO)
        if isinstance(value, DiffLineInfo):
            return value
    line_to_info = dialog_state.get("line_to_info")
    if not isinstance(line_to_info, dict) or not line_to_info:
        return None
    selected_line = int(dialog_state.get("selected_line", 0) or 0)
    info = line_to_info.get(selected_line)
    return info if isinstance(info, DiffLineInfo) else None


def _dialog_item_line_infos(item: QTreeWidgetItem | None) -> tuple[DiffLineInfo | None, DiffLineInfo | None]:
    if item is None:
        return (None, None)
    old_value = item.data(0, ROLE_DIALOG_OLD_LINE_INFO)
    new_value = item.data(0, ROLE_DIALOG_NEW_LINE_INFO)
    old_info = old_value if isinstance(old_value, DiffLineInfo) else None
    new_info = new_value if isinstance(new_value, DiffLineInfo) else None
    if old_info is None and new_info is None:
        legacy_value = item.data(0, ROLE_DIALOG_LINE_INFO)
        legacy_info = legacy_value if isinstance(legacy_value, DiffLineInfo) else None
        if legacy_info is not None:
            if legacy_info.line_type == "removed":
                old_info = legacy_info
            elif legacy_info.line_type == "added":
                new_info = legacy_info
    return (old_info, new_info)


def _build_patch_for_dialog_row(
    diff_data: DiffData,
    *,
    old_line_info: DiffLineInfo | None,
    new_line_info: DiffLineInfo | None,
) -> str | None:
    if old_line_info is None and new_line_info is None:
        return None
    if old_line_info is not None and new_line_info is not None:
        header = f"@@ -{int(old_line_info.old_line)},1 +{int(new_line_info.new_line)},1 @@"
        return (
            "\n".join(
                [
                    *diff_data.header_lines,
                    header,
                    f"-{old_line_info.content}",
                    f"+{new_line_info.content}",
                ]
            )
            + "\n"
        )
    single_line = old_line_info if old_line_info is not None else new_line_info
    if single_line is None:
        return None
    return build_patch_for_line(diff_data, single_line)


def _dialog_line_marker(dialog_state: dict[str, object], line_info: DiffLineInfo) -> str:
    if line_info.line_type not in ("added", "removed"):
        return ""
    scope = str(dialog_state.get("scope", "")).strip()
    if scope == "staged":
        return "[x]"
    return "[ ]"


def _dialog_hunk_marker(dialog_state: dict[str, object], _hunk_index: int, hunk: DiffHunk) -> str:
    if not any(line.line_type in ("added", "removed") for line in hunk.lines):
        return ""
    scope = str(dialog_state.get("scope", "")).strip()
    if scope == "staged":
        return "[x]"
    return "[ ]"


def _refresh_commit_diff_dialog_views(window: object, dialog_state: dict[str, object]) -> None:
    path = str(dialog_state.get("path", "")).strip()
    if not path:
        return
    scope_label = dialog_state.get("scope_label")
    info_label = dialog_state.get("info_label")
    unified_view = dialog_state.get("unified_view")
    side_tree = dialog_state.get("side_tree")
    if not isinstance(unified_view, CommitDiffView) or not isinstance(side_tree, QTreeWidget):
        return

    try:
        display_patch, scope = _load_commit_patch_for_path(window, path, word_diff=False)
        operation_patch = display_patch
    except RuntimeError as exc:
        QMessageBox.critical(window, "Diff", str(exc))
        return

    dialog_state["scope"] = scope
    if isinstance(scope_label, QLabel):
        if scope == "staged":
            scope_label.setText("Escopo: staged")
        elif scope == "unstaged":
            scope_label.setText("Escopo: unstaged")
        else:
            scope_label.setText("Escopo: sem diff")
    if isinstance(info_label, QLabel):
        info_label.setText(
            "Use o checkbox central para stage/unstage por linha/bloco. Clique direito para copiar ou reverter."
        )

    current_item = side_tree.currentItem()
    selected_key = _dialog_tree_item_key(current_item) if current_item is not None else None
    dialog_state["rendering_tree"] = True
    side_tree.clear()

    if not display_patch:
        empty_item = QTreeWidgetItem(["(sem diff para este arquivo)", "", "", "", ""])
        empty_item.setData(0, ROLE_DIALOG_KIND, "meta")
        side_tree.addTopLevelItem(empty_item)
        dialog_state["line_to_hunk"] = {}
        dialog_state["line_to_info"] = {}
        dialog_state["selected_line"] = 0
        dialog_state["operation_diff_data"] = DiffData(header_lines=[], hunks=[])
        dialog_state["rendering_tree"] = False
        return

    rendered = render_diff_into_widget(
        unified_view,
        display_patch,
        line_marker_resolver=lambda info: _dialog_line_marker(dialog_state, info),
        hunk_marker_resolver=lambda idx, hunk: _dialog_hunk_marker(dialog_state, idx, hunk),
        show_header_lines=False,
        include_marker_column=True,
        word_diff_plain=False,
    )
    dialog_state["line_to_hunk"] = dict(rendered.line_to_hunk)
    dialog_state["line_to_info"] = dict(rendered.line_to_info)
    dialog_state["operation_diff_data"] = parse_diff_data(operation_patch) if operation_patch else rendered.diff_data

    line_no_by_hunk_header: dict[int, int] = {}
    for line_no, hunk_index in rendered.line_to_hunk.items():
        if line_no in rendered.line_to_info:
            continue
        current_line = line_no_by_hunk_header.get(hunk_index)
        if current_line is None or line_no < current_line:
            line_no_by_hunk_header[hunk_index] = line_no

    line_no_by_info_id: dict[int, int] = {}
    for line_no, line_info in rendered.line_to_info.items():
        line_no_by_info_id[id(line_info)] = line_no

    first_selectable_item: QTreeWidgetItem | None = None
    for hunk_index, hunk in enumerate(rendered.diff_data.hunks):
        hunk_row = QTreeWidgetItem([f"Secao: {hunk.header}", "", "", "", ""])
        hunk_row.setData(0, ROLE_DIALOG_KIND, "hunk")
        hunk_row.setData(0, ROLE_DIALOG_HUNK, hunk_index)
        hunk_line_no = line_no_by_hunk_header.get(hunk_index, 0)
        hunk_row.setData(0, ROLE_DIALOG_LINE_NO, hunk_line_no)
        hunk_row.setTextAlignment(1, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        hunk_row.setTextAlignment(3, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        hunk_marker = _dialog_hunk_marker(dialog_state, hunk_index, hunk)
        _dialog_apply_marker_to_item(hunk_row, hunk_marker)
        for column in range(5):
            font = hunk_row.font(column)
            font.setBold(True)
            hunk_row.setFont(column, font)
        _dialog_apply_row_color(hunk_row, line_type="hunk", target_columns=(0, 4))
        side_tree.addTopLevelItem(hunk_row)
        if first_selectable_item is None and hunk_line_no > 0 and hunk_marker.strip():
            first_selectable_item = hunk_row

        lines = hunk.lines
        line_index = 0
        while line_index < len(lines):
            current_line = lines[line_index]
            if current_line.line_type == "context":
                row_line_no = int(line_no_by_info_id.get(id(current_line), 0) or 0)
                row_item = QTreeWidgetItem(
                    [
                        current_line.content,
                        str(int(current_line.old_line)),
                        "",
                        str(int(current_line.new_line)),
                        current_line.content,
                    ]
                )
                row_item.setData(0, ROLE_DIALOG_KIND, "line")
                row_item.setData(0, ROLE_DIALOG_HUNK, hunk_index)
                row_item.setData(0, ROLE_DIALOG_LINE_NO, row_line_no)
                row_item.setData(0, ROLE_DIALOG_OLD_RAW, current_line.content)
                row_item.setData(0, ROLE_DIALOG_NEW_RAW, current_line.content)
                row_item.setTextAlignment(1, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                row_item.setTextAlignment(3, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                _dialog_apply_real_line_tooltips(
                    row_item,
                    old_real_line=int(current_line.old_line),
                    new_real_line=int(current_line.new_line),
                )
                _dialog_apply_row_color(row_item, line_type="context", target_columns=(0, 1, 3, 4))
                side_tree.addTopLevelItem(row_item)
                line_index += 1
                continue

            removed_lines: list[tuple[DiffLineInfo, int]] = []
            added_lines: list[tuple[DiffLineInfo, int]] = []
            while line_index < len(lines) and lines[line_index].line_type in {"removed", "added"}:
                run_line = lines[line_index]
                row_line_no = int(line_no_by_info_id.get(id(run_line), 0) or 0)
                if run_line.line_type == "removed":
                    removed_lines.append((run_line, row_line_no))
                else:
                    added_lines.append((run_line, row_line_no))
                line_index += 1

            pair_count = max(len(removed_lines), len(added_lines))
            display_number_seed = 1
            if removed_lines and added_lines:
                display_number_seed = min(
                    int(removed_lines[0][0].old_line),
                    int(added_lines[0][0].new_line),
                )
            elif removed_lines:
                display_number_seed = int(removed_lines[0][0].old_line)
            elif added_lines:
                display_number_seed = int(added_lines[0][0].new_line)
            for pair_index in range(pair_count):
                removed_entry = removed_lines[pair_index] if pair_index < len(removed_lines) else None
                added_entry = added_lines[pair_index] if pair_index < len(added_lines) else None
                removed_line = removed_entry[0] if removed_entry else None
                added_line = added_entry[0] if added_entry else None
                row_line_no = 0
                if removed_entry is not None and removed_entry[1] > 0:
                    row_line_no = int(removed_entry[1])
                elif added_entry is not None and added_entry[1] > 0:
                    row_line_no = int(added_entry[1])

                old_content = removed_line.content if removed_line is not None else ""
                new_content = added_line.content if added_line is not None else ""
                display_no = str(display_number_seed + pair_index)
                old_no = display_no if removed_line is not None or added_line is not None else ""
                new_no = display_no if removed_line is not None or added_line is not None else ""

                row_item = QTreeWidgetItem([old_content, old_no, "", new_no, new_content])
                row_item.setData(0, ROLE_DIALOG_KIND, "line")
                row_item.setData(0, ROLE_DIALOG_HUNK, hunk_index)
                row_item.setData(0, ROLE_DIALOG_LINE_NO, row_line_no)
                row_item.setTextAlignment(1, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                row_item.setTextAlignment(3, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                _dialog_apply_real_line_tooltips(
                    row_item,
                    old_real_line=int(removed_line.old_line) if removed_line is not None else None,
                    new_real_line=int(added_line.new_line) if added_line is not None else None,
                )
                if removed_line is not None:
                    row_item.setData(0, ROLE_DIALOG_OLD_LINE_INFO, removed_line)
                    row_item.setData(0, ROLE_DIALOG_OLD_RAW, old_content)
                    row_item.setData(0, ROLE_DIALOG_LINE_INFO, removed_line)
                    _dialog_apply_row_color(row_item, line_type="removed", target_columns=(0, 1))
                if added_line is not None:
                    row_item.setData(0, ROLE_DIALOG_NEW_LINE_INFO, added_line)
                    row_item.setData(0, ROLE_DIALOG_NEW_RAW, new_content)
                    if removed_line is None:
                        row_item.setData(0, ROLE_DIALOG_LINE_INFO, added_line)
                    _dialog_apply_row_color(row_item, line_type="added", target_columns=(3, 4))
                if removed_line is not None or added_line is not None:
                    marker = "[x]" if scope == "staged" else "[ ]"
                    _dialog_apply_marker_to_item(row_item, marker)
                    if first_selectable_item is None and row_line_no > 0:
                        first_selectable_item = row_item
                side_tree.addTopLevelItem(row_item)

    target_item: QTreeWidgetItem | None = None
    if selected_key is not None:
        for row_index in range(side_tree.topLevelItemCount()):
            candidate = side_tree.topLevelItem(row_index)
            if candidate is None:
                continue
            if _dialog_tree_item_key(candidate) == selected_key:
                target_item = candidate
                break
    if target_item is None:
        target_item = first_selectable_item
    if target_item is not None:
        side_tree.setCurrentItem(target_item)
        side_tree.scrollToItem(target_item)
        line_no_value = target_item.data(0, ROLE_DIALOG_LINE_NO)
        dialog_state["selected_line"] = int(line_no_value) if isinstance(line_no_value, int) else 0
    else:
        dialog_state["selected_line"] = 0
    dialog_state["rendering_tree"] = False


def _refresh_after_commit_diff_dialog_change(window: object, dialog_state: dict[str, object], status: str) -> None:
    path = str(dialog_state.get("path", "")).strip()
    if path:
        window.commit_selected_path = path
    window._set_status(status)
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    _refresh_commit_diff_dialog_views(window, dialog_state)


def _apply_commit_diff_dialog_stage_change(
    window: object,
    dialog_state: dict[str, object],
    *,
    patch: str,
    reverse: bool,
    success_message: str,
) -> None:
    if not window.repo_path:
        return
    if not patch.strip():
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=reverse)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _refresh_after_commit_diff_dialog_change(window, dialog_state, success_message)


def _apply_commit_diff_dialog_revert_change(
    window: object,
    dialog_state: dict[str, object],
    *,
    patch: str,
    success_message: str,
) -> None:
    if not window.repo_path:
        return
    if not patch.strip():
        return
    scope = str(dialog_state.get("scope", "")).strip()
    try:
        if scope == "staged":
            core_apply_patch_to_index(window.repo_path, patch, reverse=True)
            core_apply_patch_to_worktree(window.repo_path, patch, reverse=True)
        else:
            core_apply_patch_to_worktree(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _refresh_after_commit_diff_dialog_change(window, dialog_state, success_message)


def _on_commit_diff_dialog_marker_clicked(window: object, dialog_state: dict[str, object], line_no: int) -> None:
    dialog_state["selected_line"] = max(1, int(line_no or 1))
    scope = str(dialog_state.get("scope", "")).strip()
    operation_diff_data = dialog_state.get("operation_diff_data")
    if not isinstance(operation_diff_data, DiffData):
        return
    current_item = _dialog_tree_current_item(dialog_state)
    old_line_info, new_line_info = _dialog_item_line_infos(current_item)
    if old_line_info is not None or new_line_info is not None:
        patch = _build_patch_for_dialog_row(
            operation_diff_data,
            old_line_info=old_line_info,
            new_line_info=new_line_info,
        )
        if not patch:
            return
        if scope == "staged":
            _apply_commit_diff_dialog_stage_change(
                window,
                dialog_state,
                patch=patch,
                reverse=True,
                success_message="Linha removida do stage.",
            )
            return
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=False,
            success_message="Linha adicionada ao stage.",
        )
        return
    hunk_index = _dialog_selected_hunk_index(dialog_state)
    if hunk_index is None:
        return
    patch = build_patch_for_hunk(operation_diff_data, hunk_index)
    if not patch:
        return
    if scope == "staged":
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=True,
            success_message="Bloco removido do stage.",
        )
        return
    _apply_commit_diff_dialog_stage_change(
        window,
        dialog_state,
        patch=patch,
        reverse=False,
        success_message="Bloco adicionado ao stage.",
    )


def _on_commit_diff_dialog_tree_selection_changed(dialog_state: dict[str, object]) -> None:
    current_item = _dialog_tree_current_item(dialog_state)
    if current_item is None:
        dialog_state["selected_line"] = 0
        return
    line_no_value = current_item.data(0, ROLE_DIALOG_LINE_NO)
    dialog_state["selected_line"] = int(line_no_value) if isinstance(line_no_value, int) else 0


def _on_commit_diff_dialog_item_changed(
    window: object,
    dialog_state: dict[str, object],
    item: QTreeWidgetItem,
    column: int,
) -> None:
    if bool(dialog_state.get("rendering_tree", False)):
        return
    if column != 2:
        return
    kind_value = item.data(0, ROLE_DIALOG_KIND)
    kind = str(kind_value).strip() if kind_value is not None else ""
    if kind not in {"line", "hunk"}:
        return
    line_no_value = item.data(0, ROLE_DIALOG_LINE_NO)
    if not isinstance(line_no_value, int) or line_no_value <= 0:
        return
    scope = str(dialog_state.get("scope", "")).strip()
    state = item.checkState(2)
    should_toggle = (
        (scope == "unstaged" and state == Qt.CheckState.Checked)
        or (scope == "staged" and state == Qt.CheckState.Unchecked)
    )
    if not should_toggle:
        return
    dialog_state["selected_line"] = line_no_value
    _on_commit_diff_dialog_marker_clicked(window, dialog_state, line_no_value)


def _on_commit_diff_dialog_context_menu(window: object, dialog_state: dict[str, object], pos: object) -> None:
    side_tree = dialog_state.get("side_tree")
    if not isinstance(side_tree, QTreeWidget):
        return
    operation_diff_data = dialog_state.get("operation_diff_data")
    if not isinstance(operation_diff_data, DiffData):
        return
    item = side_tree.itemAt(pos)
    if item is None:
        return
    side_tree.setCurrentItem(item)
    line_no_value = item.data(0, ROLE_DIALOG_LINE_NO)
    if isinstance(line_no_value, int):
        dialog_state["selected_line"] = line_no_value

    scope = str(dialog_state.get("scope", "")).strip()
    old_line_info, new_line_info = _dialog_item_line_infos(item)
    hunk_index = _dialog_selected_hunk_index(dialog_state)
    changed_line = bool(old_line_info is not None or new_line_info is not None)
    old_raw_value = item.data(0, ROLE_DIALOG_OLD_RAW)
    new_raw_value = item.data(0, ROLE_DIALOG_NEW_RAW)
    old_raw = str(old_raw_value).strip() if old_raw_value is not None else ""
    new_raw = str(new_raw_value).strip() if new_raw_value is not None else ""

    menu = QMenu(side_tree)
    action_copy_removed = menu.addAction("Copiar conteudo removido") if old_raw else None
    action_copy_added = menu.addAction("Copiar conteudo adicionado") if new_raw else None
    action_copy_line = menu.addAction("Copiar linha") if changed_line else None
    action_copy_hunk = menu.addAction("Copiar bloco") if hunk_index is not None else None
    if action_copy_removed or action_copy_added or action_copy_line or action_copy_hunk:
        menu.addSeparator()
    action_stage_line = None
    action_unstage_line = None
    action_stage_hunk = None
    action_unstage_hunk = None
    if scope == "staged":
        if hunk_index is not None:
            action_unstage_hunk = menu.addAction("Unstage bloco")
        if changed_line:
            action_unstage_line = menu.addAction("Unstage linha")
    elif scope == "unstaged":
        if hunk_index is not None:
            action_stage_hunk = menu.addAction("Stage bloco")
        if changed_line:
            action_stage_line = menu.addAction("Stage linha")
    action_revert_line = menu.addAction("Reverter linha") if changed_line else None
    action_revert_hunk = menu.addAction("Reverter bloco") if hunk_index is not None else None
    if not menu.actions():
        return

    chosen_action = menu.exec(side_tree.viewport().mapToGlobal(pos))
    if chosen_action is None:
        return
    if chosen_action == action_copy_removed and old_raw:
        window._copy_to_clipboard(old_raw, status="Conteudo removido copiado.")
        return
    if chosen_action == action_copy_added and new_raw:
        window._copy_to_clipboard(new_raw, status="Conteudo adicionado copiado.")
        return
    if chosen_action == action_copy_line and changed_line:
        lines_to_copy: list[str] = []
        if old_line_info is not None:
            lines_to_copy.append(f"-{old_line_info.content}")
        if new_line_info is not None:
            lines_to_copy.append(f"+{new_line_info.content}")
        payload = "\n".join(lines_to_copy).strip()
        if payload:
            window._copy_to_clipboard(payload, status="Linha copiada.")
        return
    if chosen_action == action_copy_hunk and hunk_index is not None:
        patch = build_patch_for_hunk(operation_diff_data, hunk_index) or ""
        payload = patch.strip()
        if payload:
            window._copy_to_clipboard(payload, status="Bloco copiado.")
        return
    if chosen_action == action_stage_line and changed_line:
        patch = _build_patch_for_dialog_row(
            operation_diff_data,
            old_line_info=old_line_info,
            new_line_info=new_line_info,
        ) or ""
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=False,
            success_message="Linha adicionada ao stage.",
        )
        return
    if chosen_action == action_unstage_line and changed_line:
        patch = _build_patch_for_dialog_row(
            operation_diff_data,
            old_line_info=old_line_info,
            new_line_info=new_line_info,
        ) or ""
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=True,
            success_message="Linha removida do stage.",
        )
        return
    if chosen_action == action_stage_hunk and hunk_index is not None:
        patch = build_patch_for_hunk(operation_diff_data, hunk_index) or ""
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=False,
            success_message="Bloco adicionado ao stage.",
        )
        return
    if chosen_action == action_unstage_hunk and hunk_index is not None:
        patch = build_patch_for_hunk(operation_diff_data, hunk_index) or ""
        _apply_commit_diff_dialog_stage_change(
            window,
            dialog_state,
            patch=patch,
            reverse=True,
            success_message="Bloco removido do stage.",
        )
        return
    if chosen_action == action_revert_line and changed_line:
        patch = _build_patch_for_dialog_row(
            operation_diff_data,
            old_line_info=old_line_info,
            new_line_info=new_line_info,
        ) or ""
        _apply_commit_diff_dialog_revert_change(
            window,
            dialog_state,
            patch=patch,
            success_message="Linha revertida no arquivo.",
        )
        return
    if chosen_action == action_revert_hunk and hunk_index is not None:
        patch = build_patch_for_hunk(operation_diff_data, hunk_index) or ""
        _apply_commit_diff_dialog_revert_change(
            window,
            dialog_state,
            patch=patch,
            success_message="Bloco revertido no arquivo.",
        )


def open_commit_diff_window(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Diff", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Diff", "Selecione um arquivo na aba Commit.")
        return

    dialog = QDialog(window)
    dialog.setModal(True)
    dialog.setWindowTitle(f"Diff avançado - {path}")
    dialog.resize(max(window.width(), 1200), max(window.height(), 760))

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    top_row = QWidget(dialog)
    top_layout = QHBoxLayout(top_row)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(6)
    top_layout.addWidget(QLabel(f"Arquivo: {path}", top_row), stretch=1)
    refresh_button = QPushButton("Atualizar", top_row)
    top_layout.addWidget(refresh_button)
    layout.addWidget(top_row)

    info_row = QWidget(dialog)
    info_layout = QHBoxLayout(info_row)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(8)
    scope_label = QLabel("Escopo: -", info_row)
    info_layout.addWidget(scope_label)
    info_label = QLabel("", info_row)
    info_layout.addWidget(info_label, stretch=1)
    layout.addWidget(info_row)

    # View oculta usada para manter parser/render e mapeamento de linha->hunk/linha.
    unified_view = CommitDiffView(dialog)
    unified_view.setReadOnly(True)
    unified_view.setProperty("role", "diff")
    unified_view.hide()

    side_tree = QTreeWidget(dialog)
    side_tree.setObjectName("DiffColumnsView")
    side_tree.setRootIsDecorated(False)
    side_tree.setItemsExpandable(False)
    side_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    side_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    side_tree.setAlternatingRowColors(False)
    side_tree.setWordWrap(True)
    side_tree.setColumnCount(5)
    side_tree.setHeaderLabels(["Conteudo removido", "N-", "Check", "N+", "Conteudo adicionado"])
    side_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    side_tree.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    side_tree.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    side_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    side_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    side_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    side_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    side_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    side_tree.setColumnWidth(2, 48)
    layout.addWidget(side_tree, stretch=1)

    close_row = QWidget(dialog)
    close_layout = QHBoxLayout(close_row)
    close_layout.setContentsMargins(0, 0, 0, 0)
    close_layout.setSpacing(6)
    close_layout.addStretch(1)
    close_button = QPushButton("Fechar", close_row)
    close_button.clicked.connect(dialog.accept)
    close_layout.addWidget(close_button)
    layout.addWidget(close_row)

    dialog_state: dict[str, object] = {
        "path": path,
        "scope_label": scope_label,
        "info_label": info_label,
        "unified_view": unified_view,
        "side_tree": side_tree,
        "line_to_hunk": {},
        "line_to_info": {},
        "selected_line": 0,
        "scope": "",
        "operation_diff_data": DiffData(header_lines=[], hunks=[]),
        "rendering_tree": False,
    }

    refresh_button.clicked.connect(lambda: _refresh_commit_diff_dialog_views(window, dialog_state))
    side_tree.itemSelectionChanged.connect(lambda: _on_commit_diff_dialog_tree_selection_changed(dialog_state))
    side_tree.itemChanged.connect(
        lambda item, column: _on_commit_diff_dialog_item_changed(window, dialog_state, item, column)
    )
    side_tree.customContextMenuRequested.connect(
        lambda pos: _on_commit_diff_dialog_context_menu(window, dialog_state, pos)
    )

    _refresh_commit_diff_dialog_views(window, dialog_state)
    dialog.showMaximized()
    dialog.exec()


def _selected_commit_hunk_index(window: object) -> int | None:
    if not hasattr(window, "commit_diff_view"):
        return None
    current_item = window.commit_diff_view.currentItem()
    if current_item is None:
        return None
    value = current_item.data(0, HUNK_INDEX_ROLE)
    if isinstance(value, int):
        return value
    return None


def _selected_commit_line_info(window: object) -> object | None:
    if not hasattr(window, "commit_diff_view"):
        return None
    current_item = window.commit_diff_view.currentItem()
    if current_item is None:
        return None
    value = current_item.data(0, LINE_INFO_ROLE)
    if isinstance(value, DiffLineInfo):
        return value
    return None


def on_commit_diff_cursor_changed(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    current_item = window.commit_diff_view.currentItem()
    if current_item is not None:
        row_index = window.commit_diff_view.indexOfTopLevelItem(current_item)
        window.commit_diff_selected_line = row_index + 1 if row_index >= 0 else 0
    else:
        window.commit_diff_selected_line = 0
    _sync_active_commit_diff_data(window)
    _sync_commit_stage_buttons(window)


def on_commit_diff_item_clicked(window: object, item: object, column: int) -> None:
    if not window.repo_path:
        return
    if item is None:
        return
    row_index = window.commit_diff_view.indexOfTopLevelItem(item)
    if row_index < 0:
        return
    window.commit_diff_selected_line = row_index + 1
    _sync_commit_stage_buttons(window)


def on_commit_diff_item_changed(window: object, item: object, column: int) -> None:
    if not window.repo_path or not hasattr(window, "commit_diff_view"):
        return
    if bool(getattr(window, "commit_diff_rendering", False)):
        return
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    if column != marker_column:
        return
    row_index = window.commit_diff_view.indexOfTopLevelItem(item)
    if row_index < 0:
        return
    kind_value = item.data(0, ROW_KIND_ROLE)
    kind = str(kind_value).strip() if kind_value is not None else ""
    if kind not in {"hunk", "added", "removed"}:
        return
    window.commit_diff_selected_line = row_index + 1
    on_commit_diff_marker_clicked(window, window.commit_diff_selected_line)


def on_commit_diff_marker_clicked(window: object, line_no: int) -> None:
    if not window.repo_path:
        return
    window.commit_diff_selected_line = max(1, int(line_no or 1))
    scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    line_info = _selected_commit_line_info(window)
    if line_info is not None and line_info.line_type in ("added", "removed"):
        if scope == "staged":
            unstage_selected_commit_line(window)
            return
        if scope in {"unstaged", "untracked"}:
            stage_selected_commit_line(window)
            return
    hunk_index = _selected_commit_hunk_index(window)
    if hunk_index is None:
        return
    if scope == "staged":
        unstage_selected_commit_hunk(window)
        return
    if scope in {"unstaged", "untracked"}:
        stage_selected_commit_hunk(window)


def on_commit_diff_context_menu(window: object, pos: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    if not window.repo_path:
        return
    path = _current_commit_file_path(window)
    if not path:
        return
    entry = window.commit_status_entries_by_path.get(path, {})
    has_unstaged = bool(entry.get("unstaged", False))
    has_staged = bool(entry.get("staged", False))
    selected_hunk = _selected_commit_hunk_index(window)
    line_info = _selected_commit_line_info(window)
    is_changed_line = bool(line_info and line_info.line_type in ("added", "removed"))
    scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()

    menu = QMenu(window.commit_diff_view)
    action_stage_file = menu.addAction("Stage arquivo") if has_unstaged else None
    action_unstage_file = menu.addAction("Unstage arquivo") if has_staged else None
    if menu.actions():
        menu.addSeparator()
    action_stage_hunk = None
    action_unstage_hunk = None
    action_stage_line = None
    action_unstage_line = None
    if selected_hunk is not None and scope in {"unstaged", "untracked"}:
        action_stage_hunk = menu.addAction("Stage bloco selecionado")
        if is_changed_line:
            action_stage_line = menu.addAction("Stage linha selecionada")
    if selected_hunk is not None and scope == "staged":
        action_unstage_hunk = menu.addAction("Unstage bloco selecionado")
        if is_changed_line:
            action_unstage_line = menu.addAction("Unstage linha selecionada")
    if not menu.actions():
        return
    if hasattr(window.commit_diff_view, "viewport"):
        chosen_action = menu.exec(window.commit_diff_view.viewport().mapToGlobal(pos))
    else:
        chosen_action = menu.exec(window.commit_diff_view.mapToGlobal(pos))
    if chosen_action is None:
        return
    if chosen_action == action_stage_file:
        stage_selected_commit_file(window)
        return
    if chosen_action == action_unstage_file:
        unstage_selected_commit_file(window)
        return
    if chosen_action == action_stage_hunk:
        stage_selected_commit_hunk(window)
        return
    if chosen_action == action_unstage_hunk:
        unstage_selected_commit_hunk(window)
        return
    if chosen_action == action_stage_line:
        stage_selected_commit_line(window)
        return
    if chosen_action == action_unstage_line:
        unstage_selected_commit_line(window)


def stage_selected_commit_file(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para stage.")
        return
    try:
        core_stage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    window._set_status(f"Arquivo adicionado ao stage: {path}")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_file(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para unstage.")
        return
    try:
        core_unstage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    window._set_status(f"Arquivo removido do stage: {path}")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def stage_selected_commit_hunk(window: object) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope not in {"unstaged", "untracked"}:
        QMessageBox.information(window, "Commit", "Selecione um diff unstaged para stage do bloco.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "unstaged")
    if diff_data is None:
        QMessageBox.information(window, "Commit", "Selecione um arquivo com diff disponível.")
        return
    hunk_index = _selected_commit_hunk_index(window)
    if hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    patch = build_patch_for_hunk(diff_data, hunk_index)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Bloco adicionado ao stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_hunk(window: object) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope != "staged":
        QMessageBox.information(window, "Commit", "Selecione um diff staged para unstage do bloco.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "staged")
    if diff_data is None:
        QMessageBox.information(window, "Commit", "Selecione um arquivo com diff disponível.")
        return
    hunk_index = _selected_commit_hunk_index(window)
    if hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    patch = build_patch_for_hunk(diff_data, hunk_index)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Bloco removido do stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def stage_selected_commit_line(window: object) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope not in {"unstaged", "untracked"}:
        QMessageBox.information(window, "Commit", "Selecione um diff unstaged para stage da linha.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "unstaged")
    line_info = _selected_commit_line_info(window)
    if diff_data is None or line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Linha adicionada ao stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def unstage_selected_commit_line(window: object) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope != "staged":
        QMessageBox.information(window, "Commit", "Selecione um diff staged para unstage da linha.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "staged")
    line_info = _selected_commit_line_info(window)
    if diff_data is None or line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return
    path = _current_commit_file_path(window)
    window._set_status("Linha removida do stage.")
    window.commit_selected_path = path
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def _stash_tab_index(window: object) -> int:
    if not hasattr(window, "tabs") or not hasattr(window, "stash_tab"):
        return -1
    for index in range(window.tabs.count()):
        if window.tabs.widget(index) is window.stash_tab:
            return index
    return -1


def _is_stash_tab_visible(window: object) -> bool:
    return _stash_tab_index(window) >= 0


def _ensure_stash_tab_visible(window: object) -> None:
    if _is_stash_tab_visible(window):
        return
    insert_index = window.tabs.count()
    for index in range(window.tabs.count()):
        if window.tabs.tabText(index) == "Commit":
            insert_index = index + 1
            break
    window.stash_tab.setParent(window.tabs)
    window.tabs.insertTab(insert_index, window.stash_tab, "Stash")


def _hide_stash_tab(window: object) -> None:
    tab_index = _stash_tab_index(window)
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
    window.stash_tab.hide()


def _selected_stash_ref(window: object) -> str:
    if not hasattr(window, "stash_entries_list"):
        return ""
    selected_items = window.stash_entries_list.selectedItems()
    if not selected_items:
        return ""
    value = selected_items[0].data(ROLE_PATH)
    return str(value).strip() if value is not None else ""


def _selected_stash_file(window: object) -> str:
    if not hasattr(window, "stash_files_list"):
        return ""
    selected_items = window.stash_files_list.selectedItems()
    if not selected_items:
        return ""
    value = selected_items[0].data(ROLE_PATH)
    return str(value).strip() if value is not None else ""


def _set_stash_actions_enabled(window: object, enabled: bool) -> None:
    for attr_name in ("stash_apply_button", "stash_pop_button", "stash_drop_button"):
        button = getattr(window, attr_name, None)
        if button is not None:
            button.setEnabled(enabled)


def _format_stash_list_label(stash_ref: str) -> str:
    normalized = stash_ref.strip()
    if normalized.startswith("stash@{") and normalized.endswith("}"):
        index_text = normalized[len("stash@{") : -1].strip()
        if index_text.isdigit():
            return index_text
    return normalized


def _set_stash_header_labels(window: object) -> None:
    if not hasattr(window, "stash_repo_label") or not hasattr(window, "stash_branch_label"):
        return
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        window.stash_repo_label.setText("Repositorio: (nenhum)")
        window.stash_branch_label.setText("Branch: (nenhuma)")
        return
    repo_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
    if hasattr(window, "_format_workspace_relative_path"):
        relative = str(window._format_workspace_relative_path(repo_path)).strip()
        if relative and relative != repo_path:
            repo_name = f"{repo_name} {relative}"
    branch_name = ""
    if hasattr(window, "_get_repo_branch_name"):
        branch_name = str(window._get_repo_branch_name(repo_path)).strip()
    window.stash_repo_label.setText(f"Repositorio: {repo_name}")
    window.stash_branch_label.setText(f"Branch: {branch_name or '(desconhecida)'}")


def _clear_stash_view(window: object, message: str) -> None:
    if hasattr(window, "stash_entries_list"):
        window.stash_entries_list.clear()
    if hasattr(window, "stash_files_list"):
        window.stash_files_list.clear()
    if hasattr(window, "stash_patch_table"):
        render_diff_into_columns(window.stash_patch_table, message, show_header_lines=False)
    if hasattr(window, "stash_patch_text"):
        window.stash_patch_text.setPlainText(message)
    if hasattr(window, "stash_patch_stack"):
        window.stash_patch_stack.setCurrentIndex(0)
    _set_stash_actions_enabled(window, False)


def _reload_stash_entries(window: object, preferred_ref: str = "", stash_entries: list[object] | None = None) -> None:
    if not hasattr(window, "stash_entries_list"):
        return
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        _clear_stash_view(window, "(sem repositorio selecionado)")
        return
    selected_ref = preferred_ref.strip() or _selected_stash_ref(window)
    entries = stash_entries
    if entries is None:
        try:
            entries = core_list_stashes(repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Stash", str(exc))
            return
    window.stash_entries_list.blockSignals(True)
    window.stash_entries_list.clear()
    selected_row = 0
    for index, stash_entry in enumerate(entries):
        item = QListWidgetItem(_format_stash_list_label(stash_entry.ref), window.stash_entries_list)
        item.setData(ROLE_PATH, stash_entry.ref)
        item.setToolTip(f"{stash_entry.ref}: {stash_entry.description}")
        if stash_entry.ref == selected_ref:
            selected_row = index
    window.stash_entries_list.blockSignals(False)
    if window.stash_entries_list.count() <= 0:
        _clear_stash_view(window, "(sem stashes)")
        return
    window.stash_entries_list.setCurrentRow(selected_row)
    on_stash_entry_selected(window)


def refresh_stash_tab_visibility(window: object) -> None:
    _set_stash_header_labels(window)
    repo_path = str(getattr(window, "repo_path", "")).strip()
    has_repo = bool(repo_path)
    if hasattr(window, "stash_create_button"):
        window.stash_create_button.setEnabled(has_repo)
    if hasattr(window, "stash_refresh_button"):
        window.stash_refresh_button.setEnabled(has_repo)
    if not has_repo:
        _clear_stash_view(window, "(sem repositorio selecionado)")
        _hide_stash_tab(window)
        return
    try:
        stash_entries = core_list_stashes(repo_path)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        _clear_stash_view(window, "(falha ao carregar stashes)")
        _hide_stash_tab(window)
        return
    if not stash_entries:
        _clear_stash_view(window, "(sem stashes)")
        _hide_stash_tab(window)
        return
    _ensure_stash_tab_visible(window)
    _reload_stash_entries(window, stash_entries=stash_entries)


def on_stash_entry_selected(window: object) -> None:
    if not hasattr(window, "stash_files_list"):
        return
    repo_path = str(getattr(window, "repo_path", "")).strip()
    stash_ref = _selected_stash_ref(window)
    if not repo_path or not stash_ref:
        window.stash_files_list.clear()
        if hasattr(window, "stash_patch_table"):
            render_diff_into_columns(window.stash_patch_table, "(sem stash selecionado)", show_header_lines=False)
        if hasattr(window, "stash_patch_text"):
            window.stash_patch_text.setPlainText("(sem stash selecionado)")
        _set_stash_actions_enabled(window, False)
        return
    try:
        full_patch = core_get_stash_patch(repo_path, stash_ref, word_diff=False)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    file_paths = core_list_stash_files_from_patch(full_patch)
    window.stash_files_list.blockSignals(True)
    window.stash_files_list.clear()
    for file_path in file_paths:
        item = QListWidgetItem(file_path, window.stash_files_list)
        item.setData(ROLE_PATH, file_path)
    window.stash_files_list.blockSignals(False)
    _set_stash_actions_enabled(window, True)
    if window.stash_files_list.count() > 0:
        window.stash_files_list.setCurrentRow(0)
    else:
        refresh_stash_patch_view(window)


def on_stash_file_selected(window: object) -> None:
    refresh_stash_patch_view(window)


def on_stash_entry_context_menu(window: object, pos: QPoint) -> None:
    if not hasattr(window, "stash_entries_list"):
        return
    item = window.stash_entries_list.itemAt(pos)
    if item is None:
        selected = window.stash_entries_list.selectedItems()
        item = selected[0] if selected else None
    if item is None:
        return
    stash_ref_value = item.data(ROLE_PATH)
    stash_ref = str(stash_ref_value).strip() if stash_ref_value is not None else ""
    if not stash_ref:
        return
    if not item.isSelected():
        window.stash_entries_list.setCurrentItem(item)

    menu = QMenu(window.stash_entries_list)
    action_apply = menu.addAction("Aplicar")
    action_pop = menu.addAction("Aplicar e remover")
    action_drop = menu.addAction("Descartar")
    selected_action = menu.exec(window.stash_entries_list.viewport().mapToGlobal(pos))
    if selected_action is None:
        return
    if selected_action == action_apply:
        _apply_stash_ref(window, stash_ref, pop=False)
        return
    if selected_action == action_pop:
        _apply_stash_ref(window, stash_ref, pop=True)
        return
    if selected_action == action_drop:
        _drop_stash_ref(window, stash_ref)


def refresh_stash_patch_view(window: object) -> None:
    if not hasattr(window, "stash_patch_table"):
        return
    repo_path = str(getattr(window, "repo_path", "")).strip()
    stash_ref = _selected_stash_ref(window)
    if not repo_path or not stash_ref:
        render_diff_into_columns(window.stash_patch_table, "(sem stash selecionado)", show_header_lines=False)
        if hasattr(window, "stash_patch_text"):
            window.stash_patch_text.setPlainText("(sem stash selecionado)")
        _set_stash_actions_enabled(window, False)
        return
    selected_file = _selected_stash_file(window)
    word_diff = bool(
        getattr(window, "stash_word_diff_check", None) and window.stash_word_diff_check.isChecked()
    )
    try:
        patch = core_get_stash_patch(
            repo_path,
            stash_ref,
            word_diff=word_diff,
            path_for_git=selected_file,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    if hasattr(window, "stash_patch_stack"):
        window.stash_patch_stack.setCurrentIndex(0)
    render_diff_into_columns(
        window.stash_patch_table,
        patch or "",
        show_header_lines=False,
        word_diff_plain=word_diff,
    )
    _set_stash_actions_enabled(window, True)


def _sync_after_stash_change(window: object, preferred_ref: str = "") -> None:
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()
    refresh_stash_tab_visibility(window)
    if preferred_ref and _is_stash_tab_visible(window):
        _reload_stash_entries(window, preferred_ref=preferred_ref)


def create_stash_from_commit_tab(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Stash", "Selecione um repositório válido primeiro.")
        return
    selected_paths = get_selected_commit_paths(window)
    if not selected_paths:
        QMessageBox.information(window, "Stash", "Selecione ao menos um arquivo para enviar ao stash.")
        return
    try:
        core_create_stash(
            window.repo_path,
            message=STASH_MESSAGE_DEFAULT,
            include_untracked=True,
            paths=selected_paths,
        )
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    window._set_status(f"Stash criado com sucesso ({len(selected_paths)} arquivo(s)).")
    _sync_after_stash_change(window, preferred_ref="stash@{0}")
    stash_index = _stash_tab_index(window)
    if stash_index >= 0:
        window.tabs.setCurrentIndex(stash_index)


def _apply_stash_ref(window: object, stash_ref: str, *, pop: bool) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Stash", "Selecione um repositório válido primeiro.")
        return
    normalized_ref = stash_ref.strip()
    if not normalized_ref:
        QMessageBox.information(window, "Stash", "Selecione um stash.")
        return
    try:
        core_apply_stash(window.repo_path, normalized_ref, pop=pop)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    if pop:
        window._set_status(f"Stash {normalized_ref} aplicado e removido.")
        _sync_after_stash_change(window)
        return
    window._set_status(f"Stash {normalized_ref} aplicado.")
    _sync_after_stash_change(window, preferred_ref=normalized_ref)


def _drop_stash_ref(window: object, stash_ref: str) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Stash", "Selecione um repositório válido primeiro.")
        return
    normalized_ref = stash_ref.strip()
    if not normalized_ref:
        QMessageBox.information(window, "Stash", "Selecione um stash.")
        return
    confirm = QMessageBox.question(
        window,
        "Descartar stash",
        f"Deseja descartar {normalized_ref}?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if confirm != QMessageBox.StandardButton.Yes:
        return
    try:
        core_drop_stash(window.repo_path, normalized_ref)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Stash", str(exc))
        return
    window._set_status(f"Stash {normalized_ref} descartado.")
    _sync_after_stash_change(window)


def apply_selected_stash(window: object) -> None:
    _apply_stash_ref(window, _selected_stash_ref(window), pop=False)


def pop_selected_stash(window: object) -> None:
    _apply_stash_ref(window, _selected_stash_ref(window), pop=True)


def drop_selected_stash(window: object) -> None:
    _drop_stash_ref(window, _selected_stash_ref(window))


def undo_last_commit_from_commit_tab(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Undo commit", "Selecione um repositório válido primeiro.")
        return
    try:
        subject = core_get_last_commit_subject(window.repo_path)
    except RuntimeError as exc:
        QMessageBox.warning(window, "Undo commit", str(exc))
        return
    if not subject:
        QMessageBox.information(window, "Undo commit", "Nenhum commit encontrado para desfazer.")
        return
    modes = ["soft", "mixed"]
    selected_mode, accepted = QInputDialog.getItem(
        window,
        "Undo commit",
        f"Commit alvo: {subject}\nModo de reset:",
        modes,
        current=1,
        editable=False,
    )
    if not accepted or not selected_mode:
        return
    mode = str(selected_mode).strip().lower()
    try:
        core_undo_last_commit(window.repo_path, mode=mode)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Undo commit", str(exc))
        return
    window._set_status(f"Último commit desfeito ({mode}).")
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()


def select_all_commit_files(window: object) -> None:
    paths = list(window.commit_file_item_by_path.keys())
    _set_commit_paths_checked(window, paths, True)
    _sync_commit_group_check_states(window)
    window.commit_auto_stage_disabled = True
    changed = _apply_stage_state_from_selection(window, paths)
    update_commit_selection_label(window)
    if not changed:
        return
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def clear_commit_file_selection(window: object) -> None:
    paths = list(window.commit_file_item_by_path.keys())
    _set_commit_paths_checked(window, paths, False)
    _sync_commit_group_check_states(window)
    window.commit_auto_stage_disabled = True
    changed = _apply_stage_state_from_selection(window, paths)
    update_commit_selection_label(window)
    if not changed:
        return
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()


def get_selected_commit_paths(window: object) -> list[str]:
    selected: list[str] = []
    for item in _iter_commit_file_items(window):
        if item.checkState() != Qt.CheckState.Checked:
            continue
        value = item.data(ROLE_PATH)
        path = str(value).strip() if value is not None else ""
        if path:
            selected.append(path)
    return selected


def create_commit_from_selection(window: object) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositorio valido primeiro.")
        return
    title = window.commit_title_input.text().strip()
    if not title:
        QMessageBox.warning(window, "Commit", "Titulo do commit e obrigatorio.")
        return
    selected_paths = get_selected_commit_paths(window)
    if not selected_paths:
        QMessageBox.warning(window, "Commit", "Selecione ao menos um arquivo para commit.")
        return
    description = window.commit_description_input.toPlainText().strip()
    try:
        core_unstage_all(window.repo_path)
        core_stage_paths(window.repo_path, selected_paths)
        if not core_has_staged_changes(window.repo_path):
            QMessageBox.warning(window, "Commit", "Nenhuma alteracao ficou staged para commit.")
            return
        core_create_commit(window.repo_path, title, description)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        refresh_commit_files(window)
        window._refresh_repo_state_ui()
        window._refresh_workspace_tree()
        return
    window.commit_title_input.clear()
    window.commit_description_input.clear()
    window._set_status("Commit concluido.")
    refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()
