import unittest
from unittest.mock import patch

from viewer.core.git_client import FIELD_SEP, RECORD_SEP, build_log_args, load_commit_summaries, parse_numstat


class TestParseNumstat(unittest.TestCase):
    def test_parse_numstat_mixed(self) -> None:
        output = "3\t2\tapp.py\n-\t-\timage.png\n0\t1\tREADME.md\n"
        stats, added, deleted = parse_numstat(output)

        self.assertEqual(added, 3)
        self.assertEqual(deleted, 3)
        self.assertEqual(len(stats), 3)

        self.assertEqual(stats[0].path, "app.py")
        self.assertFalse(stats[0].is_binary)
        self.assertEqual(stats[0].added, 3)
        self.assertEqual(stats[0].deleted, 2)

        self.assertEqual(stats[1].path, "image.png")
        self.assertTrue(stats[1].is_binary)
        self.assertEqual(stats[1].added, 0)
        self.assertEqual(stats[1].deleted, 0)

        self.assertEqual(stats[2].path, "README.md")
        self.assertFalse(stats[2].is_binary)
        self.assertEqual(stats[2].added, 0)
        self.assertEqual(stats[2].deleted, 1)


class TestCommitSummaries(unittest.TestCase):
    def test_build_log_args_includes_metadata(self) -> None:
        args = build_log_args(limit=25, skip=5, filters=None)

        self.assertIn("--date=iso", args)
        pretty_values = [item for item in args if item.startswith("--pretty=format:")]
        self.assertEqual(len(pretty_values), 1)
        self.assertIn("%an", pretty_values[0])
        self.assertIn("%ad", pretty_values[0])
        self.assertIn("%ct", pretty_values[0])

    @patch("viewer.core.git_client.run_git")
    def test_load_commit_summaries_parses_metadata(self, run_git_mock: unittest.mock.Mock) -> None:
        run_git_mock.return_value = (
            f"1111111{FIELD_SEP}fix: ajuste UI{FIELD_SEP}Joao{FIELD_SEP}"
            f"2026-02-08 19:21:16 -0300{FIELD_SEP}1739053276{RECORD_SEP}"
            f"2222222{FIELD_SEP}feat: novo fluxo{FIELD_SEP}Maria{FIELD_SEP}"
            f"2026-02-07 11:02:01 -0300{FIELD_SEP}0{RECORD_SEP}"
        )

        summaries = load_commit_summaries("/tmp/repo", limit=10)

        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].commit_hash, "1111111")
        self.assertEqual(summaries[0].subject, "fix: ajuste UI")
        self.assertEqual(summaries[0].author, "Joao")
        self.assertEqual(summaries[0].date, "2026-02-08 19:21:16 -0300")
        self.assertEqual(summaries[0].timestamp, 1739053276)
        self.assertEqual(summaries[1].author, "Maria")
        self.assertEqual(summaries[1].timestamp, 0)


if __name__ == "__main__":
    unittest.main()
