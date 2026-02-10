#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import threading
import time
from datetime import datetime
from pathlib import Path
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
from .ui.ui_import import ImportTabMixin
from .ui.ui_repos import ReposTabMixin
from .ui.ui_settings import SettingsTabMixin
from .ui.ui_stash import StashMixin


RECENT_REPOS_LIMIT = 20
FAVORITE_REPOS_LIMIT = 50
READ_MODE_THRESHOLD = 1200
READ_MODE_MAX_LINES = 400
PERF_LOG_FILENAME = "performance.log"
STARTUP_SHOW_MIN_WAIT_SEC = 0.45


class CommitsViewer(
    GlobalBarMixin,
    HistoryTabMixin,
    ImportTabMixin,
    BranchesTabMixin,
    CommitTabMixin,
    ReposTabMixin,
    SettingsTabMixin,
    StashMixin,
    tk.Tk,
):
    def __init__(
        self,
        repo_path: str,
        summaries: list[CommitSummary],
        patch_limit: int,
        commit_limit: int,
        perf_enabled: bool = False,
    ) -> None:
        super().__init__()
        self.repo_path = repo_path
        self.commit_summaries = summaries
        self.patch_limit = patch_limit
        self.commit_limit = commit_limit
        self.perf_enabled = perf_enabled
        self.withdraw()
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
        self.title("Git Viewer")
        self.geometry("1200x700")
        self._maximize_window()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

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
        self._async_busy_count = 0
        self.commit_list_epoch = 0
        self.loading_commits = False
        self.status_loading = False
        self.branches_loading = False
        self.commit_details_pending: set[str] = set()
        self.status_signature = ""
        self.settings_path = get_settings_path()
        self.settings_data: dict[str, object] = {}
        self.last_tab_index = 0
        self.last_repo_path = ""
        self.recent_repos: list[str] = []
        self.favorite_repos: list[str] = []
        self.repo_scan_root = ""
        self.theme_name = "light"
        self.ui_font_family = ""
        self.ui_font_size = 0
        self.mono_font_family = ""
        self.mono_font_size = 0
        self.theme_palette: dict[str, str] = {}
        self.github_ssh_cache: dict[str, object] = {}
        self.perf_var = tk.StringVar(value="")
        self.perf_log_path = self._resolve_perf_log_path() if self.perf_enabled else None
        self._startup_window_pending = True
        self._startup_ready_not_before = 0.0
        self._startup_poll_job: str | None = None
        self.hover_tooltip_window: tk.Toplevel | None = None
        self.hover_tooltip_label: ttk.Label | None = None
        self.hover_tooltip_owner = ""
        self._load_settings()

        self._build_global_bar()
        self._build_busy_indicator()
        self._build_tabs()
        self._apply_theme_settings()
        self._bind_shortcuts()
        self._populate_commit_list()
        self._update_window_title()
        if self.repo_path and is_git_repo(self.repo_path):
            self._set_repo_path(self.repo_path, initial=True)
        else:
            self._set_repo_ui_no_repo()
        self._startup_ready_not_before = time.monotonic() + STARTUP_SHOW_MIN_WAIT_SEC
        self._schedule_startup_show_check()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_tabs(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

        self.repos_tab = ttk.Frame(self.tabs)
        self.history_tab = ttk.Frame(self.tabs)
        self.import_tab = ttk.Frame(self.tabs)
        self.branches_tab = ttk.Frame(self.tabs)
        self.branch_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)

        self.tabs.add(self.repos_tab, text="Repositórios")
        self.tabs.add(self.branch_tab, text="Commit")
        self.tabs.add(self.history_tab, text="Histórico")
        self.tabs.add(self.import_tab, text="Importar")
        self.tabs.add(self.branches_tab, text="Comparar")
        self.tabs.add(self.settings_tab, text="Configurações")

        self._build_repos_tab()
        self._build_branch_tab()
        self._build_history_tab()
        self._build_import_tab()
        self._build_branches_tab()
        self._build_settings_tab()
        tab_count = self.tabs.index("end")
        if tab_count > 0:
            if self.last_tab_index >= tab_count:
                self.last_tab_index = tab_count - 1
            self.tabs.select(self.last_tab_index)
        self.tabs.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed, add=True)
        self.after_idle(self._on_notebook_tab_changed)

    def _on_notebook_tab_changed(self, _event: tk.Event | None = None) -> None:
        if hasattr(self, "tabs"):
            try:
                selected = self.tabs.select()
                self.last_tab_index = self.tabs.index(selected) if selected else 0
            except tk.TclError:
                self.last_tab_index = 0
        if hasattr(self, "_dismiss_repo_context_menu"):
            self._dismiss_repo_context_menu(close_dropdown=True)
        if hasattr(self, "_dismiss_commit_context_menu"):
            self._dismiss_commit_context_menu()
        if hasattr(self, "_dismiss_history_file_context_menu"):
            self._dismiss_history_file_context_menu()
        if hasattr(self, "_dismiss_import_commit_context_menu"):
            self._dismiss_import_commit_context_menu()
        if hasattr(self, "_dismiss_compare_commit_context_menu"):
            self._dismiss_compare_commit_context_menu()
        if hasattr(self, "_dismiss_compare_file_context_menu"):
            self._dismiss_compare_file_context_menu()
        if hasattr(self, "_refresh_repo_selector_visibility"):
            self._refresh_repo_selector_visibility()

    def _is_startup_loading_pending(self) -> bool:
        if self._async_busy_count > 0:
            return True
        if getattr(self, "workspace_card_refresh_job", None) is not None:
            return True
        if getattr(self, "loading_commits", False):
            return True
        if getattr(self, "branches_loading", False):
            return True
        if getattr(self, "status_loading", False):
            return True
        if getattr(self, "loading_more", False):
            return True
        return False

    def _schedule_startup_show_check(self, delay_ms: int = 80) -> None:
        if not self._startup_window_pending:
            return
        if self._startup_poll_job is not None:
            try:
                self.after_cancel(self._startup_poll_job)
            except tk.TclError:
                pass
            self._startup_poll_job = None
        self._startup_poll_job = self.after(delay_ms, self._finish_startup_show_if_ready)

    def _finish_startup_show_if_ready(self) -> None:
        self._startup_poll_job = None
        if not self._startup_window_pending:
            return
        if time.monotonic() < self._startup_ready_not_before:
            self._schedule_startup_show_check(80)
            return
        if self._is_startup_loading_pending():
            self._schedule_startup_show_check(120)
            return
        self._startup_window_pending = False
        self.deiconify()
        self.lift()

    def _on_close(self) -> None:
        if self._startup_poll_job is not None:
            try:
                self.after_cancel(self._startup_poll_job)
            except tk.TclError:
                pass
            self._startup_poll_job = None
        if hasattr(self, "_dismiss_repo_context_menu"):
            self._dismiss_repo_context_menu(close_dropdown=True)
        if hasattr(self, "_dismiss_commit_context_menu"):
            self._dismiss_commit_context_menu()
        if hasattr(self, "_dismiss_history_file_context_menu"):
            self._dismiss_history_file_context_menu()
        if hasattr(self, "_dismiss_import_commit_context_menu"):
            self._dismiss_import_commit_context_menu()
        if hasattr(self, "_dismiss_compare_commit_context_menu"):
            self._dismiss_compare_commit_context_menu()
        if hasattr(self, "_dismiss_compare_file_context_menu"):
            self._dismiss_compare_file_context_menu()
        if hasattr(self, "_hide_conflicts_tab"):
            self._hide_conflicts_tab(select_history=False)
        self._hide_hover_tooltip()
        if hasattr(self, "tabs"):
            try:
                selected = self.tabs.select()
                self.last_tab_index = self.tabs.index(selected) if selected else 0
            except tk.TclError:
                self.last_tab_index = 0
        self._persist_settings()
        self.destroy()

    def _build_busy_indicator(self) -> None:
        self.busy_indicator_frame = ttk.Frame(self)
        self.busy_indicator_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))
        self.busy_indicator_frame.grid_columnconfigure(0, weight=1)
        self.busy_indicator = ttk.Progressbar(
            self.busy_indicator_frame,
            orient="horizontal",
            mode="indeterminate",
            style="Busy.Horizontal.TProgressbar",
        )
        self.busy_indicator.grid(row=0, column=0, sticky="ew")
        self.busy_indicator_frame.grid_remove()

    def _set_busy_indicator_visible(self, visible: bool) -> None:
        if not hasattr(self, "busy_indicator_frame") or not hasattr(self, "busy_indicator"):
            return
        if visible:
            self.busy_indicator_frame.grid()
            self.busy_indicator.start(12)
            return
        self.busy_indicator.stop()
        self.busy_indicator_frame.grid_remove()

    def _begin_async_busy(self) -> None:
        self._async_busy_count += 1
        if self._async_busy_count == 1:
            self._set_busy_indicator_visible(True)

    def _end_async_busy(self) -> None:
        if self._async_busy_count <= 0:
            self._async_busy_count = 0
            self._set_busy_indicator_visible(False)
            return
        self._async_busy_count -= 1
        if self._async_busy_count == 0:
            self._set_busy_indicator_visible(False)

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
        self.bind_all("<Control-Key-1>", lambda _e: self._select_tab(0), add=True)
        self.bind_all("<Control-Key-2>", lambda _e: self._select_tab(1), add=True)
        self.bind_all("<Control-Key-3>", lambda _e: self._select_tab(3), add=True)
        self.bind_all("<Control-Key-4>", lambda _e: self._select_tab(4), add=True)
        self.bind_all("<Control-Key-5>", lambda _e: self._select_tab(5), add=True)
        self.bind_all("<Control-Key-6>", lambda _e: self._select_tab(2), add=True)
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
        self._on_notebook_tab_changed()

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
        self._reload_commits(trigger="manual_refresh_all")
        self._refresh_status(trigger="manual_refresh_all")
        self._refresh_branches(trigger="manual_refresh_all")
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

    @staticmethod
    def _normalize_perf_trigger(trigger: str | None) -> str:
        if trigger is None:
            return ""
        return str(trigger).strip()

    def _format_perf_label(self, label: str, trigger: str = "") -> str:
        normalized_trigger = self._normalize_perf_trigger(trigger)
        if not normalized_trigger:
            return label
        return f"{label} [{normalized_trigger}]"

    def _perf_start(self, label: str, trigger: str = "") -> float:
        if not getattr(self, "perf_enabled", False):
            return 0.0
        if not hasattr(self, "perf_var"):
            return 0.0
        display_label = self._format_perf_label(label, trigger)
        self.perf_var.set(f"{display_label}...")
        try:
            self.update_idletasks()
        except tk.TclError:
            pass
        return time.perf_counter()

    def _perf_end(self, label: str, start: float, trigger: str = "") -> None:
        if not getattr(self, "perf_enabled", False):
            return
        if not start or not hasattr(self, "perf_var"):
            return
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        display_label = self._format_perf_label(label, trigger)
        self.perf_var.set(f"{display_label}: {elapsed_ms:.0f} ms")
        self._append_perf_log(label, elapsed_ms, trigger)

    def _resolve_perf_log_path(self) -> Path:
        project_root = Path(__file__).resolve().parent.parent
        candidates = [
            project_root / PERF_LOG_FILENAME,
            Path.cwd() / PERF_LOG_FILENAME,
        ]
        for candidate in candidates:
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.touch(exist_ok=True)
            except OSError:
                continue
            return candidate
        return candidates[0]

    def _append_perf_log(self, label: str, elapsed_ms: float, trigger: str = "") -> None:
        if not getattr(self, "perf_enabled", False):
            return
        log_path = getattr(self, "perf_log_path", None)
        if not isinstance(log_path, Path):
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        repo_name = "(nenhum)"
        if self.repo_path:
            repo_name = os.path.basename(self.repo_path.rstrip(os.sep)) or self.repo_path
        normalized_trigger = self._normalize_perf_trigger(trigger)
        trigger_suffix = f" | trigger={normalized_trigger}" if normalized_trigger else ""
        line = f"{timestamp} | repo={repo_name} | {label} | {elapsed_ms:.0f} ms{trigger_suffix}\n"
        try:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            return

    def _update_window_title(self) -> None:
        base_title = "Git Viewer"
        if not getattr(self, "repo_ready", False) or not self.repo_path:
            self.title(f"{base_title} (padrão)")
            return
        repo_path = self.repo_path.rstrip(os.sep)
        repo_name = os.path.basename(repo_path) or repo_path
        branch = ""
        if hasattr(self, "branch_var"):
            branch = self.branch_var.get().strip()
        if branch:
            self.title(f"{base_title} {repo_name} - {branch}")
        else:
            self.title(f"{base_title} {repo_name}")

    def _maximize_window(self) -> None:
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.attributes("-zoomed", True)
            return
        except tk.TclError:
            pass
        self.update_idletasks()
        width = self.winfo_screenwidth()
        height = self.winfo_screenheight()
        self.geometry(f"{width}x{height}+0+0")

    def _show_hover_tooltip(self, owner: str, text: str, x: int, y: int) -> None:
        content = text.strip()
        if not content:
            self._hide_hover_tooltip()
            return
        window = getattr(self, "hover_tooltip_window", None)
        label = getattr(self, "hover_tooltip_label", None)
        if window is not None and window.winfo_exists() and label is not None:
            self.hover_tooltip_owner = owner
            if str(label.cget("text")) != content:
                label.configure(text=content)
            window.geometry(f"+{x}+{y}")
            return
        self._hide_hover_tooltip()
        tip_window = tk.Toplevel(self)
        tip_window.wm_overrideredirect(True)
        try:
            tip_window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        tip_label = ttk.Label(tip_window, text=content, justify="left", padding=(8, 4))
        tip_label.pack(fill="both", expand=True)
        tip_window.geometry(f"+{x}+{y}")
        self.hover_tooltip_window = tip_window
        self.hover_tooltip_label = tip_label
        self.hover_tooltip_owner = owner

    def _hide_hover_tooltip(self, _event: tk.Event | None = None) -> None:
        window = getattr(self, "hover_tooltip_window", None)
        self.hover_tooltip_window = None
        self.hover_tooltip_label = None
        self.hover_tooltip_owner = ""
        if window is None:
            return
        if not window.winfo_exists():
            return
        window.destroy()

    def _run_async(
        self,
        key: str,
        label: str,
        func: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        perf_trigger: str = "",
    ) -> int:
        token = self._async_tokens.get(key, 0) + 1
        self._async_tokens[key] = token
        self._begin_async_busy()
        normalized_trigger = self._normalize_perf_trigger(perf_trigger) or key
        start = self._perf_start(label, normalized_trigger) if label else 0.0

        def finish_success(result: object) -> None:
            self._end_async_busy()
            if self._async_tokens.get(key) != token:
                return
            if on_success:
                on_success(result)
            if label:
                self._perf_end(label, start, normalized_trigger)

        def finish_error(exc: Exception) -> None:
            self._end_async_busy()
            if self._async_tokens.get(key) != token:
                return
            if on_error:
                on_error(exc)
            else:
                messagebox.showerror("Erro", str(exc))
            if label:
                self._perf_end(label, start, normalized_trigger)

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

    def _run_with_perf(self, label: str, trigger: str, func: Callable[[], Any]) -> Any:
        normalized_trigger = self._normalize_perf_trigger(trigger)
        start = self._perf_start(label, normalized_trigger)
        try:
            return func()
        finally:
            self._perf_end(label, start, normalized_trigger)

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
        self.last_tab_index = int(self.settings_data.get("last_tab_index", self.last_tab_index))
        self.last_repo_path = str(self.settings_data.get("last_repo_path", "")).strip()
        self.recent_repos = list(self.settings_data.get("recent_repos", []))
        self.favorite_repos = list(self.settings_data.get("favorite_repos", []))
        self.repo_scan_root = str(self.settings_data.get("repo_scan_root", "")).strip()
        self.theme_name = str(self.settings_data.get("theme", "light"))
        self.ui_font_family = str(self.settings_data.get("ui_font_family", "")).strip()
        self.ui_font_size = int(self.settings_data.get("ui_font_size", 0))
        self.mono_font_family = str(self.settings_data.get("mono_font_family", "")).strip()
        self.mono_font_size = int(self.settings_data.get("mono_font_size", 0))
        cache_raw = self.settings_data.get("github_ssh_cache", {})
        self.github_ssh_cache = dict(cache_raw) if isinstance(cache_raw, dict) else {}
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
        if self.repo_ready and self.repo_path:
            self.last_repo_path = normalize_repo_path(self.repo_path)
        self.settings_data = {
            "commit_limit": self.commit_limit,
            "fetch_interval_sec": self.fetch_interval_sec,
            "status_interval_sec": self.status_interval_sec,
            "last_tab_index": self.last_tab_index,
            "last_repo_path": self.last_repo_path,
            "recent_repos": self.recent_repos,
            "favorite_repos": self.favorite_repos,
            "repo_scan_root": self.repo_scan_root,
            "theme": self.theme_name,
            "ui_font_family": self.ui_font_family,
            "ui_font_size": self.ui_font_size,
            "mono_font_family": self.mono_font_family,
            "mono_font_size": self.mono_font_size,
            "github_ssh_cache": self.github_ssh_cache,
        }
        save_settings(self.settings_path, self.settings_data)

    def _register_recent_repo(self, path: str, *, promote: bool = True) -> None:
        normalized = normalize_repo_path(path)
        if promote:
            self.recent_repos = [normalized] + [item for item in self.recent_repos if item != normalized]
        elif normalized not in self.recent_repos:
            self.recent_repos.append(normalized)
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
        style.configure(
            "Busy.Horizontal.TProgressbar",
            troughcolor=palette["bg"],
            background=palette["accent"],
            lightcolor=palette["accent"],
            darkcolor=palette["accent"],
            bordercolor=palette["bg"],
            thickness=3,
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
            "import_commits_listbox",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualiza commits do Git em uma interface Tkinter.")
    parser.add_argument(
        "--repo",
        default=None,
        help="Caminho do repositório Git (default: último aberto, senão diretório atual se for Git)",
    )
    parser.add_argument("--limit", type=int, default=100, help="Quantidade de commits (default: 100)")
    parser.add_argument(
        "--patch-limit",
        type=int,
        default=0,
        help="(ignorado) mantido por compatibilidade",
    )
    parser.add_argument(
        "--perf",
        action="store_true",
        help="habilita indicador de performance na UI e log em performance.log",
    )
    return parser.parse_args()


def _resolve_startup_repo(repo_arg: str | None) -> str:
    explicit_repo = (repo_arg or "").strip()
    if explicit_repo:
        candidate = os.path.abspath(explicit_repo)
        if os.path.isdir(candidate) and is_git_repo(candidate):
            return candidate
        return ""

    settings = load_settings(get_settings_path())
    cached_repo_raw = settings.get("last_repo_path", "")
    if isinstance(cached_repo_raw, str) and cached_repo_raw.strip():
        cached_repo = normalize_repo_path(cached_repo_raw)
        if os.path.isdir(cached_repo) and is_git_repo(cached_repo):
            return cached_repo

    fallback = os.path.abspath(os.getcwd())
    if os.path.isdir(fallback) and is_git_repo(fallback):
        return fallback
    return ""


def main() -> int:
    args = parse_args()
    repo_path = _resolve_startup_repo(args.repo)
    commits: list[CommitSummary] = []
    if repo_path:
        try:
            commits = load_commit_summaries(repo_path, args.limit)
        except RuntimeError as exc:
            messagebox.showerror("Erro", str(exc))
            repo_path = ""
    app = CommitsViewer(repo_path, commits, args.patch_limit, args.limit, perf_enabled=bool(args.perf))
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
