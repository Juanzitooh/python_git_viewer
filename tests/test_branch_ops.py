#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.branch_ops import (
    checkout_branch,
    delete_local_branch,
    delete_remote_branch,
    local_branch_exists,
    remote_branch_exists,
)


class TestBranchOps(unittest.TestCase):
    def test_checkout_branch_direct(self) -> None:
        with patch("viewer.core.branch_ops.run_git") as mocked_run_git:
            checkout_branch("/tmp/repo", "main")
        mocked_run_git.assert_called_once_with("/tmp/repo", ["checkout", "main"])

    def test_checkout_branch_tracks_remote_when_local_missing(self) -> None:
        calls: list[list[str]] = []

        def fake_run_git(_repo: str, args: list[str]) -> str:
            calls.append(list(args))
            if args == ["checkout", "feature/remote"]:
                raise RuntimeError("git falhou: pathspec 'feature/remote' did not match any file(s) known to git")
            if args == ["show-ref", "--verify", "--quiet", "refs/remotes/feature/remote"]:
                raise RuntimeError("git falhou: nao encontrado")
            if args == ["show-ref", "--verify", "--quiet", "refs/remotes/origin/feature/remote"]:
                return ""
            if args == ["checkout", "-b", "feature/remote", "--track", "origin/feature/remote"]:
                return ""
            raise AssertionError(f"Comando inesperado: {args}")

        with patch("viewer.core.branch_ops.run_git", side_effect=fake_run_git):
            checkout_branch("/tmp/repo", "feature/remote")

        self.assertEqual(
            calls,
            [
                ["checkout", "feature/remote"],
                ["show-ref", "--verify", "--quiet", "refs/remotes/feature/remote"],
                ["show-ref", "--verify", "--quiet", "refs/remotes/origin/feature/remote"],
                ["checkout", "-b", "feature/remote", "--track", "origin/feature/remote"],
            ],
        )

    def test_checkout_branch_does_not_mask_non_lookup_errors(self) -> None:
        with patch(
            "viewer.core.branch_ops.run_git",
            side_effect=RuntimeError("git falhou: Your local changes would be overwritten by checkout"),
        ) as mocked_run_git:
            with self.assertRaises(RuntimeError):
                checkout_branch("/tmp/repo", "main")
        mocked_run_git.assert_called_once_with("/tmp/repo", ["checkout", "main"])

    def test_local_branch_exists(self) -> None:
        with patch("viewer.core.branch_ops.run_git", return_value=""):
            self.assertTrue(local_branch_exists("/tmp/repo", "main"))
        with patch("viewer.core.branch_ops.run_git", side_effect=RuntimeError("nao encontrado")):
            self.assertFalse(local_branch_exists("/tmp/repo", "main"))

    def test_remote_branch_exists(self) -> None:
        with patch("viewer.core.branch_ops.run_git", return_value=""):
            self.assertTrue(remote_branch_exists("/tmp/repo", "origin/main"))
        with patch("viewer.core.branch_ops.run_git", side_effect=RuntimeError("nao encontrado")):
            self.assertFalse(remote_branch_exists("/tmp/repo", "origin/main"))

    def test_delete_local_branch_default_and_force(self) -> None:
        with patch("viewer.core.branch_ops.run_git") as mocked_run_git:
            delete_local_branch("/tmp/repo", "feature/demo")
            delete_local_branch("/tmp/repo", "feature/demo", force=True)
        self.assertEqual(
            mocked_run_git.call_args_list,
            [
                unittest.mock.call("/tmp/repo", ["branch", "-d", "feature/demo"]),
                unittest.mock.call("/tmp/repo", ["branch", "-D", "feature/demo"]),
            ],
        )

    def test_delete_remote_branch(self) -> None:
        with patch("viewer.core.branch_ops.run_git") as mocked_run_git:
            delete_remote_branch("/tmp/repo", "origin", "feature/demo")
        mocked_run_git.assert_called_once_with(
            "/tmp/repo",
            ["push", "origin", "--delete", "feature/demo"],
        )


if __name__ == "__main__":
    unittest.main()
