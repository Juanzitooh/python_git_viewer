#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from .repo_workspace import default_repo_scan_root

DEFAULT_SETTINGS: dict[str, object] = {
    "commit_limit": 100,
    "fetch_interval_sec": 60,
    "status_interval_sec": 15,
    "last_tab_index": 0,
    "last_repo_path": "",
    "recent_repos": [],
    "favorite_repos": [],
    "repo_scan_root": default_repo_scan_root(),
    "theme": "light",
    "ui_font_family": "",
    "ui_font_size": 0,
    "mono_font_family": "",
    "mono_font_size": 0,
    "github_ssh_cache": {},
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


def _sanitize_repo_root(value: object) -> str:
    if not isinstance(value, str):
        return str(DEFAULT_SETTINGS["repo_scan_root"])
    candidate = value.strip()
    if not candidate:
        return str(DEFAULT_SETTINGS["repo_scan_root"])
    return normalize_repo_path(candidate)


def _sanitize_repo_path(value: object) -> str:
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    if not candidate:
        return ""
    return normalize_repo_path(candidate)


def _sanitize_github_ssh_cache(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    has_key = bool(value.get("has_key", False))
    authenticated = bool(value.get("authenticated", False))
    key_path_raw = value.get("key_path", "")
    key_path = ""
    if isinstance(key_path_raw, str) and key_path_raw.strip():
        key_path = normalize_repo_path(key_path_raw)
    checked_at_raw = value.get("checked_at", 0)
    key_mtime_ns_raw = value.get("key_mtime_ns", 0)
    try:
        checked_at = int(checked_at_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        checked_at = 0
    try:
        key_mtime_ns = int(key_mtime_ns_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        key_mtime_ns = 0
    if checked_at < 0:
        checked_at = 0
    if key_mtime_ns < 0:
        key_mtime_ns = 0
    if not has_key:
        key_path = ""
        key_mtime_ns = 0
    return {
        "has_key": has_key,
        "authenticated": authenticated,
        "key_path": key_path,
        "checked_at": checked_at,
        "key_mtime_ns": key_mtime_ns,
    }


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
        data["last_tab_index"] = _coerce_int(
            raw.get("last_tab_index"),
            int(DEFAULT_SETTINGS["last_tab_index"]),
            minimum=0,
        )
        data["last_repo_path"] = _sanitize_repo_path(raw.get("last_repo_path"))
        data["recent_repos"] = _sanitize_repo_list(raw.get("recent_repos"))
        data["favorite_repos"] = _sanitize_repo_list(raw.get("favorite_repos"))
        data["repo_scan_root"] = _sanitize_repo_root(raw.get("repo_scan_root"))
        theme = _coerce_str(raw.get("theme"), str(DEFAULT_SETTINGS["theme"]))
        data["theme"] = theme if theme in ("light", "dark") else str(DEFAULT_SETTINGS["theme"])
        data["ui_font_family"] = _coerce_str(raw.get("ui_font_family"), "")
        data["ui_font_size"] = _coerce_int(raw.get("ui_font_size"), 0, minimum=0)
        data["mono_font_family"] = _coerce_str(raw.get("mono_font_family"), "")
        data["mono_font_size"] = _coerce_int(raw.get("mono_font_size"), 0, minimum=0)
        data["github_ssh_cache"] = _sanitize_github_ssh_cache(raw.get("github_ssh_cache"))
    return data


def save_settings(path: Path, settings: dict[str, object]) -> None:
    data = dict(DEFAULT_SETTINGS)
    data.update(settings)
    data["last_repo_path"] = _sanitize_repo_path(data.get("last_repo_path"))
    data["recent_repos"] = _sanitize_repo_list(data.get("recent_repos"))
    data["favorite_repos"] = _sanitize_repo_list(data.get("favorite_repos"))
    data["repo_scan_root"] = _sanitize_repo_root(data.get("repo_scan_root"))
    data["github_ssh_cache"] = _sanitize_github_ssh_cache(data.get("github_ssh_cache"))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
