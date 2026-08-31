#!/usr/bin/env python3
"""Build the static Kodi repository published on GitHub Pages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import re
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
    "search_results_ui.py",
)
PLUGIN_DIRECTORIES = ("resources",)
FIXED_ZIP_DATE = (2020, 1, 1, 0, 0, 0)
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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


def version_from_plugin_zip(path: Path, addon_id: str) -> str | None:
    prefix = f"{addon_id}-"
    if not path.name.startswith(prefix) or not path.name.endswith(".zip"):
        return None
    version = path.name[len(prefix) : -4]
    return version if SEMVER_RE.fullmatch(version) else None


def version_sort_key(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(version)
    if not match:
        raise ValueError(f"Unsupported release version: {version}")
    return tuple(int(part) for part in match.groups())


def validate_archived_plugin_zip(path: Path, addon_id: str, version: str) -> None:
    manifest_path = f"{addon_id}/addon.xml"
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = ET.fromstring(archive.read(manifest_path))
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError(f"Invalid archived plugin ZIP: {path}") from exc

    if manifest.tag != "addon":
        raise ValueError(f"Archived ZIP has invalid add-on manifest: {path}")
    if manifest.get("id") != addon_id or manifest.get("version") != version:
        raise ValueError(
            f"Archived ZIP metadata does not match filename {path.name}: "
            f"id={manifest.get('id')!r}, version={manifest.get('version')!r}"
        )


def copy_archived_plugin_zips(output: Path, addon_id: str, archive_dir: Path | None) -> list[Path]:
    if archive_dir is None or not archive_dir.is_dir():
        return []

    destination_dir = output / "zips" / addon_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied = []

    for source in sorted(path for path in archive_dir.glob("*.zip") if path.is_file()):
        version = version_from_plugin_zip(source, addon_id)
        if version is None:
            continue
        validate_archived_plugin_zip(source, addon_id, version)

        destination = destination_dir / source.name
        if destination.exists():
            # The freshly-built current release wins over an archived copy of the same version.
            continue
        shutil.copy2(source, destination)
        copied.append(destination)

    return copied


def available_plugin_versions(output: Path, addon_id: str) -> list[tuple[str, Path]]:
    plugin_dir = output / "zips" / addon_id
    versions = []
    for path in plugin_dir.glob("*.zip"):
        version = version_from_plugin_zip(path, addon_id)
        if version is not None:
            versions.append((version, path))
    return sorted(versions, key=lambda item: version_sort_key(item[0]), reverse=True)


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


def write_plugin_archive_index(output: Path, plugin_id: str, current_version: str) -> Path:
    plugin_dir = output / "zips" / plugin_id
    versions = available_plugin_versions(output, plugin_id)
    items = []
    for version, path in versions:
        suffix = " (current)" if version == current_version else ""
        items.append(
            f'    <li><a href="{html.escape(path.name)}">'
            f'{html.escape(path.name)}{suffix}</a></li>'
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NAWSP plugin versions</title>
</head>
<body>
  <h1>NAWSP plugin versions</h1>
  <p>The Kodi repository metadata advertises the newest version. Older ZIPs are retained here for manual rollback and testing.</p>
  <ul>
{chr(10).join(items)}
  </ul>
</body>
</html>
"""
    index_path = plugin_dir / "index.html"
    index_path.write_text(page, encoding="utf-8")
    return index_path


def write_index(output: Path, repository_zip: Path, plugin_id: str, plugin_version: str) -> None:
    repo_zip_name = html.escape(repository_zip.name)
    plugin_label = html.escape(f"{plugin_id} {plugin_version}")
    archive_href = html.escape(f"zips/{plugin_id}/")

    # Kodi's HTTP directory parser is more reliable when installable ZIPs are linked
    # directly from the source root instead of only through a nested HTML page.
    version_items = []
    for version, path in available_plugin_versions(output, plugin_id):
        href = html.escape(f"zips/{plugin_id}/{path.name}")
        label = html.escape(path.name)
        suffix = " (current)" if version == plugin_version else ""
        version_items.append(f'    <li><a href="{href}">{label}{suffix}</a></li>')

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
{chr(10).join(version_items)}
    <li><a href="{archive_href}">All plugin versions</a></li>
    <li><a href="addons.xml">addons.xml</a></li>
    <li><a href="addons.xml.md5">addons.xml.md5</a></li>
  </ul>
  <p>Published plugin: {plugin_label}</p>
</body>
</html>
"""
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")


def build(output: Path, archive_dir: Path | None = None) -> None:
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
    archived = copy_archived_plugin_zips(output, plugin_id, archive_dir)
    write_repository_metadata(output, plugin_manifest, repository_manifest)
    write_plugin_archive_index(output, plugin_id, plugin_version)
    write_index(output, repository_zip, plugin_id, plugin_version)

    print(f"Built {plugin_zip.relative_to(output)}")
    print(f"Built {repository_zip.relative_to(output)}")
    print(f"Retained {len(archived)} archived plugin version(s)")
    print(f"Bootstrap ZIP: {repository_zip.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "site",
        help="Directory to build (default: ./site)",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        help="Optional directory containing previously published plugin ZIPs to retain",
    )
    args = parser.parse_args()
    archive_dir = args.archive_dir.resolve() if args.archive_dir else None
    build(args.output.resolve(), archive_dir)


if __name__ == "__main__":
    main()
