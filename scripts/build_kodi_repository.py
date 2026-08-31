#!/usr/bin/env python3
"""Build the static Kodi repository published on GitHub Pages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST = ROOT / "addon.xml"
REPOSITORY_SOURCE = ROOT / "repository.nawsp"
REPOSITORY_MANIFEST = REPOSITORY_SOURCE / "addon.xml"

PLUGIN_ROOT_FILES = (
    "addon.xml",
    "LICENSE",
    "main.py",
    "md5crypt.py",
    "series_manager.py",
    "yawsp.py",
    "webshare_api.py",
    "download_utils.py",
    "media_results.py",
)
PLUGIN_DIRECTORIES = ("resources",)
FIXED_ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def parse_manifest(path: Path) -> ET.Element:
    root = ET.parse(path).getroot()
    if root.tag != "addon":
        raise ValueError(f"{path} does not contain an <addon> root element")
    for attribute in ("id", "name", "version", "provider-name"):
        if not root.get(attribute):
            raise ValueError(f"{path} is missing required attribute {attribute!r}")
    return root


def add_bytes(archive: zipfile.ZipFile, archive_path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(archive_path, FIXED_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def add_file(archive: zipfile.ZipFile, source: Path, archive_path: str) -> None:
    add_bytes(archive, archive_path, source.read_bytes())


def build_plugin_zip(output: Path, addon_id: str, version: str) -> Path:
    destination = output / "zips" / addon_id / f"{addon_id}-{version}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(destination, "w") as archive:
        for filename in PLUGIN_ROOT_FILES:
            source = ROOT / filename
            if not source.is_file():
                raise FileNotFoundError(f"Required plugin file is missing: {source}")
            add_file(archive, source, f"{addon_id}/{filename}")

        for dirname in PLUGIN_DIRECTORIES:
            source_dir = ROOT / dirname
            if not source_dir.is_dir():
                raise FileNotFoundError(f"Required plugin directory is missing: {source_dir}")
            for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
                relative = source.relative_to(ROOT).as_posix()
                add_file(archive, source, f"{addon_id}/{relative}")

    return destination


def build_repository_zip(output: Path, addon_id: str, version: str) -> Path:
    destination = output / "zips" / addon_id / f"{addon_id}-{version}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(destination, "w") as archive:
        for source in sorted(path for path in REPOSITORY_SOURCE.rglob("*") if path.is_file()):
            relative = source.relative_to(REPOSITORY_SOURCE).as_posix()
            add_file(archive, source, f"{addon_id}/{relative}")

    # Kodi File Manager bootstrap: keep the repository ZIP directly at site root too.
    shutil.copy2(destination, output / destination.name)
    return destination


def write_repository_metadata(
    output: Path,
    plugin_manifest: ET.Element,
    repository_manifest: ET.Element,
) -> None:
    addons = ET.Element("addons")
    addons.append(copy.deepcopy(repository_manifest))
    addons.append(copy.deepcopy(plugin_manifest))
    ET.indent(addons, space="    ")

    metadata_path = output / "addons.xml"
    ET.ElementTree(addons).write(
        metadata_path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=True,
    )

    digest = hashlib.md5(metadata_path.read_bytes()).hexdigest()  # Kodi compatibility.
    (output / "addons.xml.md5").write_text(digest + "\n", encoding="ascii")


def write_index(output: Path, repository_zip: Path, plugin_id: str, plugin_version: str) -> None:
    repo_zip_name = html.escape(repository_zip.name)
    plugin_label = html.escape(f"{plugin_id} {plugin_version}")
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NAWSP Kodi Repository</title>
</head>
<body>
  <h1>NAWSP Kodi Repository</h1>
  <p>Install the repository ZIP in Kodi, then install Not Another WebShare Plugin from the NAWSP Repository.</p>
  <ul>
    <li><a href="{repo_zip_name}">{repo_zip_name}</a></li>
    <li><a href="addons.xml">addons.xml</a></li>
    <li><a href="addons.xml.md5">addons.xml.md5</a></li>
  </ul>
  <p>Published plugin: {plugin_label}</p>
</body>
</html>
"""
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")


def build(output: Path) -> None:
    plugin_manifest = parse_manifest(PLUGIN_MANIFEST)
    repository_manifest = parse_manifest(REPOSITORY_MANIFEST)

    plugin_id = plugin_manifest.get("id")
    plugin_version = plugin_manifest.get("version")
    repository_id = repository_manifest.get("id")
    repository_version = repository_manifest.get("version")
    assert plugin_id and plugin_version and repository_id and repository_version

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    plugin_zip = build_plugin_zip(output, plugin_id, plugin_version)
    repository_zip = build_repository_zip(output, repository_id, repository_version)
    write_repository_metadata(output, plugin_manifest, repository_manifest)
    write_index(output, repository_zip, plugin_id, plugin_version)

    print(f"Built {plugin_zip.relative_to(output)}")
    print(f"Built {repository_zip.relative_to(output)}")
    print(f"Bootstrap ZIP: {repository_zip.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "site",
        help="Directory to build (default: ./site)",
    )
    args = parser.parse_args()
    build(args.output.resolve())


if __name__ == "__main__":
    main()
