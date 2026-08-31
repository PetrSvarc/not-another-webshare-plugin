# -*- coding: utf-8 -*-
# Kodi-independent media filename parsing, grouping and ranking for NAWSP.
# License: AGPL-3.0

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence


VIDEO_EXTENSIONS = (
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".ts",
    ".m2ts",
    ".webm",
)
LANGUAGE_ALIASES = {
    "cz": "CZ",
    "cs": "CZ",
    "cze": "CZ",
    "czech": "CZ",
    "sk": "SK",
    "svk": "SK",
    "slovak": "SK",
    "en": "EN",
    "eng": "EN",
    "english": "EN",
}
RESOLUTION_SCORES = {
    "480p": 10,
    "576p": 15,
    "720p": 25,
    "1080p": 35,
    "2160p": 40,
}
RESOLUTION_ORDER = {
    "480p": 0,
    "576p": 1,
    "720p": 2,
    "1080p": 3,
    "2160p": 4,
}

_EPISODE_RE = re.compile(
    r"(?i)(?:^|[ ._\-\[\(])(?:s(?P<s1>\d{1,2})[ ._\-]*e(?P<e1>\d{1,3})|(?P<s2>\d{1,2})x(?P<e2>\d{1,3}))(?:$|[ ._\-\]\)])"
)
_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_RESOLUTION_PATTERNS = (
    ("2160p", re.compile(r"(?i)(?:^|[^a-z0-9])(?:2160p|4k)(?:$|[^a-z0-9])")),
    ("1080p", re.compile(r"(?i)(?:^|[^a-z0-9])1080[pi](?:$|[^a-z0-9])")),
    ("720p", re.compile(r"(?i)(?:^|[^a-z0-9])720p(?:$|[^a-z0-9])")),
    ("576p", re.compile(r"(?i)(?:^|[^a-z0-9])576p(?:$|[^a-z0-9])")),
    ("480p", re.compile(r"(?i)(?:^|[^a-z0-9])480p(?:$|[^a-z0-9])")),
)
_CODEC_PATTERNS = (
    ("HEVC", re.compile(r"(?i)(?:^|[^a-z0-9])(?:x265|h\.?265|hevc)(?:$|[^a-z0-9])")),
    ("H.264", re.compile(r"(?i)(?:^|[^a-z0-9])(?:x264|h\.?264|avc)(?:$|[^a-z0-9])")),
    ("AV1", re.compile(r"(?i)(?:^|[^a-z0-9])av1(?:$|[^a-z0-9])")),
    ("VP9", re.compile(r"(?i)(?:^|[^a-z0-9])vp9(?:$|[^a-z0-9])")),
)


@dataclass(frozen=True)
class MediaDescriptor:
    kind: str
    title: str
    normalized_title: str
    group_key: Optional[str]
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    resolution: Optional[str] = None
    language: Optional[str] = None
    codec: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.kind == "episode" and self.season is not None and self.episode is not None:
            return f"{self.title} — S{self.season:02d}E{self.episode:02d}"
        if self.kind == "movie" and self.year is not None:
            return f"{self.title} ({self.year})"
        return self.title


@dataclass(frozen=True)
class MediaPreferences:
    preferred_language: str = ""
    preferred_resolution: str = ""
    prefer_hevc: bool = False
    hide_password_protected: bool = False


@dataclass(frozen=True)
class MediaVersion:
    item: Mapping[str, str]
    media: MediaDescriptor
    score: int


@dataclass(frozen=True)
class ResultGroup:
    key: Optional[str]
    versions: Sequence[MediaVersion]

    @property
    def grouped(self) -> bool:
        return self.key is not None and len(self.versions) > 1

    @property
    def best(self) -> MediaVersion:
        return self.versions[0]


def _strip_video_extension(name: str) -> str:
    lower = name.lower()
    for extension in VIDEO_EXTENSIONS:
        if lower.endswith(extension):
            return name[: -len(extension)]
    return name


def _clean_title(value: str) -> str:
    value = re.sub(r"[\[\]\(\){}]+", " ", value)
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s*-\s*", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -._")
    if not value:
        return ""

    words = []
    for word in value.split():
        if word.isupper() and 1 < len(word) <= 4:
            words.append(word)
        else:
            words.append(word[:1].upper() + word[1:])
    return " ".join(words)


def _normalize_title(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.findall(r"\w+", plain.casefold(), flags=re.UNICODE))


def _resolution(name: str) -> Optional[str]:
    for label, pattern in _RESOLUTION_PATTERNS:
        if pattern.search(name):
            return label
    return None


def _language(name: str) -> Optional[str]:
    tokens = [token.casefold() for token in _TOKEN_RE.findall(name)]
    for token in tokens:
        language = LANGUAGE_ALIASES.get(token)
        if language:
            return language
    return None


def _codec(name: str) -> Optional[str]:
    for label, pattern in _CODEC_PATTERNS:
        if pattern.search(name):
            return label
    return None


def parse_media(name: str) -> MediaDescriptor:
    base = _strip_video_extension(name or "").strip()
    resolution = _resolution(base)
    language = _language(base)
    codec = _codec(base)

    episode_match = _EPISODE_RE.search(base)
    if episode_match:
        season = int(episode_match.group("s1") or episode_match.group("s2"))
        episode = int(episode_match.group("e1") or episode_match.group("e2"))
        title = _clean_title(base[: episode_match.start()])
        normalized = _normalize_title(title)
        key = (
            f"episode|{normalized}|s{season:02d}|e{episode:03d}"
            if normalized
            else None
        )
        return MediaDescriptor(
            kind="episode",
            title=title or base,
            normalized_title=normalized,
            group_key=key,
            season=season,
            episode=episode,
            resolution=resolution,
            language=language,
            codec=codec,
        )

    year_matches = list(_YEAR_RE.finditer(base))
    if year_matches:
        # The release year is normally the last year token before technical tags.
        # This handles titles such as "1917.2019.1080p" and "Blade.Runner.2049.2017".
        year_match = year_matches[-1]
        year = int(year_match.group(1))
        title = _clean_title(base[: year_match.start()])
        normalized = _normalize_title(title)
        key = f"movie|{normalized}|{year}" if normalized else None
        return MediaDescriptor(
            kind="movie",
            title=title or base,
            normalized_title=normalized,
            group_key=key,
            year=year,
            resolution=resolution,
            language=language,
            codec=codec,
        )

    title = _clean_title(base)
    return MediaDescriptor(
        kind="unknown",
        title=title or base or "Unknown",
        normalized_title=_normalize_title(title),
        group_key=None,
        resolution=resolution,
        language=language,
        codec=codec,
    )


def is_password_protected(item: Mapping[str, str]) -> bool:
    value = str(item.get("password") or "").strip().casefold()
    return value not in ("", "0", "false", "no", "none")


def _int_value(item: Mapping[str, str], key: str) -> int:
    try:
        return int(item.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def rank_score(
    item: Mapping[str, str],
    media: MediaDescriptor,
    preferences: MediaPreferences,
) -> int:
    score = RESOLUTION_SCORES.get(media.resolution or "", 0)

    if preferences.preferred_language:
        if media.language == preferences.preferred_language:
            score += 200
        elif media.language:
            score -= 40

    if preferences.preferred_resolution:
        preferred = RESOLUTION_ORDER.get(preferences.preferred_resolution)
        actual = RESOLUTION_ORDER.get(media.resolution or "")
        if preferred is not None and actual is not None:
            distance = abs(preferred - actual)
            score += {0: 120, 1: 50, 2: 15}.get(distance, 0)

    if preferences.prefer_hevc and media.codec == "HEVC":
        score += 40

    votes = _int_value(item, "positive_votes") - _int_value(item, "negative_votes")
    score += max(-20, min(20, votes))
    if is_password_protected(item):
        score -= 100
    return score


def _rank_key(version: MediaVersion):
    item = version.item
    votes = _int_value(item, "positive_votes") - _int_value(item, "negative_votes")
    resolution = RESOLUTION_ORDER.get(version.media.resolution or "", -1)
    try:
        size = int(item.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    size_unknown = size <= 0
    return (
        -version.score,
        -votes,
        -resolution,
        size_unknown,
        size if not size_unknown else 0,
        str(item.get("name") or "").casefold(),
        str(item.get("ident") or ""),
    )


def group_results(
    items: Iterable[Mapping[str, str]],
    preferences: MediaPreferences,
) -> list[ResultGroup]:
    grouped = {}
    order = []

    for item in items:
        if preferences.hide_password_protected and is_password_protected(item):
            continue

        media = parse_media(str(item.get("name") or ""))
        version = MediaVersion(
            item=dict(item),
            media=media,
            score=rank_score(item, media, preferences),
        )

        if media.group_key:
            if media.group_key not in grouped:
                grouped[media.group_key] = []
                order.append(("group", media.group_key))
            grouped[media.group_key].append(version)
        else:
            order.append(("single", version))

    result = []
    for kind, value in order:
        if kind == "single":
            result.append(ResultGroup(key=None, versions=[value]))
            continue

        versions = sorted(grouped[value], key=_rank_key)
        result.append(
            ResultGroup(
                key=value if len(versions) > 1 else None,
                versions=versions,
            )
        )
    return result
