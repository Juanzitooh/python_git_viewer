"""Builders das abas PySide6."""

from .commit_tab import build_commit_tab
from .conflict_tab import build_conflict_tab
from .compare_tab import build_compare_tab
from .history_tab import build_history_tab
from .import_tab import build_import_tab
from .repositories_tab import build_repositories_tab
from .settings_tab import build_settings_tab
from .stash_tab import build_stash_tab

__all__ = [
    "build_repositories_tab",
    "build_commit_tab",
    "build_conflict_tab",
    "build_stash_tab",
    "build_history_tab",
    "build_import_tab",
    "build_compare_tab",
    "build_settings_tab",
]
