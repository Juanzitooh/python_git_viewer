from __future__ import annotations

import os
import sys
from pathlib import Path


def _sanitize_path_list_env(var_name: str) -> None:
    raw_value = os.environ.get(var_name)
    if raw_value is None:
        return
    value = raw_value.strip()
    if not value:
        os.environ.pop(var_name, None)
        return
    parts = [item.strip() for item in value.split(os.pathsep) if item.strip()]
    if not parts:
        os.environ.pop(var_name, None)
        return
    existing = [item for item in parts if os.path.isdir(item)]
    if not existing:
        os.environ.pop(var_name, None)
        return
    os.environ[var_name] = os.pathsep.join(existing)


def prepare_qt_runtime_env() -> None:
    # Remove stale values that usually break PySide startup after one-file extractions.
    _sanitize_path_list_env("QT_PLUGIN_PATH")
    _sanitize_path_list_env("QT_QPA_PLATFORM_PLUGIN_PATH")

    bundle_root = getattr(sys, "_MEIPASS", "")
    if not bundle_root:
        return
    qt_plugins = Path(bundle_root) / "PySide6" / "Qt" / "plugins"
    qt_platforms = qt_plugins / "platforms"
    if qt_plugins.is_dir():
        os.environ["QT_PLUGIN_PATH"] = str(qt_plugins)
    if qt_platforms.is_dir():
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(qt_platforms)

