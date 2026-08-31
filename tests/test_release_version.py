# License: AGPL-3.0

import tempfile
import unittest
from pathlib import Path

from scripts.set_release_version import update_addon_xml, update_readme, version_tuple


class ReleaseVersionTests(unittest.TestCase):
    def test_version_tuple_rejects_non_semver(self):
        with self.assertRaises(ValueError):
            version_tuple("v0.5.1")

    def test_updates_addon_and_readme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            addon = root / "addon.xml"
            readme = root / "README.md"
            addon.write_text(
                '<addon id="plugin.video.nawsp" version="0.5.0"></addon>\n',
                encoding="utf-8",
            )
            readme.write_text(
                "- **Current version:** 0.5.0\n",
                encoding="utf-8",
            )

            self.assertTrue(update_addon_xml(addon, "0.5.1"))
            self.assertTrue(update_readme(readme, "0.5.1"))
            self.assertIn('version="0.5.1"', addon.read_text(encoding="utf-8"))
            self.assertIn(
                "- **Current version:** 0.5.1",
                readme.read_text(encoding="utf-8"),
            )

    def test_refuses_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            addon = Path(directory) / "addon.xml"
            addon.write_text(
                '<addon id="plugin.video.nawsp" version="0.5.1"></addon>\n',
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                update_addon_xml(addon, "0.5.0")


if __name__ == "__main__":
    unittest.main()
