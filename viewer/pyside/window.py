#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ..core.git_client import is_git_repo
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
from ..core.repo_state import get_current_branch as core_get_current_branch
from ..core.settings_store import get_settings_path, load_settings, normalize_repo_path, save_settings
from .controllers import (
    add_recent_repo,
    apply_import_source_repo_from_combo,
    clear_import_selection,
    clear_commit_file_selection,
    clear_compare_view,
    collect_known_repos,
    collect_repo_paths_from_settings,
    create_commit_from_selection,
    format_repo_display_label,
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
    on_compare_commit_context_menu,
    on_compare_file_selected,
    on_branch_changed,
    on_workspace_item_double_clicked,
    on_workspace_tree_context_menu,
    on_workspace_root_edited,
    on_workspace_selection_changed,
    on_repo_combo_context_menu,
    on_repo_combo_dropdown_context_menu,
    open_clone_dialog,
    on_import_source_branch_changed,
    on_import_source_repo_changed,
    pick_workspace_root,
    pull_repo,
    push_repo,
    refresh_commit_files,
    refresh_commit_diff,
    refresh_import_source_repos,
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
    pick_settings_workspace_root,
    save_settings_from_tab,
    select_all_commit_files,
    stage_selected_commit_hunk,
    stage_selected_commit_line,
    stage_selected_commit_file,
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
    on_compare_file_context_menu,
    on_history_commit_context_menu,
    on_history_commit_selected,
    on_history_file_context_menu,
    on_import_commit_context_menu,
    on_history_file_selected,
    refresh_history_patch_view,
    reload_history_commits,
    show_conflicts_dialog,
)
from .layout import build_status_bar, build_top_bar
from .tabs import (
    build_commit_tab,
    build_compare_tab,
    build_history_tab,
    build_import_tab,
    build_repositories_tab,
    build_settings_tab,
)

try:
    from PySide6.QtCore import QPoint, Qt, QUrl
    from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QListWidgetItem,
        QLabel,
        QMainWindow,
        QMessageBox,
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

        self.setWindowTitle("Git Viewer (PySide6)")
        self.resize(1280, 820)

        self._apply_theme_from_settings()
        self._build_ui()
        self._load_repo_selector_items()

        initial_repo = self.repo_path
        if not initial_repo and self.repo_combo.count() > 0:
            initial_repo = self.repo_combo.currentData() or ""
        self._set_repo(initial_repo, save=True)

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
        self._build_history_tab()
        self._build_import_tab()
        self._build_compare_tab()
        self._build_settings_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self.tabs, stretch=1)

        build_status_bar(self, root)
        self._set_status("PySide6 shell iniciado.")
        self._set_busy_message("Pronto")

    def _apply_theme_from_settings(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme = str(self.settings_data.get("theme", "light"))
        app.setStyleSheet(self._build_theme_stylesheet(theme))

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
            "commit_description_input",
            "commit_diff_view",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setFont(mono_font)

    @staticmethod
    def _build_theme_stylesheet(theme: str) -> str:
        if theme == "dark":
            palette = {
                "bg": "#161b22",
                "fg": "#e6edf3",
                "panel": "#1f2630",
                "field": "#0d1117",
                "border": "#30363d",
                "accent": "#2f81f7",
                "accent_fg": "#ffffff",
                "accent_soft": "#1d3d67",
                "button_bg": "#222c38",
                "button_hover": "#2b3846",
                "chip_bg": "#1f3147",
            }
        else:
            palette = {
                "bg": "#eef1f5",
                "fg": "#1f2328",
                "panel": "#ffffff",
                "field": "#ffffff",
                "border": "#d0d7de",
                "accent": "#0969da",
                "accent_fg": "#ffffff",
                "accent_soft": "#dbeafe",
                "button_bg": "#f3f4f6",
                "button_hover": "#e5e9ef",
                "chip_bg": "#e7eef9",
            }
        return f"""
        QMainWindow {{
          background-color: {palette["bg"]};
        }}
        QWidget {{
          color: {palette["fg"]};
        }}
        QWidget#TopBar {{
          background-color: {palette["panel"]};
          border: 1px solid {palette["border"]};
          border-radius: 10px;
        }}
        QTabWidget::pane {{
          border: 1px solid {palette["border"]};
          border-radius: 10px;
          background-color: {palette["panel"]};
          margin-top: 6px;
          padding: 6px;
        }}
        QTabBar::tab {{
          background-color: {palette["button_bg"]};
          border: 1px solid {palette["border"]};
          border-bottom: none;
          border-top-left-radius: 8px;
          border-top-right-radius: 8px;
          padding: 7px 12px;
          margin-right: 4px;
        }}
        QTabBar::tab:selected {{
          background-color: {palette["panel"]};
          color: {palette["fg"]};
          border-color: {palette["accent"]};
        }}
        QLineEdit, QComboBox, QPlainTextEdit, QListWidget, QTreeWidget {{
          background-color: {palette["field"]};
          border: 1px solid {palette["border"]};
          border-radius: 8px;
          padding: 6px;
          selection-background-color: {palette["accent_soft"]};
        }}
        QTreeWidget::item {{
          height: 22px;
        }}
        QPushButton {{
          background-color: {palette["button_bg"]};
          border: 1px solid {palette["border"]};
          border-radius: 8px;
          padding: 6px 10px;
        }}
        QPushButton:hover {{
          background-color: {palette["button_hover"]};
          border-color: {palette["accent"]};
        }}
        QPushButton[role="primary"] {{
          background-color: {palette["accent"]};
          color: {palette["accent_fg"]};
          border-color: {palette["accent"]};
          font-weight: 600;
        }}
        QPushButton[role="primary"]:hover {{
          background-color: {palette["accent"]};
          border-color: {palette["accent"]};
        }}
        QLabel#SyncChip, QLabel#BusyBadge {{
          background-color: {palette["chip_bg"]};
          border: 1px solid {palette["border"]};
          border-radius: 10px;
          padding: 3px 8px;
        }}
        QProgressBar#BusyBar {{
          background-color: {palette["field"]};
          border: 1px solid {palette["border"]};
          border-radius: 8px;
        }}
        QProgressBar#BusyBar::chunk {{
          background-color: {palette["accent"]};
          border-radius: 8px;
        }}
        """

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

    def _build_history_tab(self) -> None:
        build_history_tab(self)

    def _clear_history_view(self) -> None:
        clear_history_view(self)

    def _get_history_limit_value(self) -> int:
        return get_history_limit_value(self)

    def _reload_history_commits(self) -> None:
        reload_history_commits(self)

    def _on_history_commit_selected(self) -> None:
        on_history_commit_selected(self)

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

    def _on_import_commit_context_menu(self, pos: QPoint) -> None:
        on_import_commit_context_menu(self, pos)

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

    def _open_clone_dialog(self) -> None:
        open_clone_dialog(self)

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

    def _on_commit_diff_cursor_changed(self) -> None:
        on_commit_diff_cursor_changed(self)

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

    def _select_all_commit_files(self) -> None:
        select_all_commit_files(self)

    def _clear_commit_file_selection(self) -> None:
        clear_commit_file_selection(self)

    def _get_selected_commit_paths(self) -> list[str]:
        return get_selected_commit_paths(self)

    def _create_commit_from_selection(self) -> None:
        create_commit_from_selection(self)

    def _set_repo(self, repo_path: str, *, save: bool) -> None:
        set_repo(self, repo_path, save=save)

    def _select_repo_combo_item(self, repo_path: str) -> None:
        select_repo_combo_item(self, repo_path)

    def _refresh_repo_state_ui(self) -> None:
        refresh_repo_state_ui(self)

    def _add_recent_repo(self, repo_path: str) -> None:
        add_recent_repo(self, repo_path)

    def _persist_state(self) -> None:
        self.settings_data["last_repo_path"] = self.repo_path
        self.settings_data["last_tab_index"] = self.tabs.currentIndex()
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

    def _open_repo_file_in_vscode(self, repo_relative_path: str, repo_path: str = "") -> bool:
        absolute_path = self._resolve_repo_file_path(repo_relative_path, repo_path)
        if not absolute_path:
            QMessageBox.warning(self, "VS Code", "Arquivo invalido para abrir no VS Code.")
            return False
        code_bin = shutil.which("code")
        if not code_bin:
            QMessageBox.warning(self, "VS Code", "Comando 'code' nao encontrado no PATH.")
            return False
        try:
            subprocess.Popen([code_bin, "--goto", absolute_path])
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

    def _open_commit_pr_in_github(self) -> bool:
        resolved_repo = self._get_resolved_repo_path(self.repo_path)
        if not resolved_repo:
            QMessageBox.information(self, "GitHub", "Selecione um repositorio valido.")
            return False
        try:
            repo_base_url = self._get_repo_github_base_url(resolved_repo)
            base_branch = core_get_default_base_branch_for_pr(resolved_repo).strip() or "main"
            head_branch = core_get_current_branch_for_pr(resolved_repo).strip()
        except RuntimeError as exc:
            QMessageBox.warning(self, "GitHub", str(exc))
            return False
        if not head_branch:
            QMessageBox.information(self, "GitHub", "Nao foi possivel identificar a branch atual.")
            return False
        if head_branch == base_branch:
            QMessageBox.information(
                self,
                "GitHub",
                "Branch atual igual a branch base. Crie ou troque para uma branch de trabalho.",
            )
            return False
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
        self._persist_state()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
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
