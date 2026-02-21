#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.history_local_ops import apply_local_commit_reorder
from viewer.core.history_local_ops import analyze_local_reorder_dependencies
from viewer.core.models import CommitSummary


class TestHistoryLocalOps(unittest.TestCase):
    @patch("viewer.core.history_local_ops.build_reorder_backup_branch", return_value="backup/reorder-main-1")
    @patch("viewer.core.history_local_ops.run_git")
    def test_apply_local_commit_reorder_conflict_keeps_cherry_pick_state(
        self,
        mocked_run_git: unittest.mock.Mock,
        _mocked_backup: unittest.mock.Mock,
    ) -> None:
        commits = [
            CommitSummary(commit_hash="aaa111", subject="a"),
            CommitSummary(commit_hash="bbb222", subject="b"),
        ]

        def side_effect(_repo_path: str, args: list[str]) -> str:
            if args[:2] == ["branch", "backup/reorder-main-1"]:
                return ""
            if args == ["reset", "--hard", "origin/main"]:
                return ""
            if args[:1] == ["cherry-pick"] and len(args) >= 2 and args[1] != "--abort":
                raise RuntimeError("git falhou: conflict")
            if args == ["diff", "--name-only", "--diff-filter=U"]:
                return "README.md\n"
            return ""

        mocked_run_git.side_effect = side_effect
        result = apply_local_commit_reorder(
            "/tmp/repo",
            "origin/main",
            commits,
            current_branch="main",
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.conflict_in_progress)
        self.assertEqual(result.backup_branch, "backup/reorder-main-1")
        call_args = [call.args[1] for call in mocked_run_git.call_args_list]
        self.assertNotIn(["reset", "--hard", "backup/reorder-main-1"], call_args)

    @patch("viewer.core.history_local_ops.build_reorder_backup_branch", return_value="backup/reorder-main-1")
    @patch("viewer.core.history_local_ops.run_git")
    def test_apply_local_commit_reorder_non_conflict_restores_backup(
        self,
        mocked_run_git: unittest.mock.Mock,
        _mocked_backup: unittest.mock.Mock,
    ) -> None:
        commits = [CommitSummary(commit_hash="aaa111", subject="a")]

        def side_effect(_repo_path: str, args: list[str]) -> str:
            if args[:2] == ["branch", "backup/reorder-main-1"]:
                return ""
            if args == ["reset", "--hard", "origin/main"]:
                return ""
            if args[:1] == ["cherry-pick"] and len(args) >= 2 and args[1] != "--abort":
                raise RuntimeError("git falhou: fatal")
            if args == ["diff", "--name-only", "--diff-filter=U"]:
                return ""
            if args == ["rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD"]:
                raise RuntimeError("git falhou: not found")
            if args == ["cherry-pick", "--abort"]:
                return ""
            if args == ["reset", "--hard", "backup/reorder-main-1"]:
                return ""
            return ""

        mocked_run_git.side_effect = side_effect
        result = apply_local_commit_reorder(
            "/tmp/repo",
            "origin/main",
            commits,
            current_branch="main",
        )

        self.assertFalse(result.ok)
        self.assertFalse(result.conflict_in_progress)
        call_args = [call.args[1] for call in mocked_run_git.call_args_list]
        self.assertIn(["reset", "--hard", "backup/reorder-main-1"], call_args)

    @patch("viewer.core.history_local_ops.build_reorder_backup_branch", return_value="backup/reorder-main-1")
    @patch("viewer.core.history_local_ops.run_git")
    def test_apply_local_commit_reorder_conflict_detected_by_error_text(
        self,
        mocked_run_git: unittest.mock.Mock,
        _mocked_backup: unittest.mock.Mock,
    ) -> None:
        commits = [CommitSummary(commit_hash="aaa111", subject="a")]

        def side_effect(_repo_path: str, args: list[str]) -> str:
            if args[:2] == ["branch", "backup/reorder-main-1"]:
                return ""
            if args == ["reset", "--hard", "origin/main"]:
                return ""
            if args[:1] == ["cherry-pick"] and len(args) >= 2 and args[1] != "--abort":
                raise RuntimeError("git falhou: error: could not apply aaa111... test\nhint: git cherry-pick --continue")
            if args == ["diff", "--name-only", "--diff-filter=U"]:
                return ""
            if args == ["rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD"]:
                raise RuntimeError("git falhou: not found")
            return ""

        mocked_run_git.side_effect = side_effect
        result = apply_local_commit_reorder(
            "/tmp/repo",
            "origin/main",
            commits,
            current_branch="main",
        )

        self.assertFalse(result.ok)
        self.assertTrue(result.conflict_in_progress)
        call_args = [call.args[1] for call in mocked_run_git.call_args_list]
        self.assertNotIn(["reset", "--hard", "backup/reorder-main-1"], call_args)

    @patch("viewer.core.history_local_ops.run_git")
    def test_analyze_local_reorder_dependencies_detects_modify_before_add(
        self,
        mocked_run_git: unittest.mock.Mock,
    ) -> None:
        commits = [
            CommitSummary(commit_hash="bbb222", subject="M test.md"),
            CommitSummary(commit_hash="aaa111", subject="A test.md"),
        ]

        def side_effect(_repo_path: str, args: list[str]) -> str:
            if args[-1] == "bbb222":
                return "M\ttest.md\n"
            if args[-1] == "aaa111":
                return "A\ttest.md\n"
            return ""

        mocked_run_git.side_effect = side_effect
        issues = analyze_local_reorder_dependencies("/tmp/repo", commits)
        self.assertTrue(any(issue.reason == "modify_before_add" for issue in issues))


if __name__ == "__main__":
    unittest.main()
