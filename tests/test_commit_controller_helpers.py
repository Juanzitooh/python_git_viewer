#!/usr/bin/env python3
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from viewer.core.models import DiffData

_IMPORT_ERROR: Exception | None = None
try:
    from viewer.pyside.controllers.commit_controller import (
        _diff_has_dev_null_transition,
        _load_commit_status_entries,
    )
except Exception as exc:  # pragma: no cover - ambiente sem runtime Qt/PySide6
    _IMPORT_ERROR = exc
    _diff_has_dev_null_transition = None
    _load_commit_status_entries = None


@unittest.skipIf(_IMPORT_ERROR is not None, "PySide6 não disponível no ambiente de testes.")
class TestCommitControllerHelpers(unittest.TestCase):
    def test_diff_has_dev_null_transition_for_new_file(self) -> None:
        diff_data = DiffData(
            header_lines=[
                "diff --git a/file.txt b/file.txt",
                "--- /dev/null",
                "+++ b/file.txt",
            ],
            hunks=[],
        )
        self.assertTrue(_diff_has_dev_null_transition(diff_data))

    def test_diff_has_dev_null_transition_for_regular_file(self) -> None:
        diff_data = DiffData(
            header_lines=[
                "diff --git a/file.txt b/file.txt",
                "--- a/file.txt",
                "+++ b/file.txt",
            ],
            hunks=[],
        )
        self.assertFalse(_diff_has_dev_null_transition(diff_data))

    def test_load_commit_status_entries_cleans_phantom_dev_null(self) -> None:
        window = SimpleNamespace(repo_path="/tmp/repo", commit_selected_path="", commit_diff_scope="")
        first_status = [
            {"status": "AD", "path": "dev/null", "path_for_git": "dev/null", "staged": True, "unstaged": True},
            {"status": "??", "path": "file.txt", "path_for_git": "file.txt", "staged": False, "unstaged": True},
        ]
        second_status = [
            {"status": "??", "path": "file.txt", "path_for_git": "file.txt", "staged": False, "unstaged": True},
        ]

        def _exists(path: str) -> bool:
            return path != "/tmp/repo/dev/null"

        with patch(
            "viewer.pyside.controllers.commit_controller.core_list_status_entries",
            side_effect=[first_status, second_status],
        ) as mocked_list, patch(
            "viewer.pyside.controllers.commit_controller.core_unstage_paths"
        ) as mocked_unstage, patch(
            "viewer.pyside.controllers.commit_controller.os.path.exists",
            side_effect=_exists,
        ):
            entries = _load_commit_status_entries(window)

        self.assertEqual(entries, second_status)
        mocked_unstage.assert_called_once_with("/tmp/repo", ["dev/null"])
        self.assertEqual(mocked_list.call_count, 2)


if __name__ == "__main__":
    unittest.main()
