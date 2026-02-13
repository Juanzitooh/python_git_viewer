import unittest

from viewer.core.diff_utils import build_read_mode_diff, parse_diff_data, strip_word_diff_markers


class TestDiffUtils(unittest.TestCase):
    def test_parse_diff_data(self) -> None:
        diff_text = (
            "diff --git a/file.txt b/file.txt\n"
            "index 83db48f..f735c2d 100644\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1,2 +1,3 @@\n"
            "-line1\n"
            "+line1-mod\n"
            " line2\n"
            "+line3\n"
        )
        data = parse_diff_data(diff_text, word_diff_plain=True)
        self.assertEqual(len(data.hunks), 1)
        lines = data.hunks[0].lines
        self.assertEqual([line.line_type for line in lines], ["removed", "added", "context", "added"])

    def test_build_read_mode_diff(self) -> None:
        diff_text = "\n".join(f"line {idx}" for idx in range(20))
        preview, truncated = build_read_mode_diff(diff_text, threshold=10, max_lines=6)
        self.assertTrue(truncated)
        self.assertIn("linhas omitidas", preview)
        self.assertTrue(preview.endswith("\n"))

    def test_parse_diff_data_word_diff_plain_lines(self) -> None:
        diff_text = (
            "diff --git a/file.txt b/file.txt\n"
            "index 83db48f..f735c2d 100644\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -1,1 +1,1 @@\n"
            "[-valor antigo-]\n"
            "{+valor novo+}\n"
            " linha comum com [-troca-]{+troca2+}\n"
        )
        data = parse_diff_data(diff_text, word_diff_plain=True)
        self.assertEqual(len(data.hunks), 1)
        lines = data.hunks[0].lines
        self.assertEqual([line.line_type for line in lines], ["removed", "added", "removed", "added"])
        self.assertEqual(lines[0].content, "valor antigo")
        self.assertEqual(lines[1].content, "valor novo")
        self.assertEqual(lines[2].content.strip(), "linha comum com troca")
        self.assertEqual(lines[3].content.strip(), "linha comum com troca2")

    def test_parse_diff_data_word_diff_plain_with_markdown_bullet(self) -> None:
        diff_text = (
            "diff --git a/file.txt b/file.txt\n"
            "index 83db48f..f735c2d 100644\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -10,3 +10,3 @@ title\n"
            "- [-[ ]-]{+[x]+} item\n"
        )
        data = parse_diff_data(diff_text, word_diff_plain=True)
        self.assertEqual(len(data.hunks), 1)
        lines = data.hunks[0].lines
        self.assertEqual([line.line_type for line in lines], ["removed", "added"])
        self.assertEqual(lines[0].old_line, 10)
        self.assertEqual(lines[1].new_line, 10)
        self.assertEqual(lines[0].content, "- [ ] item")
        self.assertEqual(lines[1].content, "- [x] item")

    def test_parse_diff_data_word_diff_plain_preserves_line_prefix_in_content(self) -> None:
        diff_text = (
            "diff --git a/file.txt b/file.txt\n"
            "index 83db48f..f735c2d 100644\n"
            "--- a/file.txt\n"
            "+++ b/file.txt\n"
            "@@ -7,1 +7,1 @@\n"
            "+ [-old-]{+new+} value\n"
        )
        data = parse_diff_data(diff_text, word_diff_plain=True)
        lines = data.hunks[0].lines
        self.assertEqual([line.line_type for line in lines], ["removed", "added"])
        self.assertEqual(lines[0].content, "+ old value")
        self.assertEqual(lines[1].content, "+ new value")

    def test_strip_word_diff_markers(self) -> None:
        text = "{+novo+} e [-antigo-] e {-removido-}"
        self.assertEqual(strip_word_diff_markers(text), "novo e antigo e removido")


if __name__ == "__main__":
    unittest.main()
