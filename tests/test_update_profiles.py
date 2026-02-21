#!/usr/bin/env python3
from __future__ import annotations

import unittest

from viewer.pyside.update_profiles import resolve_update_profile


class TestUpdateProfiles(unittest.TestCase):
    def test_resolve_known_profile(self) -> None:
        profile = resolve_update_profile({"update_profile": "economic"})
        self.assertEqual(profile.key, "economic")
        self.assertEqual(profile.status_interval_sec, 30)
        self.assertEqual(profile.fetch_interval_sec, 600)

    def test_resolve_custom_profile_uses_custom_intervals(self) -> None:
        profile = resolve_update_profile(
            {
                "update_profile": "custom",
                "status_interval_sec": 9,
                "fetch_interval_sec": 30,
                "history_refresh_interval_sec": 44,
                "workspace_refresh_interval_sec": 90,
            }
        )
        self.assertEqual(profile.key, "custom")
        self.assertEqual(profile.status_interval_sec, 9)
        self.assertEqual(profile.fetch_interval_sec, 30)
        self.assertEqual(profile.history_interval_sec, 44)
        self.assertEqual(profile.workspace_interval_sec, 90)

    def test_resolve_custom_profile_fallbacks_for_invalid_values(self) -> None:
        profile = resolve_update_profile(
            {
                "update_profile": "custom",
                "status_interval_sec": "bad",
                "fetch_interval_sec": 0,
                "history_refresh_interval_sec": 1,
                "workspace_refresh_interval_sec": -10,
            }
        )
        self.assertEqual(profile.key, "custom")
        self.assertEqual(profile.status_interval_sec, 15)
        self.assertEqual(profile.fetch_interval_sec, 180)
        self.assertEqual(profile.history_interval_sec, 45)
        self.assertEqual(profile.workspace_interval_sec, 120)


if __name__ == "__main__":
    unittest.main()

