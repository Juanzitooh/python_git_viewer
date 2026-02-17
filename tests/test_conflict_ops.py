#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.conflict_ops import (
    abort_conflict_operation,
    mark_conflict_file_resolved,
    resolve_active_conflict_operation,
    resolve_conflict_file_using_side,
)


class TestConflictOps(unittest.TestCase):
    def test_resolve_active_conflict_prefers_squash_when_unmerged_exists(self) -> None:
        with patch("viewer.core.conflict_ops.is_conflict_operation_in_progress", return_value=False), patch(
            "viewer.core.conflict_ops.has_unmerged_conflicts",
            return_value=True,
        ):
            operation = resolve_active_conflict_operation("/tmp/repo", preferred="squash_merge")
        self.assertEqual(operation, "squash_merge")

    def test_abort_squash_merge_falls_back_to_reset_merge(self) -> None:
        calls: list[list[str]] = []

        def fake_run_git(_repo: str, args: list[str]) -> str:
            calls.append(list(args))
            if args == ["merge", "--abort"]:
                raise RuntimeError("git falhou: sem merge_head")
            if args == ["reset", "--merge"]:
                return ""
            raise AssertionError(f"Comando inesperado: {args}")

        with patch("viewer.core.conflict_ops.run_git", side_effect=fake_run_git):
            abort_conflict_operation("/tmp/repo", "squash_merge")

        self.assertEqual(calls, [["merge", "--abort"], ["reset", "--merge"]])

    def test_resolve_conflict_file_using_side_runs_checkout_and_add(self) -> None:
        with patch("viewer.core.conflict_ops.run_git") as mocked_run_git:
            resolve_conflict_file_using_side("/tmp/repo", "docs/README.md", "ours")
        self.assertEqual(
            mocked_run_git.call_args_list,
            [
                unittest.mock.call("/tmp/repo", ["checkout", "--ours", "--", "docs/README.md"]),
                unittest.mock.call("/tmp/repo", ["add", "--", "docs/README.md"]),
            ],
        )

    def test_mark_conflict_file_resolved_runs_git_add(self) -> None:
        with patch("viewer.core.conflict_ops.run_git") as mocked_run_git:
            mark_conflict_file_resolved("/tmp/repo", "README.md")
        mocked_run_git.assert_called_once_with("/tmp/repo", ["add", "--", "README.md"])


if __name__ == "__main__":
    unittest.main()

