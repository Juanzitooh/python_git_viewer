#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - optional dependency in some environments
    QApplication = None

try:
    from viewer.pyside.window import QtShellWindow
except Exception:  # pragma: no cover - optional dependency in some environments
    QtShellWindow = None


def _run(cmd: list[str], cwd: str) -> None:
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "command failed")


@unittest.skipIf(QApplication is None or QtShellWindow is None, "PySide6 indisponivel")
class TestPySideShellSmoke(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.repo_path = self.tmp_path / "repo"
        self.repo_path.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.tmp_path / "settings.json"
        self._init_repo()
        self._write_settings()

        self.app = QApplication.instance() or QApplication([])
        self.window = QtShellWindow(str(self.repo_path), self.settings_path)

    def tearDown(self) -> None:
        if hasattr(self, "window"):
            self.window.close()
        self._tmp.cleanup()

    def _init_repo(self) -> None:
        _run(["git", "init", "-b", "main"], cwd=str(self.repo_path))
        _run(["git", "config", "user.name", "Tester"], cwd=str(self.repo_path))
        _run(["git", "config", "user.email", "tester@example.com"], cwd=str(self.repo_path))
        file_path = self.repo_path / "README.md"
        file_path.write_text("hello\n", encoding="utf-8")
        _run(["git", "add", "README.md"], cwd=str(self.repo_path))
        _run(["git", "commit", "-m", "initial"], cwd=str(self.repo_path))
        _run(["git", "checkout", "-b", "feature/smoke"], cwd=str(self.repo_path))
        file_path.write_text("hello\nworld\n", encoding="utf-8")
        _run(["git", "add", "README.md"], cwd=str(self.repo_path))
        _run(["git", "commit", "-m", "feature change"], cwd=str(self.repo_path))
        _run(["git", "checkout", "main"], cwd=str(self.repo_path))

    def _write_settings(self) -> None:
        payload = {
            "theme": "light",
            "commit_limit": 100,
            "repo_scan_root": str(self.tmp_path),
            "recent_repos": [str(self.repo_path)],
            "favorite_repos": [str(self.repo_path)],
            "last_repo_path": str(self.repo_path),
            "last_tab_index": 0,
        }
        self.settings_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_shell_initializes_with_expected_tabs(self) -> None:
        self.assertEqual(self.window.tabs.count(), 6)
        self.assertTrue(self.window.repo_path.endswith("repo"))
        self.assertGreaterEqual(self.window.repo_combo.count(), 1)

    def test_core_views_refresh_without_errors(self) -> None:
        self.window._refresh_repo_state_ui()
        self.window._refresh_commit_files()
        self.window._reload_history_commits()
        self.window._refresh_compare_branch_options()
        self.window._refresh_import_source_repos()

        self.assertGreaterEqual(self.window.commit_files_list.count(), 0)
        self.assertGreaterEqual(self.window.history_commits_list.count(), 1)
        self.assertGreaterEqual(self.window.compare_origin_combo.count(), 1)
        self.assertGreaterEqual(self.window.import_source_repo_combo.count(), 1)

    def test_history_rows_show_local_marker_without_upstream(self) -> None:
        self.window._reload_history_commits()
        self.assertGreaterEqual(self.window.history_commits_list.count(), 1)
        first_item = self.window.history_commits_list.item(0)
        self.assertIsNotNone(first_item)
        text = first_item.text() if first_item is not None else ""
        self.assertTrue(text.startswith("[L] "))


if __name__ == "__main__":
    unittest.main()
