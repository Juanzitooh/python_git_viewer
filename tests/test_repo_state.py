#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.repo_state import get_default_branch, list_branches, list_local_branches_with_upstream


class TestRepoState(unittest.TestCase):
    def test_list_branches_includes_remote_and_deduplicates(self) -> None:
        output = "\n".join(
            [
                "refs/heads/main",
                "refs/heads/feature/local",
                "refs/heads/backup/reorder-main-20260221",
                "refs/remotes/origin/main",
                "refs/remotes/origin/feature/remote",
                "refs/remotes/upstream/main",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/feature/local",
            ]
        )
        with patch("viewer.core.repo_state.run_git", return_value=output):
            branches = list_branches("/tmp/repo")
        self.assertEqual(
            branches,
            [
                "main",
                "feature/local",
                "origin/feature/remote",
                "upstream/main",
            ],
        )

    def test_get_default_branch_from_origin_head(self) -> None:
        with patch("viewer.core.repo_state.run_git", return_value="refs/remotes/origin/main\n"):
            default_branch = get_default_branch("/tmp/repo")
        self.assertEqual(default_branch, "main")

    def test_get_default_branch_falls_back_to_main(self) -> None:
        with patch("viewer.core.repo_state.run_git", side_effect=RuntimeError("git falhou: sem origin/HEAD")):
            with patch("viewer.core.repo_state.list_branches", return_value=["dev", "main"]):
                default_branch = get_default_branch("/tmp/repo")
        self.assertEqual(default_branch, "main")

    def test_list_local_branches_with_upstream(self) -> None:
        output = "\n".join(
            [
                "main|origin/main",
                "feature/demo|origin/feature/demo",
                "hotfix/local-only|",
            ]
        )
        with patch("viewer.core.repo_state.run_git", return_value=output):
            tracked = list_local_branches_with_upstream("/tmp/repo")
        self.assertEqual(tracked, {"main", "feature/demo"})


if __name__ == "__main__":
    unittest.main()
