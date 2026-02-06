#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from git_client import is_git_repo, load_commit_summaries
from models import CommitFilters, CommitInfo, CommitSummary, DiffData, DiffLineInfo
from ui_commit import CommitTabMixin
from ui_global import GlobalBarMixin
from ui_history import HistoryTabMixin
from ui_settings import SettingsTabMixin
from ui_stash import StashMixin


class CommitsViewer(GlobalBarMixin, HistoryTabMixin, CommitTabMixin, SettingsTabMixin, StashMixin, tk.Tk):
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

        self._build_global_bar()
        self._build_tabs()
        self._populate_commit_list()
        if self.repo_path and is_git_repo(self.repo_path):
            self._set_repo_path(self.repo_path, initial=True)
        else:
            self._set_repo_ui_no_repo()

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.history_tab = ttk.Frame(self.tabs)
        self.branch_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.history_tab, text="Histórico")
        self.tabs.add(self.branch_tab, text="Commit")
        self.tabs.add(self.settings_tab, text="Configurações")

        self._build_history_tab()
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

    def _word_diff_enabled(self) -> bool:
        if not hasattr(self, "word_diff_var"):
            return False
        return bool(self.word_diff_var.get())
