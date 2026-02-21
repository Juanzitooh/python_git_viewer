#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.conflict_ops import (
    abort_conflict_operation,
    abort_conflict_operation_and_restore,
    continue_conflict_operation,
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

    def test_abort_conflict_operation_and_restore_runs_reset_hard(self) -> None:
        with patch("viewer.core.conflict_ops.run_git") as mocked_run_git:
            abort_conflict_operation_and_restore(
                "/tmp/repo",
                "cherry-pick",
                restore_ref="backup/reorder-main-20260221",
            )
        self.assertEqual(
            mocked_run_git.call_args_list,
            [
                unittest.mock.call("/tmp/repo", ["cherry-pick", "--abort"]),
                unittest.mock.call("/tmp/repo", ["reset", "--hard", "backup/reorder-main-20260221"]),
            ],
        )

    def test_abort_conflict_operation_and_restore_can_delete_backup_branch(self) -> None:
        with patch("viewer.core.conflict_ops.run_git") as mocked_run_git:
            abort_conflict_operation_and_restore(
                "/tmp/repo",
                "cherry-pick",
                restore_ref="backup/reorder-main-20260221",
                delete_restore_ref=True,
            )
        self.assertEqual(
            mocked_run_git.call_args_list,
            [
                unittest.mock.call("/tmp/repo", ["cherry-pick", "--abort"]),
                unittest.mock.call("/tmp/repo", ["reset", "--hard", "backup/reorder-main-20260221"]),
                unittest.mock.call("/tmp/repo", ["branch", "-D", "backup/reorder-main-20260221"]),
            ],
        )

    @patch("viewer.core.conflict_ops.subprocess.run")
    def test_continue_cherry_pick_uses_non_interactive_editor_env(self, mocked_run: unittest.mock.Mock) -> None:
        mocked_run.return_value.returncode = 0
        mocked_run.return_value.stdout = ""
        mocked_run.return_value.stderr = ""

        continue_conflict_operation("/tmp/repo", "cherry-pick")

        mocked_run.assert_called_once()
        args, kwargs = mocked_run.call_args
        self.assertEqual(args[0], ["git", "-C", "/tmp/repo", "cherry-pick", "--continue"])
        env = kwargs.get("env", {})
        self.assertEqual(env.get("GIT_EDITOR"), "true")
        self.assertEqual(env.get("EDITOR"), "true")
        self.assertEqual(env.get("VISUAL"), "true")


if __name__ == "__main__":
    unittest.main()
