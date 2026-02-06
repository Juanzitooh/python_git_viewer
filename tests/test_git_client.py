import unittest

from viewer.core.git_client import parse_numstat


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


if __name__ == "__main__":
    unittest.main()
