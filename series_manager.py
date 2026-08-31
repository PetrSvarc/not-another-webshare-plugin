# -*- coding: utf-8 -*-
# Module: series_manager
# Original extension author: community/user extension
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html
# Modernized for Not Another WebShare Plugin (NAWSP), 2026-08-31.

from __future__ import annotations

import io
import json
import os
import re

import xbmc
import xbmcgui
import xbmcplugin


EPISODE_PATTERNS = (
    re.compile(r"[Ss](\d+)[Ee](\d+)"),
    re.compile(r"(\d+)x(\d+)", re.IGNORECASE),
    re.compile(r"[Ee]pisode\s*(\d+)", re.IGNORECASE),
    re.compile(r"[Ee]p\s*(\d+)", re.IGNORECASE),
    re.compile(r"[Ee](\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\.\s*(\d+)"),
)

EPISODE_KEYWORDS = (
    "episode",
    "season",
    "series",
    "serie",
    "ep",
    "complete",
    "disk",
)


class SeriesManager:
    def __init__(self, addon, profile, client):
        self.addon = addon
        self.profile = profile
        self.client = client
        self.series_db_path = os.path.join(profile, "series_db")
        self.ensure_db_exists()

    def log(self, message, level=xbmc.LOGINFO):
        xbmc.log(f"NAWSP Series Manager: {message}", level=level)

    def ensure_db_exists(self):
        try:
            os.makedirs(self.series_db_path, exist_ok=True)
        except OSError as exc:
            self.log(f"Failed to create series database: {exc}", xbmc.LOGERROR)

    def search_series(self, series_name, token):
        series_data = {
            "name": series_name,
            "last_updated": xbmc.getInfoLabel("System.Date"),
            "seasons": {},
        }

        search_queries = (
            series_name,
            f"{series_name} season",
            f"{series_name} s01",
            f"{series_name} episode",
        )

        results_by_ident = {}
        for query in search_queries:
            for result in self._perform_search(query, token):
                ident = result.get("ident")
                filename = result.get("name", "")
                if ident and ident not in results_by_ident and self._is_likely_episode(
                    filename,
                    series_name,
                ):
                    results_by_ident[ident] = result

        for item in results_by_ident.values():
            season_num, episode_num = self._detect_episode_info(
                item["name"],
                series_name,
            )
            if season_num is None or episode_num is None:
                continue

            season_key = str(season_num)
            episode_key = str(episode_num)
            series_data["seasons"].setdefault(season_key, {})[episode_key] = {
                "name": item["name"],
                "ident": item["ident"],
                "size": item.get("size", "0"),
            }

        self._save_series_data(series_name, series_data)
        return series_data

    def _perform_search(self, search_query, token):
        xml = self.client.search(
            token,
            search_query,
            category="video",
            sort="recent",
            limit=100,
            offset=0,
        )

        results = []
        for file_element in xml.iter("file"):
            item = {child.tag: child.text for child in file_element}
            if item.get("ident") and item.get("name"):
                results.append(item)
        return results

    def _is_likely_episode(self, filename, series_name):
        if not re.search(re.escape(series_name), filename, re.IGNORECASE):
            return False

        if any(pattern.search(filename) for pattern in EPISODE_PATTERNS):
            return True

        filename_lower = filename.lower()
        return any(keyword in filename_lower for keyword in EPISODE_KEYWORDS)

    def _detect_episode_info(self, filename, series_name):
        cleaned = re.sub(
            re.escape(series_name),
            "",
            filename,
            flags=re.IGNORECASE,
        ).strip()

        for pattern in EPISODE_PATTERNS:
            match = pattern.search(cleaned)
            if not match:
                continue

            groups = match.groups()
            if len(groups) == 2:
                return int(groups[0]), int(groups[1])
            return 1, int(groups[0])

        season_match = re.search(r"(?:season|serie|řada|rada)\s*(\d+)", cleaned, re.IGNORECASE)
        if season_match:
            remainder = cleaned.replace(season_match.group(0), " ")
            episode_match = re.search(r"(?:episode|epizoda|ep|e)?\s*(\d+)", remainder, re.IGNORECASE)
            if episode_match:
                return int(season_match.group(1)), int(episode_match.group(1))

        return None, None

    def _save_series_data(self, series_name, series_data):
        file_path = os.path.join(
            self.series_db_path,
            f"{self._safe_filename(series_name)}.json",
        )
        try:
            with io.open(file_path, "w", encoding="utf-8") as output:
                json.dump(
                    series_data,
                    output,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError as exc:
            self.log(f"Failed to save series data: {exc}", xbmc.LOGERROR)

    def load_series_data(self, series_name):
        file_path = os.path.join(
            self.series_db_path,
            f"{self._safe_filename(series_name)}.json",
        )
        if not os.path.exists(file_path):
            return None

        try:
            with io.open(file_path, "r", encoding="utf-8") as source:
                data = json.load(source)
            return data if isinstance(data, dict) else None
        except (OSError, ValueError, TypeError) as exc:
            self.log(f"Failed to load series data: {exc}", xbmc.LOGERROR)
            return None

    def get_all_series(self):
        result = []
        try:
            filenames = sorted(os.listdir(self.series_db_path))
        except OSError as exc:
            self.log(f"Failed to list series database: {exc}", xbmc.LOGERROR)
            return result

        for filename in filenames:
            if not filename.endswith(".json"):
                continue

            path = os.path.join(self.series_db_path, filename)
            try:
                with io.open(path, "r", encoding="utf-8") as source:
                    data = json.load(source)
            except (OSError, ValueError, TypeError):
                continue

            result.append(
                {
                    "name": data.get("name") or os.path.splitext(filename)[0].replace("_", " "),
                    "filename": filename,
                }
            )

        return result

    @staticmethod
    def _safe_filename(name):
        safe = re.sub(r"[^\w\-. ]", "_", name, flags=re.UNICODE)
        return safe.lower().replace(" ", "_")


def get_url(**kwargs):
    from yawsp import get_url as plugin_get_url

    return plugin_get_url(**kwargs)


def create_series_menu(manager, handle):
    listitem = xbmcgui.ListItem(label=manager.addon.getLocalizedString(30402))
    listitem.setArt({"icon": "DefaultAddSource.png"})
    xbmcplugin.addDirectoryItem(
        handle,
        get_url(action="series_search"),
        listitem,
        True,
    )

    for series in manager.get_all_series():
        listitem = xbmcgui.ListItem(label=series["name"])
        listitem.setArt({"icon": "DefaultFolder.png"})
        xbmcplugin.addDirectoryItem(
            handle,
            get_url(action="series_detail", series_name=series["name"]),
            listitem,
            True,
        )

    xbmcplugin.endOfDirectory(handle)


def create_seasons_menu(manager, handle, series_name):
    series_data = manager.load_series_data(series_name)
    if not series_data:
        xbmcgui.Dialog().notification(
            manager.addon.getAddonInfo("name"),
            manager.addon.getLocalizedString(30403),
            xbmcgui.NOTIFICATION_WARNING,
        )
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    listitem = xbmcgui.ListItem(label=manager.addon.getLocalizedString(30404))
    listitem.setArt({"icon": "DefaultAddonsSearch.png"})
    xbmcplugin.addDirectoryItem(
        handle,
        get_url(action="series_refresh", series_name=series_name),
        listitem,
        True,
    )

    for season_num in sorted(series_data.get("seasons", {}), key=int):
        listitem = xbmcgui.ListItem(
            label=manager.addon.getLocalizedString(30408).format(season_num)
        )
        listitem.setArt({"icon": "DefaultFolder.png"})
        xbmcplugin.addDirectoryItem(
            handle,
            get_url(
                action="series_season",
                series_name=series_name,
                season=season_num,
            ),
            listitem,
            True,
        )

    xbmcplugin.endOfDirectory(handle)


def create_episodes_menu(manager, handle, series_name, season_num):
    series_data = manager.load_series_data(series_name)
    season = (series_data or {}).get("seasons", {}).get(str(season_num))

    if not season:
        xbmcgui.Dialog().notification(
            manager.addon.getAddonInfo("name"),
            manager.addon.getLocalizedString(30410),
            xbmcgui.NOTIFICATION_WARNING,
        )
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    for episode_num in sorted(season, key=int):
        episode = season[episode_num]
        listitem = xbmcgui.ListItem(
            label=manager.addon.getLocalizedString(30411).format(
                episode_num,
                episode["name"],
            )
        )
        listitem.setArt({"icon": "DefaultVideo.png"})
        listitem.setProperty("IsPlayable", "true")
        xbmcplugin.addDirectoryItem(
            handle,
            get_url(
                action="play",
                ident=episode["ident"],
                name=episode["name"],
            ),
            listitem,
            False,
        )

    xbmcplugin.endOfDirectory(handle)
