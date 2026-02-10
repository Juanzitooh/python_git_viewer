#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..core.branch_compare import (
    get_ahead_behind_between as core_get_ahead_behind_between,
    has_potential_conflict as core_has_potential_conflict,
    load_compare_commits as core_load_compare_commits,
    load_compare_file_patch as core_load_compare_file_patch,
    load_compare_file_stats as core_load_compare_file_stats,
)
from ..core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ..core.commit_content import (
    get_commit_patch as core_get_commit_patch,
    list_commit_files as core_list_commit_files,
)
from ..core.commit_ops import (
    create_commit as core_create_commit,
    has_staged_changes as core_has_staged_changes,
    list_modified_files as core_list_modified_files,
    stage_paths as core_stage_paths,
    unstage_all as core_unstage_all,
)
from ..core.git_client import is_git_repo, load_commit_details, load_commit_summaries
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

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFileDialog,
        QComboBox,
        QHBoxLayout,
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
        QStatusBar,
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

        bar = QWidget(root)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(6)

        self.repo_combo = QComboBox(bar)
        self.repo_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.repo_combo.currentIndexChanged.connect(self._on_repo_changed)
        bar_layout.addWidget(self.repo_combo, stretch=1)

        self.branch_combo = QComboBox(bar)
        self.branch_combo.setMinimumWidth(180)
        self.branch_combo.currentIndexChanged.connect(self._on_branch_changed)
        bar_layout.addWidget(QLabel("Branch:", bar))
        bar_layout.addWidget(self.branch_combo)

        self.new_branch_button = QPushButton("Nova branch", bar)
        self.new_branch_button.clicked.connect(self._create_new_branch)
        bar_layout.addWidget(self.new_branch_button)

        bar_layout.addStretch(1)

        self.fetch_button = QPushButton("Fetch", bar)
        self.fetch_button.clicked.connect(self._fetch_repo)
        bar_layout.addWidget(self.fetch_button)

        self.pull_button = QPushButton("Pull", bar)
        self.pull_button.clicked.connect(self._pull_repo)
        bar_layout.addWidget(self.pull_button)

        self.push_button = QPushButton("Push", bar)
        self.push_button.clicked.connect(self._push_repo)
        bar_layout.addWidget(self.push_button)

        self.sync_label = QLabel("Ahead: 0 | Behind: 0", bar)
        bar_layout.addWidget(self.sync_label)

        root_layout.addWidget(bar)

        self.tabs = QTabWidget(root)
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
        self._build_placeholder_tab(self.import_tab, "Importar")
        self._build_compare_tab()
        self._build_placeholder_tab(self.settings_tab, "Configuracoes")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root_layout.addWidget(self.tabs, stretch=1)

        self.status = QStatusBar(root)
        self.setStatusBar(self.status)
        self._set_status("PySide6 shell iniciado.")

    def _apply_theme_from_settings(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme = str(self.settings_data.get("theme", "light"))
        if theme == "dark":
            app.setStyleSheet(
                """
                QWidget { background-color: #1f2328; color: #e6edf3; }
                QLineEdit, QComboBox, QTabWidget::pane { background-color: #0d1117; color: #e6edf3; }
                QPushButton { background-color: #22272e; border: 1px solid #30363d; padding: 4px 8px; }
                QPushButton:hover { background-color: #2d333b; }
                """
            )
        else:
            app.setStyleSheet(
                """
                QWidget { background-color: #f6f8fa; color: #1f2328; }
                QLineEdit, QComboBox, QTabWidget::pane { background-color: #ffffff; color: #1f2328; }
                QPushButton { background-color: #f3f4f6; border: 1px solid #d0d7de; padding: 4px 8px; }
                QPushButton:hover { background-color: #e7ecf1; }
                """
            )

        family = str(self.settings_data.get("ui_font_family", "")).strip()
        size_raw = self.settings_data.get("ui_font_size", 0)
        try:
            size = int(size_raw)
        except (TypeError, ValueError):
            size = 0
        if family and size > 0:
            app.setFont(QFont(family, size))

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
        layout = QVBoxLayout(self.repositories_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        root_row = QWidget(self.repositories_tab)
        root_row_layout = QHBoxLayout(root_row)
        root_row_layout.setContentsMargins(0, 0, 0, 0)
        root_row_layout.setSpacing(6)

        root_row_layout.addWidget(QLabel("Raiz local do Workspace GitHub:", root_row))
        self.workspace_root_edit = QLineEdit(root_row)
        self.workspace_root_edit.setText(self.repo_scan_root)
        self.workspace_root_edit.editingFinished.connect(self._on_workspace_root_edited)
        root_row_layout.addWidget(self.workspace_root_edit, stretch=1)

        self.workspace_root_pick_button = QPushButton("Pasta...", root_row)
        self.workspace_root_pick_button.clicked.connect(self._pick_workspace_root)
        root_row_layout.addWidget(self.workspace_root_pick_button)

        self.workspace_rescan_button = QPushButton("Reescanear", root_row)
        self.workspace_rescan_button.clicked.connect(self._scan_workspace_repos)
        root_row_layout.addWidget(self.workspace_rescan_button)

        layout.addWidget(root_row)

        self.workspace_scan_status_label = QLabel("Aguardando scan do workspace...", self.repositories_tab)
        layout.addWidget(self.workspace_scan_status_label)

        self.workspace_tree = QTreeWidget(self.repositories_tab)
        self.workspace_tree.setRootIsDecorated(False)
        self.workspace_tree.setAlternatingRowColors(True)
        self.workspace_tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self.workspace_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.workspace_tree.setColumnCount(6)
        self.workspace_tree.setHeaderLabels(["Repositório", "Caminho", "Branch", "Ahead", "Behind", "Status"])
        self.workspace_tree.itemSelectionChanged.connect(self._on_workspace_selection_changed)
        self.workspace_tree.itemDoubleClicked.connect(self._on_workspace_item_double_clicked)
        layout.addWidget(self.workspace_tree, stretch=1)

        self._scan_workspace_repos()

    def _build_commit_tab(self) -> None:
        layout = QVBoxLayout(self.commit_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QWidget(self.commit_tab)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self.commit_refresh_button = QPushButton("Atualizar status", top_row)
        self.commit_refresh_button.clicked.connect(self._refresh_commit_files)
        top_layout.addWidget(self.commit_refresh_button)

        self.commit_select_all_button = QPushButton("Selecionar tudo", top_row)
        self.commit_select_all_button.clicked.connect(self._select_all_commit_files)
        top_layout.addWidget(self.commit_select_all_button)

        self.commit_clear_selection_button = QPushButton("Limpar selecao", top_row)
        self.commit_clear_selection_button.clicked.connect(self._clear_commit_file_selection)
        top_layout.addWidget(self.commit_clear_selection_button)

        top_layout.addStretch(1)
        self.commit_selection_label = QLabel("Selecionados: 0/0", top_row)
        top_layout.addWidget(self.commit_selection_label)

        layout.addWidget(top_row)

        self.commit_files_list = QListWidget(self.commit_tab)
        self.commit_files_list.itemChanged.connect(self._on_commit_file_item_changed)
        layout.addWidget(self.commit_files_list, stretch=1)

        self.commit_title_input = QLineEdit(self.commit_tab)
        self.commit_title_input.setPlaceholderText("Titulo do commit (obrigatorio)")
        layout.addWidget(self.commit_title_input)

        self.commit_description_input = QPlainTextEdit(self.commit_tab)
        self.commit_description_input.setPlaceholderText("Descricao do commit (opcional)")
        self.commit_description_input.setFixedHeight(120)
        layout.addWidget(self.commit_description_input)

        action_row = QWidget(self.commit_tab)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)

        self.commit_run_button = QPushButton("Commit", action_row)
        self.commit_run_button.clicked.connect(self._create_commit_from_selection)
        action_layout.addWidget(self.commit_run_button)

        layout.addWidget(action_row)
        self._refresh_commit_files()

    def _build_history_tab(self) -> None:
        self.history_summaries: list[CommitSummary] = []
        self.history_summary_by_hash: dict[str, CommitSummary] = {}
        self.history_current_commit_hash = ""
        self.history_current_file_path = ""

        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QWidget(self.history_tab)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        self.history_refresh_button = QPushButton("Atualizar", top_row)
        self.history_refresh_button.clicked.connect(self._reload_history_commits)
        top_layout.addWidget(self.history_refresh_button)

        top_layout.addWidget(QLabel("Buscar:", top_row))
        self.history_search_input = QLineEdit(top_row)
        self.history_search_input.setPlaceholderText("Filtrar por texto no commit")
        self.history_search_input.returnPressed.connect(self._reload_history_commits)
        top_layout.addWidget(self.history_search_input, stretch=1)

        top_layout.addWidget(QLabel("Limite:", top_row))
        self.history_limit_combo = QComboBox(top_row)
        self.history_limit_combo.addItem("50", 50)
        self.history_limit_combo.addItem("100", 100)
        self.history_limit_combo.addItem("200", 200)
        self.history_limit_combo.setCurrentIndex(1)
        self.history_limit_combo.currentIndexChanged.connect(self._reload_history_commits)
        top_layout.addWidget(self.history_limit_combo)

        self.history_word_diff_check = QCheckBox("Diff por palavra", top_row)
        self.history_word_diff_check.stateChanged.connect(self._refresh_history_patch_view)
        top_layout.addWidget(self.history_word_diff_check)

        layout.addWidget(top_row)

        body = QWidget(self.history_tab)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self.history_commits_list = QListWidget(body)
        self.history_commits_list.itemSelectionChanged.connect(self._on_history_commit_selected)
        body_layout.addWidget(self.history_commits_list, stretch=2)

        right_panel = QWidget(body)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.history_commit_info = QPlainTextEdit(right_panel)
        self.history_commit_info.setReadOnly(True)
        self.history_commit_info.setFixedHeight(130)
        right_layout.addWidget(self.history_commit_info)

        self.history_files_list = QListWidget(right_panel)
        self.history_files_list.itemSelectionChanged.connect(self._on_history_file_selected)
        right_layout.addWidget(self.history_files_list, stretch=1)

        self.history_patch_view = QPlainTextEdit(right_panel)
        self.history_patch_view.setReadOnly(True)
        right_layout.addWidget(self.history_patch_view, stretch=2)

        body_layout.addWidget(right_panel, stretch=3)
        layout.addWidget(body, stretch=1)

        self._clear_history_view()

    def _clear_history_view(self) -> None:
        self.history_summaries = []
        self.history_summary_by_hash = {}
        self.history_current_commit_hash = ""
        self.history_current_file_path = ""
        if hasattr(self, "history_commits_list"):
            self.history_commits_list.clear()
        if hasattr(self, "history_files_list"):
            self.history_files_list.clear()
        if hasattr(self, "history_commit_info"):
            self.history_commit_info.setPlainText("")
        if hasattr(self, "history_patch_view"):
            self.history_patch_view.setPlainText("")

    def _get_history_limit_value(self) -> int:
        data = self.history_limit_combo.currentData()
        try:
            value = int(data)
        except (TypeError, ValueError):
            value = 100
        return max(1, value)

    def _reload_history_commits(self) -> None:
        if not self.repo_path:
            self._clear_history_view()
            return
        text_filter = self.history_search_input.text().strip()
        filters = CommitFilters(text=text_filter)
        limit = self._get_history_limit_value()
        try:
            summaries = load_commit_summaries(self.repo_path, limit=limit, filters=filters)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Historico", str(exc))
            self._clear_history_view()
            return

        self.history_summaries = summaries
        self.history_summary_by_hash = {item.commit_hash: item for item in summaries}
        self.history_current_commit_hash = ""
        self.history_current_file_path = ""

        self.history_commits_list.blockSignals(True)
        self.history_commits_list.clear()
        for summary in summaries:
            label = f"{summary.commit_hash[:7]} | {summary.subject}"
            item = QListWidgetItem(label, self.history_commits_list)
            item.setData(Qt.ItemDataRole.UserRole, summary.commit_hash)
        self.history_commits_list.blockSignals(False)

        if summaries:
            self.history_commits_list.setCurrentRow(0)
        else:
            self.history_files_list.clear()
            self.history_commit_info.setPlainText("Nenhum commit encontrado.")
            self.history_patch_view.setPlainText("")

    def _on_history_commit_selected(self) -> None:
        selected_items = self.history_commits_list.selectedItems()
        if not selected_items:
            self.history_current_commit_hash = ""
            self.history_current_file_path = ""
            self.history_files_list.clear()
            self.history_commit_info.setPlainText("")
            self.history_patch_view.setPlainText("")
            return
        item = selected_items[0]
        value = item.data(Qt.ItemDataRole.UserRole)
        commit_hash = str(value).strip() if value is not None else ""
        if not commit_hash:
            return
        self.history_current_commit_hash = commit_hash
        self.history_current_file_path = ""
        self._load_history_commit_content(commit_hash)

    def _load_history_commit_content(self, commit_hash: str) -> None:
        try:
            details = load_commit_details(self.repo_path, commit_hash)
            files = core_list_commit_files(self.repo_path, commit_hash)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Historico", str(exc))
            self.history_files_list.clear()
            self.history_patch_view.setPlainText("")
            return

        info_lines = [
            f"Hash: {details.commit_hash}",
            f"Autor: {details.author}",
            f"Data: {details.date}",
            f"Titulo: {details.subject}",
            f"Arquivos: {len(details.file_stats)} | +{details.total_added} -{details.total_deleted}",
        ]
        if details.body:
            info_lines.extend(["", details.body.strip()])
        self.history_commit_info.setPlainText("\n".join(info_lines))

        self.history_files_list.blockSignals(True)
        self.history_files_list.clear()
        all_files_item = QListWidgetItem("(todos os arquivos)", self.history_files_list)
        all_files_item.setData(Qt.ItemDataRole.UserRole, "")
        for path in files:
            file_item = QListWidgetItem(path, self.history_files_list)
            file_item.setData(Qt.ItemDataRole.UserRole, path)
        self.history_files_list.blockSignals(False)
        self.history_files_list.setCurrentRow(0)

    def _on_history_file_selected(self) -> None:
        selected_items = self.history_files_list.selectedItems()
        if not selected_items:
            self.history_current_file_path = ""
            self._refresh_history_patch_view()
            return
        item = selected_items[0]
        value = item.data(Qt.ItemDataRole.UserRole)
        self.history_current_file_path = str(value).strip() if value is not None else ""
        self._refresh_history_patch_view()

    def _refresh_history_patch_view(self) -> None:
        commit_hash = self.history_current_commit_hash.strip()
        if not commit_hash:
            self.history_patch_view.setPlainText("")
            return
        word_diff = self.history_word_diff_check.isChecked()
        path = self.history_current_file_path.strip() or None
        try:
            patch = core_get_commit_patch(
                self.repo_path,
                commit_hash,
                path=path,
                word_diff=word_diff,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Historico", str(exc))
            self.history_patch_view.setPlainText("")
            return
        self.history_patch_view.setPlainText(patch)

    def _build_compare_tab(self) -> None:
        self.compare_file_entries: list[dict[str, object]] = []
        self.compare_current_file_path = ""
        self._setting_compare_branches_programmatically = False

        layout = QVBoxLayout(self.compare_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QWidget(self.compare_tab)
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        top_layout.addWidget(QLabel("Origem:", top_row))
        self.compare_origin_combo = QComboBox(top_row)
        self.compare_origin_combo.currentIndexChanged.connect(self._on_compare_branches_changed)
        top_layout.addWidget(self.compare_origin_combo)

        self.compare_swap_button = QPushButton("Trocar", top_row)
        self.compare_swap_button.clicked.connect(self._swap_compare_branches)
        top_layout.addWidget(self.compare_swap_button)

        top_layout.addWidget(QLabel("Destino:", top_row))
        self.compare_dest_combo = QComboBox(top_row)
        self.compare_dest_combo.currentIndexChanged.connect(self._on_compare_branches_changed)
        top_layout.addWidget(self.compare_dest_combo)

        self.compare_refresh_button = QPushButton("Atualizar", top_row)
        self.compare_refresh_button.clicked.connect(self._refresh_compare_view)
        top_layout.addWidget(self.compare_refresh_button)

        self.compare_word_diff_check = QCheckBox("Diff por palavra", top_row)
        self.compare_word_diff_check.stateChanged.connect(self._refresh_compare_patch)
        top_layout.addWidget(self.compare_word_diff_check)

        top_layout.addStretch(1)
        layout.addWidget(top_row)

        self.compare_status_label = QLabel("Selecione origem e destino para comparar.", self.compare_tab)
        layout.addWidget(self.compare_status_label)

        body = QWidget(self.compare_tab)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self.compare_commits_list = QListWidget(body)
        body_layout.addWidget(self.compare_commits_list, stretch=2)

        self.compare_files_list = QListWidget(body)
        self.compare_files_list.itemSelectionChanged.connect(self._on_compare_file_selected)
        body_layout.addWidget(self.compare_files_list, stretch=2)

        self.compare_patch_view = QPlainTextEdit(body)
        self.compare_patch_view.setReadOnly(True)
        body_layout.addWidget(self.compare_patch_view, stretch=3)

        layout.addWidget(body, stretch=1)
        self._clear_compare_view()

    def _clear_compare_view(self) -> None:
        self.compare_file_entries = []
        self.compare_current_file_path = ""
        if hasattr(self, "compare_commits_list"):
            self.compare_commits_list.clear()
        if hasattr(self, "compare_files_list"):
            self.compare_files_list.clear()
        if hasattr(self, "compare_patch_view"):
            self.compare_patch_view.setPlainText("")
        if hasattr(self, "compare_status_label"):
            self.compare_status_label.setText("Selecione origem e destino para comparar.")

    def _refresh_compare_branch_options(self) -> None:
        if not hasattr(self, "compare_origin_combo"):
            return
        if not self.repo_path:
            self._setting_compare_branches_programmatically = True
            try:
                self.compare_origin_combo.clear()
                self.compare_dest_combo.clear()
            finally:
                self._setting_compare_branches_programmatically = False
            self._clear_compare_view()
            return
        try:
            branches = core_list_branches(self.repo_path)
            current = core_get_current_branch(self.repo_path).strip()
        except RuntimeError as exc:
            QMessageBox.critical(self, "Comparar", str(exc))
            self._clear_compare_view()
            return

        origin_value = self.compare_origin_combo.currentData()
        dest_value = self.compare_dest_combo.currentData()
        origin_selected = str(origin_value).strip() if origin_value is not None else ""
        dest_selected = str(dest_value).strip() if dest_value is not None else ""

        if origin_selected not in branches:
            origin_selected = current or (branches[0] if branches else "")
        if dest_selected not in branches or dest_selected == origin_selected:
            dest_selected = ""
            for branch in branches:
                if branch != origin_selected:
                    dest_selected = branch
                    break
            if not dest_selected and branches:
                dest_selected = branches[0]

        self._setting_compare_branches_programmatically = True
        try:
            self.compare_origin_combo.clear()
            self.compare_dest_combo.clear()
            for branch in branches:
                self.compare_origin_combo.addItem(branch, branch)
                self.compare_dest_combo.addItem(branch, branch)
            origin_index = self.compare_origin_combo.findData(origin_selected)
            if origin_index >= 0:
                self.compare_origin_combo.setCurrentIndex(origin_index)
            dest_index = self.compare_dest_combo.findData(dest_selected)
            if dest_index >= 0:
                self.compare_dest_combo.setCurrentIndex(dest_index)
        finally:
            self._setting_compare_branches_programmatically = False
        self._refresh_compare_view()

    def _get_compare_branches(self) -> tuple[str, str]:
        origin_value = self.compare_origin_combo.currentData()
        dest_value = self.compare_dest_combo.currentData()
        origin = str(origin_value).strip() if origin_value is not None else ""
        dest = str(dest_value).strip() if dest_value is not None else ""
        return origin, dest

    def _on_compare_branches_changed(self, _index: int) -> None:
        if self._setting_compare_branches_programmatically:
            return
        self._refresh_compare_view()

    def _swap_compare_branches(self) -> None:
        origin, dest = self._get_compare_branches()
        if not origin and not dest:
            return
        self._setting_compare_branches_programmatically = True
        try:
            origin_index = self.compare_origin_combo.findData(dest)
            dest_index = self.compare_dest_combo.findData(origin)
            if origin_index >= 0:
                self.compare_origin_combo.setCurrentIndex(origin_index)
            if dest_index >= 0:
                self.compare_dest_combo.setCurrentIndex(dest_index)
        finally:
            self._setting_compare_branches_programmatically = False
        self._refresh_compare_view()

    def _refresh_compare_view(self) -> None:
        if not self.repo_path:
            self._clear_compare_view()
            return
        origin, dest = self._get_compare_branches()
        if not origin or not dest:
            self._clear_compare_view()
            return
        if origin == dest:
            self._clear_compare_view()
            self.compare_status_label.setText("Origem e destino devem ser diferentes.")
            return

        try:
            commits = core_load_compare_commits(self.repo_path, origin, dest)
            file_stats, totals = core_load_compare_file_stats(self.repo_path, origin, dest)
            behind, ahead = core_get_ahead_behind_between(self.repo_path, origin, dest)
            has_conflict = core_has_potential_conflict(self.repo_path, origin, dest)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Comparar", str(exc))
            self._clear_compare_view()
            return

        self.compare_file_entries = file_stats
        self.compare_current_file_path = ""

        self.compare_commits_list.clear()
        for line in commits:
            self.compare_commits_list.addItem(line)

        self.compare_files_list.blockSignals(True)
        self.compare_files_list.clear()
        for entry in file_stats:
            path = str(entry.get("path", "")).strip()
            if not path:
                continue
            added = int(entry.get("added", 0) or 0)
            deleted = int(entry.get("deleted", 0) or 0)
            binary = bool(entry.get("binary", False))
            if binary:
                label = f"{path} [binario]"
            else:
                label = f"{path} (+{added}/-{deleted})"
            item = QListWidgetItem(label, self.compare_files_list)
            item.setData(Qt.ItemDataRole.UserRole, path)
        self.compare_files_list.blockSignals(False)

        conflict_label = "possivel conflito" if has_conflict else "sem conflito aparente"
        self.compare_status_label.setText(
            (
                f"{origin} -> {dest} | commits: {len(commits)} | arquivos: {totals.get('files', 0)} "
                f"| +{totals.get('added', 0)} -{totals.get('deleted', 0)} | "
                f"ahead/behind: {ahead}/{behind} | {conflict_label}"
            )
        )

        if self.compare_files_list.count() > 0:
            self.compare_files_list.setCurrentRow(0)
        else:
            self.compare_patch_view.setPlainText("(nenhuma diferença)")

    def _on_compare_file_selected(self) -> None:
        selected_items = self.compare_files_list.selectedItems()
        if not selected_items:
            self.compare_current_file_path = ""
            self._refresh_compare_patch()
            return
        item = selected_items[0]
        value = item.data(Qt.ItemDataRole.UserRole)
        self.compare_current_file_path = str(value).strip() if value is not None else ""
        self._refresh_compare_patch()

    def _refresh_compare_patch(self) -> None:
        if not self.repo_path:
            self.compare_patch_view.setPlainText("")
            return
        origin, dest = self._get_compare_branches()
        if not origin or not dest or origin == dest:
            self.compare_patch_view.setPlainText("")
            return
        selected_path = self.compare_current_file_path.strip()
        if not selected_path:
            self.compare_patch_view.setPlainText("(selecione um arquivo)")
            return
        word_diff = self.compare_word_diff_check.isChecked()
        try:
            patch = core_load_compare_file_patch(
                self.repo_path,
                origin,
                dest,
                path=selected_path,
                word_diff=word_diff,
            )
        except RuntimeError as exc:
            QMessageBox.critical(self, "Comparar", str(exc))
            self.compare_patch_view.setPlainText("")
            return
        self.compare_patch_view.setPlainText(patch or "(sem diff para este arquivo)")

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
            return

        behind, ahead = core_get_ahead_behind(self.repo_path, upstream)
        self.sync_label.setText(f"Ahead: {ahead} | Behind: {behind}")
        self.pull_button.setEnabled(behind > 0)
        self.push_button.setEnabled(ahead > 0)
        self.fetch_button.setText(f"Fetch ({behind})" if behind > 0 else "Fetch")
        self.pull_button.setText(f"Pull ({behind})" if behind > 0 else "Pull")
        self.push_button.setText(f"Push ({ahead})" if ahead > 0 else "Push")

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
        try:
            core_fetch_all_prune(self.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Fetch", str(exc))
            return
        self._set_status("Fetch concluido.")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_view()
        self._persist_state()

    def _pull_repo(self) -> None:
        if not self.repo_path:
            return
        try:
            core_pull_ff_only(self.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Pull", str(exc))
            return
        self._set_status("Pull concluido.")
        self._refresh_repo_state_ui()
        self._refresh_workspace_tree()
        self._reload_history_commits()
        self._refresh_compare_branch_options()
        self._persist_state()

    def _push_repo(self) -> None:
        if not self.repo_path:
            return
        try:
            core_push_current_branch(self.repo_path)
        except RuntimeError as exc:
            QMessageBox.critical(self, "Push", str(exc))
            return
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
