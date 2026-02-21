#!/usr/bin/env python3
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from viewer.pyside.diff_columns import DiffColumnsView, HUNK_INDEX_ROLE, LINE_INFO_ROLE, render_diff_into_columns
except Exception:  # pragma: no cover - optional dependency in some environments
    QApplication = None
    DiffColumnsView = None
    HUNK_INDEX_ROLE = None
    LINE_INFO_ROLE = None
    render_diff_into_columns = None


@unittest.skipIf(QApplication is None or DiffColumnsView is None, "PySide6 indisponivel")
class TestPySideDiffColumns(unittest.TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])

    def test_render_diff_without_marker_column(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        patch = (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-before\n"
            "+after\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=False)
        self.assertEqual(view.topLevelItemCount(), 2)
        first_item = view.topLevelItem(0)
        second_item = view.topLevelItem(1)
        self.assertIsNotNone(first_item)
        self.assertIsNotNone(second_item)
        self.assertEqual(first_item.text(0), "1")
        self.assertEqual(first_item.text(1), "1")
        self.assertTrue(first_item.text(2).startswith("Secao: @@"))
        self.assertEqual(second_item.text(0), "1")
        self.assertEqual(second_item.text(1), "1")
        self.assertEqual(second_item.text(2), "after")
        self.assertEqual(second_item.toolTip(2), "Linha original: before")

    def test_copy_selected_content_uses_only_content_column(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        patch = (
            "@@ -1,1 +1,1 @@\n"
            "-before\n"
            "+after\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=False)
        line_item = view.topLevelItem(1)
        self.assertIsNotNone(line_item)
        line_item.setSelected(True)
        view._copy_selected_content()
        clipboard = QApplication.clipboard().text()
        self.assertEqual(clipboard, "after")

    def test_copy_ignores_hunk_or_meta_rows(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        patch = (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-before\n"
            "+after\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=True)
        header_item = view.topLevelItem(0)
        hunk_item = view.topLevelItem(4)
        line_item = view.topLevelItem(5)
        self.assertIsNotNone(header_item)
        self.assertIsNotNone(hunk_item)
        self.assertIsNotNone(line_item)
        header_item.setSelected(True)
        hunk_item.setSelected(True)
        line_item.setSelected(True)
        view._copy_selected_content()
        clipboard = QApplication.clipboard().text()
        self.assertEqual(clipboard, "after")

    def test_preserves_original_patch_line_order_for_non_paired_lines(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        patch = (
            "@@ -1,1 +1,1 @@\n"
            "+added-first-in-patch\n"
            "-removed-second-in-patch\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=False)
        hunk_item = view.topLevelItem(0)
        first_line = view.topLevelItem(1)
        second_line = view.topLevelItem(2)
        self.assertIsNotNone(hunk_item)
        self.assertIsNotNone(first_line)
        self.assertIsNotNone(second_line)
        self.assertEqual(hunk_item.text(0), "1")
        self.assertEqual(hunk_item.text(1), "1")
        self.assertEqual(first_line.text(0), "")
        self.assertEqual(first_line.text(1), "1")
        self.assertEqual(first_line.text(2), "added-first-in-patch")
        self.assertEqual(second_line.text(0), "1")
        self.assertEqual(second_line.text(1), "")
        self.assertEqual(second_line.text(2), "removed-second-in-patch")

    def test_render_message_when_patch_has_no_hunks(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        render_diff_into_columns(view, "(selecione um arquivo)", show_header_lines=False)
        self.assertEqual(view.topLevelItemCount(), 1)
        item = view.topLevelItem(0)
        self.assertIsNotNone(item)
        self.assertEqual(item.text(2), "(selecione um arquivo)")

    def test_render_binary_patch_summary(self) -> None:
        view = DiffColumnsView(include_marker_column=False)
        patch = (
            "diff --git a/blob.zip b/blob.zip\n"
            "new file mode 100644\n"
            "index 0000000..1234567\n"
            "Binary files /dev/null and b/blob.zip differ\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=False)
        self.assertGreaterEqual(view.topLevelItemCount(), 4)
        first_row = view.topLevelItem(0)
        self.assertIsNotNone(first_row)
        self.assertIn("arquivo binario", first_row.text(2))

    def test_render_with_marker_column_exposes_hunk_and_line_roles(self) -> None:
        view = DiffColumnsView(include_marker_column=True)
        patch = (
            "@@ -10,2 +10,2 @@\n"
            "-before\n"
            "+after\n"
        )
        render_diff_into_columns(view, patch, show_header_lines=False)
        self.assertEqual(view.topLevelItemCount(), 4)
        hunk_item = view.topLevelItem(0)
        separator_item = view.topLevelItem(1)
        removed_item = view.topLevelItem(2)
        added_item = view.topLevelItem(3)
        self.assertIsNotNone(hunk_item)
        self.assertIsNotNone(separator_item)
        self.assertIsNotNone(removed_item)
        self.assertIsNotNone(added_item)
        self.assertEqual(int(hunk_item.data(0, HUNK_INDEX_ROLE)), 0)
        self.assertIsNone(separator_item.data(0, LINE_INFO_ROLE))
        self.assertEqual(int(removed_item.data(0, HUNK_INDEX_ROLE)), 0)
        self.assertEqual(int(added_item.data(0, HUNK_INDEX_ROLE)), 0)
        self.assertIsNotNone(removed_item.data(0, LINE_INFO_ROLE))
        self.assertIsNotNone(added_item.data(0, LINE_INFO_ROLE))


if __name__ == "__main__":
    unittest.main()
