# License: AGPL-3.0

import unittest

from media_results import MediaPreferences, group_results


class MediaResultRegressionTests(unittest.TestCase):
    def test_known_size_beats_missing_size_when_other_rank_signals_tie(self):
        items = [
            {
                "ident": "missing-size",
                "name": "Film.2024.1080p.CZ.mkv",
            },
            {
                "ident": "known-size",
                "name": "Film.2024.1080p.CZ.mkv",
                "size": "5000000000",
            },
        ]

        group = group_results(items, MediaPreferences())[0]

        self.assertEqual(group.best.item["ident"], "known-size")


if __name__ == "__main__":
    unittest.main()
