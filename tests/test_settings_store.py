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


if __name__ == "__main__":
    unittest.main()
