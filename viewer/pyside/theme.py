from __future__ import annotations

import re
from typing import TypedDict, cast


class ThemePalette(TypedDict):
    # Cores base da janela e texto.
    bg: str
    fg: str
    muted: str
    # Cores de superficies e campos.
    panel: str
    field: str
    # Cores de borda.
    border: str
    border_soft: str
    # Cores de destaque (botoes primarios, foco).
    accent: str
    accent_hover: str
    accent_fg: str
    # Cores de selecao.
    selection_bg: str
    selection_fg: str
    # Cores de botoes/chips neutros.
    button_bg: str
    button_hover: str
    chip_bg: str
    diff_bg: str
    # Cores de diff e status.
    diff_added: str
    diff_removed: str
    diff_modified: str
    diff_context: str
    diff_hunk: str
    diff_meta: str
    diff_word_added_fg: str
    diff_word_added_bg: str
    diff_word_removed_fg: str
    diff_word_removed_bg: str
    status_renamed: str
    status_deleted: str
    status_added: str
    status_modified: str


THEME_PALETTES: dict[str, ThemePalette] = {
    "dark": {
        "bg": "#0f1520",
        "fg": "#e5e7eb",
        "muted": "#9aa4b2",
        "panel": "#1a2230",
        "field": "#000000",
        "border": "#334155",
        "border_soft": "#1f2937",
        "accent": "#3b82f6",
        "accent_hover": "#2563eb",
        "accent_fg": "#ffffff",
        "selection_bg": "#1e3a5f",
        "selection_fg": "#ffffff",
        "button_bg": "#1f2937",
        "button_hover": "#273449",
        "chip_bg": "#1a3357",
        "diff_bg": "#000000",
        "diff_added": "#22c55e",
        "diff_removed": "#ef4444",
        "diff_modified": "#f59e0b",
        "diff_context": "#ffffff",
        "diff_hunk": "#93c5fd",
        "diff_meta": "#9ca3af",
        "diff_word_added_fg": "#86efac",
        "diff_word_added_bg": "#14532d",
        "diff_word_removed_fg": "#fca5a5",
        "diff_word_removed_bg": "#7f1d1d",
        "status_renamed": "#60a5fa",
        "status_deleted": "#ef4444",
        "status_added": "#22c55e",
        "status_modified": "#f59e0b",
    },
    "light": {
        "bg": "#f4f7fb",
        "fg": "#0f172a",
        "muted": "#475569",
        "panel": "#ffffff",
        "field": "#ffffff",
        "border": "#cbd5e1",
        "border_soft": "#e2e8f0",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_fg": "#ffffff",
        "selection_bg": "#dbeafe",
        "selection_fg": "#0f172a",
        "button_bg": "#f8fafc",
        "button_hover": "#eef2f7",
        "chip_bg": "#eaf1ff",
        "diff_bg": "#ffffff",
        "diff_added": "#15803d",
        "diff_removed": "#b91c1c",
        "diff_modified": "#b45309",
        "diff_context": "#0f172a",
        "diff_hunk": "#1d4ed8",
        "diff_meta": "#475569",
        "diff_word_added_fg": "#166534",
        "diff_word_added_bg": "#dcfce7",
        "diff_word_removed_fg": "#991b1b",
        "diff_word_removed_bg": "#fee2e2",
        "status_renamed": "#1d4ed8",
        "status_deleted": "#b91c1c",
        "status_added": "#15803d",
        "status_modified": "#b45309",
    },
}

# Campos editaveis da paleta e seus rotulos para UI.
THEME_COLOR_FIELDS: tuple[tuple[str, str], ...] = (
    ("bg", "Fundo da janela"),
    ("fg", "Texto principal"),
    ("muted", "Texto secundario"),
    ("panel", "Painel"),
    ("field", "Campos"),
    ("border", "Borda"),
    ("border_soft", "Borda suave"),
    ("accent", "Destaque"),
    ("accent_hover", "Destaque hover"),
    ("accent_fg", "Texto do destaque"),
    ("selection_bg", "Selecao (fundo)"),
    ("selection_fg", "Selecao (texto)"),
    ("button_bg", "Botao (fundo)"),
    ("button_hover", "Botao hover"),
    ("chip_bg", "Chip"),
    ("diff_bg", "Diff (fundo)"),
    ("diff_added", "Diff adicionado"),
    ("diff_removed", "Diff removido"),
    ("diff_modified", "Diff modificado"),
    ("diff_context", "Diff contexto"),
    ("diff_hunk", "Diff secao"),
    ("diff_meta", "Diff metadado"),
    ("diff_word_added_fg", "Diff palavra + (texto)"),
    ("diff_word_added_bg", "Diff palavra + (fundo)"),
    ("diff_word_removed_fg", "Diff palavra - (texto)"),
    ("diff_word_removed_bg", "Diff palavra - (fundo)"),
    ("status_renamed", "Status renomeado"),
    ("status_deleted", "Status deletado"),
    ("status_added", "Status adicionado"),
    ("status_modified", "Status modificado"),
)

PALETTE_KEYS = tuple(field for field, _ in THEME_COLOR_FIELDS)
HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def normalize_hex_color(value: str) -> str | None:
    candidate = str(value or "").strip()
    if not HEX_COLOR_PATTERN.match(candidate):
        return None
    if len(candidate) == 4:
        candidate = "#" + "".join([char * 2 for char in candidate[1:]])
    return candidate.upper()


def normalize_theme_name(theme: str) -> str:
    candidate = str(theme or "").strip().lower()
    if candidate in THEME_PALETTES:
        return candidate
    return "light"


def sanitize_theme_overrides(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, dict[str, str]] = {}
    for theme_name in THEME_PALETTES:
        raw_theme = value.get(theme_name)
        if not isinstance(raw_theme, dict):
            continue
        theme_colors: dict[str, str] = {}
        for color_key in PALETTE_KEYS:
            raw_color = raw_theme.get(color_key)
            if not isinstance(raw_color, str):
                continue
            normalized_color = normalize_hex_color(raw_color)
            if normalized_color is None:
                continue
            theme_colors[color_key] = normalized_color
        if theme_colors:
            sanitized[theme_name] = theme_colors
    return sanitized


def get_theme_palette(theme: str, overrides: object | None = None) -> ThemePalette:
    theme_name = normalize_theme_name(theme)
    palette_data = dict(THEME_PALETTES[theme_name])
    if overrides is not None:
        sanitized_overrides = sanitize_theme_overrides(overrides)
        palette_data.update(sanitized_overrides.get(theme_name, {}))
    return cast(ThemePalette, palette_data)


def get_diff_kind_color(
    kind: str,
    *,
    is_light: bool,
    theme_overrides: object | None = None,
) -> str | None:
    theme_name = "light" if is_light else "dark"
    palette = get_theme_palette(theme_name, theme_overrides)
    mapping = {
        "added": "diff_added",
        "removed": "diff_removed",
        "modified": "diff_modified",
        "context": "diff_context",
        "hunk": "diff_hunk",
    }
    color_key = mapping.get(kind)
    if color_key is None:
        return None
    return palette[color_key]


def get_commit_status_color(
    status_kind: str,
    *,
    is_light: bool,
    theme_overrides: object | None = None,
) -> str | None:
    theme_name = "light" if is_light else "dark"
    palette = get_theme_palette(theme_name, theme_overrides)
    mapping = {
        "renamed": "status_renamed",
        "deleted": "status_deleted",
        "added": "status_added",
        "modified": "status_modified",
    }
    color_key = mapping.get(status_kind)
    if color_key is None:
        return None
    return palette[color_key]


def get_diff_render_color(
    color_kind: str,
    *,
    is_light: bool,
    theme_overrides: object | None = None,
) -> str | None:
    theme_name = "light" if is_light else "dark"
    palette = get_theme_palette(theme_name, theme_overrides)
    mapping = {
        "line_added": "diff_added",
        "line_removed": "diff_removed",
        "line_context": "diff_context",
        "line_hunk": "diff_hunk",
        "line_meta": "diff_meta",
        "word_added_fg": "diff_word_added_fg",
        "word_added_bg": "diff_word_added_bg",
        "word_removed_fg": "diff_word_removed_fg",
        "word_removed_bg": "diff_word_removed_bg",
    }
    color_key = mapping.get(color_kind)
    if color_key is None:
        return None
    return palette[color_key]


def build_theme_stylesheet(theme: str, theme_overrides: object | None = None) -> str:
    p = get_theme_palette(theme, theme_overrides)
    return f"""
    QMainWindow {{
      background-color: {p["bg"]};
    }}
    QWidget {{
      color: {p["fg"]};
    }}
    QToolTip {{
      color: {p["fg"]};
      background-color: {p["panel"]};
      border: 1px solid {p["border"]};
      padding: 4px;
    }}
    QWidget#TopBar {{
      background-color: {p["panel"]};
      border: 1px solid {p["border"]};
      border-radius: 10px;
    }}
    QStatusBar {{
      background-color: {p["panel"]};
      border-top: 1px solid {p["border_soft"]};
    }}
    QTabWidget::pane {{
      border: 1px solid {p["border"]};
      border-radius: 10px;
      background-color: {p["panel"]};
      margin-top: 6px;
      padding: 6px;
    }}
    QTabBar::tab {{
      background-color: {p["button_bg"]};
      border: 1px solid {p["border"]};
      border-bottom: none;
      border-top-left-radius: 8px;
      border-top-right-radius: 8px;
      padding: 7px 12px;
      margin-right: 4px;
    }}
    QTabBar::tab:hover {{
      background-color: {p["button_hover"]};
    }}
    QTabBar::tab:selected {{
      background-color: {p["panel"]};
      color: {p["fg"]};
      border-color: {p["accent"]};
    }}
    QLineEdit, QComboBox, QPlainTextEdit {{
      background-color: {p["field"]};
      border: 1px solid {p["border"]};
      border-radius: 8px;
      padding: 6px;
      selection-background-color: {p["selection_bg"]};
      selection-color: {p["selection_fg"]};
    }}
    QListWidget, QTreeWidget {{
      background-color: {p["field"]};
      border: 1px solid {p["border"]};
      border-radius: 8px;
      padding: 6px;
      selection-background-color: {p["selection_bg"]};
    }}
    QScrollArea#SettingsScrollArea {{
      background-color: {p["panel"]};
      border: 1px solid {p["border"]};
      border-radius: 8px;
    }}
    QWidget#SettingsScrollContent {{
      background-color: {p["panel"]};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus, QTreeWidget:focus {{
      border: 1px solid {p["accent"]};
    }}
    QComboBox QAbstractItemView {{
      background-color: {p["field"]};
      color: {p["fg"]};
      border: 1px solid {p["border"]};
      selection-background-color: {p["selection_bg"]};
      selection-color: {p["selection_fg"]};
      outline: 0;
    }}
    QPlainTextEdit[role="diff"] {{
      background-color: {p["diff_bg"]};
    }}
    QTreeWidget#DiffColumnsView, QTreeWidget#DiffColumnsView::item {{
      background-color: {p["diff_bg"]};
    }}
    QTreeWidget#DiffColumnsView::indicator {{
      width: 14px;
      height: 14px;
      border: 1px solid {p["border"]};
      border-radius: 2px;
      background-color: {p["field"]};
    }}
    QTreeWidget#DiffColumnsView::indicator:checked {{
      background-color: {p["accent"]};
      border-color: {p["accent"]};
    }}
    QTreeWidget#DiffColumnsView::indicator:indeterminate {{
      background-color: {p["chip_bg"]};
      border-color: {p["accent"]};
    }}
    QListWidget::item {{
      min-height: 22px;
      padding: 1px 4px;
    }}
    QTreeWidget::item {{
      padding: 1px 4px;
    }}
    QTreeWidget#DiffColumnsView::item {{
      padding: 1px 2px;
    }}
    QListWidget::item:selected {{
      background-color: {p["selection_bg"]};
    }}
    QTreeWidget::item:selected {{
      background-color: {p["selection_bg"]};
    }}
    QFrame#WorkspaceCard {{
      background-color: {p["field"]};
      border: 1px solid {p["border"]};
      border-radius: 10px;
    }}
    QFrame#WorkspaceCard[selected="true"] {{
      border: 1px solid {p["accent"]};
      background-color: {p["selection_bg"]};
    }}
    QFrame#WorkspaceCardAdd {{
      background-color: {p["button_bg"]};
      border: 1px dashed {p["border"]};
      border-radius: 10px;
    }}
    QScrollArea#WorkspaceCardsScroll {{
      background-color: {p["field"]};
      border: 1px solid {p["border_soft"]};
      border-radius: 8px;
    }}
    QWidget#WorkspaceCardsViewport, QWidget#WorkspaceCardsContainer {{
      background-color: {p["field"]};
    }}
    QLabel#WorkspaceCardTitle {{
      font-weight: 600;
    }}
    QLabel#WorkspaceCardPath, QLabel#WorkspaceCardMeta {{
      color: {p["muted"]};
    }}
    QPushButton {{
      background-color: {p["button_bg"]};
      border: 1px solid {p["border"]};
      border-radius: 8px;
      padding: 6px 10px;
    }}
    QPushButton:hover {{
      background-color: {p["button_hover"]};
      border-color: {p["accent"]};
    }}
    QPushButton[role="primary"] {{
      background-color: {p["accent"]};
      color: {p["accent_fg"]};
      border-color: {p["accent"]};
      font-weight: 600;
    }}
    QPushButton[role="primary"]:hover {{
      background-color: {p["accent_hover"]};
      border-color: {p["accent_hover"]};
    }}
    QPushButton:disabled {{
      color: {p["muted"]};
    }}
    QLabel#SyncChip, QLabel#BusyBadge, QPushButton#SyncChip {{
      background-color: {p["chip_bg"]};
      border: 1px solid {p["border"]};
      border-radius: 10px;
      padding: 3px 8px;
    }}
    QProgressBar#BusyBar {{
      background-color: {p["field"]};
      border: 1px solid {p["border"]};
      border-radius: 8px;
    }}
    QProgressBar#BusyBar::chunk {{
      background-color: {p["accent"]};
      border-radius: 8px;
    }}
    """
