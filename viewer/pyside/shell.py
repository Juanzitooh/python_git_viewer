#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..core.branch_ops import checkout_branch as core_checkout_branch, create_branch as core_create_branch
from ..core.git_client import is_git_repo
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
)
from ..core.settings_store import get_settings_path, load_settings, normalize_repo_path, save_settings

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QStatusBar,
        QTabWidget,
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
        self._setting_repo_programmatically = False
        self._setting_branch_programmatically = False

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
        for name in TAB_NAMES:
            tab = QWidget(self.tabs)
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(12, 12, 12, 12)
            tab_layout.addWidget(
                QLabel(
                    "Migracao em andamento para PySide6.\n"
                    "Use a UI Tk para os fluxos completos por enquanto.",
                    tab,
                )
            )
            tab_layout.addStretch(1)
            self.tabs.addTab(tab, name)
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

    def _collect_known_repos(self) -> list[str]:
        ordered: list[str] = []
        for key in ("favorite_repos", "recent_repos"):
            items = self.settings_data.get(key, [])
            if not isinstance(items, list):
                continue
            for raw in items:
                if not isinstance(raw, str):
                    continue
                normalized = normalize_repo_path(raw)
                if normalized in ordered:
                    continue
                if not os.path.isdir(normalized):
                    continue
                if not is_git_repo(normalized):
                    continue
                ordered.append(normalized)
        return ordered

    def _load_repo_selector_items(self) -> None:
        repos = self._collect_known_repos()
        self.repo_combo.clear()
        for repo in repos:
            self.repo_combo.addItem(repo, repo)
        if self.repo_path and self.repo_path not in repos and os.path.isdir(self.repo_path) and is_git_repo(self.repo_path):
            self.repo_combo.addItem(self.repo_path, self.repo_path)

    def _set_repo(self, repo_path: str, *, save: bool) -> None:
        normalized = normalize_repo_path(repo_path) if repo_path else ""
        if not normalized or not os.path.isdir(normalized) or not is_git_repo(normalized):
            self.repo_path = ""
            self._refresh_repo_state_ui()
            if save:
                self._persist_state()
            return
        self.repo_path = normalized
        self._select_repo_combo_item(normalized)
        self._refresh_repo_state_ui()
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

    def _persist_state(self) -> None:
        self.settings_data["last_repo_path"] = self.repo_path
        self.settings_data["last_tab_index"] = self.tabs.currentIndex()
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

