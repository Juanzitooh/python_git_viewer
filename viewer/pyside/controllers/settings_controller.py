from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFileDialog

from ...core.repo_workspace import default_repo_scan_root
from ...core.settings_store import normalize_repo_path
from ..theme import (
    THEME_COLOR_FIELDS,
    get_theme_palette,
    normalize_hex_color,
    normalize_theme_name,
    sanitize_theme_overrides,
)
from ..update_profiles import resolve_update_profile


def _get_selected_theme(window: object) -> str:
    theme_data = window.settings_theme_combo.currentData()
    theme = str(theme_data).strip() if theme_data is not None else "light"
    return normalize_theme_name(theme)


def _get_theme_overrides_draft(window: object) -> dict[str, dict[str, str]]:
    draft = getattr(window, "_theme_overrides_draft", None)
    if isinstance(draft, dict):
        return sanitize_theme_overrides(draft)
    sanitized = sanitize_theme_overrides(window.settings_data.get("theme_overrides", {}))
    window._theme_overrides_draft = sanitized
    return sanitized


def _set_color_preview(window: object, color_key: str, color_value: str) -> None:
    preview = window.settings_theme_color_previews.get(color_key)
    if preview is None:
        return
    theme = _get_selected_theme(window)
    palette = get_theme_palette(theme, _get_theme_overrides_draft(window))
    border_color = palette["border"]
    preview.setStyleSheet(
        f"background-color: {color_value}; border: 1px solid {border_color}; border-radius: 4px;"
    )
    preview.setToolTip(color_value)


def _sync_theme_color_inputs(window: object) -> None:
    if not hasattr(window, "settings_theme_color_inputs"):
        return
    theme = _get_selected_theme(window)
    theme_palette = get_theme_palette(theme)
    theme_overrides = _get_theme_overrides_draft(window).get(theme, {})
    for color_key, _label in THEME_COLOR_FIELDS:
        color_input = window.settings_theme_color_inputs.get(color_key)
        if color_input is None:
            continue
        color_value = theme_overrides.get(color_key, theme_palette[color_key]).upper()
        was_blocked = color_input.blockSignals(True)
        color_input.setText(color_value)
        color_input.blockSignals(was_blocked)
        _set_color_preview(window, color_key, color_value)


def _apply_theme_preview_from_settings(window: object) -> None:
    theme = _get_selected_theme(window)
    theme_overrides = _get_theme_overrides_draft(window)
    window._apply_theme(theme, theme_overrides)


def _sync_update_profile_summary(window: object) -> None:
    if not hasattr(window, "settings_update_profile_combo"):
        return
    profile = resolve_update_profile(
        {
            **window.settings_data,
            "update_profile": window.settings_update_profile_combo.currentData(),
        }
    )
    summary = (
        f"Status {profile.status_interval_sec}s | "
        f"Fetch {profile.fetch_interval_sec}s | "
        f"Head historico {profile.history_interval_sec}s | "
        f"Cards {profile.workspace_interval_sec}s"
    )
    if hasattr(window, "settings_update_profile_summary_label"):
        window.settings_update_profile_summary_label.setText(summary)


def load_settings_into_tab(window: object) -> None:
    if not hasattr(window, "settings_theme_combo"):
        return
    window._theme_overrides_draft = sanitize_theme_overrides(
        window.settings_data.get("theme_overrides", {})
    )
    theme = str(window.settings_data.get("theme", "light"))
    theme_index = window.settings_theme_combo.findData(theme)
    if theme_index < 0:
        theme_index = window.settings_theme_combo.findData("light")
    if theme_index >= 0:
        window.settings_theme_combo.setCurrentIndex(theme_index)
    _sync_theme_color_inputs(window)

    if hasattr(window, "settings_update_profile_combo"):
        selected_profile = str(window.settings_data.get("update_profile", "balanced")).strip().lower()
        profile_index = window.settings_update_profile_combo.findData(selected_profile)
        if profile_index < 0:
            profile_index = window.settings_update_profile_combo.findData("balanced")
        if profile_index >= 0:
            window.settings_update_profile_combo.setCurrentIndex(profile_index)
        _sync_update_profile_summary(window)

    workspace_root = str(window.settings_data.get("repo_scan_root", window.repo_scan_root)).strip()
    if workspace_root:
        workspace_root = normalize_repo_path(workspace_root)
    else:
        workspace_root = normalize_repo_path(default_repo_scan_root())
    window.settings_workspace_root_edit.setText(workspace_root)


def pick_settings_workspace_root(window: object) -> None:
    current = window.settings_workspace_root_edit.text().strip() or window.repo_scan_root
    selected = QFileDialog.getExistingDirectory(window, "Selecionar raiz do workspace", current)
    if not selected:
        return
    normalized = normalize_repo_path(selected)
    window.settings_workspace_root_edit.setText(normalized)


def on_settings_theme_changed(window: object) -> None:
    _sync_theme_color_inputs(window)
    _apply_theme_preview_from_settings(window)
    window.settings_status_label.setText("Preview de tema aplicado (salve para persistir).")


def on_settings_update_profile_changed(window: object) -> None:
    selected_data = window.settings_update_profile_combo.currentData()
    selected_profile = str(selected_data).strip().lower() if selected_data is not None else "balanced"
    if selected_profile not in {"realtime", "balanced", "economic", "custom"}:
        selected_profile = "balanced"
    window._apply_background_update_profile(selected_profile)
    _sync_update_profile_summary(window)
    window.settings_status_label.setText("Perfil de atualizacao aplicado (salve para persistir).")


def on_settings_theme_color_edited(window: object, color_key: str) -> None:
    color_input = window.settings_theme_color_inputs.get(color_key)
    if color_input is None:
        return
    typed_value = color_input.text().strip()
    normalized_color = normalize_hex_color(typed_value)
    theme = _get_selected_theme(window)
    theme_palette = get_theme_palette(theme)
    if normalized_color is None:
        fallback_value = _get_theme_overrides_draft(window).get(theme, {}).get(
            color_key,
            theme_palette[color_key],
        )
        color_input.setText(fallback_value.upper())
        _set_color_preview(window, color_key, fallback_value.upper())
        window.settings_status_label.setText("Cor invalida. Use formato #RRGGBB.")
        return
    theme_overrides = _get_theme_overrides_draft(window)
    theme_bucket = dict(theme_overrides.get(theme, {}))
    if normalized_color.upper() == theme_palette[color_key].upper():
        theme_bucket.pop(color_key, None)
    else:
        theme_bucket[color_key] = normalized_color.upper()
    if theme_bucket:
        theme_overrides[theme] = theme_bucket
    else:
        theme_overrides.pop(theme, None)
    window._theme_overrides_draft = sanitize_theme_overrides(theme_overrides)
    color_input.setText(normalized_color.upper())
    _set_color_preview(window, color_key, normalized_color.upper())
    _apply_theme_preview_from_settings(window)
    window.settings_status_label.setText("Preview de cor aplicado (salve para persistir).")


def pick_settings_theme_color(window: object, color_key: str) -> None:
    color_input = window.settings_theme_color_inputs.get(color_key)
    if color_input is None:
        return
    current_text = color_input.text().strip()
    if QColor(current_text).isValid():
        current_color = QColor(current_text)
    else:
        theme = _get_selected_theme(window)
        palette = get_theme_palette(theme, _get_theme_overrides_draft(window))
        current_color = QColor(palette["accent"])
    selected = QColorDialog.getColor(current_color, window, "Selecionar cor")
    if not selected.isValid():
        return
    color_input.setText(selected.name().upper())
    on_settings_theme_color_edited(window, color_key)


def reset_settings_theme_colors(window: object) -> None:
    theme = _get_selected_theme(window)
    theme_overrides = _get_theme_overrides_draft(window)
    theme_overrides.pop(theme, None)
    window._theme_overrides_draft = sanitize_theme_overrides(theme_overrides)
    _sync_theme_color_inputs(window)
    _apply_theme_preview_from_settings(window)
    window.settings_status_label.setText("Cores do tema atual resetadas (salve para persistir).")


def save_settings_from_tab(window: object) -> None:
    theme = _get_selected_theme(window)
    update_profile_data = window.settings_update_profile_combo.currentData()
    update_profile = str(update_profile_data).strip().lower()
    if update_profile not in {"realtime", "balanced", "economic", "custom"}:
        update_profile = "balanced"

    workspace_text = window.settings_workspace_root_edit.text().strip()
    workspace_root = (
        normalize_repo_path(workspace_text)
        if workspace_text
        else normalize_repo_path(default_repo_scan_root())
    )

    window.settings_data["theme"] = theme
    window.settings_data["update_profile"] = update_profile
    window.settings_data["theme_overrides"] = sanitize_theme_overrides(
        _get_theme_overrides_draft(window)
    )
    window.settings_data["repo_scan_root"] = workspace_root
    window.repo_scan_root = workspace_root

    window._persist_state()
    window._apply_background_update_profile()
    window._apply_theme_from_settings()
    window.workspace_root_edit.setText(window.repo_scan_root)
    window._scan_workspace_repos()
    window._reload_history_commits()
    window.settings_status_label.setText("Configurações salvas.")
    window._set_status("Configurações salvas.")
