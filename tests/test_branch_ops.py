#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.branch_ops import checkout_branch


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


if __name__ == "__main__":
    unittest.main()
