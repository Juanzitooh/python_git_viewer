#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS: dict[str, object] = {
    "commit_limit": 100,
    "fetch_interval_sec": 60,
    "status_interval_sec": 15,
    "recent_repos": [],
    "favorite_repos": [],
    "theme": "light",
    "ui_font_family": "",
    "ui_font_size": 0,
    "mono_font_family": "",
    "mono_font_size": 0,
}


def get_settings_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "git_commits_viewer" / "settings.json"
        return Path.home() / "AppData" / "Roaming" / "git_commits_viewer" / "settings.json"
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "git_commits_viewer" / "settings.json"


def normalize_repo_path(path: str) -> str:
    expanded = os.path.expanduser(path.strip())
    return os.path.normpath(os.path.abspath(expanded))


def _coerce_int(value: object, default: int, minimum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    return parsed


def _coerce_str(value: object, default: str) -> str:
    if not isinstance(value, str):
        return default
    return value.strip()


def _sanitize_repo_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    result: list[str] = []
    for raw in items:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate:
            continue
        normalized = normalize_repo_path(candidate)
        if normalized not in result:
            result.append(normalized)
    return result


def load_settings(path: Path) -> dict[str, object]:
    data = dict(DEFAULT_SETTINGS)
    if not path.exists():
        return data
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return data
    if isinstance(raw, dict):
        data["commit_limit"] = _coerce_int(
            raw.get("commit_limit"),
            int(DEFAULT_SETTINGS["commit_limit"]),
            minimum=1,
        )
        data["fetch_interval_sec"] = _coerce_int(
            raw.get("fetch_interval_sec"),
            int(DEFAULT_SETTINGS["fetch_interval_sec"]),
            minimum=10,
        )
        data["status_interval_sec"] = _coerce_int(
            raw.get("status_interval_sec"),
            int(DEFAULT_SETTINGS["status_interval_sec"]),
            minimum=5,
        )
        data["recent_repos"] = _sanitize_repo_list(raw.get("recent_repos"))
        data["favorite_repos"] = _sanitize_repo_list(raw.get("favorite_repos"))
        theme = _coerce_str(raw.get("theme"), str(DEFAULT_SETTINGS["theme"]))
        data["theme"] = theme if theme in ("light", "dark") else str(DEFAULT_SETTINGS["theme"])
        data["ui_font_family"] = _coerce_str(raw.get("ui_font_family"), "")
        data["ui_font_size"] = _coerce_int(raw.get("ui_font_size"), 0, minimum=0)
        data["mono_font_family"] = _coerce_str(raw.get("mono_font_family"), "")
        data["mono_font_size"] = _coerce_int(raw.get("mono_font_size"), 0, minimum=0)
    return data


def save_settings(path: Path, settings: dict[str, object]) -> None:
    data = dict(DEFAULT_SETTINGS)
    data.update(settings)
    data["recent_repos"] = _sanitize_repo_list(data.get("recent_repos"))
    data["favorite_repos"] = _sanitize_repo_list(data.get("favorite_repos"))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
