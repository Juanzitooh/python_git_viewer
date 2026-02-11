"""Controladores de fluxo da UI PySide6."""

from .compare_controller import (
    clear_compare_view,
    get_compare_branches,
    on_compare_branches_changed,
    on_compare_file_selected,
    refresh_compare_branch_options,
    refresh_compare_patch,
    refresh_compare_view,
    swap_compare_branches,
)
from .history_controller import (
    clear_history_view,
    get_history_limit_value,
    load_history_commit_content,
    on_history_commit_selected,
    on_history_file_selected,
    refresh_history_patch_view,
    reload_history_commits,
)

__all__ = [
    "clear_compare_view",
    "get_compare_branches",
    "refresh_compare_branch_options",
    "on_compare_branches_changed",
    "swap_compare_branches",
    "refresh_compare_view",
    "on_compare_file_selected",
    "refresh_compare_patch",
    "clear_history_view",
    "get_history_limit_value",
    "reload_history_commits",
    "on_history_commit_selected",
    "load_history_commit_content",
    "on_history_file_selected",
    "refresh_history_patch_view",
]
