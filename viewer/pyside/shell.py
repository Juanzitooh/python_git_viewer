#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ..core.cherry_pick_ops import (
    cherry_pick_commit as core_cherry_pick_commit,
    has_unmerged_conflicts as core_has_unmerged_conflicts,
)
from ..core.commit_ops import (
    create_commit as core_create_commit,
    has_staged_changes as core_has_staged_changes,
    list_modified_files as core_list_modified_files,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
)
from ..core.git_client import is_git_repo, load_commit_summaries
from ..core.models import CommitFilters, CommitSummary
from ..core.remote_ops import (
    fetch_all_prune as core_fetch_all_prune,
    pull_ff_only as core_pull_ff_only,
    push_current_branch as core_push_current_branch,
)
from ..core.repo_state import (
    get_ahead_behind as core_get_ahead_behind,
    get_current_branch as core_get_current_branch,
    get_upstream as core_get_upstream,
    list_branches as core_list_branches,
    list_worktree_changed_files as core_list_worktree_changed_files,
)
from ..core.repo_workspace import default_repo_scan_root, discover_git_repositories
from ..core.settings_store import get_settings_path, load_settings, normalize_repo_path, save_settings
from .controllers import (
    clear_compare_view,
    get_compare_branches,
    on_compare_branches_changed,
    on_compare_file_selected,
    refresh_compare_branch_options,
    refresh_compare_patch,
    refresh_compare_view,
    swap_compare_branches,
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
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QFileDialog,
        QComboBox,
        QInputDialog,
        QListWidget,
        QListWidgetItem,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QTabWidget,
        QTreeWidget,
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

RECENT_REPOS_LIMIT = 20


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
        if not hasattr(self, "import_target_label"):
            return
        if not self.repo_path:
            self.import_target_label.setText("Destino: (nenhum repositório selecionado)")
            return
        try:
            branch = core_get_current_branch(self.repo_path).strip()
        except RuntimeError:
            branch = "(desconhecida)"
        display = self._format_workspace_relative_path(self.repo_path)
        self.import_target_label.setText(f"Destino: {display} | Branch atual: {branch}")

    def _clear_import_selection(self, status_message: str) -> None:
        self.import_commit_summaries = []
        if hasattr(self, "import_commits_list"):
            self.import_commits_list.clear()
        self.import_status_label.setText(status_message)
        self._update_import_controls_state()

    def _refresh_import_source_repos(self) -> None:
        if not hasattr(self, "import_source_repo_combo"):
            return
        repos = self._collect_known_repos()
        source_path = normalize_repo_path(self.import_source_repo_path) if self.import_source_repo_path else ""

        labels: list[str] = []
        lookup: dict[str, str] = {}
        for repo in repos:
            label_base = self._format_repo_display_label(repo)
            label = label_base
            suffix = 2
            while label in lookup:
                label = f"{label_base} [{suffix}]"
                suffix += 1
            labels.append(label)
            lookup[label] = repo
        self.import_source_repo_lookup = lookup

        self.import_source_repo_combo.blockSignals(True)
        self.import_source_repo_combo.clear()
        for label in labels:
            self.import_source_repo_combo.addItem(label, lookup[label])
        self.import_source_repo_combo.blockSignals(False)

        if source_path and source_path in lookup.values():
            idx = self.import_source_repo_combo.findData(source_path)
            if idx >= 0:
                self.import_source_repo_combo.setCurrentIndex(idx)
        elif labels:
            self.import_source_repo_combo.setCurrentIndex(0)
        else:
            self.import_source_repo_path = ""
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Nenhum repositório disponível para origem.")

        if self.import_source_repo_combo.count() > 0:
            self._apply_import_source_repo_from_combo()
        self._update_import_controls_state()

    def _on_import_source_repo_changed(self, _index: int) -> None:
        self._apply_import_source_repo_from_combo()

    def _apply_import_source_repo_from_combo(self) -> None:
        selected = self.import_source_repo_combo.currentData()
        repo = str(selected).strip() if selected is not None else ""
        if not repo:
            self.import_source_repo_path = ""
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Selecione o repositório de origem para carregar commits.")
            return
        normalized = normalize_repo_path(repo)
        if not os.path.isdir(normalized) or not is_git_repo(normalized):
            self.import_source_repo_path = ""
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Repositório de origem inválido.")
            return
        self.import_source_repo_path = normalized
        self._load_import_source_branches()

    def _use_current_repo_as_import_source(self) -> None:
        if not self.repo_path:
            QMessageBox.information(self, "Importar", "Selecione um repositório destino válido primeiro.")
            return
        index = self.import_source_repo_combo.findData(self.repo_path)
        if index < 0:
            self._refresh_import_source_repos()
            index = self.import_source_repo_combo.findData(self.repo_path)
        if index >= 0:
            self.import_source_repo_combo.setCurrentIndex(index)
            self._apply_import_source_repo_from_combo()

    def _load_import_source_branches(self) -> None:
        source_repo = self.import_source_repo_path
        if not source_repo:
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Selecione o repositório de origem para carregar commits.")
            return
        try:
            branches = core_list_branches(source_repo)
            current = core_get_current_branch(source_repo).strip()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Importar", str(exc))
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Falha ao carregar branches da origem.")
            return
        if not branches:
            self.import_source_branch_combo.clear()
            self._clear_import_selection("Nenhuma branch encontrada na origem.")
            return
        self.import_source_branch_combo.blockSignals(True)
        self.import_source_branch_combo.clear()
        for branch in branches:
            self.import_source_branch_combo.addItem(branch, branch)
        self.import_source_branch_combo.blockSignals(False)
        idx = self.import_source_branch_combo.findData(current)
        if idx < 0:
            idx = 0
        self.import_source_branch_combo.setCurrentIndex(idx)
        self._load_import_source_commits()

    def _on_import_source_branch_changed(self, _index: int) -> None:
        self._load_import_source_commits()

    def _load_import_source_commits(self) -> None:
        self._begin_busy("Carregando commits de origem...")
        try:
            source_repo = self.import_source_repo_path
            selected_branch = self.import_source_branch_combo.currentData()
            branch = str(selected_branch).strip() if selected_branch is not None else ""
            if not source_repo or not branch:
                self._clear_import_selection("Selecione origem e branch para carregar commits.")
                return
            self.import_status_label.setText(f"Carregando commits de {branch}...")
            filters = CommitFilters(ref=branch)
            limit_raw = self.settings_data.get("commit_limit", 100)
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 100
            limit = max(1, limit)
            try:
                summaries = load_commit_summaries(source_repo, limit=limit, filters=filters)
            except RuntimeError as exc:
                QMessageBox.critical(self, "Importar", str(exc))
                self._clear_import_selection("Falha ao carregar commits da origem.")
                return
            self.import_commit_summaries = summaries
            self.import_commits_list.clear()
            for summary in summaries:
                label = f"{summary.commit_hash[:7]} | {summary.subject}"
                item = QListWidgetItem(label, self.import_commits_list)
                item.setData(Qt.ItemDataRole.UserRole, summary.commit_hash)
            if summaries:
                self.import_status_label.setText(f"{len(summaries)} commits carregados da branch {branch}.")
            else:
                self.import_status_label.setText(f"Nenhum commit encontrado na branch {branch}.")
            self._update_import_controls_state()
        finally:
            self._end_busy()

    def _get_selected_import_summaries(self) -> list[CommitSummary]:
        selected_indexes = self.import_commits_list.selectedIndexes()
        if not selected_indexes:
            return []
        selected_hashes: list[str] = []
        for model_index in sorted(selected_indexes, key=lambda index: int(index.row())):
            item = self.import_commits_list.item(model_index.row())
            if item is None:
                continue
            value = item.data(Qt.ItemDataRole.UserRole)
            commit_hash = str(value).strip() if value is not None else ""
            if commit_hash:
                selected_hashes.append(commit_hash)
        summaries_by_hash = {item.commit_hash: item for item in self.import_commit_summaries}
        selected: list[CommitSummary] = []
        for commit_hash in selected_hashes:
            summary = summaries_by_hash.get(commit_hash)
            if summary is not None:
                selected.append(summary)
        return selected

    def _copy_selected_import_hashes(self) -> None:
        selected = self._get_selected_import_summaries()
        if not selected:
            QMessageBox.information(self, "Importar", "Selecione commits para copiar os hashes.")
            return
        payload = "\n".join(item.commit_hash for item in selected)
        QApplication.clipboard().setText(payload)
        self._set_status("Hashes copiados.")

    def _import_selected_commits(self) -> None:
        if not self.repo_path:
            QMessageBox.information(self, "Importar", "Selecione um repositório destino válido primeiro.")
            return
        source_repo = self.import_source_repo_path
        if not source_repo:
            QMessageBox.warning(self, "Importar", "Selecione o repositório de origem.")
            return
        selected = self._get_selected_import_summaries()
        if not selected:
            QMessageBox.warning(self, "Importar", "Selecione ao menos um commit para importar.")
            return
        target_branch = self.branch_combo.currentData()
        target = str(target_branch).strip() if target_branch is not None else ""
        if not target:
            target = core_get_current_branch(self.repo_path).strip()
        source_branch_data = self.import_source_branch_combo.currentData()
        source_branch = str(source_branch_data).strip() if source_branch_data is not None else ""
        confirm = QMessageBox.question(
            self,
            "Importar commits",
            (
                f"Importar {len(selected)} commit(s)\n"
                f"Origem: {source_repo} ({source_branch or '(sem branch)'})\n"
                f"Destino: {self.repo_path} ({target or '(desconhecida)'})"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        source_is_target = normalize_repo_path(source_repo) == normalize_repo_path(self.repo_path)
        ordered = list(reversed(selected))
        applied = 0
        self.import_status_label.setText("Importando commits...")
        self._begin_busy(f"Importando commits (0/{len(ordered)})...")
        try:
            for summary in ordered:
                self._set_busy_message(f"Importando commits ({applied + 1}/{len(ordered)})...")
                try:
                    core_cherry_pick_commit(
                        self.repo_path,
                        summary.commit_hash,
                        source_repo=source_repo,
                        fetch_source=not source_is_target,
                    )
                except RuntimeError as exc:
                    has_conflicts = False
                    try:
                        has_conflicts = core_has_unmerged_conflicts(self.repo_path)
                    except RuntimeError:
                        has_conflicts = False
                    suffix = "Conflitos detectados." if has_conflicts else "Importação interrompida."
                    QMessageBox.critical(
                        self,
                        "Importar",
                        f"Falha ao importar {summary.commit_hash[:7]}.\n{exc}\n{suffix}",
                    )
                    self.import_status_label.setText(f"Importação interrompida após {applied} commit(s).")
                    self._refresh_repo_state_ui()
                    self._refresh_workspace_tree()
                    self._reload_history_commits()
                    self._refresh_compare_branch_options()
                    self._refresh_commit_files()
                    self._update_import_controls_state()
                    return
                applied += 1
        finally:
            self._end_busy()

        self.import_status_label.setText(f"Importação concluída: {applied} commit(s) em {target}.")
        self._set_status(f"Importado em {target}: {applied} commit(s).")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._refresh_commit_files()
        self._load_import_source_commits()
        self._update_import_controls_state()

    def _update_import_controls_state(self) -> None:
        if not hasattr(self, "import_run_button"):
            return
        source_ready = bool(self.import_source_repo_path and self.import_source_branch_combo.currentData())
        selected = bool(self.import_commits_list.selectedItems())
        has_source_options = self.import_source_repo_combo.count() > 0
        can_import = bool(self.repo_path and source_ready and selected)
        self.import_run_button.setEnabled(can_import)
        self.import_copy_hashes_button.setEnabled(selected)
        self.import_source_branch_combo.setEnabled(source_ready or bool(self.import_source_repo_path))
        self.import_source_branch_refresh_button.setEnabled(source_ready)
        self.import_source_repo_combo.setEnabled(has_source_options)
        self.import_source_repo_refresh_button.setEnabled(True)

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
        if not hasattr(self, "settings_theme_combo"):
            return
        theme = str(self.settings_data.get("theme", "light"))
        theme_index = self.settings_theme_combo.findData(theme)
        if theme_index < 0:
            theme_index = self.settings_theme_combo.findData("light")
        if theme_index >= 0:
            self.settings_theme_combo.setCurrentIndex(theme_index)

        commit_limit_raw = self.settings_data.get("commit_limit", 100)
        try:
            commit_limit = int(commit_limit_raw)
        except (TypeError, ValueError):
            commit_limit = 100
        limit_index = self.settings_commit_limit_combo.findData(commit_limit)
        if limit_index < 0:
            limit_index = self.settings_commit_limit_combo.findData(100)
        if limit_index >= 0:
            self.settings_commit_limit_combo.setCurrentIndex(limit_index)

        workspace_root = str(self.settings_data.get("repo_scan_root", self.repo_scan_root)).strip()
        if workspace_root:
            workspace_root = normalize_repo_path(workspace_root)
        else:
            workspace_root = normalize_repo_path(default_repo_scan_root())
        self.settings_workspace_root_edit.setText(workspace_root)

    def _pick_settings_workspace_root(self) -> None:
        current = self.settings_workspace_root_edit.text().strip() or self.repo_scan_root
        selected = QFileDialog.getExistingDirectory(self, "Selecionar raiz do workspace", current)
        if not selected:
            return
        normalized = normalize_repo_path(selected)
        self.settings_workspace_root_edit.setText(normalized)

    def _save_settings_from_tab(self) -> None:
        theme_data = self.settings_theme_combo.currentData()
        theme = str(theme_data).strip() if theme_data is not None else "light"
        if theme not in ("light", "dark"):
            theme = "light"

        limit_data = self.settings_commit_limit_combo.currentData()
        try:
            commit_limit = int(limit_data)
        except (TypeError, ValueError):
            commit_limit = 100
        commit_limit = max(1, commit_limit)

        workspace_text = self.settings_workspace_root_edit.text().strip()
        workspace_root = normalize_repo_path(workspace_text) if workspace_text else normalize_repo_path(default_repo_scan_root())

        self.settings_data["theme"] = theme
        self.settings_data["commit_limit"] = commit_limit
        self.settings_data["repo_scan_root"] = workspace_root
        self.repo_scan_root = workspace_root

        self._persist_state()
        self._apply_theme_from_settings()
        self.workspace_root_edit.setText(self.repo_scan_root)
        self._scan_workspace_repos()
        self._reload_history_commits()
        self.settings_status_label.setText("Configurações salvas.")
        self._set_status("Configurações salvas.")

    def _collect_repo_paths_from_settings(self, key: str) -> list[str]:
        items = self.settings_data.get(key, [])
        if not isinstance(items, list):
            return []
        repos: list[str] = []
        for raw in items:
            if not isinstance(raw, str):
                continue
            normalized = normalize_repo_path(raw)
            if not os.path.isdir(normalized) or not is_git_repo(normalized):
                continue
            if normalized not in repos:
                repos.append(normalized)
        return repos

    def _repo_is_favorite(self, repo_path: str) -> bool:
        favorites = self._collect_repo_paths_from_settings("favorite_repos")
        return normalize_repo_path(repo_path) in favorites

    def _format_workspace_relative_path(self, repo_path: str) -> str:
        normalized_repo = normalize_repo_path(repo_path)
        root = normalize_repo_path(self.repo_scan_root) if self.repo_scan_root else ""
        if root:
            try:
                relative = os.path.relpath(normalized_repo, root)
            except ValueError:
                relative = normalized_repo
            if not relative.startswith(".."):
                return f"/{relative}".replace("\\", "/")
        return normalized_repo

    def _format_repo_display_label(self, repo_path: str) -> str:
        base_name = os.path.basename(repo_path.rstrip(os.sep)) or repo_path
        relative = self._format_workspace_relative_path(repo_path)
        favorite_prefix = "★ " if self._repo_is_favorite(repo_path) else ""
        return f"{favorite_prefix}{base_name} {relative}"

    def _collect_known_repos(self) -> list[str]:
        ordered: list[str] = []
        for source in (
            self._collect_repo_paths_from_settings("favorite_repos"),
            self._collect_repo_paths_from_settings("recent_repos"),
            self.scanned_repos,
            [self.repo_path] if self.repo_path else [],
        ):
            for repo in source:
                normalized = normalize_repo_path(repo)
                if normalized in ordered:
                    continue
                if not os.path.isdir(normalized) or not is_git_repo(normalized):
                    continue
                ordered.append(normalized)
        return ordered

    def _load_repo_selector_items(self) -> None:
        selected = self.repo_path
        if not selected:
            current = self.repo_combo.currentData()
            selected = str(current).strip() if current is not None else ""
        repos = self._collect_known_repos()
        self._setting_repo_programmatically = True
        try:
            self.repo_combo.clear()
            for repo in repos:
                self.repo_combo.addItem(self._format_repo_display_label(repo), repo)
            if selected:
                index = self.repo_combo.findData(selected)
                if index >= 0:
                    self.repo_combo.setCurrentIndex(index)
        finally:
            self._setting_repo_programmatically = False

    def _on_workspace_root_edited(self) -> None:
        candidate = self.workspace_root_edit.text().strip()
        normalized = normalize_repo_path(candidate) if candidate else normalize_repo_path(default_repo_scan_root())
        if normalized == self.repo_scan_root:
            return
        self.repo_scan_root = normalized
        self.workspace_root_edit.setText(self.repo_scan_root)
        self._scan_workspace_repos()
        self._persist_state()

    def _pick_workspace_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar raiz do workspace", self.repo_scan_root)
        if not selected:
            return
        self.repo_scan_root = normalize_repo_path(selected)
        self.workspace_root_edit.setText(self.repo_scan_root)
        self._scan_workspace_repos()
        self._persist_state()

    def _scan_workspace_repos(self) -> None:
        self._begin_busy("Escaneando workspace...")
        try:
            root = normalize_repo_path(self.repo_scan_root) if self.repo_scan_root else normalize_repo_path(default_repo_scan_root())
            os.makedirs(root, exist_ok=True)
            self.repo_scan_root = root
            self.workspace_root_edit.setText(root)
            discovered = discover_git_repositories(root, max_depth=4)
            self.scanned_repos = [normalize_repo_path(path) for path in discovered]
            self.workspace_scan_status_label.setText(
                f"Scan inicial: {len(self.scanned_repos)} encontrados em {root}"
            )
            self._load_repo_selector_items()
            self._refresh_workspace_tree()
            self._refresh_import_source_repos()
        finally:
            self._end_busy()

    def _build_repo_status_summary(self, repo_path: str) -> str:
        try:
            changed = core_list_worktree_changed_files(repo_path)
        except RuntimeError:
            return "(indisponivel)"
        if not changed:
            return "limpo"
        if len(changed) <= 2:
            suffix = "arquivo" if len(changed) == 1 else "arquivos"
            return f"{len(changed)} {suffix}: {', '.join(changed)}"
        return f"{len(changed)} arquivos: {changed[0]}, {changed[1]}, +{len(changed) - 2}"

    def _build_repo_snapshot(self, repo_path: str) -> tuple[str, int, int, str]:
        branch = "(desconhecida)"
        ahead = 0
        behind = 0
        try:
            branch = core_get_current_branch(repo_path).strip() or branch
        except RuntimeError:
            return branch, ahead, behind, "(indisponivel)"
        upstream = core_get_upstream(repo_path)
        if upstream:
            try:
                behind, ahead = core_get_ahead_behind(repo_path, upstream)
            except RuntimeError:
                behind, ahead = 0, 0
        status = self._build_repo_status_summary(repo_path)
        return branch, ahead, behind, status

    def _refresh_workspace_tree(self) -> None:
        self.workspace_tree.clear()
        repos = self._collect_known_repos()
        if not repos:
            placeholder = QTreeWidgetItem(["(sem repositorios)", "", "", "", "", ""])
            placeholder.setData(0, Qt.ItemDataRole.UserRole, "")
            self.workspace_tree.addTopLevelItem(placeholder)
            self.workspace_tree.resizeColumnToContents(0)
            self.workspace_tree.resizeColumnToContents(2)
            self.workspace_tree.resizeColumnToContents(3)
            self.workspace_tree.resizeColumnToContents(4)
            return
        for repo in repos:
            branch, ahead, behind, status = self._build_repo_snapshot(repo)
            item = QTreeWidgetItem(
                [
                    self._format_repo_display_label(repo),
                    self._format_workspace_relative_path(repo),
                    branch,
                    str(ahead),
                    str(behind),
                    status,
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, repo)
            self.workspace_tree.addTopLevelItem(item)
        self.workspace_tree.resizeColumnToContents(0)
        self.workspace_tree.resizeColumnToContents(2)
        self.workspace_tree.resizeColumnToContents(3)
        self.workspace_tree.resizeColumnToContents(4)
        self._sync_workspace_tree_selection()

    def _sync_workspace_tree_selection(self) -> None:
        self._setting_workspace_selection = True
        try:
            for index in range(self.workspace_tree.topLevelItemCount()):
                item = self.workspace_tree.topLevelItem(index)
                path_value = item.data(0, Qt.ItemDataRole.UserRole)
                repo = str(path_value).strip() if path_value is not None else ""
                should_select = bool(self.repo_path and repo == self.repo_path)
                item.setSelected(should_select)
                if should_select:
                    self.workspace_tree.scrollToItem(item)
        finally:
            self._setting_workspace_selection = False

    def _on_workspace_selection_changed(self) -> None:
        if self._setting_workspace_selection:
            return
        selected_items = self.workspace_tree.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        path_value = item.data(0, Qt.ItemDataRole.UserRole)
        target_repo = str(path_value).strip() if path_value is not None else ""
        if not target_repo:
            return
        if self.repo_path and normalize_repo_path(self.repo_path) == normalize_repo_path(target_repo):
            return
        self._set_repo(target_repo, save=True)

    def _on_workspace_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        path_value = item.data(0, Qt.ItemDataRole.UserRole)
        target_repo = str(path_value).strip() if path_value is not None else ""
        if not target_repo:
            return
        self._set_repo(target_repo, save=True)

    def _refresh_commit_files(self) -> None:
        self.commit_files_list.blockSignals(True)
        self.commit_files_list.clear()
        if not self.repo_path:
            self.commit_files_list.blockSignals(False)
            self._update_commit_selection_label()
            return
        try:
            files = core_list_modified_files(self.repo_path)
        except RuntimeError as exc:
            self.commit_files_list.blockSignals(False)
            QMessageBox.critical(self, "Commit", str(exc))
            self._update_commit_selection_label()
            return
        for path in files:
            item = QListWidgetItem(path, self.commit_files_list)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(Qt.CheckState.Checked)
        self.commit_files_list.blockSignals(False)
        self._update_commit_selection_label()

    def _iter_commit_items(self) -> list[QListWidgetItem]:
        items: list[QListWidgetItem] = []
        for index in range(self.commit_files_list.count()):
            item = self.commit_files_list.item(index)
            if item is not None:
                items.append(item)
        return items

    def _update_commit_selection_label(self) -> None:
        items = self._iter_commit_items()
        selected = 0
        for item in items:
            if item.checkState() == Qt.CheckState.Checked:
                selected += 1
        self.commit_selection_label.setText(f"Selecionados: {selected}/{len(items)}")

    def _on_commit_file_item_changed(self, _item: QListWidgetItem) -> None:
        self._update_commit_selection_label()

    def _select_all_commit_files(self) -> None:
        self.commit_files_list.blockSignals(True)
        for item in self._iter_commit_items():
            item.setCheckState(Qt.CheckState.Checked)
        self.commit_files_list.blockSignals(False)
        self._update_commit_selection_label()

    def _clear_commit_file_selection(self) -> None:
        self.commit_files_list.blockSignals(True)
        for item in self._iter_commit_items():
            item.setCheckState(Qt.CheckState.Unchecked)
        self.commit_files_list.blockSignals(False)
        self._update_commit_selection_label()

    def _get_selected_commit_paths(self) -> list[str]:
        selected: list[str] = []
        for item in self._iter_commit_items():
            if item.checkState() != Qt.CheckState.Checked:
                continue
            path = item.text().strip()
            if path:
                selected.append(path)
        return selected

    def _create_commit_from_selection(self) -> None:
        if not self.repo_path:
            QMessageBox.information(self, "Commit", "Selecione um repositorio valido primeiro.")
            return
        title = self.commit_title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Commit", "Titulo do commit e obrigatorio.")
            return
        selected_paths = self._get_selected_commit_paths()
        if not selected_paths:
            QMessageBox.warning(self, "Commit", "Selecione ao menos um arquivo para commit.")
            return
        description = self.commit_description_input.toPlainText().strip()
        try:
            core_unstage_all(self.repo_path)
            core_stage_paths(self.repo_path, selected_paths)
            if not core_has_staged_changes(self.repo_path):
                QMessageBox.warning(self, "Commit", "Nenhuma alteracao ficou staged para commit.")
                return
            core_create_commit(self.repo_path, title, description)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Commit", str(exc))
            self._refresh_commit_files()
            self._refresh_repo_state_ui()
            self._refresh_workspace_tree()
            return
        self.commit_title_input.clear()
        self.commit_description_input.clear()
        self._set_status("Commit concluido.")
        self._refresh_commit_files()
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()

    def _set_repo(self, repo_path: str, *, save: bool) -> None:
        normalized = normalize_repo_path(repo_path) if repo_path else ""
        if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
            self.repo_path = ""
            self._refresh_repo_state_ui()
            self._refresh_commit_files()
            self._clear_history_view()
            self._refresh_compare_branch_options()
            self._sync_import_target_label()
            self._sync_workspace_tree_selection()
            if save:
                self._persist_state()
            return
        self.repo_path = normalized
        self._add_recent_repo(normalized)
        self._select_repo_combo_item(normalized)
        self._refresh_repo_state_ui()
        self._refresh_commit_files()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._refresh_import_source_repos()
        self._sync_import_target_label()
        self._sync_workspace_tree_selection()
        self._set_status(f"Repositorio ativo: {normalized}")
        if save:
            self._persist_state()

    def _select_repo_combo_item(self, repo_path: str) -> None:
        self._setting_repo_programmatically = True
        try:
            index = self.repo_combo.findData(repo_path)
            if index < 0:
                self.repo_combo.addItem(repo_path, repo_path)
                index = self.repo_combo.findData(repo_path)
            if index >= 0:
                self.repo_combo.setCurrentIndex(index)
        finally:
            self._setting_repo_programmatically = False

    def _refresh_repo_state_ui(self) -> None:
        has_repo = bool(self.repo_path)
        self.fetch_button.setEnabled(has_repo)
        self.new_branch_button.setEnabled(has_repo)
        self.branch_combo.setEnabled(has_repo)
        if not has_repo:
            self.pull_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.sync_label.setText("Ahead: 0 | Behind: 0")
            self.branch_combo.clear()
            self._sync_import_target_label()
            return

        try:
            branches = core_list_branches(self.repo_path)
            current = core_get_current_branch(self.repo_path).strip()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Erro", str(exc))
            self.repo_path = ""
            self._refresh_repo_state_ui()
            return

        self._setting_branch_programmatically = True
        try:
            self.branch_combo.clear()
            for branch in branches:
                self.branch_combo.addItem(branch, branch)
            index = self.branch_combo.findData(current)
            if index >= 0:
                self.branch_combo.setCurrentIndex(index)
        finally:
            self._setting_branch_programmatically = False

        upstream = core_get_upstream(self.repo_path)
        if not upstream:
            self.pull_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.sync_label.setText("Ahead: 0 | Behind: 0 (sem upstream)")
            self.fetch_button.setText("Fetch")
            self._sync_import_target_label()
            return

        behind, ahead = core_get_ahead_behind(self.repo_path, upstream)
        self.sync_label.setText(f"Ahead: {ahead} | Behind: {behind}")
        self.pull_button.setEnabled(behind > 0)
        self.push_button.setEnabled(ahead > 0)
        self.fetch_button.setText(f"Fetch ({behind})" if behind > 0 else "Fetch")
        self.pull_button.setText(f"Pull ({behind})" if behind > 0 else "Pull")
        self.push_button.setText(f"Push ({ahead})" if ahead > 0 else "Push")
        self._sync_import_target_label()

    def _add_recent_repo(self, repo_path: str) -> None:
        normalized = normalize_repo_path(repo_path)
        current_items = self.settings_data.get("recent_repos", [])
        items: list[str] = []
        if isinstance(current_items, list):
            for raw in current_items:
                if isinstance(raw, str) and raw.strip():
                    entry = normalize_repo_path(raw)
                    if entry not in items and os.path.isdir(entry) and is_git_repo(entry):
                        items.append(entry)
        if normalized in items:
            items.remove(normalized)
        items.insert(0, normalized)
        self.settings_data["recent_repos"] = items[:RECENT_REPOS_LIMIT]
        self._load_repo_selector_items()
        self._refresh_workspace_tree()

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
