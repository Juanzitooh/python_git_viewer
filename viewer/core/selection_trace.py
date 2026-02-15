#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock

TRACE_ENV_VAR = "GIT_VIEWER_TRACE_SELECTION"
TRACE_FILE_ENV_VAR = "GIT_VIEWER_TRACE_FILE"
DEFAULT_TRACE_FILENAME = "selection_trace.log"

_TRACE_LOCK = Lock()


def is_selection_trace_enabled() -> bool:
    raw_value = os.getenv(TRACE_ENV_VAR, "").strip().lower()
    return raw_value in {"1", "true", "yes", "on", "debug"}


def _resolve_trace_path() -> Path:
    raw_path = os.getenv(TRACE_FILE_ENV_VAR, "").strip()
    if raw_path:
        return Path(raw_path).expanduser()
    return Path.cwd() / DEFAULT_TRACE_FILENAME


def _serialize_field(value: object) -> object:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_field(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            normalized[str(key)] = _serialize_field(item)
        return normalized
    return str(value)


def trace_selection(event: str, **fields: object) -> None:
    if not is_selection_trace_enabled():
        return
    target_path = _resolve_trace_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "event": event.strip() or "unknown",
    }
    for key, value in fields.items():
        record[str(key)] = _serialize_field(value)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with _TRACE_LOCK:
        with target_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
