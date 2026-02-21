#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from viewer.pyside.diff_render import build_rendered_diff, sanitize_copied_diff_text
except Exception:  # pragma: no cover - optional dependency in some environments
    build_rendered_diff = None
    sanitize_copied_diff_text = None


@unittest.skipIf(build_rendered_diff is None, "PySide6 indisponivel")
class TestPySideDiffRender(unittest.TestCase):
    def test_rendered_diff_preserves_line_order_and_mapping(self) -> None:
        patch = (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -10,2 +10,2 @@\n"
            "-old_value\n"
            "+new_value\n"
            " context_line\n"
        )
        rendered = build_rendered_diff(patch)
        self.assertGreater(len(rendered.line_to_hunk), 0)
        self.assertGreater(len(rendered.line_to_info), 0)
        self.assertGreater(len(rendered.line_kinds), 0)
        keys = list(rendered.line_to_hunk.keys())
        self.assertEqual(keys, sorted(keys))
        self.assertIn("old_value", rendered.text)
        self.assertIn("new_value", rendered.text)

    def test_rendered_diff_accepts_markers(self) -> None:
        patch = (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-before\n"
            "+after\n"
        )
        rendered = build_rendered_diff(
            patch,
            line_marker_resolver=lambda _line: "[x]",
            hunk_marker_resolver=lambda _idx, _hunk: "[~]",
        )
        self.assertIn("      [~] @ Secao: @@", rendered.text)
        self.assertIn(" [x] - before", rendered.text)
        self.assertIn(" [x] + after", rendered.text)

    def test_rendered_diff_without_marker_column(self) -> None:
        patch = (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-before\n"
            "+after\n"
        )
        rendered = build_rendered_diff(
            patch,
            show_header_lines=False,
            include_marker_column=False,
        )
        self.assertIn("     1  - before", rendered.text)
        self.assertIn("     1  + after", rendered.text)
        self.assertNotIn("[x]", rendered.text)
        self.assertNotIn("Secao:", rendered.text)

    def test_rendered_diff_without_marker_column_preserves_patch_order(self) -> None:
        patch = (
            "@@ -1,1 +1,1 @@\n"
            "+added-first-in-patch\n"
            "-removed-second-in-patch\n"
        )
        rendered = build_rendered_diff(
            patch,
            show_header_lines=False,
            include_marker_column=False,
        )
        lines = rendered.text.splitlines()
        self.assertEqual(lines[0].rstrip(), "     1  + added-first-in-patch")
        self.assertEqual(lines[1].rstrip(), "     1  - removed-second-in-patch")

    def test_sanitize_copied_diff_text_removes_visual_prefix(self) -> None:
        copied = (
            "    36  [x] + - [BUG] Push habilita/desabilita corretamente conforme ahead.\n"
            "    37  [x] + - [X] Menus de contexto de repositorio funcionam:\n"
            "    38  [x] +   - [x] Abrir no VS Code"
        )
        clean = sanitize_copied_diff_text(copied)
        self.assertEqual(
            clean,
            "- [BUG] Push habilita/desabilita corretamente conforme ahead.\n"
            "- [X] Menus de contexto de repositorio funcionam:\n"
            "  - [x] Abrir no VS Code",
        )

    def test_sanitize_copied_diff_text_removes_word_diff_markers(self) -> None:
        copied = "{+function onUpdateDatabase()+}\n[-antigo-]\n{+novo+}"
        clean = sanitize_copied_diff_text(copied)
        self.assertEqual(clean, "function onUpdateDatabase()\nantigo\nnovo")


if __name__ == "__main__":
    unittest.main()
