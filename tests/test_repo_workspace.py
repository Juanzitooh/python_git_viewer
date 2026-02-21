#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viewer.core.repo_workspace import _parse_clone_target_path


class TestParseCloneTargetPath(unittest.TestCase):
    def test_folder_name_is_treated_as_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = _parse_clone_target_path(
                "git@github.com:example/otclient.git",
                root,
                "elemental",
            )
            self.assertEqual(target, root / "elemental" / "otclient")

    def test_folder_with_repo_suffix_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = _parse_clone_target_path(
                "git@github.com:example/otclient.git",
                root,
                "elemental/otclient",
            )
            self.assertEqual(target, root / "elemental" / "otclient")


if __name__ == "__main__":
    unittest.main()
