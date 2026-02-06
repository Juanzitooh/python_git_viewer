#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from .core.git_client import is_git_repo, load_commit_summaries
from .core.models import CommitFilters, CommitInfo, CommitSummary, DiffData, DiffLineInfo
from .core.settings_store import get_settings_path, load_settings, normalize_repo_path, save_settings
from .ui.ui_branches import BranchesTabMixin
from .ui.ui_commit import CommitTabMixin
from .ui.ui_global import GlobalBarMixin
from .ui.ui_history import HistoryTabMixin
from .ui.ui_repos import ReposTabMixin
from .ui.ui_settings import SettingsTabMixin
from .ui.ui_stash import StashMixin


RECENT_REPOS_LIMIT = 20
FAVORITE_REPOS_LIMIT = 50


class CommitsViewer(
    GlobalBarMixin,
    HistoryTabMixin,
    BranchesTabMixin,
    CommitTabMixin,
    ReposTabMixin,
    SettingsTabMixin,
    StashMixin,
    tk.Tk,
):
    def __init__(self, repo_path: str, summaries: list[CommitSummary], patch_limit: int, commit_limit: int) -> None:
        super().__init__()
        self.repo_path = repo_path
        self.commit_summaries = summaries
        self.patch_limit = patch_limit
        self.commit_limit = commit_limit
        self.fetch_interval_sec = 60
        self.status_interval_sec = 15
        self.commit_filters = CommitFilters()
        self.tag_list: list[str] = []
        self.word_diff_var = tk.BooleanVar(value=False)
        self.diff_scope_var = tk.StringVar(value="Unstaged")
        self.worktree_diff_data: DiffData | None = None
        self.worktree_line_map: dict[int, DiffLineInfo] = {}
        self.worktree_diff_scope: str = ""
        self.title("Git Commits Viewer")
        self.geometry("1200x700")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.patch_cache: dict[tuple[str, str], str] = {}
        self.full_patch_cache: dict[str, str] = {}
        self.selected_file_by_commit: dict[str, int] = {}
        self.current_commit_hash: str | None = None
        self.branch_list: list[str] = []
        self.auto_fetch_job: str | None = None
        self.auto_status_job: str | None = None
        self.stage_sync_job: str | None = None
        self.suspend_stage_sync = False
        self.commit_details_cache: dict[str, CommitInfo] = {}
        self.commit_offset = len(summaries)
        self.loading_more = False
        self.no_more_commits = False
        self.repo_ready = False
        self.settings_path = get_settings_path()
        self.settings_data: dict[str, object] = {}
        self.recent_repos: list[str] = []
        self.favorite_repos: list[str] = []
        self._load_settings()

        self._build_global_bar()
        self._build_tabs()
        self._bind_shortcuts()
        self._populate_commit_list()
        if self.repo_path and is_git_repo(self.repo_path):
            self._set_repo_path(self.repo_path, initial=True)
        else:
            self._set_repo_ui_no_repo()

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.repos_tab = ttk.Frame(self.tabs)
        self.history_tab = ttk.Frame(self.tabs)
        self.branches_tab = ttk.Frame(self.tabs)
        self.branch_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.repos_tab, text="Repositórios")
        self.tabs.add(self.history_tab, text="Histórico")
        self.tabs.add(self.branches_tab, text="Comparar")
        self.tabs.add(self.branch_tab, text="Commit")
        self.tabs.add(self.settings_tab, text="Configurações")

        self._build_repos_tab()
        self._build_history_tab()
        self._build_branches_tab()
        self._build_branch_tab()
        self._build_settings_tab()

    def _toggle_word_diff(self) -> None:
        self.patch_cache.clear()
        self.full_patch_cache.clear()
        self.worktree_diff_data = None
        self.worktree_line_map.clear()
        selection = self.commit_listbox.curselection()
        if selection:
            self._show_commit(selection[-1])
        self._update_worktree_diff_from_selection()
        if hasattr(self, "_refresh_compare_diff"):
            self._refresh_compare_diff()

    def _word_diff_enabled(self) -> bool:
        if not hasattr(self, "word_diff_var"):
            return False
        return bool(self.word_diff_var.get())

    def _bind_shortcuts(self) -> None:
        self.bind_all("<F5>", self._on_refresh_shortcut, add=True)
        self.bind_all("<Control-r>", self._on_refresh_shortcut, add=True)
        self.bind_all("<Control-1>", lambda _e: self._select_tab(0), add=True)
        self.bind_all("<Control-2>", lambda _e: self._select_tab(1), add=True)
        self.bind_all("<Control-3>", lambda _e: self._select_tab(2), add=True)
        self.bind_all("<Control-4>", lambda _e: self._select_tab(3), add=True)
        self.bind_all("<Control-5>", lambda _e: self._select_tab(4), add=True)
        self.bind_all("<Alt-Up>", lambda _e: self._navigate_lists(-1), add=True)
        self.bind_all("<Alt-Down>", lambda _e: self._navigate_lists(1), add=True)
        self.bind_all("<Control-Return>", self._on_commit_shortcut, add=True)
        self.bind_all("<Control-Shift-Return>", self._on_commit_push_shortcut, add=True)

    def _select_tab(self, index: int) -> None:
        if not hasattr(self, "tabs"):
            return
        if index < 0 or index >= self.tabs.index("end"):
            return
        self.tabs.select(index)

    def _navigate_lists(self, delta: int) -> None:
        if not hasattr(self, "tabs"):
            return
        current_label = self.tabs.tab(self.tabs.select(), "text")
        if current_label == "Histórico":
            self._move_commit_selection(delta)
        elif current_label == "Commit":
            self._move_status_selection(delta)

    def _on_refresh_shortcut(self, _event: tk.Event) -> None:
        self._refresh_all()

    def _refresh_all(self) -> None:
        if not self.repo_ready:
            self._set_status("Selecione um repositório antes de atualizar.")
            return
        self._reload_commits()
        self._refresh_status()
        self._refresh_branches()
        self._update_pull_push_labels()
        if hasattr(self, "_refresh_branch_comparison"):
            self._refresh_branch_comparison()

    def _on_commit_shortcut(self, _event: tk.Event) -> None:
        if not self.repo_ready:
            messagebox.showinfo("Commit", "Selecione um repositório válido antes de commitar.")
            return
        self._commit_changes()

    def _on_commit_push_shortcut(self, _event: tk.Event) -> None:
        if not self.repo_ready:
            messagebox.showinfo("Commit", "Selecione um repositório válido antes de commitar.")
            return
        self._commit_and_push()

    def _load_settings(self) -> None:
        self.settings_data = load_settings(self.settings_path)
        self.commit_limit = int(self.settings_data.get("commit_limit", self.commit_limit))
        self.fetch_interval_sec = int(self.settings_data.get("fetch_interval_sec", self.fetch_interval_sec))
        self.status_interval_sec = int(self.settings_data.get("status_interval_sec", self.status_interval_sec))
        self.recent_repos = list(self.settings_data.get("recent_repos", []))
        self.favorite_repos = list(self.settings_data.get("favorite_repos", []))
        if len(self.recent_repos) > RECENT_REPOS_LIMIT:
            self.recent_repos = self.recent_repos[:RECENT_REPOS_LIMIT]
        if len(self.favorite_repos) > FAVORITE_REPOS_LIMIT:
            self.favorite_repos = self.favorite_repos[:FAVORITE_REPOS_LIMIT]

    def _persist_settings(self) -> None:
        self.settings_data = {
            "commit_limit": self.commit_limit,
            "fetch_interval_sec": self.fetch_interval_sec,
            "status_interval_sec": self.status_interval_sec,
            "recent_repos": self.recent_repos,
            "favorite_repos": self.favorite_repos,
        }
        save_settings(self.settings_path, self.settings_data)

    def _register_recent_repo(self, path: str) -> None:
        normalized = normalize_repo_path(path)
        self.recent_repos = [normalized] + [item for item in self.recent_repos if item != normalized]
        if len(self.recent_repos) > RECENT_REPOS_LIMIT:
            self.recent_repos = self.recent_repos[:RECENT_REPOS_LIMIT]
        self._persist_settings()
        if hasattr(self, "_refresh_repo_lists"):
            self._refresh_repo_lists()

    def _add_favorite_repo(self, path: str) -> None:
        normalized = normalize_repo_path(path)
        if normalized in self.favorite_repos:
            return
        self.favorite_repos = [normalized] + [item for item in self.favorite_repos if item != normalized]
        if len(self.favorite_repos) > FAVORITE_REPOS_LIMIT:
            self.favorite_repos = self.favorite_repos[:FAVORITE_REPOS_LIMIT]
        self._persist_settings()
        if hasattr(self, "_refresh_repo_lists"):
            self._refresh_repo_lists()

    def _remove_favorite_repo(self, path: str) -> None:
        normalized = normalize_repo_path(path)
        self.favorite_repos = [item for item in self.favorite_repos if item != normalized]
        self._persist_settings()
        if hasattr(self, "_refresh_repo_lists"):
            self._refresh_repo_lists()

    def _remove_recent_repo(self, path: str) -> None:
        normalized = normalize_repo_path(path)
        self.recent_repos = [item for item in self.recent_repos if item != normalized]
        self._persist_settings()
        if hasattr(self, "_refresh_repo_lists"):
            self._refresh_repo_lists()
