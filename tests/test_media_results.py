# License: AGPL-3.0

import unittest

from media_results import MediaPreferences, group_results, parse_media


class MediaParsingTests(unittest.TestCase):
    def test_groups_movie_releases_by_title_and_year(self):
        items = [
            {
                "ident": "a",
                "name": "Dune.Part.Two.2024.1080p.WEB-DL.CZ.mkv",
                "size": "5400000000",
            },
            {
                "ident": "b",
                "name": "Dune.Part.Two.2024.2160p.HEVC.EN.mkv",
                "size": "12100000000",
            },
        ]

        groups = group_results(items, MediaPreferences())

        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0].grouped)
        self.assertEqual(groups[0].best.media.display_title, "Dune Part Two (2024)")

    def test_groups_episode_notation_variants(self):
        items = [
            {"ident": "a", "name": "The.Bear.S03E01.1080p.CZ.x265.mkv"},
            {"ident": "b", "name": "The.Bear.3x01.720p.EN.x264.mkv"},
        ]

        groups = group_results(items, MediaPreferences())

        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0].grouped)
        self.assertEqual(groups[0].best.media.display_title, "The Bear — S03E01")

    def test_ambiguous_filename_remains_individual(self):
        parsed = parse_media("Random.File.Without.Year.1080p.mkv")

        self.assertEqual(parsed.kind, "unknown")
        self.assertIsNone(parsed.group_key)

    def test_different_movie_years_do_not_group(self):
        items = [
            {"ident": "a", "name": "Dune.1984.1080p.mkv"},
            {"ident": "b", "name": "Dune.2021.1080p.mkv"},
        ]

        groups = group_results(items, MediaPreferences())

        self.assertEqual(len(groups), 2)
        self.assertTrue(all(not group.grouped for group in groups))


class MediaRankingTests(unittest.TestCase):
    def test_language_and_resolution_preferences_select_best_version(self):
        items = [
            {
                "ident": "4k-en",
                "name": "Dune.Part.Two.2024.2160p.HEVC.EN.mkv",
                "positive_votes": "30",
            },
            {
                "ident": "1080-cz",
                "name": "Dune.Part.Two.2024.1080p.CZ.x264.mkv",
                "positive_votes": "5",
            },
        ]
        preferences = MediaPreferences(
            preferred_language="CZ",
            preferred_resolution="1080p",
        )

        group = group_results(items, preferences)[0]

        self.assertEqual(group.best.item["ident"], "1080-cz")

    def test_prefer_hevc_breaks_otherwise_similar_match(self):
        items = [
            {"ident": "h264", "name": "Film.2024.1080p.CZ.x264.mkv"},
            {"ident": "hevc", "name": "Film.2024.1080p.CZ.x265.mkv"},
        ]

        group = group_results(
            items,
            MediaPreferences(preferred_language="CZ", prefer_hevc=True),
        )[0]

        self.assertEqual(group.best.item["ident"], "hevc")

    def test_password_protected_files_can_be_hidden(self):
        items = [
            {"ident": "open", "name": "Film.2024.1080p.CZ.mkv", "password": "0"},
            {"ident": "locked", "name": "Film.2024.2160p.CZ.mkv", "password": "1"},
        ]

        groups = group_results(
            items,
            MediaPreferences(hide_password_protected=True),
        )

        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0].grouped)
        self.assertEqual(groups[0].best.item["ident"], "open")

    def test_ranking_is_deterministic(self):
        items = [
            {"ident": "b", "name": "Film.2024.1080p.CZ.mkv"},
            {"ident": "a", "name": "Film.2024.1080p.CZ.mkv"},
        ]

        first = group_results(items, MediaPreferences())[0].best.item["ident"]
        second = group_results(list(reversed(items)), MediaPreferences())[0].best.item["ident"]

        self.assertEqual(first, "a")
        self.assertEqual(second, "a")


if __name__ == "__main__":
    unittest.main()
