#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ..core.git_client import is_git_repo
from ..core.models import CommitSummary
from ..core.remote_ops import (
    fetch_all_prune as core_fetch_all_prune,
    pull_ff_only as core_pull_ff_only,
    push_current_branch as core_push_current_branch,
)
from ..core.repo_state import (
    get_current_branch as core_get_current_branch,
)
from ..core.repo_workspace import default_repo_scan_root
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
    on_commit_file_item_changed,
    on_compare_branches_changed,
    on_compare_file_selected,
    on_workspace_item_double_clicked,
    on_workspace_root_edited,
    on_workspace_selection_changed,
    on_import_source_branch_changed,
    on_import_source_repo_changed,
    pick_workspace_root,
    refresh_commit_files,
    refresh_import_source_repos,
    refresh_compare_branch_options,
    refresh_compare_patch,
    refresh_compare_view,
    refresh_repo_state_ui,
    refresh_workspace_tree,
    repo_is_favorite,
    scan_workspace_repos,
    select_repo_combo_item,
    set_repo,
    load_settings_into_tab,
    pick_settings_workspace_root,
    save_settings_from_tab,
    select_all_commit_files,
    sync_workspace_tree_selection,
    sync_import_target_label,
    swap_compare_branches,
    update_commit_selection_label,
    update_import_controls_state,
    use_current_repo_as_import_source,
    copy_selected_import_hashes,
    clear_history_view,
    get_history_limit_value,
    load_history_commit_content,
    on_history_commit_selected,
    on_history_file_selected,
    refresh_history_patch_view,
    reload_history_commits,
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
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QInputDialog,
        QListWidget,
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

    def _load_history_commit_content(self, commit_hash: str) -> None:
        load_history_commit_content(self, commit_hash)

    def _on_history_file_selected(self) -> None:
        on_history_file_selected(self)

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

    def _swap_compare_branches(self) -> None:
        swap_compare_branches(self)

    def _refresh_compare_view(self) -> None:
        refresh_compare_view(self)

    def _on_compare_file_selected(self) -> None:
        on_compare_file_selected(self)

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

    def _refresh_commit_files(self) -> None:
        refresh_commit_files(self)

    def _iter_commit_items(self) -> list[QListWidgetItem]:
        return iter_commit_items(self)

    def _update_commit_selection_label(self) -> None:
        update_commit_selection_label(self)

    def _on_commit_file_item_changed(self, _item: QListWidgetItem) -> None:
        on_commit_file_item_changed(self, _item)

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

    def _on_branch_changed(self, _index: int) -> None:
        if self._setting_branch_programmatically:
            return
        if not self.repo_path:
            return
        selected = self.branch_combo.currentData()
        target = str(selected).strip() if selected is not None else ""
        if not target:
            return
        try:
            current = core_get_current_branch(self.repo_path).strip()
        except RuntimeError:
            return
        if current == target:
            return
        try:
            core_checkout_branch(self.repo_path, target)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Checkout", str(exc))
            self._refresh_repo_state_ui()
            return
        self._set_status(f"Checkout concluido: {target}")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._sync_import_target_label()
        self._persist_state()

    def _create_new_branch(self) -> None:
        if not self.repo_path:
            return
        branch_name, ok = QInputDialog.getText(self, "Nova branch", "Nome da branch:")
        if not ok:
            return
        normalized = branch_name.strip()
        if not normalized:
            return
        try:
            current = core_get_current_branch(self.repo_path).strip()
            core_create_branch(self.repo_path, normalized, current)
            core_checkout_branch(self.repo_path, normalized)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Nova branch", str(exc))
            return
        self._set_status(f"Branch criada: {normalized}")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._persist_state()

    def _fetch_repo(self) -> None:
        if not self.repo_path:
            return
        self._begin_busy("Executando fetch...")
        try:
            try:
                core_fetch_all_prune(self.repo_path)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Fetch", str(exc))
                return
        finally:
            self._end_busy()
        self._set_status("Fetch concluido.")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_view()
        self._persist_state()

    def _pull_repo(self) -> None:
        if not self.repo_path:
            return
        self._begin_busy("Executando pull...")
        try:
            try:
                core_pull_ff_only(self.repo_path)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Pull", str(exc))
                return
        finally:
            self._end_busy()
        self._set_status("Pull concluido.")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._persist_state()

    def _push_repo(self) -> None:
        if not self.repo_path:
            return
        self._begin_busy("Executando push...")
        try:
            try:
                core_push_current_branch(self.repo_path)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Push", str(exc))
                return
        finally:
            self._end_busy()
        self._set_status("Push concluido.")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_view()
        self._persist_state()

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
