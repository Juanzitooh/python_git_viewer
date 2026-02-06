import unittest

from viewer.core.diff_utils import build_read_mode_diff, parse_diff_data


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
        data = parse_diff_data(diff_text)
        self.assertEqual(len(data.hunks), 1)
        lines = data.hunks[0].lines
        self.assertEqual([line.line_type for line in lines], ["removed", "added", "context", "added"])

    def test_build_read_mode_diff(self) -> None:
        diff_text = "\n".join(f"line {idx}" for idx in range(20))
        preview, truncated = build_read_mode_diff(diff_text, threshold=10, max_lines=6)
        self.assertTrue(truncated)
        self.assertIn("linhas omitidas", preview)
        self.assertTrue(preview.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
