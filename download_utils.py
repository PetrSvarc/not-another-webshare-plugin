# -*- coding: utf-8 -*-
# Download helpers for Not Another WebShare Plugin (NAWSP).
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

from __future__ import annotations

import os
import re


_ILLEGAL_FILENAME_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_WINDOWS_RESERVED_NAME = re.compile(
    r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)",
    re.IGNORECASE,
)


def _clean_component(value: str) -> str:
    """Return one filesystem-safe filename component."""
    component = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    component = _ILLEGAL_FILENAME_CHARS.sub("_", component)
    return component.strip().strip(".")


def sanitize_filename(filename: str, fallback: str = "download", max_length: int = 240) -> str:
    """Sanitize an untrusted remote filename before writing it locally.

    Path components, control characters and characters invalid on common Kodi
    platforms are removed/replaced. Windows device names are prefixed and long
    names are trimmed while keeping a reasonable extension where possible.
    """
    safe_fallback = _clean_component(fallback) or "download"
    safe_name = _clean_component(filename) or safe_fallback

    if _WINDOWS_RESERVED_NAME.match(safe_name):
        safe_name = f"_{safe_name}"

    max_length = max(1, int(max_length))
    if len(safe_name) > max_length:
        stem, extension = os.path.splitext(safe_name)
        if extension and len(extension) < max_length:
            safe_name = stem[: max_length - len(extension)] + extension
        else:
            safe_name = safe_name[:max_length]

    return safe_name or safe_fallback
