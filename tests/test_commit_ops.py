#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

from viewer.core.commit_ops import (
    apply_stash,
    apply_patch_to_worktree,
    create_stash,
    drop_stash,
    get_stash_patch,
    list_status_entries,
    list_stash_files_from_patch,
    list_stashes,
)


class TestCommitOps(unittest.TestCase):
    def test_create_stash_with_paths(self) -> None:
        with patch("viewer.core.commit_ops.run_git") as mocked_run_git:
            create_stash(
                "/tmp/repo",
                message="selecionados",
                include_untracked=True,
                paths=["viewer/app.py", "README.md"],
            )
        mocked_run_git.assert_called_once_with(
            "/tmp/repo",
            ["stash", "push", "-u", "-m", "selecionados", "--", "viewer/app.py", "README.md"],
        )

    def test_create_stash_without_paths(self) -> None:
        with patch("viewer.core.commit_ops.run_git") as mocked_run_git:
            create_stash("/tmp/repo", message="full", include_untracked=False, paths=[])
        mocked_run_git.assert_called_once_with(
            "/tmp/repo",
            ["stash", "push", "-m", "full"],
        )

    def test_list_stashes_parses_refs_and_descriptions(self) -> None:
        output = "stash@{0}: WIP on main: abc\nstash@{1}: On dev: mensagem\n"
        with patch("viewer.core.commit_ops.run_git", return_value=output):
            entries = list_stashes("/tmp/repo")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].ref, "stash@{0}")
        self.assertEqual(entries[0].description, "WIP on main: abc")
        self.assertEqual(entries[1].ref, "stash@{1}")
        self.assertEqual(entries[1].description, "On dev: mensagem")

    def test_get_stash_patch_with_word_diff_and_file(self) -> None:
        with patch("viewer.core.commit_ops.run_git", return_value="patch") as mocked_run_git:
            patch_value = get_stash_patch(
                "/tmp/repo",
                "stash@{0}",
                word_diff=True,
                path_for_git="viewer/app.py",
            )
        self.assertEqual(patch_value, "patch")
        mocked_run_git.assert_called_once_with(
            "/tmp/repo",
            ["show", "--pretty=format:", "-p", "stash@{0}", "--word-diff=plain", "--", "viewer/app.py"],
        )

    def test_list_stash_files_from_patch(self) -> None:
        patch = (
            "diff --git a/viewer/a.py b/viewer/a.py\n"
            "--- a/viewer/a.py\n"
            "+++ b/viewer/a.py\n"
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n"
            "+++ b/README.md\n"
        )
        files = list_stash_files_from_patch(patch)
        self.assertEqual(files, ["viewer/a.py", "README.md"])

    def test_apply_and_drop_stash_commands(self) -> None:
        with patch("viewer.core.commit_ops.run_git") as mocked_run_git:
            apply_stash("/tmp/repo", "stash@{0}", pop=False)
            apply_stash("/tmp/repo", "stash@{1}", pop=True)
            drop_stash("/tmp/repo", "stash@{2}")
        self.assertEqual(
            mocked_run_git.call_args_list,
            [
                unittest.mock.call("/tmp/repo", ["stash", "apply", "stash@{0}"]),
                unittest.mock.call("/tmp/repo", ["stash", "pop", "stash@{1}"]),
                unittest.mock.call("/tmp/repo", ["stash", "drop", "stash@{2}"]),
            ],
        )

    def test_apply_patch_to_worktree_command(self) -> None:
        with patch("viewer.core.commit_ops.subprocess.run") as mocked_run:
            mocked_run.return_value.returncode = 0
            mocked_run.return_value.stderr = ""
            apply_patch_to_worktree("/tmp/repo", "@@ -1,1 +1,1 @@\n-old\n+new\n", reverse=True)
        mocked_run.assert_called_once()
        args, kwargs = mocked_run.call_args
        self.assertIn("apply", args[0])
        self.assertNotIn("--cached", args[0])
        self.assertIn("-R", args[0])
        self.assertTrue(kwargs["input"].strip().startswith("@@"))

    def test_list_status_entries_normalizes_dev_null_rename_display(self) -> None:
        porcelain = "R  /dev/null\0README.md\0"
        with patch("viewer.core.commit_ops.run_git", return_value=porcelain):
            entries = list_status_entries("/tmp/repo")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["path"], "README.md")
        self.assertEqual(entries[0]["path_for_git"], "README.md")
        self.assertEqual(entries[0]["status"], "R ")


if __name__ == "__main__":
    unittest.main()
