#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..core.git_client import is_git_repo, run_git
from ..core.github_urls import (
    build_repo_actions_url as core_build_repo_actions_url,
    build_repo_branch_commits_url as core_build_repo_branch_commits_url,
    build_repo_branch_url as core_build_repo_branch_url,
    build_commit_url as core_build_commit_url,
    build_pr_compare_url as core_build_pr_compare_url,
    build_repo_issues_url as core_build_repo_issues_url,
    build_repo_releases_url as core_build_repo_releases_url,
    get_current_branch_for_pr as core_get_current_branch_for_pr,
    get_default_base_branch_for_pr as core_get_default_base_branch_for_pr,
    get_repo_github_base_url as core_get_repo_github_base_url,
)
from ..core.models import CommitSummary
from ..core.repo_workspace import default_repo_scan_root
from ..core.repo_state import (
    get_default_branch as core_get_default_branch,
    get_current_branch as core_get_current_branch,
    get_upstream as core_get_upstream,
    list_branches as core_list_branches,
    list_local_branches_with_upstream as core_list_local_branches_with_upstream,
)
from ..core.remote_ops import fetch_all_prune as core_fetch_all_prune
from ..core.settings_store import get_settings_path, load_settings, normalize_repo_path, save_settings
from .theme import (
    build_theme_stylesheet as build_ui_theme_stylesheet,
    normalize_theme_name,
    sanitize_theme_overrides,
)
from .update_profiles import UpdateProfile, resolve_update_profile
from .controllers import (
    add_recent_repo,
    apply_selected_stash,
    apply_import_source_repo_from_combo,
    clear_import_selection,
    create_stash_from_commit_tab,
    clear_commit_file_selection,
    clear_compare_view,
    collect_known_repos,
    collect_repo_paths_from_settings,
    create_commit_from_selection,
    format_repo_display_label,
    format_branch_display_label,
    format_workspace_relative_path,
    build_repo_snapshot,
    build_repo_status_summary,
    get_compare_branches,
    get_selected_commit_paths,
    get_selected_import_summaries,
    import_selected_commits,
    iter_commit_items,
    load_repo_selector_items,
    load_import_source_branches,
    load_import_source_commits,
    on_commit_diff_cursor_changed,
    on_commit_file_item_changed,
    on_commit_file_selected,
    on_compare_action_changed,
    on_compare_branches_changed,
    on_compare_commit_selected,
    on_compare_commit_context_menu,
    on_compare_file_selected,
    on_branch_changed,
    on_workspace_item_double_clicked,
    on_workspace_tree_context_menu,
    on_workspace_root_edited,
    on_workspace_selection_changed,
    on_repo_combo_context_menu,
    on_repo_combo_dropdown_context_menu,
    on_branch_combo_context_menu,
    on_branch_combo_dropdown_context_menu,
    open_clone_dialog,
    on_import_source_branch_changed,
    on_import_source_repo_changed,
    on_import_commit_selected,
    on_import_file_context_menu,
    on_import_file_selected,
    pick_workspace_root,
    pull_repo,
    push_repo,
    refresh_commit_files,
    refresh_commit_diff,
    refresh_import_source_repos,
    refresh_import_patch_view,
    refresh_compare_branch_options,
    refresh_compare_patch,
    refresh_compare_view,
    run_compare_action,
    refresh_repo_state_ui,
    refresh_workspace_tree,
    repo_is_favorite,
    scan_workspace_repos,
    select_repo_combo_item,
    set_repo,
    create_new_branch,
    load_settings_into_tab,
    on_settings_update_profile_changed,
    on_settings_theme_changed,
    on_settings_theme_color_edited,
    pick_settings_workspace_root,
    pick_settings_theme_color,
    reset_settings_theme_colors,
    save_settings_from_tab,
    select_all_commit_files,
    stage_selected_commit_hunk,
    stage_selected_commit_line,
    stage_selected_commit_file,
    undo_last_commit_from_commit_tab,
    sync_workspace_tree_selection,
    sync_import_target_label,
    swap_compare_branches,
    update_commit_selection_label,
    update_import_controls_state,
    use_current_repo_as_import_source,
    unstage_selected_commit_hunk,
    unstage_selected_commit_line,
    unstage_selected_commit_file,
    copy_selected_import_hashes,
    fetch_repo,
    clear_history_view,
    get_history_limit_value,
    load_history_commit_content,
    load_more_history_commits,
    on_compare_file_context_menu,
    on_history_commit_context_menu,
    on_history_commit_hovered,
    on_history_commit_selected,
    on_history_search_text_changed,
    on_history_scroll_value_changed,
    on_history_file_context_menu,
    on_import_commit_context_menu,
    open_import_clone_dialog,
    on_stash_entry_selected,
    on_stash_entry_context_menu,
    on_stash_file_selected,
    on_commit_diff_context_menu,
    open_commit_diff_window,
    on_commit_file_context_menu,
    on_history_file_selected,
    on_commit_diff_item_changed,
    on_commit_diff_marker_clicked,
    on_commit_diff_item_clicked,
    open_history_export_dialog,
    open_history_reorder_dialog,
    refresh_history_patch_view,
    refresh_stash_patch_view,
    refresh_stash_tab_visibility,
    reload_history_commits,
    show_conflicts_dialog,
    pop_selected_stash,
    drop_selected_stash,
)
from .layout import build_status_bar, build_top_bar
from .tabs import (
    build_commit_tab,
    build_compare_tab,
    build_history_tab,
    build_import_tab,
    build_repositories_tab,
    build_settings_tab,
    build_stash_tab,
)

try:
    from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Signal
    from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QHBoxLayout,
        QListWidgetItem,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTabWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - environment dependent
    raise RuntimeError(
        "PySide6 nao encontrado. Instale com: pip install -r requirements.txt"
    ) from exc


TAB_NAMES = [
    "Repositorios",
    "Commit",
    "Historico",
    "Importar",
    "Comparar",
    "Configuracoes",
]


class _AutoUpdateBridge(QObject):
    finished = Signal(str, str, int, object, str)


def _collect_repo_status_snapshot(repo_path: str) -> dict[str, object]:
    branches = core_list_branches(repo_path)
    tracked_local_branches = sorted(core_list_local_branches_with_upstream(repo_path))
    current_branch = core_get_current_branch(repo_path).strip()
    default_branch = core_get_default_branch(repo_path).strip()
    upstream = core_get_upstream(repo_path) or ""
    behind = 0
    ahead = 0
    if upstream:
        behind, ahead = core_get_ahead_behind(repo_path, upstream)
    head_hash = run_git(repo_path, ["rev-parse", "HEAD"]).strip()
    return {
        "branches": branches,
        "tracked_local_branches": tracked_local_branches,
        "current_branch": current_branch,
        "default_branch": default_branch,
        "upstream": upstream,
        "behind": behind,
        "ahead": ahead,
        "head_hash": head_hash,
    }


def _collect_history_head_snapshot(repo_path: str) -> dict[str, str]:
    head_hash = run_git(repo_path, ["rev-parse", "HEAD"]).strip()
    upstream = core_get_upstream(repo_path)
    upstream_head = ""
    if upstream:
        try:
            upstream_head = run_git(repo_path, ["rev-parse", upstream]).strip()
        except RuntimeError:
            upstream_head = ""
    return {
        "head_hash": head_hash,
        "upstream_head": upstream_head,
    }


def _run_auto_fetch(repo_path: str) -> dict[str, object]:
    core_fetch_all_prune(repo_path)
    return {}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Git Viewer - shell PySide6.")
    parser.add_argument(
        "--repo",
        default=None,
        help="Caminho do repositorio Git (default: ultimo aberto, senao cwd se for Git).",
    )
    return parser.parse_args(argv)


def _resolve_startup_repo(repo_arg: str | None, settings_path: Path) -> str:
    explicit_repo = (repo_arg or "").strip()
    if explicit_repo:
        candidate = os.path.abspath(explicit_repo)
        if os.path.isdir(candidate) and is_git_repo(candidate):
            return candidate
        return ""

    settings = load_settings(settings_path)
    cached_repo_raw = settings.get("last_repo_path", "")
    if isinstance(cached_repo_raw, str) and cached_repo_raw.strip():
        cached_repo = normalize_repo_path(cached_repo_raw)
        if os.path.isdir(cached_repo) and is_git_repo(cached_repo):
            return cached_repo

    fallback = os.path.abspath(os.getcwd())
    if os.path.isdir(fallback) and is_git_repo(fallback):
        return fallback
    return ""


class QtShellWindow(QMainWindow):
    def __init__(self, repo_path: str, settings_path: Path) -> None:
        super().__init__()
        self.settings_path = settings_path
        self.settings_data = load_settings(settings_path)
        self.repo_path = normalize_repo_path(repo_path) if repo_path else ""
        self.repo_scan_root = self._load_workspace_root_from_settings()
        self.scanned_repos: list[str] = []
        self._setting_repo_programmatically = False
        self._setting_branch_programmatically = False
        self._setting_workspace_selection = False
        self._busy_depth = 0
        self._is_closing = False
        self._repo_generation = 0
        self._history_refresh_pending = False
        self._history_probe_signature = ""
        self._auto_task_state: dict[str, tuple[str, int]] = {}
        self._auto_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gv-auto")
        self._auto_update_bridge = _AutoUpdateBridge(self)
        self._auto_update_bridge.finished.connect(self._on_background_task_finished)
        self._auto_profile: UpdateProfile = resolve_update_profile(self.settings_data)

        self.setWindowTitle("Git Viewer (PySide6)")
        self.resize(1280, 820)

        self._apply_theme_from_settings()
        self._build_ui()
        self._load_repo_selector_items()

        initial_repo = self.repo_path
        if not initial_repo and self.repo_combo.count() > 0:
            initial_repo = self.repo_combo.currentData() or ""
        # Evita sobrescrever a aba salva antes de restaurar `last_tab_name`.
        self._set_repo(initial_repo, save=False)
        self._restore_last_tab_from_settings()
        self._persist_state()

        self._setup_background_timers()

    def _restore_last_tab_from_settings(self) -> None:
        if not hasattr(self, "tabs"):
            return
        last_tab_name = str(self.settings_data.get("last_tab_name", "")).strip()
        if last_tab_name:
            for index in range(self.tabs.count()):
                if self.tabs.tabText(index) == last_tab_name:
                    self.tabs.setCurrentIndex(index)
                    return
            # Se a aba Stash nao existir nesta sessao, cair em Commit mantem fluxo esperado.
            if last_tab_name == "Stash":
                for index in range(self.tabs.count()):
                    if self.tabs.tabText(index) == "Commit":
                        self.tabs.setCurrentIndex(index)
                        return
        last_tab_index = int(self.settings_data.get("last_tab_index", 0) or 0)
        if 0 <= last_tab_index < self.tabs.count():
            self.tabs.setCurrentIndex(last_tab_index)

    def _load_workspace_root_from_settings(self) -> str:
        raw = self.settings_data.get("repo_scan_root", "")
        if isinstance(raw, str) and raw.strip():
            return normalize_repo_path(raw)
        return normalize_repo_path(default_repo_scan_root())

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)
        self.setCentralWidget(root)
        build_top_bar(self, root_layout, root)

        self.tabs = QTabWidget(root)
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.repositories_tab = QWidget(self.tabs)
        self.commit_tab = QWidget(self.tabs)
        self.stash_tab = QWidget()
        self.history_tab = QWidget(self.tabs)
        self.import_tab = QWidget(self.tabs)
        self.compare_tab = QWidget(self.tabs)
        self.settings_tab = QWidget(self.tabs)

        self.tabs.addTab(self.repositories_tab, TAB_NAMES[0])
        self.tabs.addTab(self.commit_tab, TAB_NAMES[1])
        self.tabs.addTab(self.history_tab, TAB_NAMES[2])
        self.tabs.addTab(self.import_tab, TAB_NAMES[3])
        self.tabs.addTab(self.compare_tab, TAB_NAMES[4])
        self.tabs.addTab(self.settings_tab, TAB_NAMES[5])

        self._build_repositories_tab()
        self._build_commit_tab()
        self._build_stash_tab()
        self.stash_tab.hide()
        self._build_history_tab()
        self._build_import_tab()
        self._build_compare_tab()
        self._build_settings_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self.tabs, stretch=1)

        build_status_bar(self, root)
        self._set_status("PySide6 shell iniciado.")
        self._set_busy_message("Pronto")

    def _apply_theme(self, theme: str, theme_overrides: object | None = None) -> None:
        app = QApplication.instance()
        if app is None:
            return
        resolved_theme = normalize_theme_name(theme)
        resolved_overrides = sanitize_theme_overrides(theme_overrides)
        app.setProperty("gv_theme_name", resolved_theme)
        app.setProperty("gv_theme_overrides", resolved_overrides)
        app.setStyleSheet(self._build_theme_stylesheet(resolved_theme, resolved_overrides))

        family = str(self.settings_data.get("ui_font_family", "")).strip()
        size_raw = self.settings_data.get("ui_font_size", 0)
        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = 0
        if family and size > 0:
            app.setFont(QFont(family, size))
        else:
            app.setFont(QFont("Noto Sans", 10))

        mono_font = QFont("JetBrains Mono", 10)
        for widget_name in (
            "history_patch_view",
            "compare_patch_view",
            "history_commit_info",
            "import_commit_info",
            "compare_commit_info",
            "commit_description_input",
            "commit_diff_view",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setFont(mono_font)

    def _apply_theme_from_settings(self) -> None:
        theme = str(self.settings_data.get("theme", "light"))
        theme_overrides = self.settings_data.get("theme_overrides", {})
        self._apply_theme(theme, theme_overrides)

    def _setup_background_timers(self) -> None:
        self._auto_status_timer = QTimer(self)
        self._auto_status_timer.timeout.connect(self._on_auto_status_timer)
        self._auto_fetch_timer = QTimer(self)
        self._auto_fetch_timer.timeout.connect(self._on_auto_fetch_timer)
        self._auto_history_timer = QTimer(self)
        self._auto_history_timer.timeout.connect(self._on_auto_history_timer)
        self._auto_workspace_timer = QTimer(self)
        self._auto_workspace_timer.timeout.connect(self._on_auto_workspace_timer)
        self._apply_background_update_profile()
        QTimer.singleShot(350, self._kick_background_refresh)

    def _apply_background_update_profile(self) -> None:
        self._auto_profile = resolve_update_profile(self.settings_data)
        status_ms = max(5, int(self._auto_profile.status_interval_sec)) * 1000
        fetch_ms = max(10, int(self._auto_profile.fetch_interval_sec)) * 1000
        history_ms = max(10, int(self._auto_profile.history_interval_sec)) * 1000
        workspace_ms = max(20, int(self._auto_profile.workspace_interval_sec)) * 1000
        self._auto_status_timer.setInterval(status_ms)
        self._auto_fetch_timer.setInterval(fetch_ms)
        self._auto_history_timer.setInterval(history_ms)
        self._auto_workspace_timer.setInterval(workspace_ms)
        self._auto_status_timer.start()
        self._auto_fetch_timer.start()
        self._auto_history_timer.start()
        self._auto_workspace_timer.start()

    def _kick_background_refresh(self) -> None:
        self._schedule_background_status_probe(force=True)
        self._schedule_history_head_probe(force=True)
        self._on_auto_workspace_timer()

    def _on_auto_status_timer(self) -> None:
        self._schedule_background_status_probe(force=False)

    def _on_auto_history_timer(self) -> None:
        self._schedule_history_head_probe(force=False)

    def _on_auto_workspace_timer(self) -> None:
        if self._busy_depth > 0:
            return
        if self.tabs.currentWidget() is not self.repositories_tab:
            return
        self._refresh_workspace_tree()

    def _on_auto_fetch_timer(self) -> None:
        if self._busy_depth > 0:
            return
        repo_path = self._get_resolved_repo_path(self.repo_path)
        if not repo_path:
            return
        upstream = core_get_upstream(repo_path)
        if not upstream:
            return
        self._submit_background_task("fetch", repo_path, _run_auto_fetch)

    def _schedule_background_status_probe(self, *, force: bool) -> None:
        if self._busy_depth > 0 and not force:
            return
        repo_path = self._get_resolved_repo_path(self.repo_path)
        if not repo_path:
            return
        self._submit_background_task("status", repo_path, _collect_repo_status_snapshot)

    def _schedule_history_head_probe(self, *, force: bool) -> None:
        if self._busy_depth > 0 and not force:
            return
        repo_path = self._get_resolved_repo_path(self.repo_path)
        if not repo_path:
            return
        self._submit_background_task("history_head", repo_path, _collect_history_head_snapshot)

    def _submit_background_task(self, kind: str, repo_path: str, task_func) -> None:
        active = self._auto_task_state.get(kind)
        if active is not None and active[0] == repo_path:
            return
        generation = self._repo_generation
        self._auto_task_state[kind] = (repo_path, generation)
        future = self._auto_executor.submit(task_func, repo_path)

        def done_callback(done_future) -> None:
            if self._is_closing:
                return
            try:
                payload = done_future.result()
                error = ""
            except Exception as exc:  # pragma: no cover - callback path
                payload = None
                error = str(exc)
            try:
                self._auto_update_bridge.finished.emit(kind, repo_path, generation, payload, error)
            except RuntimeError:  # pragma: no cover - janela encerrando
                return

        future.add_done_callback(done_callback)

    def _on_background_task_finished(
        self,
        kind: str,
        repo_path: str,
        generation: int,
        payload: object,
        error: str,
    ) -> None:
        if self._is_closing:
            return
        self._auto_task_state.pop(kind, None)
        if generation != self._repo_generation:
            return
        current_repo = self._get_resolved_repo_path(self.repo_path)
        if not current_repo or normalize_repo_path(repo_path) != normalize_repo_path(current_repo):
            return
        if error:
            if kind == "fetch":
                self._set_status(f"Auto fetch falhou: {error}")
            return
        if kind == "status":
            if isinstance(payload, dict):
                self._apply_repo_status_snapshot(payload)
            return
        if kind == "history_head":
            if isinstance(payload, dict):
                self._handle_history_head_snapshot(payload)
            return
        if kind == "fetch":
            self._set_status("Auto fetch concluido.")
            self._schedule_background_status_probe(force=True)
            self._schedule_history_head_probe(force=True)

    def _apply_repo_status_snapshot(self, snapshot: dict[str, object]) -> None:
        branches_raw = snapshot.get("branches", [])
        branches: list[str] = []
        if isinstance(branches_raw, list):
            for value in branches_raw:
                if isinstance(value, str):
                    candidate = value.strip()
                    if candidate:
                        branches.append(candidate)
        current_branch = str(snapshot.get("current_branch", "")).strip()
        default_branch = str(snapshot.get("default_branch", "")).strip()
        tracked_local_branches_raw = snapshot.get("tracked_local_branches", [])
        tracked_local_branches: set[str] = set()
        if isinstance(tracked_local_branches_raw, list):
            for value in tracked_local_branches_raw:
                if isinstance(value, str) and value.strip():
                    tracked_local_branches.add(value.strip())
        upstream = str(snapshot.get("upstream", "")).strip()
        behind = _safe_int(snapshot.get("behind"))
        ahead = _safe_int(snapshot.get("ahead"))

        has_repo = bool(self.repo_path)
        self.fetch_button.setEnabled(has_repo)
        self.new_branch_button.setEnabled(has_repo)
        self.branch_combo.setEnabled(has_repo)
        if not has_repo:
            return

        is_popup_open = bool(self.branch_combo.view().isVisible())
        if not is_popup_open:
            current_items = [
                str(self.branch_combo.itemData(index) or "").strip()
                for index in range(self.branch_combo.count())
            ]
            if current_items != branches:
                self._setting_branch_programmatically = True
                try:
                    self.branch_combo.clear()
                    for branch_name in branches:
                        self.branch_combo.addItem(
                            format_branch_display_label(
                                branch_name,
                                default_branch,
                                tracked_local_branches,
                            ),
                            branch_name,
                        )
                finally:
                    self._setting_branch_programmatically = False
            if current_branch:
                selected_index = self.branch_combo.findData(current_branch)
                if selected_index >= 0 and selected_index != self.branch_combo.currentIndex():
                    self._setting_branch_programmatically = True
                    try:
                        self.branch_combo.setCurrentIndex(selected_index)
                    finally:
                        self._setting_branch_programmatically = False

        if not upstream:
            self.behind_button.setEnabled(False)
            self.ahead_button.setEnabled(False)
            self.behind_button.setVisible(False)
            self.ahead_button.setVisible(False)
            self.behind_button.setText("Pull: 0")
            self.ahead_button.setText("Push: 0")
            self.behind_button.setToolTip("Pull indisponivel: branch sem upstream configurado.")
            self.ahead_button.setToolTip("Push indisponivel: branch sem upstream configurado.")
            self.fetch_button.setText("Fetch")
            self._sync_import_target_label()
            return

        self.behind_button.setText(f"Pull: {behind}")
        self.ahead_button.setText(f"Push: {ahead}")
        self.behind_button.setEnabled(behind > 0)
        self.ahead_button.setEnabled(ahead > 0)
        self.behind_button.setVisible(behind > 0)
        self.ahead_button.setVisible(ahead > 0)
        if behind > 0:
            self.behind_button.setToolTip(f"Pull ({behind} commit(s) remotos).")
        else:
            self.behind_button.setToolTip("Sem commits remotos pendentes para pull.")
        if ahead > 0:
            self.ahead_button.setToolTip(f"Push ({ahead} commit(s) locais).")
        else:
            self.ahead_button.setToolTip("Sem commits locais pendentes para push.")
        self.fetch_button.setText(f"Fetch ({behind})" if behind > 0 else "Fetch")
        self._sync_import_target_label()

    def _handle_history_head_snapshot(self, snapshot: dict[str, object]) -> None:
        head_hash = str(snapshot.get("head_hash", "")).strip()
        upstream_head = str(snapshot.get("upstream_head", "")).strip()
        signature = f"{head_hash}|{upstream_head}"
        if not signature:
            return
        if not self._history_probe_signature:
            self._history_probe_signature = signature
            return
        if signature == self._history_probe_signature:
            return
        self._history_probe_signature = signature
        if self.tabs.currentWidget() is self.history_tab:
            self._reload_history_commits()
            self._history_refresh_pending = False
            return
        self._history_refresh_pending = True

    def _invalidate_background_context(self) -> None:
        self._repo_generation += 1
        self._history_refresh_pending = False
        self._history_probe_signature = ""
        self._auto_task_state.clear()

    @staticmethod
    def _build_theme_stylesheet(theme: str, theme_overrides: object | None = None) -> str:
        return build_ui_theme_stylesheet(theme, theme_overrides)

    def _build_placeholder_tab(self, tab: QWidget, name: str) -> None:
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(
            QLabel(
                f"Migracao da aba {name} em andamento para PySide6.\n"
                "Use temporariamente a UI Tk para o fluxo completo desta aba.",
                tab,
            )
        )
        layout.addStretch(1)

    def _build_repositories_tab(self) -> None:
        build_repositories_tab(self)

    def _build_commit_tab(self) -> None:
        build_commit_tab(self)

    def _build_stash_tab(self) -> None:
        build_stash_tab(self)

    def _build_history_tab(self) -> None:
        build_history_tab(self)

    def _clear_history_view(self) -> None:
        clear_history_view(self)

    def _get_history_limit_value(self) -> int:
        return get_history_limit_value(self)

    def _reload_history_commits(self) -> None:
        reload_history_commits(self)

    def _load_more_history_commits(self) -> None:
        load_more_history_commits(self)

    def _open_history_export_dialog(self) -> None:
        open_history_export_dialog(self)

    def _open_history_reorder_dialog(self) -> None:
        open_history_reorder_dialog(self)

    def _on_history_commit_selected(self) -> None:
        on_history_commit_selected(self)

    def _on_history_commit_hovered(self, item) -> None:
        on_history_commit_hovered(self, item)

    def _on_history_search_text_changed(self, text: str) -> None:
        on_history_search_text_changed(self, text)

    def _on_history_scroll_value_changed(self, value: int) -> None:
        on_history_scroll_value_changed(self, value)

    def _on_history_commit_context_menu(self, pos: QPoint) -> None:
        on_history_commit_context_menu(self, pos)

    def _load_history_commit_content(self, commit_hash: str) -> None:
        load_history_commit_content(self, commit_hash)

    def _on_history_file_selected(self) -> None:
        on_history_file_selected(self)

    def _on_history_file_context_menu(self, pos: QPoint) -> None:
        on_history_file_context_menu(self, pos)

    def _refresh_history_patch_view(self) -> None:
        refresh_history_patch_view(self)

    def _build_import_tab(self) -> None:
        build_import_tab(self)

    def _sync_import_target_label(self) -> None:
        sync_import_target_label(self)

    def _clear_import_selection(self, status_message: str) -> None:
        clear_import_selection(self, status_message)

    def _refresh_import_source_repos(self) -> None:
        refresh_import_source_repos(self)

    def _open_import_clone_dialog(self) -> None:
        open_import_clone_dialog(self)

    def _on_import_source_repo_changed(self, _index: int) -> None:
        on_import_source_repo_changed(self, _index)

    def _apply_import_source_repo_from_combo(self) -> None:
        apply_import_source_repo_from_combo(self)

    def _use_current_repo_as_import_source(self) -> None:
        use_current_repo_as_import_source(self)

    def _load_import_source_branches(self) -> None:
        load_import_source_branches(self)

    def _on_import_source_branch_changed(self, _index: int) -> None:
        on_import_source_branch_changed(self, _index)

    def _load_import_source_commits(self) -> None:
        load_import_source_commits(self)

    def _on_import_commit_selected(self) -> None:
        on_import_commit_selected(self)

    def _on_import_file_selected(self) -> None:
        on_import_file_selected(self)

    def _refresh_import_patch_view(self) -> None:
        refresh_import_patch_view(self)

    def _on_import_commit_context_menu(self, pos: QPoint) -> None:
        on_import_commit_context_menu(self, pos)

    def _on_import_file_context_menu(self, pos: QPoint) -> None:
        on_import_file_context_menu(self, pos)

    def _get_selected_import_summaries(self) -> list[CommitSummary]:
        return get_selected_import_summaries(self)

    def _copy_selected_import_hashes(self) -> None:
        copy_selected_import_hashes(self)

    def _import_selected_commits(self) -> None:
        import_selected_commits(self)

    def _update_import_controls_state(self) -> None:
        update_import_controls_state(self)

    def _build_compare_tab(self) -> None:
        build_compare_tab(self)

    def _clear_compare_view(self) -> None:
        clear_compare_view(self)

    def _refresh_compare_branch_options(self) -> None:
        refresh_compare_branch_options(self)

    def _get_compare_branches(self) -> tuple[str, str]:
        return get_compare_branches(self)

    def _on_compare_branches_changed(self, _index: int) -> None:
        on_compare_branches_changed(self, _index)

    def _on_compare_action_changed(self, _index: int) -> None:
        on_compare_action_changed(self, _index)

    def _swap_compare_branches(self) -> None:
        swap_compare_branches(self)

    def _refresh_compare_view(self) -> None:
        refresh_compare_view(self)

    def _run_compare_action(self) -> None:
        run_compare_action(self)

    def _open_commit_tab_from_compare(self) -> None:
        if not hasattr(self, "tabs"):
            return
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == "Commit":
                self.tabs.setCurrentIndex(index)
                return

    def _show_conflicts_dialog(
        self,
        operation: str,
        *,
        source_label: str = "",
        continue_message: str = "",
    ) -> None:
        show_conflicts_dialog(
            self,
            operation,
            source_label=source_label,
            continue_message=continue_message,
        )

    def _on_compare_file_selected(self) -> None:
        on_compare_file_selected(self)

    def _on_compare_commit_selected(self) -> None:
        on_compare_commit_selected(self)

    def _on_compare_commit_context_menu(self, pos: QPoint) -> None:
        on_compare_commit_context_menu(self, pos)

    def _on_compare_file_context_menu(self, pos: QPoint) -> None:
        on_compare_file_context_menu(self, pos)

    def _refresh_compare_patch(self) -> None:
        refresh_compare_patch(self)

    def _build_settings_tab(self) -> None:
        build_settings_tab(self)

    def _load_settings_into_tab(self) -> None:
        load_settings_into_tab(self)

    def _pick_settings_workspace_root(self) -> None:
        pick_settings_workspace_root(self)

    def _on_settings_theme_changed(self) -> None:
        on_settings_theme_changed(self)

    def _on_settings_update_profile_changed(self) -> None:
        on_settings_update_profile_changed(self)

    def _on_settings_theme_color_edited(self, color_key: str) -> None:
        on_settings_theme_color_edited(self, color_key)

    def _pick_settings_theme_color(self, color_key: str) -> None:
        pick_settings_theme_color(self, color_key)

    def _reset_settings_theme_colors(self) -> None:
        reset_settings_theme_colors(self)

    def _save_settings_from_tab(self) -> None:
        save_settings_from_tab(self)

    def _collect_repo_paths_from_settings(self, key: str) -> list[str]:
        return collect_repo_paths_from_settings(self, key)

    def _repo_is_favorite(self, repo_path: str) -> bool:
        return repo_is_favorite(self, repo_path)

    def _format_workspace_relative_path(self, repo_path: str) -> str:
        return format_workspace_relative_path(self, repo_path)

    def _format_repo_display_label(self, repo_path: str) -> str:
        return format_repo_display_label(self, repo_path)

    def _collect_known_repos(self) -> list[str]:
        return collect_known_repos(self)

    def _load_repo_selector_items(self) -> None:
        load_repo_selector_items(self)

    def _on_workspace_root_edited(self) -> None:
        on_workspace_root_edited(self)

    def _pick_workspace_root(self) -> None:
        pick_workspace_root(self)

    def _scan_workspace_repos(self) -> None:
        scan_workspace_repos(self)

    def _open_clone_dialog(self, *, activate_repo: bool = True, on_success=None) -> None:
        open_clone_dialog(self, activate_repo=activate_repo, on_success=on_success)

    def _build_repo_status_summary(self, repo_path: str) -> str:
        return build_repo_status_summary(self, repo_path)

    def _build_repo_snapshot(self, repo_path: str) -> tuple[str, int, int, str]:
        return build_repo_snapshot(self, repo_path)

    def _refresh_workspace_tree(self) -> None:
        refresh_workspace_tree(self)

    def _sync_workspace_tree_selection(self) -> None:
        sync_workspace_tree_selection(self)

    def _on_workspace_selection_changed(self) -> None:
        on_workspace_selection_changed(self)

    def _on_workspace_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        on_workspace_item_double_clicked(self, item, _column)

    def _on_workspace_tree_context_menu(self, pos: QPoint) -> None:
        on_workspace_tree_context_menu(self, pos)

    def _refresh_commit_files(self) -> None:
        refresh_commit_files(self)

    def _iter_commit_items(self) -> list[QListWidgetItem]:
        return iter_commit_items(self)

    def _update_commit_selection_label(self) -> None:
        update_commit_selection_label(self)

    def _on_commit_file_item_changed(self, _item: QListWidgetItem) -> None:
        on_commit_file_item_changed(self, _item)

    def _on_commit_file_context_menu(self, pos: QPoint) -> None:
        on_commit_file_context_menu(self, pos)

    def _on_commit_diff_cursor_changed(self) -> None:
        on_commit_diff_cursor_changed(self)

    def _on_commit_diff_context_menu(self, pos: QPoint) -> None:
        on_commit_diff_context_menu(self, pos)

    def _on_commit_diff_marker_clicked(self, line_no: int) -> None:
        on_commit_diff_marker_clicked(self, line_no)

    def _on_commit_diff_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        on_commit_diff_item_clicked(self, item, column)

    def _on_commit_diff_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        on_commit_diff_item_changed(self, item, column)

    def _open_commit_diff_window(self) -> None:
        open_commit_diff_window(self)

    def _on_commit_file_selected(self) -> None:
        on_commit_file_selected(self)

    def _refresh_commit_diff(self) -> None:
        refresh_commit_diff(self)

    def _stage_selected_commit_file(self) -> None:
        stage_selected_commit_file(self)

    def _unstage_selected_commit_file(self) -> None:
        unstage_selected_commit_file(self)

    def _stage_selected_commit_hunk(self) -> None:
        stage_selected_commit_hunk(self)

    def _unstage_selected_commit_hunk(self) -> None:
        unstage_selected_commit_hunk(self)

    def _stage_selected_commit_line(self) -> None:
        stage_selected_commit_line(self)

    def _unstage_selected_commit_line(self) -> None:
        unstage_selected_commit_line(self)

    def _create_stash_from_commit_tab(self) -> None:
        create_stash_from_commit_tab(self)

    def _refresh_stash_tab_visibility(self) -> None:
        refresh_stash_tab_visibility(self)

    def _on_stash_entry_selected(self) -> None:
        on_stash_entry_selected(self)

    def _on_stash_entry_context_menu(self, pos: QPoint) -> None:
        on_stash_entry_context_menu(self, pos)

    def _on_stash_file_selected(self) -> None:
        on_stash_file_selected(self)

    def _refresh_stash_patch_view(self) -> None:
        refresh_stash_patch_view(self)

    def _apply_selected_stash(self) -> None:
        apply_selected_stash(self)

    def _pop_selected_stash(self) -> None:
        pop_selected_stash(self)

    def _drop_selected_stash(self) -> None:
        drop_selected_stash(self)

    def _undo_last_commit_from_commit_tab(self) -> None:
        undo_last_commit_from_commit_tab(self)

    def _select_all_commit_files(self) -> None:
        select_all_commit_files(self)

    def _clear_commit_file_selection(self) -> None:
        clear_commit_file_selection(self)

    def _get_selected_commit_paths(self) -> list[str]:
        return get_selected_commit_paths(self)

    def _create_commit_from_selection(self) -> None:
        create_commit_from_selection(self)

    def _set_repo(self, repo_path: str, *, save: bool) -> None:
        previous_repo = normalize_repo_path(self.repo_path) if self.repo_path else ""
        set_repo(self, repo_path, save=save)
        current_repo = normalize_repo_path(self.repo_path) if self.repo_path else ""
        if current_repo == previous_repo:
            return
        self._invalidate_background_context()
        self._schedule_background_status_probe(force=True)
        self._schedule_history_head_probe(force=True)

    def _select_repo_combo_item(self, repo_path: str) -> None:
        select_repo_combo_item(self, repo_path)

    def _refresh_repo_state_ui(self) -> None:
        refresh_repo_state_ui(self)

    def _add_recent_repo(self, repo_path: str) -> None:
        add_recent_repo(self, repo_path)

    def _persist_state(self) -> None:
        self.settings_data["last_repo_path"] = self.repo_path
        current_tab_index = self.tabs.currentIndex()
        self.settings_data["last_tab_index"] = current_tab_index
        current_tab_name = ""
        if 0 <= current_tab_index < self.tabs.count():
            current_tab_name = self.tabs.tabText(current_tab_index)
        self.settings_data["last_tab_name"] = current_tab_name
        self.settings_data["repo_scan_root"] = self.repo_scan_root
        save_settings(self.settings_path, self.settings_data)

    def _get_resolved_repo_path(self, repo_path: str = "") -> str:
        target = normalize_repo_path(repo_path) if repo_path else self.repo_path
        normalized = normalize_repo_path(target) if target else ""
        if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
            return ""
        return normalized

    def _resolve_repo_file_path(self, repo_relative_path: str, repo_path: str = "") -> str:
        repo_root = self._get_resolved_repo_path(repo_path)
        relative = repo_relative_path.replace("\\", "/").strip().lstrip("/")
        if not repo_root or not relative:
            return ""
        absolute_path = os.path.abspath(os.path.join(repo_root, relative))
        try:
            if os.path.commonpath([repo_root, absolute_path]) != repo_root:
                return ""
        except ValueError:
            return ""
        return absolute_path

    def _copy_to_clipboard(self, payload: str, *, status: str) -> bool:
        value = payload.strip()
        if not value:
            return False
        QApplication.clipboard().setText(value)
        self._set_status(status)
        return True

    def _open_url_in_browser(self, url: str) -> bool:
        target = url.strip()
        if not target:
            return False
        ok = QDesktopServices.openUrl(QUrl(target))
        if not ok:
            QMessageBox.warning(self, "Git Viewer", f"Nao foi possivel abrir URL:\n{target}")
            return False
        return True

    def _open_local_path_in_explorer(self, path: str) -> bool:
        normalized = os.path.abspath(path)
        if not os.path.exists(normalized):
            QMessageBox.warning(self, "Git Viewer", f"Caminho nao encontrado:\n{normalized}")
            return False
        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(normalized))
        if not ok:
            QMessageBox.warning(self, "Git Viewer", f"Nao foi possivel abrir caminho:\n{normalized}")
            return False
        return True

    def _open_repo_file_in_vscode(
        self,
        repo_relative_path: str,
        repo_path: str = "",
        line_no: int = 0,
    ) -> bool:
        absolute_path = self._resolve_repo_file_path(repo_relative_path, repo_path)
        if not absolute_path:
            QMessageBox.warning(self, "VS Code", "Arquivo invalido para abrir no VS Code.")
            return False
        code_bin = shutil.which("code")
        if not code_bin:
            QMessageBox.warning(self, "VS Code", "Comando 'code' nao encontrado no PATH.")
            return False
        goto_target = absolute_path
        if int(line_no) > 0:
            goto_target = f"{absolute_path}:{int(line_no)}:1"
        try:
            subprocess.Popen([code_bin, "--goto", goto_target])
        except OSError as exc:
            QMessageBox.critical(self, "VS Code", f"Falha ao abrir VS Code:\n{exc}")
            return False
        return True

    def _open_repo_file_in_explorer(self, repo_relative_path: str, repo_path: str = "") -> bool:
        absolute_path = self._resolve_repo_file_path(repo_relative_path, repo_path)
        if not absolute_path:
            QMessageBox.warning(self, "Git Viewer", "Arquivo invalido para abrir na pasta.")
            return False
        if os.path.isdir(absolute_path):
            target = absolute_path
        elif os.path.exists(absolute_path):
            target = os.path.dirname(absolute_path)
        else:
            target = os.path.dirname(absolute_path)
            if not os.path.isdir(target):
                target = self._get_resolved_repo_path(repo_path or self.repo_path)
        if not target:
            QMessageBox.warning(self, "Git Viewer", "Pasta do arquivo nao encontrada.")
            return False
        return self._open_local_path_in_explorer(target)

    def _open_repo_in_vscode(self, repo_path: str = "") -> bool:
        resolved_repo = self._get_resolved_repo_path(repo_path or self.repo_path)
        if not resolved_repo:
            QMessageBox.warning(self, "VS Code", "Repositorio invalido para abrir no VS Code.")
            return False
        code_bin = shutil.which("code")
        if not code_bin:
            QMessageBox.warning(self, "VS Code", "Comando 'code' nao encontrado no PATH.")
            return False
        try:
            subprocess.Popen([code_bin, resolved_repo])
        except OSError as exc:
            QMessageBox.critical(self, "VS Code", f"Falha ao abrir VS Code:\n{exc}")
            return False
        return True

    def _open_repo_in_explorer(self, repo_path: str = "") -> bool:
        resolved_repo = self._get_resolved_repo_path(repo_path or self.repo_path)
        if not resolved_repo:
            QMessageBox.warning(self, "Git Viewer", "Repositorio invalido para abrir na pasta.")
            return False
        return self._open_local_path_in_explorer(resolved_repo)

    def _get_repo_github_base_url(self, repo_path: str = "") -> str:
        resolved_repo = self._get_resolved_repo_path(repo_path or self.repo_path)
        if not resolved_repo:
            raise RuntimeError("Repositorio invalido para acao de GitHub.")
        return core_get_repo_github_base_url(resolved_repo)

    def _get_repo_branch_name(self, repo_path: str = "") -> str:
        resolved_repo = self._get_resolved_repo_path(repo_path or self.repo_path)
        if not resolved_repo:
            return ""
        try:
            return core_get_current_branch(resolved_repo).strip()
        except RuntimeError:
            return ""

    def _open_repo_in_github(self, repo_path: str = "") -> bool:
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(repo_base_url)

    def _open_repo_branch_in_github(self, repo_path: str = "") -> bool:
        branch = self._get_repo_branch_name(repo_path)
        if not branch:
            QMessageBox.information(self, "GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_repo_branch_url(repo_base_url, branch))

    def _open_repo_branch_commits_in_github(self, repo_path: str = "") -> bool:
        branch = self._get_repo_branch_name(repo_path)
        if not branch:
            QMessageBox.information(self, "GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_repo_branch_commits_url(repo_base_url, branch))

    def _open_repo_issues_in_github(self, repo_path: str = "") -> bool:
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_repo_issues_url(repo_base_url))

    def _open_repo_actions_in_github(self, repo_path: str = "") -> bool:
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_repo_actions_url(repo_base_url))

    def _open_repo_releases_in_github(self, repo_path: str = "") -> bool:
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_repo_releases_url(repo_base_url))

    def _copy_repo_github_url(self, repo_path: str = "") -> bool:
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._copy_to_clipboard(repo_base_url, status="URL do repositorio copiada.")

    def _copy_repo_branch_github_url(self, repo_path: str = "") -> bool:
        branch = self._get_repo_branch_name(repo_path)
        if not branch:
            QMessageBox.information(self, "GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        branch_url = core_build_repo_branch_url(repo_base_url, branch)
        return self._copy_to_clipboard(branch_url, status="URL da branch copiada.")

    def _prompt_pr_branch_selection(self, resolved_repo: str) -> tuple[str, str] | None:
        try:
            branch_options = core_list_branches(resolved_repo)
            default_base = core_get_default_base_branch_for_pr(resolved_repo).strip() or "main"
            default_head = core_get_current_branch_for_pr(resolved_repo).strip()
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return None
        if not default_head:
            default_head = self._get_repo_branch_name(resolved_repo)
        for branch_name in (default_base, default_head):
            if branch_name and branch_name not in branch_options:
                branch_options.append(branch_name)
        if not branch_options:
            QMessageBox.warning(self, "GitHub", "Nao foi possivel listar branches para abrir a PR.")
            return None
        if not default_base:
            default_base = branch_options[0]
        if not default_head:
            default_head = branch_options[0]
        if default_head == default_base and len(branch_options) > 1:
            for option in branch_options:
                if option != default_base:
                    default_head = option
                    break

        dialog = QDialog(self)
        dialog.setWindowTitle("Abrir PR no GitHub")
        dialog.setModal(True)
        dialog.resize(520, 190)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Escolha as branches para abrir a pagina de Pull Request.", dialog))

        base_row = QWidget(dialog)
        base_layout = QHBoxLayout(base_row)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setSpacing(6)
        base_layout.addWidget(QLabel("Destino (base):", base_row))
        base_combo = QComboBox(base_row)
        for branch_name in branch_options:
            base_combo.addItem(branch_name, branch_name)
        base_index = base_combo.findData(default_base)
        if base_index >= 0:
            base_combo.setCurrentIndex(base_index)
        base_layout.addWidget(base_combo, stretch=1)
        layout.addWidget(base_row)

        head_row = QWidget(dialog)
        head_layout = QHBoxLayout(head_row)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(6)
        head_layout.addWidget(QLabel("Origem (head):", head_row))
        head_combo = QComboBox(head_row)
        for branch_name in branch_options:
            head_combo.addItem(branch_name, branch_name)
        head_index = head_combo.findData(default_head)
        if head_index >= 0:
            head_combo.setCurrentIndex(head_index)
        head_layout.addWidget(head_combo, stretch=1)
        layout.addWidget(head_row)

        warning_label = QLabel("", dialog)
        layout.addWidget(warning_label)

        actions_row = QWidget(dialog)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        actions_layout.addStretch(1)
        cancel_button = QPushButton("Cancelar", actions_row)
        confirm_button = QPushButton("Abrir PR", actions_row)
        confirm_button.setProperty("role", "primary")
        actions_layout.addWidget(cancel_button)
        actions_layout.addWidget(confirm_button)
        layout.addWidget(actions_row)

        result: dict[str, tuple[str, str] | None] = {"value": None}

        def validate() -> None:
            base_branch = str(base_combo.currentData() or "").strip()
            head_branch = str(head_combo.currentData() or "").strip()
            valid = bool(base_branch and head_branch and base_branch != head_branch)
            if not valid:
                warning_label.setText("Origem e destino devem ser diferentes.")
            else:
                warning_label.setText("")
            confirm_button.setEnabled(valid)

        def cancel() -> None:
            result["value"] = None
            dialog.reject()

        def confirm() -> None:
            base_branch = str(base_combo.currentData() or "").strip()
            head_branch = str(head_combo.currentData() or "").strip()
            if not base_branch or not head_branch or base_branch == head_branch:
                validate()
                return
            result["value"] = (base_branch, head_branch)
            dialog.accept()

        base_combo.currentIndexChanged.connect(validate)
        head_combo.currentIndexChanged.connect(validate)
        cancel_button.clicked.connect(cancel)
        confirm_button.clicked.connect(confirm)
        validate()
        dialog.exec()
        return result["value"]

    def _open_commit_pr_in_github(self) -> bool:
        resolved_repo = self._get_resolved_repo_path(self.repo_path)
        if not resolved_repo:
            QMessageBox.information(self, "GitHub", "Selecione um repositorio valido.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        selection = self._prompt_pr_branch_selection(resolved_repo)
        if not selection:
            return False
        base_branch, head_branch = selection
        pr_url = core_build_pr_compare_url(repo_base_url, base_branch, head_branch)
        return self._open_url_in_browser(pr_url)

    def _open_commit_in_github(self, commit_hash: str, repo_path: str = "") -> bool:
        selected_hash = commit_hash.strip()
        if not selected_hash:
            QMessageBox.information(self, "GitHub", "Selecione um commit valido.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        return self._open_url_in_browser(core_build_commit_url(repo_base_url, selected_hash))

    def _copy_commit_github_url(self, commit_hash: str, repo_path: str = "") -> bool:
        selected_hash = commit_hash.strip()
        if not selected_hash:
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(repo_path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        url = core_build_commit_url(repo_base_url, selected_hash)
        return self._copy_to_clipboard(url, status="URL do commit copiada.")

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status"):
            self.status.showMessage(text, 5000)

    def _set_busy_message(self, text: str) -> None:
        if hasattr(self, "status_busy_label"):
            self.status_busy_label.setText(text)

    def _begin_busy(self, text: str) -> None:
        self._busy_depth += 1
        if self._busy_depth == 1:
            if hasattr(self, "status_busy_progress"):
                self.status_busy_progress.setVisible(True)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self._set_busy_message(text)
        if hasattr(self, "status"):
            self.status.showMessage(text)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _end_busy(self) -> None:
        if self._busy_depth > 0:
            self._busy_depth -= 1
        if self._busy_depth > 0:
            return
        self._set_busy_message("Pronto")
        if hasattr(self, "status_busy_progress"):
            self.status_busy_progress.setVisible(False)
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def _on_repo_changed(self, _index: int) -> None:
        if self._setting_repo_programmatically:
            return
        selected = self.repo_combo.currentData()
        selected_repo = str(selected).strip() if selected is not None else ""
        self._set_repo(selected_repo, save=True)

    def _on_repo_combo_context_menu(self, pos: QPoint) -> None:
        on_repo_combo_context_menu(self, pos)

    def _on_repo_combo_dropdown_context_menu(self, pos: QPoint) -> None:
        on_repo_combo_dropdown_context_menu(self, pos)

    def _on_branch_combo_context_menu(self, pos: QPoint) -> None:
        on_branch_combo_context_menu(self, pos)

    def _on_branch_combo_dropdown_context_menu(self, pos: QPoint) -> None:
        on_branch_combo_dropdown_context_menu(self, pos)

    def _on_branch_changed(self, _index: int) -> None:
        on_branch_changed(self, _index)

    def _create_new_branch(self) -> None:
        create_new_branch(self)

    def _fetch_repo(self) -> None:
        fetch_repo(self)

    def _pull_repo(self) -> None:
        pull_repo(self)

    def _push_repo(self) -> None:
        push_repo(self)

    def _on_tab_changed(self, _index: int) -> None:
        if self.tabs.currentWidget() is self.repositories_tab:
            self._on_auto_workspace_timer()
        if self.tabs.currentWidget() is self.history_tab and self._history_refresh_pending:
            self._reload_history_commits()
            self._history_refresh_pending = False
        self._persist_state()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        self._is_closing = True
        for timer_name in (
            "_auto_status_timer",
            "_auto_fetch_timer",
            "_auto_history_timer",
            "_auto_workspace_timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()
        self._invalidate_background_context()
        self._auto_executor.shutdown(wait=False, cancel_futures=True)
        self._persist_state()
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings_path = get_settings_path()
    startup_repo = _resolve_startup_repo(args.repo, settings_path)
    qt_args = [sys.argv[0]]
    app = QApplication(qt_args)
    window = QtShellWindow(startup_repo, settings_path)
    window.showMaximized()
    return app.exec()
