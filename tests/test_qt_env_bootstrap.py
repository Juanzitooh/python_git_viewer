#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from viewer.pyside.bootstrap_env import prepare_qt_runtime_env


class TestQtEnvBootstrap(unittest.TestCase):
    def test_prepare_removes_empty_qt_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QT_PLUGIN_PATH": "   ",
                "QT_QPA_PLATFORM_PLUGIN_PATH": "",
            },
            clear=False,
        ), patch.object(sys, "_MEIPASS", "", create=True):
            prepare_qt_runtime_env()
            self.assertNotIn("QT_PLUGIN_PATH", os.environ)
            self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", os.environ)

    def test_prepare_keeps_only_existing_qt_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "plugins"
            existing.mkdir(parents=True, exist_ok=True)
            missing = Path(temp_dir) / "missing"
            with patch.dict(
                os.environ,
                {
                    "QT_PLUGIN_PATH": f"{existing}{os.pathsep}{missing}",
                    "QT_QPA_PLATFORM_PLUGIN_PATH": str(missing),
                },
                clear=False,
            ), patch.object(sys, "_MEIPASS", "", create=True):
                prepare_qt_runtime_env()
                self.assertEqual(os.environ.get("QT_PLUGIN_PATH"), str(existing))
                self.assertNotIn("QT_QPA_PLATFORM_PLUGIN_PATH", os.environ)

    def test_prepare_prefers_pyinstaller_plugin_dirs_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meipass = Path(temp_dir)
            qt_plugins = meipass / "PySide6" / "Qt" / "plugins"
            qt_platforms = qt_plugins / "platforms"
            qt_platforms.mkdir(parents=True, exist_ok=True)
            with patch.dict(
                os.environ,
                {
                    "QT_PLUGIN_PATH": "/tmp/stale-plugin-dir",
                    "QT_QPA_PLATFORM_PLUGIN_PATH": "/tmp/stale-platform-dir",
                },
                clear=False,
            ), patch.object(sys, "_MEIPASS", str(meipass), create=True):
                prepare_qt_runtime_env()
                self.assertEqual(os.environ.get("QT_PLUGIN_PATH"), str(qt_plugins))
                self.assertEqual(os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"), str(qt_platforms))


if __name__ == "__main__":
    unittest.main()
