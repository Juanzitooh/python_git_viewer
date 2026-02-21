from __future__ import annotations

import os
import hashlib

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTreeWidgetItem,
)

from ...core.models import DiffData, DiffHunk, DiffLineInfo
from ...core.commit_ops import (
    apply_stash as core_apply_stash,
    apply_patch_to_index as core_apply_patch_to_index,
    apply_patch_to_worktree as core_apply_patch_to_worktree,
    create_stash as core_create_stash,
    create_commit as core_create_commit,
    discard_file_changes as core_discard_file_changes,
    drop_stash as core_drop_stash,
    get_file_patch as core_get_file_patch,
    get_last_commit_message as core_get_last_commit_message,
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
from ...core.selection_trace import trace_selection
from ..diff_columns import (
    HUNK_HEADER_ROLE,
    HUNK_INDEX_ROLE,
    LINE_INFO_ROLE,
    ROW_KIND_ROLE,
    SCOPE_ROLE,
    render_diff_into_columns,
)
from ..diff_render import install_diff_copy_shortcut, install_diff_highlighter, render_diff_into_widget
from ..theme import get_commit_status_color, get_diff_kind_color

ROLE_PATH = Qt.ItemDataRole.UserRole
ROLE_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_FOLDER = Qt.ItemDataRole.UserRole + 2

KIND_ALL = "all"
KIND_FOLDER = "folder"
KIND_FILE = "file"
STASH_MESSAGE_DEFAULT = "git_viewer"


def _line_info_to_trace_payload(line_info: DiffLineInfo | None) -> dict[str, object]:
    if not isinstance(line_info, DiffLineInfo):
        return {}
    return {
        "line_type": line_info.line_type,
        "old_line": int(line_info.old_line),
        "new_line": int(line_info.new_line),
        "line_content": line_info.content,
    }


def _trace_commit_selection_event(window: object, event: str, **fields: object) -> None:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    selected_path = str(getattr(window, "commit_selected_path", "")).strip()
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    selected_line = int(getattr(window, "commit_diff_selected_line", 0) or 0)
    payload: dict[str, object] = {
        "repo_path": repo_path,
        "selected_path": selected_path,
        "selected_scope": selected_scope,
        "selected_line": selected_line,
    }
    payload.update(fields)
    trace_selection(event, **payload)


def _check_state_to_int(state: object) -> int:
    if isinstance(state, Qt.CheckState):
        return int(state.value)
    value = getattr(state, "value", None)
    if isinstance(value, int):
        return value
    try:
        return int(state)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return int(Qt.CheckState.Unchecked.value)


def _get_commit_auto_stage_opt_out_paths(window: object) -> set[str]:
    current = getattr(window, "commit_auto_stage_opt_out_paths", None)
    if isinstance(current, set):
        return current
    paths: set[str] = set()
    setattr(window, "commit_auto_stage_opt_out_paths", paths)
    return paths


def _mark_commit_auto_stage_opt_out(window: object, paths: list[str], *, opted_out: bool) -> None:
    if not paths:
        return
    tracked = _get_commit_auto_stage_opt_out_paths(window)
    normalized = {str(path).strip() for path in paths if str(path).strip()}
    if not normalized:
        return
    if opted_out:
        tracked.update(normalized)
        return
    tracked.difference_update(normalized)


def _summarize_patch_for_trace(patch: str) -> dict[str, object]:
    payload = patch.strip()
    if not payload:
        return {"patch_hash": "", "patch_lines": 0, "patch_preview": ""}
    lines = payload.splitlines()
    preview = "\n".join(lines[:12])
    if len(lines) > 12:
        preview += "\n...(truncated)"
    return {
        "patch_hash": hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()[:12],
        "patch_lines": len(lines),
        "patch_preview": preview,
    }


def _entry_has_staged(entry: dict[str, str | bool]) -> bool:
    return bool(entry.get("staged", False))


def _entry_has_unstaged(entry: dict[str, str | bool]) -> bool:
    return bool(entry.get("unstaged", False))


def _entry_is_fully_staged(entry: dict[str, str | bool]) -> bool:
    return _entry_has_staged(entry) and not _entry_has_unstaged(entry)


def _normalize_git_path(path: str) -> str:
    normalized = str(path).strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith(("a/", "b/")):
        normalized = normalized[2:]
    return normalized


def _is_dev_null_path(path: str) -> bool:
    return _normalize_git_path(path) in {"dev/null", "/dev/null"}


def _is_phantom_dev_null_entry(repo_path: str, entry: dict[str, str | bool]) -> bool:
    normalized_path = _normalize_git_path(str(entry.get("path_for_git", "")).strip())
    if normalized_path != "dev/null":
        return False
    candidate = os.path.join(repo_path, normalized_path)
    return not os.path.exists(candidate)


def _load_commit_status_entries(window: object) -> list[dict[str, str | bool]]:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        return []
    status_entries = core_list_status_entries(repo_path)
    has_phantom_dev_null = any(_is_phantom_dev_null_entry(repo_path, entry) for entry in status_entries)
    if not has_phantom_dev_null:
        return status_entries
    _trace_commit_selection_event(
        window,
        "ui.commit.files.dev_null.cleanup.request",
    )
    try:
        core_unstage_paths(repo_path, ["dev/null"])
    except RuntimeError as exc:
        _trace_commit_selection_event(
            window,
            "ui.commit.files.dev_null.cleanup.error",
            error=str(exc),
        )
        return status_entries
    _trace_commit_selection_event(
        window,
        "ui.commit.files.dev_null.cleanup.done",
    )
    return core_list_status_entries(repo_path)


def _diff_has_dev_null_transition(diff_data: DiffData | None) -> bool:
    if not isinstance(diff_data, DiffData):
        return False
    old_path = ""
    new_path = ""
    for raw_line in diff_data.header_lines:
        line = str(raw_line).strip()
        if line.startswith("--- "):
            old_path = line[4:].strip()
        elif line.startswith("+++ "):
            new_path = line[4:].strip()
    return _is_dev_null_path(old_path) or _is_dev_null_path(new_path)


def _apply_commit_file_level_toggle(
    window: object,
    *,
    path: str,
    stage: bool,
    preserve_diff_rows: bool,
    reason: str,
) -> bool:
    if not window.repo_path:
        return False
    normalized_path = str(path).strip()
    if not normalized_path:
        return False
    status_message = "Arquivo adicionado ao stage." if stage else "Arquivo removido do stage."
    _trace_commit_selection_event(
        window,
        "ui.commit.main.file_level_toggle.request",
        path=normalized_path,
        stage=bool(stage),
        reason=reason,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    try:
        if stage:
            core_stage_paths(window.repo_path, [normalized_path])
        else:
            core_unstage_paths(window.repo_path, [normalized_path])
    except RuntimeError as exc:
        _trace_commit_selection_event(
            window,
            "ui.commit.main.file_level_toggle.error",
            path=normalized_path,
            stage=bool(stage),
            reason=reason,
            error=str(exc),
        )
        QMessageBox.critical(window, "Commit", str(exc))
        return False
    _apply_commit_stage_change_ui(
        window,
        status_message=status_message,
        path=normalized_path,
        preserve_diff_rows=preserve_diff_rows,
    )
    return True


def _sync_commit_pr_button_state(window: object, file_count: int) -> None:
    can_open_pr = bool(window.repo_path and file_count == 0)
    if hasattr(window, "commit_open_pr_button"):
        window.commit_open_pr_button.setEnabled(can_open_pr)
    if hasattr(window, "commit_empty_open_pr_button"):
        window.commit_empty_open_pr_button.setEnabled(can_open_pr)


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


def _status_entry_to_check_state(entry: dict[str, str | bool]) -> Qt.CheckState:
    if _entry_has_staged(entry) and _entry_has_unstaged(entry):
        return Qt.CheckState.PartiallyChecked
    if _entry_has_staged(entry):
        return Qt.CheckState.Checked
    return Qt.CheckState.Unchecked


def _sync_commit_path_check_state(window: object, path: str) -> None:
    normalized_path = str(path).strip()
    if not normalized_path:
        return
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    status_entries_by_path = getattr(window, "commit_status_entries_by_path", {})
    item = file_item_by_path.get(normalized_path) if isinstance(file_item_by_path, dict) else None
    if item is None:
        return
    entry = status_entries_by_path.get(normalized_path, {}) if isinstance(status_entries_by_path, dict) else {}
    state = _status_entry_to_check_state(entry if isinstance(entry, dict) else {})
    _set_commit_item_check_state(window, item, state)
    _sync_commit_group_check_states(window)
    update_commit_selection_label(window)


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
        _trace_commit_selection_event(
            window,
            "ui.commit.files.selection.noop",
            requested_paths=paths,
            stage_paths=[],
            unstage_paths=[],
        )
        return False
    _trace_commit_selection_event(
        window,
        "ui.commit.files.selection.apply.request",
        requested_paths=paths,
        stage_paths=stage_paths,
        unstage_paths=unstage_paths,
    )
    try:
        if unstage_paths:
            core_unstage_paths(repo_path, unstage_paths)
        if stage_paths:
            core_stage_paths(repo_path, stage_paths)
    except RuntimeError as exc:
        _trace_commit_selection_event(
            window,
            "ui.commit.files.selection.apply.error",
            requested_paths=paths,
            stage_paths=stage_paths,
            unstage_paths=unstage_paths,
            error=str(exc),
        )
        QMessageBox.critical(window, "Commit", str(exc))
        return False
    _trace_commit_selection_event(
        window,
        "ui.commit.files.selection.apply.done",
        requested_paths=paths,
        stage_paths=stage_paths,
        unstage_paths=unstage_paths,
    )
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


def _sync_commit_status_entries_in_place(window: object) -> bool:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    if not repo_path:
        return False
    file_item_by_path = getattr(window, "commit_file_item_by_path", {})
    if not isinstance(file_item_by_path, dict) or not file_item_by_path:
        return False
    try:
        status_entries = _load_commit_status_entries(window)
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", str(exc))
        return False

    new_by_path: dict[str, dict[str, str | bool]] = {}
    for entry in status_entries:
        path_for_git = str(entry.get("path_for_git", "")).strip()
        if path_for_git:
            new_by_path[path_for_git] = entry

    if set(new_by_path.keys()) != set(file_item_by_path.keys()):
        return False

    window.commit_status_entries_by_path = new_by_path
    previous = bool(getattr(window, "commit_syncing_checks", False))
    window.commit_syncing_checks = True
    try:
        for path, item in file_item_by_path.items():
            entry = new_by_path.get(path, {})
            item.setCheckState(_status_entry_to_check_state(entry))
    finally:
        window.commit_syncing_checks = previous
    _sync_commit_group_check_states(window)
    update_commit_selection_label(window)
    _sync_commit_pr_button_state(window, len(file_item_by_path))
    _sync_commit_stage_buttons(window)
    return True


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


def _set_commit_diff_item_check_state(window: object, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    if item.checkState(marker_column) == state:
        return
    previous = bool(getattr(window, "commit_diff_rendering", False))
    window.commit_diff_rendering = True
    try:
        item.setCheckState(marker_column, state)
    finally:
        window.commit_diff_rendering = previous


def _is_commit_diff_item_toggleable(item: QTreeWidgetItem, marker_column: int) -> bool:
    if marker_column < 0:
        return False
    try:
        flags = item.flags()
    except RuntimeError:
        return False
    return bool(flags & Qt.ItemFlag.ItemIsUserCheckable)


def _sync_commit_diff_hunk_markers(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    current_hunk_item: QTreeWidgetItem | None = None
    current_states: list[Qt.CheckState] = []

    def _flush_current_hunk() -> None:
        nonlocal current_hunk_item, current_states
        if current_hunk_item is None:
            return
        if not _is_commit_diff_item_toggleable(current_hunk_item, marker_column):
            current_hunk_item = None
            current_states = []
            return
        if not current_states:
            target = Qt.CheckState.Unchecked
        else:
            checked_count = sum(1 for state in current_states if state == Qt.CheckState.Checked)
            if checked_count <= 0:
                target = Qt.CheckState.Unchecked
            elif checked_count >= len(current_states):
                target = Qt.CheckState.Checked
            else:
                target = Qt.CheckState.PartiallyChecked
        _set_commit_diff_item_check_state(window, current_hunk_item, target)
        current_hunk_item = None
        current_states = []

    for row_index in range(window.commit_diff_view.topLevelItemCount()):
        item = window.commit_diff_view.topLevelItem(row_index)
        if item is None:
            continue
        kind_value = item.data(0, ROW_KIND_ROLE)
        kind = str(kind_value).strip() if kind_value is not None else ""
        if kind == "hunk":
            _flush_current_hunk()
            current_hunk_item = item
            current_states = []
            continue
        if kind not in {"added", "removed"}:
            continue
        if current_hunk_item is None:
            continue
        if not _is_commit_diff_item_toggleable(item, marker_column):
            continue
        current_states.append(item.checkState(marker_column))
    _flush_current_hunk()


def _set_commit_diff_hunk_line_states(
    window: object,
    *,
    hunk_row_index: int,
    scope: str,
    state: Qt.CheckState,
) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    previous = bool(getattr(window, "commit_diff_rendering", False))
    window.commit_diff_rendering = True
    try:
        if hunk_row_index < 0:
            return
        for row_index in range(hunk_row_index + 1, window.commit_diff_view.topLevelItemCount()):
            item = window.commit_diff_view.topLevelItem(row_index)
            if item is None:
                continue
            kind_value = item.data(0, ROW_KIND_ROLE)
            kind = str(kind_value).strip() if kind_value is not None else ""
            if kind == "hunk":
                break
            if kind not in {"added", "removed"}:
                continue
            item_scope_value = item.data(0, SCOPE_ROLE)
            item_scope = str(item_scope_value).strip() if item_scope_value is not None else ""
            if scope and item_scope and item_scope != scope:
                continue
            if not _is_commit_diff_item_toggleable(item, marker_column):
                continue
            item.setCheckState(marker_column, state)
    finally:
        window.commit_diff_rendering = previous


def _apply_commit_stage_change_ui(
    window: object,
    *,
    status_message: str,
    path: str,
    preserve_diff_rows: bool,
) -> None:
    normalized_status = status_message.strip().lower()
    if "adicionado ao stage" in normalized_status:
        _mark_commit_auto_stage_opt_out(window, [path], opted_out=False)
    elif "removido do stage" in normalized_status:
        _mark_commit_auto_stage_opt_out(window, [path], opted_out=True)
    _trace_commit_selection_event(
        window,
        "ui.commit.main.stage_change_ui.start",
        status_message=status_message,
        path=path,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    window._set_status(status_message)
    window.commit_selected_path = path
    if preserve_diff_rows and _sync_commit_status_entries_in_place(window):
        _sync_commit_path_check_state(window, path)
        # Mantem linhas/ordem do diff visiveis, apenas sincronizando cache e escopo.
        _refresh_commit_diff_data_cache(window, path)
        _sync_commit_diff_rows_from_cache(window, path)
        _update_commit_diff_scope_after_toggle(window)
        _sync_commit_diff_hunk_markers(window)
        _sync_commit_stage_buttons(window)
    else:
        refresh_commit_files(window)
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    _trace_commit_selection_event(
        window,
        "ui.commit.main.stage_change_ui.done",
        status_message=status_message,
        path=path,
        preserve_diff_rows=bool(preserve_diff_rows),
    )


def _sync_commit_diff_rows_from_cache(window: object, path: str) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    normalized_path = str(path).strip()
    if not normalized_path:
        return
    current_path = _current_commit_file_path(window)
    if str(current_path).strip() != normalized_path:
        return

    staged_data = _get_commit_diff_data_for_scope(window, "staged")
    unstaged_data = _get_commit_diff_data_for_scope(window, "unstaged")
    untracked_data = _get_commit_diff_data_for_scope(window, "untracked")
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))

    previous = bool(getattr(window, "commit_diff_rendering", False))
    window.commit_diff_rendering = True
    try:
        for row_index in range(window.commit_diff_view.topLevelItemCount()):
            item = window.commit_diff_view.topLevelItem(row_index)
            if item is None:
                continue
            kind_value = item.data(0, ROW_KIND_ROLE)
            kind = str(kind_value).strip() if kind_value is not None else ""
            if kind not in {"added", "removed"}:
                continue
            line_info_value = item.data(0, LINE_INFO_ROLE)
            if not isinstance(line_info_value, DiffLineInfo):
                continue
            hunk_value = item.data(0, HUNK_INDEX_ROLE)
            fallback_hunk_index = int(hunk_value) if isinstance(hunk_value, int) else None
            hunk_header_value = item.data(0, HUNK_HEADER_ROLE)
            hunk_header = str(hunk_header_value).strip() if hunk_header_value is not None else ""

            in_staged = _line_info_exists_in_diff(
                staged_data,
                line_info=line_info_value,
                hunk_header=hunk_header,
                fallback_hunk_index=fallback_hunk_index,
            )
            in_unstaged = _line_info_exists_in_diff(
                unstaged_data,
                line_info=line_info_value,
                hunk_header=hunk_header,
                fallback_hunk_index=fallback_hunk_index,
            )
            in_untracked = _line_info_exists_in_diff(
                untracked_data,
                line_info=line_info_value,
                hunk_header=hunk_header,
                fallback_hunk_index=fallback_hunk_index,
            )
            current_scope_value = item.data(0, SCOPE_ROLE)
            current_scope = str(current_scope_value).strip() if current_scope_value is not None else ""

            target_scope = ""
            if in_staged and not (in_unstaged or in_untracked):
                target_scope = "staged"
            elif (in_unstaged or in_untracked) and not in_staged:
                target_scope = "unstaged" if in_unstaged else "untracked"
            elif in_staged and (in_unstaged or in_untracked):
                target_scope = current_scope if current_scope in {"staged", "unstaged", "untracked"} else "staged"
            if not target_scope:
                continue

            item.setData(0, SCOPE_ROLE, target_scope)

            target_data = _get_commit_diff_data_for_scope(window, target_scope)
            resolved_hunk_index = _resolve_hunk_index_by_header(target_data, hunk_header, fallback_hunk_index)
            if isinstance(resolved_hunk_index, int):
                item.setData(0, HUNK_INDEX_ROLE, resolved_hunk_index)
                fallback_hunk_index = resolved_hunk_index
            resolved_line_info = _resolve_line_info_for_diff_data(
                target_data,
                source_line_info=line_info_value,
                hunk_header=hunk_header,
                fallback_hunk_index=fallback_hunk_index,
            )
            if isinstance(resolved_line_info, DiffLineInfo):
                item.setData(0, LINE_INFO_ROLE, resolved_line_info)

            if _is_commit_diff_item_toggleable(item, marker_column):
                expected = Qt.CheckState.Checked if target_scope == "staged" else Qt.CheckState.Unchecked
                item.setCheckState(marker_column, expected)

        for row_index in range(window.commit_diff_view.topLevelItemCount()):
            item = window.commit_diff_view.topLevelItem(row_index)
            if item is None:
                continue
            kind_value = item.data(0, ROW_KIND_ROLE)
            kind = str(kind_value).strip() if kind_value is not None else ""
            if kind != "hunk":
                continue
            scopes_in_hunk: set[str] = set()
            first_hunk_index: int | None = None
            for child_index in range(row_index + 1, window.commit_diff_view.topLevelItemCount()):
                child = window.commit_diff_view.topLevelItem(child_index)
                if child is None:
                    continue
                child_kind_value = child.data(0, ROW_KIND_ROLE)
                child_kind = str(child_kind_value).strip() if child_kind_value is not None else ""
                if child_kind == "hunk":
                    break
                if child_kind not in {"added", "removed"}:
                    continue
                child_scope_value = child.data(0, SCOPE_ROLE)
                child_scope = str(child_scope_value).strip() if child_scope_value is not None else ""
                if child_scope:
                    scopes_in_hunk.add(child_scope)
                child_hunk_index = child.data(0, HUNK_INDEX_ROLE)
                if first_hunk_index is None and isinstance(child_hunk_index, int):
                    first_hunk_index = child_hunk_index
            if len(scopes_in_hunk) == 1:
                item.setData(0, SCOPE_ROLE, next(iter(scopes_in_hunk)))
            if isinstance(first_hunk_index, int):
                item.setData(0, HUNK_INDEX_ROLE, first_hunk_index)
    finally:
        window.commit_diff_rendering = previous


def _is_effective_commit_change_line(window: object, scope: str, line_info: DiffLineInfo) -> bool:
    if line_info.line_type not in {"added", "removed"}:
        return False
    diff_data = _get_commit_diff_data_for_scope(window, scope)
    if not isinstance(diff_data, DiffData):
        return True
    hunk_index = int(getattr(line_info, "hunk_index", -1))
    if hunk_index < 0 or hunk_index >= len(diff_data.hunks):
        return True
    hunk = diff_data.hunks[hunk_index]
    for candidate in hunk.lines:
        if candidate.line_type not in {"added", "removed"}:
            continue
        if candidate.line_type == line_info.line_type:
            continue
        if (
            candidate.content == line_info.content
            and int(candidate.old_line) == int(line_info.old_line)
            and int(candidate.new_line) == int(line_info.new_line)
        ):
            return False
    return True


def _commit_diff_line_marker_for_scope(window: object, scope: str, line_info: DiffLineInfo) -> str:
    if line_info.line_type not in ("added", "removed"):
        return ""
    if not _is_effective_commit_change_line(window, scope, line_info):
        return ""
    if scope == "staged":
        return "[x]"
    if scope in {"unstaged", "untracked"}:
        return "[ ]"
    return "[~]"


def _commit_diff_hunk_marker_for_scope(window: object, scope: str, _hunk_index: int, hunk: DiffHunk) -> str:
    has_changes = any(_is_effective_commit_change_line(window, scope, line) for line in hunk.lines)
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


def _acquire_commit_diff_action_lock(window: object) -> bool:
    if bool(getattr(window, "commit_diff_action_inflight", False)):
        return False
    window.commit_diff_action_inflight = True
    if hasattr(window, "commit_diff_view"):
        window.commit_diff_view.setEnabled(False)
    return True


def _release_commit_diff_action_lock(window: object) -> None:
    window.commit_diff_action_inflight = False
    if hasattr(window, "commit_diff_view"):
        window.commit_diff_view.setEnabled(True)


def _refresh_commit_diff_data_cache(window: object, path: str) -> None:
    if not getattr(window, "repo_path", ""):
        window.commit_diff_data_by_scope = {}
        window.commit_diff_scope = ""
        window.commit_current_patch = ""
        window.commit_diff_data = None
        return
    preferred_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    try:
        patches_by_scope = _load_commit_patches_by_scope(
            window,
            path,
            word_diff=bool(getattr(window, "commit_word_diff_check", None) and window.commit_word_diff_check.isChecked()),
            preferred_scope=preferred_scope,
        )
    except RuntimeError:
        # Mantem o cache anterior caso o patch momentaneamente falhe.
        return
    new_by_scope: dict[str, DiffData] = {}
    for scope, patch in patches_by_scope:
        new_by_scope[scope] = parse_diff_data(
            patch,
            word_diff_plain=bool(
                getattr(window, "commit_word_diff_check", None) and window.commit_word_diff_check.isChecked()
            ),
        )
    window.commit_diff_data_by_scope = new_by_scope
    if not patches_by_scope:
        window.commit_diff_scope = ""
        window.commit_current_patch = ""
        window.commit_diff_data = None
        return
    window.commit_diff_scope = patches_by_scope[0][0] if len(patches_by_scope) == 1 else "mixed"
    window.commit_current_patch = "\n".join(section_patch for _scope, section_patch in patches_by_scope)
    _sync_active_commit_diff_data(window)


def _diff_line_anchor(line_info: DiffLineInfo) -> int:
    if line_info.line_type == "removed":
        return int(line_info.old_line)
    return int(line_info.new_line)


def _resolve_hunk_index_by_header(
    diff_data: DiffData | None,
    hunk_header: str,
    fallback_index: int | None,
) -> int | None:
    if not isinstance(diff_data, DiffData):
        return None
    normalized_header = str(hunk_header).strip()
    fallback_valid = isinstance(fallback_index, int) and 0 <= fallback_index < len(diff_data.hunks)
    if fallback_valid:
        fallback_header = diff_data.hunks[fallback_index].header.strip()
        if normalized_header and fallback_header == normalized_header:
            return fallback_index
    if normalized_header:
        matched_indices = [
            index for index, hunk in enumerate(diff_data.hunks) if hunk.header.strip() == normalized_header
        ]
        if matched_indices:
            if fallback_valid and fallback_index in matched_indices:
                return fallback_index
            if fallback_valid:
                return min(matched_indices, key=lambda index: abs(index - int(fallback_index)))
            return matched_indices[0]
    if fallback_valid:
        return int(fallback_index)
    return None


def _resolve_line_info_in_diff(
    diff_data: DiffData | None,
    *,
    source_line_info: DiffLineInfo | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
) -> tuple[int | None, DiffLineInfo | None]:
    if not isinstance(source_line_info, DiffLineInfo):
        return (fallback_hunk_index, None)
    if not isinstance(diff_data, DiffData):
        return (fallback_hunk_index, None)
    target_hunk_index = _resolve_hunk_index_by_header(diff_data, hunk_header, fallback_hunk_index)
    source_anchor = _diff_line_anchor(source_line_info)
    best_score: int | None = None
    best_hunk: int | None = None
    best_line: DiffLineInfo | None = None

    candidate_hunks: list[tuple[int, DiffHunk]]
    if isinstance(target_hunk_index, int):
        candidate_hunks = [(target_hunk_index, diff_data.hunks[target_hunk_index])]
    else:
        candidate_hunks = list(enumerate(diff_data.hunks))

    for hunk_index, hunk in candidate_hunks:
        for line_info in hunk.lines:
            if line_info.line_type != source_line_info.line_type:
                continue
            if line_info.content != source_line_info.content:
                continue
            score = abs(_diff_line_anchor(line_info) - source_anchor)
            if best_score is None or score < best_score:
                best_score = score
                best_hunk = hunk_index
                best_line = line_info
                if score == 0:
                    return (best_hunk, best_line)
    if best_line is not None:
        return (best_hunk, best_line)
    return (target_hunk_index, None)


def _resolve_line_info_for_scope(
    window: object,
    *,
    target_scope: str,
    source_line_info: DiffLineInfo | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
) -> tuple[int | None, DiffLineInfo | None]:
    if not isinstance(source_line_info, DiffLineInfo):
        return (fallback_hunk_index, None)
    diff_data = _get_commit_diff_data_for_scope(window, target_scope)
    return _resolve_line_info_in_diff(
        diff_data,
        source_line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=fallback_hunk_index,
    )


def _line_info_exists_in_diff(
    diff_data: DiffData | None,
    *,
    line_info: DiffLineInfo | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
) -> bool:
    if not isinstance(diff_data, DiffData) or not isinstance(line_info, DiffLineInfo):
        return False
    target_hunk_index = _resolve_hunk_index_by_header(diff_data, hunk_header, fallback_hunk_index)
    candidate_hunks: list[DiffHunk]
    if isinstance(target_hunk_index, int) and 0 <= target_hunk_index < len(diff_data.hunks):
        candidate_hunks = [diff_data.hunks[target_hunk_index]]
    else:
        candidate_hunks = list(diff_data.hunks)
    for hunk in candidate_hunks:
        for current in hunk.lines:
            if (
                current.line_type == line_info.line_type
                and int(current.old_line) == int(line_info.old_line)
                and int(current.new_line) == int(line_info.new_line)
                and current.content == line_info.content
            ):
                return True
    return False


def _resolve_line_info_for_diff_data(
    diff_data: DiffData | None,
    *,
    source_line_info: DiffLineInfo | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
) -> DiffLineInfo | None:
    if not isinstance(diff_data, DiffData) or not isinstance(source_line_info, DiffLineInfo):
        return None
    if _line_info_exists_in_diff(
        diff_data,
        line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=fallback_hunk_index,
    ):
        return source_line_info
    _resolved_hunk_index, resolved_line_info = _resolve_line_info_in_diff(
        diff_data,
        source_line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=fallback_hunk_index,
    )
    return resolved_line_info if isinstance(resolved_line_info, DiffLineInfo) else None


def _hunk_changed_signature(lines: list[DiffLineInfo]) -> tuple[tuple[str, str], ...]:
    return tuple((line.line_type, line.content) for line in lines if line.line_type in {"added", "removed"})


def _collect_hunk_changed_signature_from_view(window: object, hunk_row_index: int, scope: str) -> tuple[tuple[str, str], ...]:
    if not hasattr(window, "commit_diff_view") or hunk_row_index < 0:
        return ()
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    signature: list[tuple[str, str]] = []
    for row_index in range(hunk_row_index + 1, window.commit_diff_view.topLevelItemCount()):
        item = window.commit_diff_view.topLevelItem(row_index)
        if item is None:
            continue
        kind_value = item.data(0, ROW_KIND_ROLE)
        kind = str(kind_value).strip() if kind_value is not None else ""
        if kind == "hunk":
            break
        if kind not in {"added", "removed"}:
            continue
        item_scope_value = item.data(0, SCOPE_ROLE)
        item_scope = str(item_scope_value).strip() if item_scope_value is not None else ""
        if scope and item_scope and item_scope != scope:
            continue
        if not _is_commit_diff_item_toggleable(item, marker_column):
            continue
        line_info_value = item.data(0, LINE_INFO_ROLE)
        if isinstance(line_info_value, DiffLineInfo):
            signature.append((line_info_value.line_type, line_info_value.content))
    return tuple(signature)


def _resolve_hunk_index_for_row_snapshot(
    window: object,
    diff_data: DiffData | None,
    *,
    hunk_header: str,
    fallback_hunk_index: int | None,
    hunk_row_index: int,
    row_scope: str,
) -> int | None:
    if not isinstance(diff_data, DiffData):
        return None

    view_signature = _collect_hunk_changed_signature_from_view(window, hunk_row_index, row_scope)
    if view_signature:
        exact_matches: list[int] = []
        for index, hunk in enumerate(diff_data.hunks):
            if _hunk_changed_signature(hunk.lines) == view_signature:
                exact_matches.append(index)
        if exact_matches:
            if isinstance(fallback_hunk_index, int) and fallback_hunk_index in exact_matches:
                return fallback_hunk_index
            normalized_header = str(hunk_header).strip()
            if normalized_header:
                for index in exact_matches:
                    if diff_data.hunks[index].header.strip() == normalized_header:
                        return index
            return exact_matches[0]

    return _resolve_hunk_index_by_header(diff_data, hunk_header, fallback_hunk_index)


def _collect_hunk_candidate_indices_for_snapshot(
    window: object,
    diff_data: DiffData | None,
    *,
    resolved_hunk_index: int | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
    hunk_row_index: int,
    row_scope: str,
) -> list[int]:
    if not isinstance(diff_data, DiffData):
        return []
    candidates: list[int] = []

    def _add(index_value: int | None) -> None:
        if not isinstance(index_value, int):
            return
        if index_value < 0 or index_value >= len(diff_data.hunks):
            return
        if index_value not in candidates:
            candidates.append(index_value)

    _add(resolved_hunk_index)
    _add(fallback_hunk_index)

    normalized_header = str(hunk_header).strip()
    if normalized_header:
        for index, hunk in enumerate(diff_data.hunks):
            if hunk.header.strip() == normalized_header:
                _add(index)

    view_signature = _collect_hunk_changed_signature_from_view(window, hunk_row_index, row_scope)
    if view_signature:
        for index, hunk in enumerate(diff_data.hunks):
            if _hunk_changed_signature(hunk.lines) == view_signature:
                _add(index)

    return candidates


def _collect_line_candidates_for_diff_data(
    diff_data: DiffData | None,
    *,
    source_line_info: DiffLineInfo | None,
    hunk_header: str,
    fallback_hunk_index: int | None,
) -> list[DiffLineInfo]:
    if not isinstance(diff_data, DiffData) or not isinstance(source_line_info, DiffLineInfo):
        return []
    candidates: list[DiffLineInfo] = []
    seen: set[tuple[str, int, int, str]] = set()

    def _add(line_info: DiffLineInfo | None) -> None:
        if not isinstance(line_info, DiffLineInfo):
            return
        key = (
            line_info.line_type,
            int(line_info.old_line),
            int(line_info.new_line),
            line_info.content,
        )
        if key in seen:
            return
        seen.add(key)
        candidates.append(line_info)

    resolved_line = _resolve_line_info_for_diff_data(
        diff_data,
        source_line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=fallback_hunk_index,
    )
    _add(resolved_line)
    if _line_info_exists_in_diff(
        diff_data,
        line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=fallback_hunk_index,
    ):
        _add(source_line_info)

    target_hunk_index = _resolve_hunk_index_by_header(diff_data, hunk_header, fallback_hunk_index)
    candidate_hunks: list[DiffHunk]
    if isinstance(target_hunk_index, int) and 0 <= target_hunk_index < len(diff_data.hunks):
        candidate_hunks = [diff_data.hunks[target_hunk_index]]
    else:
        candidate_hunks = list(diff_data.hunks)

    source_anchor = _diff_line_anchor(source_line_info)
    same_content_pool: list[DiffLineInfo] = []
    fallback_pool: list[DiffLineInfo] = []
    for hunk in candidate_hunks:
        for line_info in hunk.lines:
            if line_info.line_type != source_line_info.line_type:
                continue
            if line_info.content == source_line_info.content:
                same_content_pool.append(line_info)
            else:
                fallback_pool.append(line_info)

    same_content_pool.sort(key=lambda line_info: abs(_diff_line_anchor(line_info) - source_anchor))
    fallback_pool.sort(key=lambda line_info: abs(_diff_line_anchor(line_info) - source_anchor))
    for line_info in same_content_pool:
        _add(line_info)
    if not candidates:
        for line_info in fallback_pool:
            _add(line_info)
    return candidates


def _resolve_selected_commit_line_for_scope(window: object, target_scope: str) -> DiffLineInfo | None:
    source_line_info = _selected_commit_line_info(window)
    if not isinstance(source_line_info, DiffLineInfo):
        return None
    hunk_header = _selected_commit_hunk_header(window)
    hunk_index = _selected_commit_hunk_index(window)
    _resolved_hunk_index, line_info = _resolve_line_info_for_scope(
        window,
        target_scope=target_scope,
        source_line_info=source_line_info,
        hunk_header=hunk_header,
        fallback_hunk_index=hunk_index,
    )
    if isinstance(line_info, DiffLineInfo):
        return line_info

    # Retry rapido: atualiza cache e tenta de novo sem rebuild visual.
    path = _current_commit_file_path(window)
    if path:
        _refresh_commit_diff_data_cache(window, path)
        _resolved_hunk_index, line_info = _resolve_line_info_for_scope(
            window,
            target_scope=target_scope,
            source_line_info=source_line_info,
            hunk_header=hunk_header,
            fallback_hunk_index=hunk_index,
        )
        if isinstance(line_info, DiffLineInfo):
            return line_info
    return None


def _load_operation_diff_data_for_scope(window: object, path: str, scope: str) -> DiffData | None:
    repo_path = str(getattr(window, "repo_path", "")).strip()
    normalized_path = str(path).strip()
    normalized_scope = str(scope).strip()
    if not repo_path or not normalized_path or normalized_scope not in {"staged", "unstaged", "untracked"}:
        return None
    entry = window.commit_status_entries_by_path.get(normalized_path, {})
    status_code = str(entry.get("status", "")).strip()
    untracked = status_code == "??"
    try:
        patch = core_get_file_patch(
            repo_path,
            normalized_path,
            word_diff=False,
            cached=(normalized_scope == "staged"),
            untracked=(normalized_scope in {"unstaged", "untracked"} and untracked),
        )
    except RuntimeError:
        return None
    if not patch.strip():
        return None
    return parse_diff_data(patch, word_diff_plain=False)


def _update_commit_diff_scope_after_toggle(window: object) -> None:
    if not hasattr(window, "commit_diff_view"):
        return
    current_item = window.commit_diff_view.currentItem()
    if current_item is None:
        return
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    item_state = current_item.checkState(marker_column)
    if item_state == Qt.CheckState.Checked:
        target_scope = "staged"
    elif item_state == Qt.CheckState.Unchecked:
        target_scope = "unstaged"
    else:
        return
    scope_value = current_item.data(0, SCOPE_ROLE)
    current_scope = str(scope_value).strip() if scope_value is not None else ""
    if current_scope not in {"staged", "unstaged", "untracked"}:
        return
    if current_scope == target_scope:
        return

    kind_value = current_item.data(0, ROW_KIND_ROLE)
    kind = str(kind_value).strip() if kind_value is not None else ""
    hunk_value = current_item.data(0, HUNK_INDEX_ROLE)
    hunk_index = int(hunk_value) if isinstance(hunk_value, int) else None
    hunk_header_value = current_item.data(0, HUNK_HEADER_ROLE)
    hunk_header = str(hunk_header_value).strip() if hunk_header_value is not None else ""
    target_diff_data = _get_commit_diff_data_for_scope(window, target_scope)
    target_hunk_index = _resolve_hunk_index_by_header(target_diff_data, hunk_header, hunk_index)
    if (
        target_hunk_index is None
        and isinstance(target_diff_data, DiffData)
        and len(target_diff_data.hunks) == 1
    ):
        target_hunk_index = 0
    target_hunk_header = ""
    if (
        isinstance(target_diff_data, DiffData)
        and isinstance(target_hunk_index, int)
        and 0 <= target_hunk_index < len(target_diff_data.hunks)
    ):
        target_hunk_header = target_diff_data.hunks[target_hunk_index].header

    previous = bool(getattr(window, "commit_diff_rendering", False))
    window.commit_diff_rendering = True
    try:
        if kind == "hunk" and isinstance(hunk_index, int):
            for row_index in range(window.commit_diff_view.topLevelItemCount()):
                item = window.commit_diff_view.topLevelItem(row_index)
                if item is None:
                    continue
                item_kind_value = item.data(0, ROW_KIND_ROLE)
                item_kind = str(item_kind_value).strip() if item_kind_value is not None else ""
                if item_kind not in {"hunk", "added", "removed", "context"}:
                    continue
                item_hunk = item.data(0, HUNK_INDEX_ROLE)
                if not isinstance(item_hunk, int) or item_hunk != hunk_index:
                    continue
                item_scope_value = item.data(0, SCOPE_ROLE)
                item_scope = str(item_scope_value).strip() if item_scope_value is not None else ""
                if item_scope != current_scope:
                    continue
                item.setData(0, SCOPE_ROLE, target_scope)
                if isinstance(target_hunk_index, int):
                    item.setData(0, HUNK_INDEX_ROLE, target_hunk_index)
                    if target_hunk_header:
                        item.setData(0, HUNK_HEADER_ROLE, target_hunk_header)
                if item_kind in {"added", "removed"}:
                    source_line_info = item.data(0, LINE_INFO_ROLE)
                    source_info = source_line_info if isinstance(source_line_info, DiffLineInfo) else None
                    line_hunk_index, target_line_info = _resolve_line_info_for_scope(
                        window,
                        target_scope=target_scope,
                        source_line_info=source_info,
                        hunk_header=hunk_header,
                        fallback_hunk_index=target_hunk_index,
                    )
                    if not isinstance(target_hunk_index, int) and isinstance(line_hunk_index, int):
                        target_hunk_index = line_hunk_index
                        if (
                            isinstance(target_diff_data, DiffData)
                            and 0 <= target_hunk_index < len(target_diff_data.hunks)
                        ):
                            target_hunk_header = target_diff_data.hunks[target_hunk_index].header
                    if isinstance(target_hunk_index, int):
                        item.setData(0, HUNK_INDEX_ROLE, target_hunk_index)
                        if target_hunk_header:
                            item.setData(0, HUNK_HEADER_ROLE, target_hunk_header)
                    elif isinstance(line_hunk_index, int):
                        item.setData(0, HUNK_INDEX_ROLE, line_hunk_index)
                    if isinstance(target_line_info, DiffLineInfo):
                        item.setData(0, LINE_INFO_ROLE, target_line_info)
                    item.setCheckState(marker_column, item_state)
            current_item.setData(0, SCOPE_ROLE, target_scope)
            if isinstance(target_hunk_index, int):
                current_item.setData(0, HUNK_INDEX_ROLE, target_hunk_index)
                if target_hunk_header:
                    current_item.setData(0, HUNK_HEADER_ROLE, target_hunk_header)
            current_item.setCheckState(marker_column, item_state)
        elif kind in {"added", "removed"}:
            current_item.setData(0, SCOPE_ROLE, target_scope)
            source_line_info = current_item.data(0, LINE_INFO_ROLE)
            source_info = source_line_info if isinstance(source_line_info, DiffLineInfo) else None
            line_hunk_index, target_line_info = _resolve_line_info_for_scope(
                window,
                target_scope=target_scope,
                source_line_info=source_info,
                hunk_header=hunk_header,
                fallback_hunk_index=target_hunk_index,
            )
            if isinstance(line_hunk_index, int):
                current_item.setData(0, HUNK_INDEX_ROLE, line_hunk_index)
            if isinstance(target_line_info, DiffLineInfo):
                current_item.setData(0, LINE_INFO_ROLE, target_line_info)
            current_item.setCheckState(marker_column, item_state)
    finally:
        window.commit_diff_rendering = previous
    _sync_commit_diff_hunk_markers(window)
    _sync_active_commit_diff_data(window)


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


def _sync_commit_empty_state(window: object, *, has_changes: bool) -> None:
    stack = getattr(window, "commit_stack", None)
    main_page = getattr(window, "commit_main_page", None)
    empty_page = getattr(window, "commit_empty_page", None)
    has_repo = bool(str(getattr(window, "repo_path", "")).strip())
    show_empty = has_repo and not has_changes

    if stack is not None and main_page is not None and empty_page is not None:
        target = empty_page if show_empty else main_page
        if stack.currentWidget() is not target:
            stack.setCurrentWidget(target)

    open_readme_button = getattr(window, "commit_open_readme_button", None)
    if open_readme_button is not None:
        open_readme_button.setEnabled(has_repo)
    empty_undo_button = getattr(window, "commit_empty_undo_button", None)
    if empty_undo_button is not None:
        empty_undo_button.setEnabled(has_repo)
    empty_open_pr_button = getattr(window, "commit_empty_open_pr_button", None)
    if empty_open_pr_button is not None:
        empty_open_pr_button.setEnabled(has_repo and not has_changes)

    title_label = getattr(window, "commit_empty_title_label", None)
    hint_label = getattr(window, "commit_empty_hint_label", None)
    if title_label is not None:
        if has_repo:
            repo_name = os.path.basename(str(getattr(window, "repo_path", "")).rstrip("/")) or "repositorio"
            title_label.setText(f"Worktree limpo: {repo_name}")
        else:
            title_label.setText("Selecione um repositorio")
    if hint_label is not None:
        if has_repo:
            hint_label.setText(
                "Nao ha mudancas para commitar. Abra o README no VS Code para continuar editando este repositorio."
            )
        else:
            hint_label.setText("Selecione um repositorio para visualizar e commitar mudancas.")


def refresh_commit_files(window: object) -> None:
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
    auto_stage_opt_out_paths = _get_commit_auto_stage_opt_out_paths(window)
    if repo_switched:
        window.commit_diff_scope_by_path = {}
        window.commit_last_diff_path = ""
        auto_stage_opt_out_paths.clear()
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
        auto_stage_opt_out_paths.clear()
        _sync_commit_empty_state(window, has_changes=False)
        update_commit_selection_label(window)
        return
    try:
        status_entries = _load_commit_status_entries(window)
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
        _sync_commit_empty_state(window, has_changes=False)
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
    tracked_paths = set(window.commit_status_entries_by_path.keys())
    auto_stage_opt_out_paths.intersection_update(tracked_paths)
    auto_stage_targets: list[str] = []
    for path_for_git, entry in window.commit_status_entries_by_path.items():
        if path_for_git in auto_stage_opt_out_paths:
            continue
        if not _entry_is_fully_staged(entry):
            auto_stage_targets.append(path_for_git)
    should_auto_stage = bool(auto_stage_targets)
    if should_auto_stage:
        try:
            core_stage_paths(window.repo_path, auto_stage_targets)
        except RuntimeError as exc:
            window.commit_files_list.blockSignals(False)
            QMessageBox.critical(window, "Commit", str(exc))
            return
        window.commit_files_list.blockSignals(False)
        if len(auto_stage_targets) == 1:
            window._set_status(f"Arquivo stageado automaticamente: {auto_stage_targets[0]}")
        else:
            window._set_status(f"{len(auto_stage_targets)} arquivos stageados automaticamente.")
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
    _sync_commit_empty_state(window, has_changes=bool(window.commit_file_item_by_path))
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
    if affected_paths:
        state = item.checkState()
        if state == Qt.CheckState.Checked:
            _mark_commit_auto_stage_opt_out(window, affected_paths, opted_out=False)
        elif state == Qt.CheckState.Unchecked:
            _mark_commit_auto_stage_opt_out(window, affected_paths, opted_out=True)
    _trace_commit_selection_event(
        window,
        "ui.commit.files.item_changed",
        item_kind=kind,
        item_state=_check_state_to_int(item.checkState()),
        affected_paths=affected_paths,
        selected_path_before=selected_path,
    )
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


def on_commit_file_double_clicked(window: object, item: QListWidgetItem) -> None:
    if not window.repo_path or item is None:
        return
    if _commit_item_kind(item) != KIND_FILE:
        return
    path_value = item.data(ROLE_PATH)
    file_path = str(path_value).strip() if path_value is not None else ""
    if not file_path:
        return
    window._open_repo_file_in_vscode(file_path)


def on_commit_file_context_menu(window: object, pos: QPoint) -> None:
    if not hasattr(window, "commit_files_list"):
        return
    item = window.commit_files_list.itemAt(pos)
    if item is None:
        selected_items = window.commit_files_list.selectedItems()
        item = selected_items[-1] if selected_items else None
    if item is None:
        return
    kind_value = item.data(ROLE_KIND)
    kind = str(kind_value).strip() if kind_value is not None else ""
    path_value = item.data(ROLE_PATH)
    file_path = str(path_value).strip() if path_value is not None else ""
    if kind != KIND_FILE or not file_path:
        return

    menu = QMenu(window.commit_files_list)
    action_open_vscode = menu.addAction("Abrir arquivo no VS Code")
    action_open_folder = menu.addAction("Abrir na pasta")
    action_copy_relative = menu.addAction("Copiar caminho relativo")
    menu.addSeparator()
    action_revert_file = menu.addAction("Reverter alteracoes do arquivo")

    selected_action = menu.exec(window.commit_files_list.viewport().mapToGlobal(pos))
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
    if selected_action == action_revert_file:
        confirm = QMessageBox.question(
            window,
            "Commit",
            (
                f"Reverter alteracoes locais do arquivo?\n\n"
                f"{file_path}\n\n"
                "Esta acao remove alteracoes staged/unstaged deste arquivo."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            core_discard_file_changes(window.repo_path, file_path)
        except RuntimeError as exc:
            QMessageBox.critical(window, "Commit", str(exc))
            return
        refresh_commit_files(window)
        window._refresh_repo_state_ui()
        window._refresh_workspace_tree()
        window._set_status(f"Arquivo revertido: {file_path}")


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
                    window, current_scope, info
                ),
                hunk_marker_resolver=lambda idx, hunk, current_scope=scope: _commit_diff_hunk_marker_for_scope(
                    window, current_scope, idx, hunk
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
    _sync_commit_diff_hunk_markers(window)
    _sync_active_commit_diff_data(window)
    window.commit_current_patch = "\n".join(section_patch for _scope, section_patch in patches_by_scope)
    _sync_commit_stage_buttons(window)


def _set_diff_text_with_kinds(widget: QPlainTextEdit, text: str, line_kinds: list[str]) -> None:
    install_diff_copy_shortcut(widget)
    highlighter = install_diff_highlighter(widget)
    widget.setPlainText(text)
    highlighter.set_line_kinds(line_kinds)




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


def _selected_commit_hunk_header(window: object) -> str:
    if not hasattr(window, "commit_diff_view"):
        return ""
    current_item = window.commit_diff_view.currentItem()
    if current_item is None:
        return ""
    value = current_item.data(0, HUNK_HEADER_ROLE)
    return str(value).strip() if value is not None else ""


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


def _selected_commit_editor_line(window: object) -> int:
    line_info = _selected_commit_line_info(window)
    if not isinstance(line_info, DiffLineInfo):
        return 0
    if int(line_info.new_line) > 0:
        return int(line_info.new_line)
    if int(line_info.old_line) > 0:
        return int(line_info.old_line)
    return 0


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
    try:
        row_index = window.commit_diff_view.indexOfTopLevelItem(item)
    except RuntimeError:
        return
    if row_index < 0:
        return
    window.commit_diff_selected_line = row_index + 1
    _sync_commit_stage_buttons(window)


def on_commit_diff_item_double_clicked(window: object, item: object, column: int) -> None:
    if not window.repo_path or item is None:
        return
    try:
        row_index = window.commit_diff_view.indexOfTopLevelItem(item)
    except RuntimeError:
        return
    if row_index < 0:
        return
    window.commit_diff_selected_line = row_index + 1
    line_info_value = item.data(0, LINE_INFO_ROLE)
    if not isinstance(line_info_value, DiffLineInfo):
        return
    line_no = int(line_info_value.new_line) if int(line_info_value.new_line) > 0 else int(line_info_value.old_line)
    if line_no <= 0:
        return
    path = _current_commit_file_path(window)
    if not path:
        return
    window._open_repo_file_in_vscode(path, line_no=line_no)


def _toggle_commit_diff_row_from_snapshot(
    window: object,
    *,
    path: str,
    row_index: int,
    row_kind: str,
    row_scope: str,
    checked_state: Qt.CheckState,
    hunk_index: int | None,
    hunk_header: str,
    line_info: DiffLineInfo | None,
    preserve_diff_rows: bool,
) -> None:
    if not window.repo_path:
        return
    effective_path = path.strip() if isinstance(path, str) else ""
    if not effective_path:
        effective_path = _current_commit_file_path(window)
    if not effective_path:
        return
    if row_scope not in {"staged", "unstaged", "untracked"}:
        return
    if checked_state == Qt.CheckState.PartiallyChecked:
        return
    should_unstage = row_scope == "staged" and checked_state == Qt.CheckState.Unchecked
    should_stage = row_scope in {"unstaged", "untracked"} and checked_state == Qt.CheckState.Checked
    if not should_stage and not should_unstage:
        _trace_commit_selection_event(
            window,
            "ui.commit.main.snapshot_toggle.noop",
            path=effective_path,
            row_kind=row_kind,
            row_scope=row_scope,
            checked_state=_check_state_to_int(checked_state),
        )
        return

    patch = ""
    patch_candidates: list[str] = []
    reverse = should_unstage
    status_message = ""
    if row_kind == "hunk":
        source_scope = "staged" if reverse else "unstaged"
        diff_data = _load_operation_diff_data_for_scope(window, effective_path, source_scope)
        if diff_data is None:
            diff_data = _get_commit_diff_data_for_scope(window, source_scope)
        if _diff_has_dev_null_transition(diff_data):
            _apply_commit_file_level_toggle(
                window,
                path=effective_path,
                stage=not reverse,
                preserve_diff_rows=preserve_diff_rows,
                reason="dev_null_hunk",
            )
            return
        resolved_hunk_index = _resolve_hunk_index_for_row_snapshot(
            window,
            diff_data,
            hunk_header=hunk_header,
            fallback_hunk_index=hunk_index,
            hunk_row_index=row_index,
            row_scope=row_scope,
        )
        if not isinstance(diff_data, DiffData) or resolved_hunk_index is None:
            return
        candidate_hunk_indices = _collect_hunk_candidate_indices_for_snapshot(
            window,
            diff_data,
            resolved_hunk_index=resolved_hunk_index,
            hunk_header=hunk_header,
            fallback_hunk_index=hunk_index,
            hunk_row_index=row_index,
            row_scope=row_scope,
        )
        for candidate_index in candidate_hunk_indices:
            candidate_patch = build_patch_for_hunk(diff_data, candidate_index) or ""
            if not candidate_patch.strip():
                continue
            if candidate_patch in patch_candidates:
                continue
            patch_candidates.append(candidate_patch)
        patch = patch_candidates[0] if patch_candidates else ""
        status_message = "Bloco removido do stage." if reverse else "Bloco adicionado ao stage."
    elif row_kind in {"added", "removed"} and isinstance(line_info, DiffLineInfo):
        source_scope = "staged" if reverse else "unstaged"
        diff_data = _load_operation_diff_data_for_scope(window, effective_path, source_scope)
        if diff_data is None:
            diff_data = _get_commit_diff_data_for_scope(window, source_scope)
        if _diff_has_dev_null_transition(diff_data):
            _apply_commit_file_level_toggle(
                window,
                path=effective_path,
                stage=not reverse,
                preserve_diff_rows=preserve_diff_rows,
                reason="dev_null_line",
            )
            return
        resolved_line_info = _resolve_line_info_for_diff_data(
            diff_data,
            source_line_info=line_info,
            hunk_header=hunk_header,
            fallback_hunk_index=hunk_index,
        )
        if not isinstance(diff_data, DiffData) or not isinstance(resolved_line_info, DiffLineInfo):
            return
        line_candidates = _collect_line_candidates_for_diff_data(
            diff_data,
            source_line_info=line_info,
            hunk_header=hunk_header,
            fallback_hunk_index=hunk_index,
        )
        for candidate_line in line_candidates:
            candidate_patch = build_patch_for_line(diff_data, candidate_line) or ""
            if not candidate_patch.strip():
                continue
            if candidate_patch in patch_candidates:
                continue
            patch_candidates.append(candidate_patch)
        patch = patch_candidates[0] if patch_candidates else ""
        status_message = "Linha removida do stage." if reverse else "Linha adicionada ao stage."
    else:
        return

    if not patch.strip():
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.snapshot_toggle.request",
        path=effective_path,
        row_kind=row_kind,
        row_scope=row_scope,
        checked_state=_check_state_to_int(checked_state),
        reverse=bool(reverse),
        preserve_diff_rows=bool(preserve_diff_rows),
        hunk_index=hunk_index,
        hunk_header=hunk_header,
        **_line_info_to_trace_payload(line_info),
    )
    last_error: RuntimeError | None = None
    applied = False
    candidates = patch_candidates or [patch]
    for candidate_patch in candidates:
        try:
            core_apply_patch_to_index(window.repo_path, candidate_patch, reverse=reverse)
            patch = candidate_patch
            applied = True
            break
        except RuntimeError as exc:
            last_error = exc
            continue
    if not applied:
        exc = last_error if isinstance(last_error, RuntimeError) else RuntimeError("Falha ao aplicar patch.")
        _trace_commit_selection_event(
            window,
            "ui.commit.main.snapshot_toggle.error",
            path=effective_path,
            row_kind=row_kind,
            row_scope=row_scope,
            checked_state=_check_state_to_int(checked_state),
            reverse=bool(reverse),
            error=str(exc),
        )
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message=status_message,
        path=effective_path,
        preserve_diff_rows=preserve_diff_rows,
    )


def on_commit_diff_item_changed(window: object, item: object, column: int) -> None:
    if not window.repo_path or not hasattr(window, "commit_diff_view"):
        return
    if bool(getattr(window, "commit_diff_rendering", False)):
        return
    try:
        _ = item.treeWidget()
    except RuntimeError:
        return
    marker_column = int(getattr(window.commit_diff_view, "_marker_column", 0))
    if column != marker_column:
        return
    try:
        row_index = window.commit_diff_view.indexOfTopLevelItem(item)
    except RuntimeError:
        return
    if row_index < 0:
        return
    if not _is_commit_diff_item_toggleable(item, marker_column):
        return
    kind_value = item.data(0, ROW_KIND_ROLE)
    kind = str(kind_value).strip() if kind_value is not None else ""
    if kind not in {"hunk", "added", "removed"}:
        return
    scope_value = item.data(0, SCOPE_ROLE)
    row_scope = str(scope_value).strip() if scope_value is not None else ""
    checked_state = item.checkState(marker_column)
    line_info_value = item.data(0, LINE_INFO_ROLE)
    line_info = line_info_value if isinstance(line_info_value, DiffLineInfo) else None
    _trace_commit_selection_event(
        window,
        "ui.commit.main.item_changed",
        row_index=row_index + 1,
        marker_column=marker_column,
        row_scope=row_scope,
        row_kind=kind,
        checked_state=_check_state_to_int(checked_state),
        hunk_index=item.data(0, HUNK_INDEX_ROLE),
        **_line_info_to_trace_payload(line_info),
    )
    if checked_state == Qt.CheckState.PartiallyChecked:
        window.commit_diff_selected_line = row_index + 1
        _sync_commit_diff_hunk_markers(window)
        _sync_commit_stage_buttons(window)
        return
    if kind == "hunk":
        _set_commit_diff_hunk_line_states(
            window,
            hunk_row_index=row_index,
            scope=row_scope,
            state=checked_state,
        )
    window.commit_diff_selected_line = row_index + 1
    window.commit_diff_view.setCurrentItem(item)
    _sync_commit_diff_hunk_markers(window)

    hunk_value = item.data(0, HUNK_INDEX_ROLE)
    hunk_index = int(hunk_value) if isinstance(hunk_value, int) else None
    hunk_header_value = item.data(0, HUNK_HEADER_ROLE)
    hunk_header = str(hunk_header_value).strip() if hunk_header_value is not None else ""
    selected_path = _current_commit_file_path(window)
    snapshot_line_info = line_info if isinstance(line_info, DiffLineInfo) else None

    if not _acquire_commit_diff_action_lock(window):
        _sync_commit_diff_hunk_markers(window)
        return

    def _run_deferred_toggle() -> None:
        try:
            if bool(getattr(window, "_is_closing", False)):
                return
            _toggle_commit_diff_row_from_snapshot(
                window,
                path=selected_path,
                row_index=row_index,
                row_kind=kind,
                row_scope=row_scope,
                checked_state=checked_state,
                hunk_index=hunk_index,
                hunk_header=hunk_header,
                line_info=snapshot_line_info,
                preserve_diff_rows=True,
            )
        finally:
            _release_commit_diff_action_lock(window)

    # Evita alterar modelo do QTreeWidget durante o sinal itemChanged.
    QTimer.singleShot(0, _run_deferred_toggle)


def on_commit_diff_marker_clicked(window: object, line_no: int, *, _lock_already_held: bool = False) -> None:
    if not _lock_already_held:
        if not _acquire_commit_diff_action_lock(window):
            return
    if not window.repo_path:
        if not _lock_already_held:
            _release_commit_diff_action_lock(window)
        return
    try:
        window.commit_diff_selected_line = max(1, int(line_no or 1))
        scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
        line_info = _selected_commit_line_info(window)
        _trace_commit_selection_event(
            window,
            "ui.commit.main.marker_clicked",
            requested_line=int(line_no or 0),
            effective_line=window.commit_diff_selected_line,
            effective_scope=scope,
            lock_already_held=bool(_lock_already_held),
            hunk_index=_selected_commit_hunk_index(window),
            **_line_info_to_trace_payload(line_info),
        )
        if line_info is not None and line_info.line_type in ("added", "removed"):
            if scope == "staged":
                unstage_selected_commit_line(window, preserve_diff_rows=True)
                _sync_commit_diff_hunk_markers(window)
                return
            if scope in {"unstaged", "untracked"}:
                stage_selected_commit_line(window, preserve_diff_rows=True)
                _sync_commit_diff_hunk_markers(window)
                return
        hunk_index = _selected_commit_hunk_index(window)
        if hunk_index is None:
            return
        if scope == "staged":
            unstage_selected_commit_hunk(window, preserve_diff_rows=True)
            _sync_commit_diff_hunk_markers(window)
            return
        if scope in {"unstaged", "untracked"}:
            stage_selected_commit_hunk(window, preserve_diff_rows=True)
            _sync_commit_diff_hunk_markers(window)
    finally:
        if not _lock_already_held:
            _release_commit_diff_action_lock(window)


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
    editor_line = _selected_commit_editor_line(window)
    scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()

    menu = QMenu(window.commit_diff_view)
    action_open_vscode = menu.addAction("Abrir arquivo no VS Code")
    action_open_line_vscode = menu.addAction("Abrir linha no VS Code")
    action_open_line_vscode.setEnabled(editor_line > 0)
    menu.addSeparator()
    action_stage_file = menu.addAction("Stage arquivo") if has_unstaged else None
    action_unstage_file = menu.addAction("Unstage arquivo") if has_staged else None
    if action_stage_file or action_unstage_file:
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
    if chosen_action == action_open_vscode:
        window._open_repo_file_in_vscode(path)
        return
    if chosen_action == action_open_line_vscode:
        if editor_line > 0:
            window._open_repo_file_in_vscode(path, line_no=editor_line)
        return
    if chosen_action == action_stage_file:
        stage_selected_commit_file(window, preserve_diff_rows=True)
        return
    if chosen_action == action_unstage_file:
        unstage_selected_commit_file(window, preserve_diff_rows=True)
        return
    if chosen_action == action_stage_hunk:
        stage_selected_commit_hunk(window, preserve_diff_rows=True)
        _sync_commit_diff_hunk_markers(window)
        return
    if chosen_action == action_unstage_hunk:
        unstage_selected_commit_hunk(window, preserve_diff_rows=True)
        _sync_commit_diff_hunk_markers(window)
        return
    if chosen_action == action_stage_line:
        stage_selected_commit_line(window, preserve_diff_rows=True)
        _sync_commit_diff_hunk_markers(window)
        return
    if chosen_action == action_unstage_line:
        unstage_selected_commit_line(window, preserve_diff_rows=True)
        _sync_commit_diff_hunk_markers(window)


def stage_selected_commit_file(window: object, *, preserve_diff_rows: bool = False) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para stage.")
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.stage_file.request",
        path=path,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    try:
        core_stage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.stage_file.error", path=path, error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message=f"Arquivo adicionado ao stage: {path}",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


def unstage_selected_commit_file(window: object, *, preserve_diff_rows: bool = False) -> None:
    if not window.repo_path:
        QMessageBox.information(window, "Commit", "Selecione um repositório válido primeiro.")
        return
    path = _current_commit_file_path(window)
    if not path:
        QMessageBox.information(window, "Commit", "Selecione um arquivo para unstage.")
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.unstage_file.request",
        path=path,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    try:
        core_unstage_paths(window.repo_path, [path])
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.unstage_file.error", path=path, error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message=f"Arquivo removido do stage: {path}",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


def stage_selected_commit_hunk(window: object, *, preserve_diff_rows: bool = False) -> None:
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
    hunk_header = _selected_commit_hunk_header(window)
    resolved_hunk_index = _resolve_hunk_index_by_header(diff_data, hunk_header, hunk_index)
    if resolved_hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    path = _current_commit_file_path(window)
    if _diff_has_dev_null_transition(diff_data):
        _apply_commit_file_level_toggle(
            window,
            path=path,
            stage=True,
            preserve_diff_rows=preserve_diff_rows,
            reason="dev_null_hunk_button",
        )
        return
    patch = build_patch_for_hunk(diff_data, resolved_hunk_index)
    if not patch:
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.stage_hunk.request",
        hunk_index=resolved_hunk_index,
        hunk_header=hunk_header,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.stage_hunk.error", error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message="Bloco adicionado ao stage.",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


def unstage_selected_commit_hunk(window: object, *, preserve_diff_rows: bool = False) -> None:
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
    hunk_header = _selected_commit_hunk_header(window)
    resolved_hunk_index = _resolve_hunk_index_by_header(diff_data, hunk_header, hunk_index)
    if resolved_hunk_index is None:
        QMessageBox.information(window, "Commit", "Selecione um bloco de diff.")
        return
    path = _current_commit_file_path(window)
    if _diff_has_dev_null_transition(diff_data):
        _apply_commit_file_level_toggle(
            window,
            path=path,
            stage=False,
            preserve_diff_rows=preserve_diff_rows,
            reason="dev_null_hunk_button",
        )
        return
    patch = build_patch_for_hunk(diff_data, resolved_hunk_index)
    if not patch:
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.unstage_hunk.request",
        hunk_index=resolved_hunk_index,
        hunk_header=hunk_header,
        preserve_diff_rows=bool(preserve_diff_rows),
    )
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.unstage_hunk.error", error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message="Bloco removido do stage.",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


def stage_selected_commit_line(window: object, *, preserve_diff_rows: bool = False) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope not in {"unstaged", "untracked"}:
        QMessageBox.information(window, "Commit", "Selecione um diff unstaged para stage da linha.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "unstaged")
    source_line_info = _selected_commit_line_info(window)
    if diff_data is None or source_line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(source_line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    selected_hunk_header = _selected_commit_hunk_header(window)
    selected_hunk_index = _selected_commit_hunk_index(window)
    if isinstance(source_line_info, DiffLineInfo) and _line_info_exists_in_diff(
        diff_data,
        line_info=source_line_info,
        hunk_header=selected_hunk_header,
        fallback_hunk_index=selected_hunk_index,
    ):
        line_info = source_line_info
    else:
        line_info = _resolve_selected_commit_line_for_scope(window, "unstaged")
    if not isinstance(line_info, DiffLineInfo):
        window._set_status("Linha nao localizada no diff atual (tente novamente).")
        return
    path = _current_commit_file_path(window)
    if _diff_has_dev_null_transition(diff_data):
        _apply_commit_file_level_toggle(
            window,
            path=path,
            stage=True,
            preserve_diff_rows=preserve_diff_rows,
            reason="dev_null_line_button",
        )
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.stage_line.request",
        preserve_diff_rows=bool(preserve_diff_rows),
        **_line_info_to_trace_payload(line_info),
    )
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=False)
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.stage_line.error", error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message="Linha adicionada ao stage.",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


def unstage_selected_commit_line(window: object, *, preserve_diff_rows: bool = False) -> None:
    if not window.repo_path:
        return
    selected_scope = _selected_commit_scope(window) or str(getattr(window, "commit_diff_scope", "")).strip()
    if selected_scope != "staged":
        QMessageBox.information(window, "Commit", "Selecione um diff staged para unstage da linha.")
        return
    diff_data = _get_commit_diff_data_for_scope(window, "staged")
    source_line_info = _selected_commit_line_info(window)
    if diff_data is None or source_line_info is None:
        QMessageBox.information(window, "Commit", "Selecione uma linha de diff.")
        return
    line_type = str(getattr(source_line_info, "line_type", ""))
    if line_type not in ("added", "removed"):
        QMessageBox.information(window, "Commit", "A linha selecionada não é uma alteração.")
        return
    selected_hunk_header = _selected_commit_hunk_header(window)
    selected_hunk_index = _selected_commit_hunk_index(window)
    if isinstance(source_line_info, DiffLineInfo) and _line_info_exists_in_diff(
        diff_data,
        line_info=source_line_info,
        hunk_header=selected_hunk_header,
        fallback_hunk_index=selected_hunk_index,
    ):
        line_info = source_line_info
    else:
        line_info = _resolve_selected_commit_line_for_scope(window, "staged")
    if not isinstance(line_info, DiffLineInfo):
        window._set_status("Linha nao localizada no diff atual (tente novamente).")
        return
    path = _current_commit_file_path(window)
    if _diff_has_dev_null_transition(diff_data):
        _apply_commit_file_level_toggle(
            window,
            path=path,
            stage=False,
            preserve_diff_rows=preserve_diff_rows,
            reason="dev_null_line_button",
        )
        return
    patch = build_patch_for_line(diff_data, line_info)
    if not patch:
        return
    _trace_commit_selection_event(
        window,
        "ui.commit.main.unstage_line.request",
        preserve_diff_rows=bool(preserve_diff_rows),
        **_line_info_to_trace_payload(line_info),
    )
    try:
        core_apply_patch_to_index(window.repo_path, patch, reverse=True)
    except RuntimeError as exc:
        _trace_commit_selection_event(window, "ui.commit.main.unstage_line.error", error=str(exc))
        QMessageBox.critical(window, "Commit", str(exc))
        return
    _apply_commit_stage_change_ui(
        window,
        status_message="Linha removida do stage.",
        path=path,
        preserve_diff_rows=preserve_diff_rows,
    )


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
        subject, description = core_get_last_commit_message(window.repo_path)
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
    window.commit_title_input.setText(subject)
    window.commit_description_input.setPlainText(description)
    window.commit_title_input.setFocus()
    window.commit_title_input.selectAll()
    window._refresh_repo_state_ui()
    window._refresh_workspace_tree()
    window._reload_history_commits()


def select_all_commit_files(window: object) -> None:
    paths = list(window.commit_file_item_by_path.keys())
    _set_commit_paths_checked(window, paths, True)
    _sync_commit_group_check_states(window)
    _mark_commit_auto_stage_opt_out(window, paths, opted_out=False)
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
    _mark_commit_auto_stage_opt_out(window, paths, opted_out=True)
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
    try:
        refresh_commit_files(window)
        window._refresh_repo_state_ui()
        window._refresh_workspace_tree()
        window._reload_history_commits()
    except RuntimeError as exc:
        QMessageBox.critical(window, "Commit", f"Commit criado, mas a interface falhou ao atualizar:\n{exc}")
