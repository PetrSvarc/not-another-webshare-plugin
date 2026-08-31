#!/usr/bin/env python3
"""Update NAWSP release metadata for an automated release."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def version_tuple(value: str) -> tuple[int, int, int]:
    if not VERSION_RE.fullmatch(value):
        raise ValueError(f"Invalid semantic version: {value}")
    return tuple(int(part) for part in value.split("."))


def update_addon_xml(path: Path, version: str) -> bool:
    content = path.read_text(encoding="utf-8")
    root = ET.fromstring(content)
    current = root.get("version") or ""
    if version_tuple(version) < version_tuple(current):
        raise ValueError(f"Refusing to downgrade addon.xml from {current} to {version}")
    if current == version:
        return False

    updated, count = re.subn(
        r'(<addon\b[^>]*\bversion=")[^"]+("[^>]*>)',
        rf"\g<1>{version}\g<2>",
        content,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not update addon version attribute")
    path.write_text(updated, encoding="utf-8")
    return True


def update_readme(path: Path, version: str) -> bool:
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(- \*\*Current version:\*\* )\d+\.\d+\.\d+",
        rf"\g<1>{version}",
        content,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not update README current version")
    if updated == content:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: set_release_version.py X.Y.Z", file=sys.stderr)
        return 2

    version = sys.argv[1].strip()
    version_tuple(version)

    changed = False
    changed |= update_addon_xml(Path("addon.xml"), version)
    changed |= update_readme(Path("README.md"), version)
    print(f"NAWSP release metadata set to {version}; changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
