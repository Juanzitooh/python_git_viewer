#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import threading
import time
from typing import Any, Callable
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from tkinter import ttk

from .core.diff_utils import build_read_mode_diff
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
READ_MODE_THRESHOLD = 1200
READ_MODE_MAX_LINES = 400


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
        self.read_mode_var = tk.BooleanVar(value=True)
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
        self.repo_state_token = 0
        self.worktree_diff_cache: dict[tuple[object, ...], str] = {}
        self.compare_diff_cache: dict[tuple[object, ...], str] = {}
        self._async_tokens: dict[str, int] = {}
        self.commit_list_epoch = 0
        self.loading_commits = False
        self.status_loading = False
        self.branches_loading = False
        self.commit_details_pending: set[str] = set()
        self.status_signature = ""
        self.settings_path = get_settings_path()
        self.settings_data: dict[str, object] = {}
        self.recent_repos: list[str] = []
        self.favorite_repos: list[str] = []
        self.theme_name = "light"
        self.ui_font_family = ""
        self.ui_font_size = 0
        self.mono_font_family = ""
        self.mono_font_size = 0
        self.theme_palette: dict[str, str] = {}
        self.perf_var = tk.StringVar(value="")
        self._load_settings()

        self._build_global_bar()
        self._build_tabs()
        self._apply_theme_settings()
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

    def _read_mode_enabled(self) -> bool:
        return bool(self.read_mode_var.get()) if hasattr(self, "read_mode_var") else False

    def _apply_read_mode_to_diff(self, diff_text: str) -> tuple[str, bool, int, int]:
        total = len(diff_text.splitlines())
        if not self._read_mode_enabled():
            return diff_text, False, total, total
        preview, truncated = build_read_mode_diff(
            diff_text,
            threshold=READ_MODE_THRESHOLD,
            max_lines=READ_MODE_MAX_LINES,
        )
        shown = len(preview.splitlines())
        return preview, truncated, shown, total

    def _toggle_read_mode(self) -> None:
        if hasattr(self, "_refresh_history_patch_view"):
            self._refresh_history_patch_view()
        if hasattr(self, "_refresh_compare_diff"):
            self._refresh_compare_diff()

    def _perf_start(self, label: str) -> float:
        if not hasattr(self, "perf_var"):
            return 0.0
        self.perf_var.set(f"{label}...")
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        return time.perf_counter()

    def _perf_end(self, label: str, start: float) -> None:
        if not start or not hasattr(self, "perf_var"):
            return
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.perf_var.set(f"{label}: {elapsed_ms:.0f} ms")

    def _run_async(
        self,
        key: str,
        label: str,
        func: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> int:
        token = self._async_tokens.get(key, 0) + 1
        self._async_tokens[key] = token
        start = self._perf_start(label) if label else 0.0

        def finish_success(result: object) -> None:
            if self._async_tokens.get(key) != token:
                return
            if on_success:
                on_success(result)
            if label:
                self._perf_end(label, start)

        def finish_error(exc: Exception) -> None:
            if self._async_tokens.get(key) != token:
                return
            if on_error:
                on_error(exc)
            else:
                messagebox.showerror("Erro", str(exc))
            if label:
                self._perf_end(label, start)

        def worker() -> None:
            try:
                result = func()
            except Exception as exc:
                self.after(0, lambda: finish_error(exc))
                return
            self.after(0, lambda: finish_success(result))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return token

    def _bump_repo_state(self) -> None:
        self.repo_state_token += 1
        if hasattr(self, "worktree_diff_cache"):
            self.worktree_diff_cache.clear()
        if hasattr(self, "compare_diff_cache"):
            self.compare_diff_cache.clear()
        if hasattr(self, "patch_cache"):
            self.patch_cache.clear()
        if hasattr(self, "full_patch_cache"):
            self.full_patch_cache.clear()

    def _load_settings(self) -> None:
        self.settings_data = load_settings(self.settings_path)
        self.commit_limit = int(self.settings_data.get("commit_limit", self.commit_limit))
        self.fetch_interval_sec = int(self.settings_data.get("fetch_interval_sec", self.fetch_interval_sec))
        self.status_interval_sec = int(self.settings_data.get("status_interval_sec", self.status_interval_sec))
        self.recent_repos = list(self.settings_data.get("recent_repos", []))
        self.favorite_repos = list(self.settings_data.get("favorite_repos", []))
        self.theme_name = str(self.settings_data.get("theme", "light"))
        self.ui_font_family = str(self.settings_data.get("ui_font_family", "")).strip()
        self.ui_font_size = int(self.settings_data.get("ui_font_size", 0))
        self.mono_font_family = str(self.settings_data.get("mono_font_family", "")).strip()
        self.mono_font_size = int(self.settings_data.get("mono_font_size", 0))
        if len(self.recent_repos) > RECENT_REPOS_LIMIT:
            self.recent_repos = self.recent_repos[:RECENT_REPOS_LIMIT]
        if len(self.favorite_repos) > FAVORITE_REPOS_LIMIT:
            self.favorite_repos = self.favorite_repos[:FAVORITE_REPOS_LIMIT]
        if self.theme_name not in ("light", "dark"):
            self.theme_name = "light"
        default_ui_family, default_ui_size, default_mono_family, default_mono_size = self._get_default_font_settings()
        if not self.ui_font_family:
            self.ui_font_family = default_ui_family
        if self.ui_font_size <= 0:
            self.ui_font_size = default_ui_size
        if not self.mono_font_family:
            self.mono_font_family = default_mono_family
        if self.mono_font_size <= 0:
            self.mono_font_size = default_mono_size

    def _persist_settings(self) -> None:
        self.settings_data = {
            "commit_limit": self.commit_limit,
            "fetch_interval_sec": self.fetch_interval_sec,
            "status_interval_sec": self.status_interval_sec,
            "recent_repos": self.recent_repos,
            "favorite_repos": self.favorite_repos,
            "theme": self.theme_name,
            "ui_font_family": self.ui_font_family,
            "ui_font_size": self.ui_font_size,
            "mono_font_family": self.mono_font_family,
            "mono_font_size": self.mono_font_size,
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

    def _get_default_font_settings(self) -> tuple[str, int, str, int]:
        ui_font = tkfont.nametofont("TkDefaultFont")
        mono_font = tkfont.nametofont("TkFixedFont")
        return (
            str(ui_font.cget("family")),
            int(ui_font.cget("size")),
            str(mono_font.cget("family")),
            int(mono_font.cget("size")),
        )

    def _reset_theme_settings(self) -> None:
        default_ui_family, default_ui_size, default_mono_family, default_mono_size = self._get_default_font_settings()
        self.theme_name = "light"
        self.ui_font_family = default_ui_family
        self.ui_font_size = default_ui_size
        self.mono_font_family = default_mono_family
        self.mono_font_size = default_mono_size
        if hasattr(self, "theme_var"):
            self.theme_var.set("Claro")
        if hasattr(self, "ui_font_family_var"):
            self.ui_font_family_var.set(self.ui_font_family)
        if hasattr(self, "ui_font_size_var"):
            self.ui_font_size_var.set(str(self.ui_font_size))
        if hasattr(self, "mono_font_family_var"):
            self.mono_font_family_var.set(self.mono_font_family)
        if hasattr(self, "mono_font_size_var"):
            self.mono_font_size_var.set(str(self.mono_font_size))
        self._apply_theme_settings()
        self._persist_settings()

    def _apply_theme_settings(self) -> None:
        palette = self._get_theme_palette(self.theme_name)
        self.theme_palette = palette
        self._apply_tk_palette(palette)
        self._apply_ttk_theme(palette)
        self._apply_fonts()
        self._apply_widget_theme(palette)

    def _get_theme_palette(self, name: str) -> dict[str, str]:
        if name == "dark":
            return {
                "bg": "#1f2328",
                "fg": "#e6edf3",
                "panel_bg": "#22272e",
                "field_bg": "#0d1117",
                "accent": "#2f81f7",
                "select_bg": "#264f78",
                "select_fg": "#e6edf3",
                "text_bg": "#0d1117",
                "text_fg": "#e6edf3",
                "diff_added": "#3fb950",
                "diff_removed": "#f85149",
                "diff_meta": "#8b949e",
                "diff_added_bg": "#0b3d1e",
                "diff_removed_bg": "#4b1113",
            }
        return {
            "bg": "#f6f6f6",
            "fg": "#1f2328",
            "panel_bg": "#ffffff",
            "field_bg": "#ffffff",
            "accent": "#0969da",
            "select_bg": "#cce0ff",
            "select_fg": "#1f2328",
            "text_bg": "#ffffff",
            "text_fg": "#1f2328",
            "diff_added": "#1a7f37",
            "diff_removed": "#d1242f",
            "diff_meta": "#57606a",
            "diff_added_bg": "#dafbe1",
            "diff_removed_bg": "#ffebe9",
        }

    def _apply_tk_palette(self, palette: dict[str, str]) -> None:
        self.tk_setPalette(
            background=palette["bg"],
            foreground=palette["fg"],
            selectBackground=palette["select_bg"],
            selectForeground=palette["select_fg"],
            insertBackground=palette["fg"],
            activeBackground=palette["panel_bg"],
            activeForeground=palette["fg"],
        )

    def _apply_ttk_theme(self, palette: dict[str, str]) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabel", background=palette["bg"], foreground=palette["fg"])
        style.configure("TLabelframe", background=palette["bg"], foreground=palette["fg"])
        style.configure("TLabelframe.Label", background=palette["bg"], foreground=palette["fg"])
        style.configure("TButton", background=palette["bg"], foreground=palette["fg"])
        style.map(
            "TButton",
            background=[("active", palette["panel_bg"])],
            foreground=[("active", palette["fg"])],
        )
        style.configure("TEntry", fieldbackground=palette["field_bg"], foreground=palette["fg"])
        style.configure("TCombobox", fieldbackground=palette["field_bg"], foreground=palette["fg"])
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["field_bg"])],
            foreground=[("readonly", palette["fg"])],
        )
        style.configure("TNotebook", background=palette["bg"])
        style.configure("TNotebook.Tab", background=palette["panel_bg"], foreground=palette["fg"], padding=(10, 4))
        style.map(
            "TNotebook.Tab",
            background=[("selected", palette["field_bg"])],
            foreground=[("selected", palette["fg"])],
        )

    def _apply_fonts(self) -> None:
        ui_font = tkfont.nametofont("TkDefaultFont")
        ui_font.configure(family=self.ui_font_family, size=self.ui_font_size)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family=self.ui_font_family, size=self.ui_font_size)
        heading_font = tkfont.nametofont("TkHeadingFont")
        heading_font.configure(family=self.ui_font_family, size=self.ui_font_size)
        mono_font = tkfont.nametofont("TkFixedFont")
        mono_font.configure(family=self.mono_font_family, size=self.mono_font_size)

    def _apply_widget_theme(self, palette: dict[str, str]) -> None:
        text_widgets = [
            "commit_info",
            "commit_body_text",
            "patch_text",
            "worktree_diff_text",
            "compare_diff_text",
        ]
        for name in text_widgets:
            widget = getattr(self, name, None)
            if widget is None:
                continue
            self._apply_text_widget_theme(widget, palette)
            self._apply_diff_tags(widget, palette)

        list_widgets = [
            "commit_listbox",
            "files_listbox",
            "status_listbox",
            "compare_commits_listbox",
            "compare_files_listbox",
            "favorite_listbox",
            "recent_listbox",
        ]
        for name in list_widgets:
            widget = getattr(self, name, None)
            if widget is None:
                continue
            self._apply_listbox_theme(widget, palette)

    def _apply_text_widget_theme(self, widget: tk.Text, palette: dict[str, str]) -> None:
        widget.configure(
            background=palette["text_bg"],
            foreground=palette["text_fg"],
            insertbackground=palette["text_fg"],
            selectbackground=palette["select_bg"],
            selectforeground=palette["select_fg"],
        )

    def _apply_listbox_theme(self, widget: tk.Listbox, palette: dict[str, str]) -> None:
        widget.configure(
            background=palette["field_bg"],
            foreground=palette["text_fg"],
            selectbackground=palette["select_bg"],
            selectforeground=palette["select_fg"],
        )

    def _apply_diff_tags(self, widget: tk.Text, palette: dict[str, str]) -> None:
        widget.tag_configure("added", foreground=palette["diff_added"])
        widget.tag_configure("removed", foreground=palette["diff_removed"])
        widget.tag_configure("meta", foreground=palette["diff_meta"])
        widget.tag_configure("added_word", foreground=palette["diff_added"], background=palette["diff_added_bg"])
        widget.tag_configure("removed_word", foreground=palette["diff_removed"], background=palette["diff_removed_bg"])
