from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from scripts import build_kodi_repository as builder


class RepositoryArchiveTests(unittest.TestCase):
    def _write_plugin_zip(self, directory: Path, version: str, addon_id: str = "plugin.video.nawsp") -> Path:
        path = directory / f"{addon_id}-{version}.zip"
        manifest = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<addon id="{addon_id}" name="NAWSP" version="{version}" provider-name="test" />'
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"{addon_id}/addon.xml", manifest)
        return path

    def test_copy_archived_versions_keeps_valid_previous_releases(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            archive.mkdir()
            output = root / "site"
            (output / "zips" / "plugin.video.nawsp").mkdir(parents=True)

            self._write_plugin_zip(archive, "0.4.0")
            self._write_plugin_zip(archive, "0.5.0")
            current = self._write_plugin_zip(output / "zips" / "plugin.video.nawsp", "0.5.1")

            copied = builder.copy_archived_plugin_zips(output, "plugin.video.nawsp", archive)

            self.assertEqual(
                {path.name for path in copied},
                {"plugin.video.nawsp-0.4.0.zip", "plugin.video.nawsp-0.5.0.zip"},
            )
            self.assertTrue(current.is_file())
            self.assertEqual(
                [version for version, _ in builder.available_plugin_versions(output, "plugin.video.nawsp")],
                ["0.5.1", "0.5.0", "0.4.0"],
            )

    def test_archived_zip_metadata_must_match_filename(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            archive.mkdir()
            output = root / "site"
            (output / "zips" / "plugin.video.nawsp").mkdir(parents=True)

            wrong = archive / "plugin.video.nawsp-0.5.0.zip"
            manifest = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<addon id="plugin.video.nawsp" name="NAWSP" version="9.9.9" provider-name="test" />'
            )
            with zipfile.ZipFile(wrong, "w") as zip_file:
                zip_file.writestr("plugin.video.nawsp/addon.xml", manifest)

            with self.assertRaises(ValueError):
                builder.copy_archived_plugin_zips(output, "plugin.video.nawsp", archive)

    def test_archive_index_marks_current_and_lists_newest_first(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            plugin_dir = output / "zips" / "plugin.video.nawsp"
            plugin_dir.mkdir(parents=True)
            self._write_plugin_zip(plugin_dir, "0.4.0")
            self._write_plugin_zip(plugin_dir, "0.5.1")
            self._write_plugin_zip(plugin_dir, "0.5.0")

            index = builder.write_plugin_archive_index(output, "plugin.video.nawsp", "0.5.1")
            content = index.read_text(encoding="utf-8")

            self.assertLess(content.index("0.5.1"), content.index("0.5.0"))
            self.assertLess(content.index("0.5.0"), content.index("0.4.0"))
            self.assertIn("plugin.video.nawsp-0.5.1.zip (current)", content)

    def test_root_index_links_all_plugin_versions_directly(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            plugin_dir = output / "zips" / "plugin.video.nawsp"
            plugin_dir.mkdir(parents=True)
            self._write_plugin_zip(plugin_dir, "0.4.0")
            self._write_plugin_zip(plugin_dir, "0.5.1")

            repository_zip = output / "repository.nawsp-1.0.0.zip"
            repository_zip.write_bytes(b"test")
            builder.write_index(output, repository_zip, "plugin.video.nawsp", "0.5.1")
            content = (output / "index.html").read_text(encoding="utf-8")

            current = "zips/plugin.video.nawsp/plugin.video.nawsp-0.5.1.zip"
            previous = "zips/plugin.video.nawsp/plugin.video.nawsp-0.4.0.zip"
            self.assertIn(f'href="{current}"', content)
            self.assertIn(f'href="{previous}"', content)
            self.assertLess(content.index(current), content.index(previous))


if __name__ == "__main__":
    unittest.main()
