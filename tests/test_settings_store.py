#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from viewer.core.settings_store import DEFAULT_SETTINGS, load_settings, save_settings


class TestSettingsStore(unittest.TestCase):
    def test_load_settings_normalizes_update_profile_and_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            payload = {
                "update_profile": "INVALID",
                "status_interval_sec": 1,
                "fetch_interval_sec": 2,
                "history_refresh_interval_sec": 3,
                "workspace_refresh_interval_sec": 4,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            data = load_settings(path)
            self.assertEqual(data["update_profile"], DEFAULT_SETTINGS["update_profile"])
            self.assertEqual(data["status_interval_sec"], DEFAULT_SETTINGS["status_interval_sec"])
            self.assertEqual(data["fetch_interval_sec"], DEFAULT_SETTINGS["fetch_interval_sec"])
            self.assertEqual(
                data["history_refresh_interval_sec"],
                DEFAULT_SETTINGS["history_refresh_interval_sec"],
            )
            self.assertEqual(
                data["workspace_refresh_interval_sec"],
                DEFAULT_SETTINGS["workspace_refresh_interval_sec"],
            )

    def test_save_settings_accepts_known_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(path, {"update_profile": "economic"})
            data = load_settings(path)
            self.assertEqual(data["update_profile"], "economic")

    def test_last_tab_name_is_loaded_and_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            payload = {
                "last_tab_index": 3,
                "last_tab_name": "Historico",
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_settings(path)
            self.assertEqual(loaded["last_tab_index"], 3)
            self.assertEqual(loaded["last_tab_name"], "Historico")

            save_settings(path, loaded)
            reloaded = load_settings(path)
            self.assertEqual(reloaded["last_tab_name"], "Historico")

    def test_theme_overrides_and_fonts_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(
                path,
                {
                    "theme": "dark",
                    "theme_overrides": {
                        "dark": {
                            "bg": "#101010",
                            "accent": "#1A73E8",
                            "invalid": "nope",
                        }
                    },
                    "ui_font_family": "Noto Sans",
                    "ui_font_size": 11,
                    "mono_font_family": "JetBrains Mono",
                    "mono_font_size": 10,
                },
            )
            data = load_settings(path)
            self.assertEqual(data["theme"], "dark")
            self.assertEqual(data["ui_font_family"], "Noto Sans")
            self.assertEqual(data["ui_font_size"], 11)
            self.assertEqual(data["mono_font_family"], "JetBrains Mono")
            self.assertEqual(data["mono_font_size"], 10)
            self.assertEqual(data["theme_overrides"]["dark"]["bg"], "#101010")
            self.assertEqual(data["theme_overrides"]["dark"]["accent"], "#1A73E8")
            self.assertNotIn("invalid", data["theme_overrides"]["dark"])

    def test_theme_system_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            save_settings(path, {"theme": "system"})
            data = load_settings(path)
            self.assertEqual(data["theme"], "system")


if __name__ == "__main__":
    unittest.main()
