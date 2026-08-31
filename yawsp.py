# -*- coding: utf-8 -*-
# Module: NAWSP Kodi UI/router
# Original YAWSP author: cache-sk
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html
# Modernized for Not Another WebShare Plugin (NAWSP), 2026-08-31.

from __future__ import annotations

import io
import json
import os
import re
import sys
import traceback
import uuid
from urllib.parse import parse_qsl, urlencode

import unidecode
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

import series_manager
from webshare_api import (
    WebshareApiError,
    WebshareClient,
    WebshareError,
    WebshareTransportError,
)


CATEGORIES = ["", "video", "images", "audio", "archives", "docs", "adult"]
SORTS = ["", "recent", "rating", "largest", "smallest"]
SEARCH_HISTORY = "search_history"
NONE_WHAT = "%#NONE#%"

_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_profile = xbmcvfs.translatePath(_addon.getAddonInfo("profile"))
_client = WebshareClient()


def log(message, level=xbmc.LOGINFO):
    xbmc.log(f"NAWSP: {message}", level=level)


def get_url(**kwargs):
    return f"{_url}?{urlencode(kwargs)}"


def popinfo(
    message,
    heading=None,
    icon=xbmcgui.NOTIFICATION_INFO,
    time=3000,
    sound=False,
):
    xbmcgui.Dialog().notification(
        heading or _addon.getAddonInfo("name"),
        message,
        icon,
        time,
        sound=sound,
    )


def handle_webshare_error(exc, message_id=30107):
    log(str(exc), xbmc.LOGERROR)
    popinfo(
        _addon.getLocalizedString(message_id),
        icon=xbmcgui.NOTIFICATION_ERROR,
        sound=True,
    )


def login():
    username = _addon.getSetting("wsuser").strip()
    password = _addon.getSetting("wspass")

    if not username or not password:
        popinfo(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return None

    try:
        token = _client.login(username, password)
    except WebshareApiError as exc:
        log(f"Login rejected by Webshare: {exc}", xbmc.LOGWARNING)
        popinfo(
            _addon.getLocalizedString(30102),
            icon=xbmcgui.NOTIFICATION_ERROR,
            sound=True,
        )
        return None
    except WebshareTransportError as exc:
        handle_webshare_error(exc)
        return None

    _addon.setSetting("token", token)
    return token


def revalidate():
    token = _addon.getSetting("token")

    if token:
        try:
            user_xml = _client.user_data(token)
            if user_xml.findtext("vip") != "1":
                popinfo(
                    _addon.getLocalizedString(30103),
                    icon=xbmcgui.NOTIFICATION_WARNING,
                )
            return token
        except WebshareError as exc:
            log(f"Stored token is not valid: {exc}", xbmc.LOGWARNING)
            _addon.setSetting("token", "")

    return login()


def element_to_dict(element, skip=None):
    skip = set(skip or ())
    result = {}

    for child in element:
        if child.tag in skip:
            continue

        value = child.text if len(child) == 0 else element_to_dict(child, skip)
        if child.tag not in result:
            result[child.tag] = value
        elif isinstance(result[child.tag], list):
            result[child.tag].append(value)
        else:
            result[child.tag] = [result[child.tag], value]

    return result


def sizelize(txtsize, units=("B", "KB", "MB", "GB")):
    if txtsize is None:
        return "?"

    try:
        size = float(txtsize)
    except (TypeError, ValueError):
        return str(txtsize)

    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        value = str(int(size)) if size.is_integer() else str(size)
    elif unit_index == 1:
        value = str(int(round(size)))
    else:
        value = str(round(size, 2))

    return f"{value}{units[unit_index]}"


def labelize(file_data):
    size = file_data.get("size")
    if size is None:
        size = file_data.get("sizelized", "?")
    else:
        size = sizelize(size)
    return f"{file_data.get('name', '?')} ({size})"


def tolistitem(file_data, extra_commands=None):
    label = labelize(file_data)
    listitem = xbmcgui.ListItem(label=label)

    if file_data.get("img"):
        listitem.setArt({"thumb": file_data["img"]})

    listitem.setInfo("video", {"title": label})
    listitem.setProperty("IsPlayable", "true")

    ident = file_data.get("ident")
    commands = []
    if ident:
        commands.extend(
            [
                (
                    _addon.getLocalizedString(30211),
                    f"RunPlugin({get_url(action='info', ident=ident)})",
                ),
                (
                    _addon.getLocalizedString(30212),
                    f"RunPlugin({get_url(action='download', ident=ident)})",
                ),
            ]
        )

    commands.extend(extra_commands or [])
    if commands:
        listitem.addContextMenuItems(commands)

    return listitem


def ask(default_text=""):
    keyboard = xbmc.Keyboard(default_text or "", _addon.getLocalizedString(30007))
    keyboard.doModal()
    return keyboard.getText() if keyboard.isConfirmed() else None


def _ensure_profile():
    if not xbmcvfs.exists(_profile):
        xbmcvfs.mkdirs(_profile)


def _history_path():
    return os.path.join(_profile, SEARCH_HISTORY)


def loadsearch():
    _ensure_profile()
    path = _history_path()

    if not xbmcvfs.exists(path):
        return []

    try:
        with io.open(path, "r", encoding="utf-8") as history_file:
            data = json.load(history_file)
        return data if isinstance(data, list) else []
    except (OSError, ValueError, TypeError):
        log("Failed to load search history", xbmc.LOGWARNING)
        return []


def _write_search_history(history):
    _ensure_profile()
    try:
        with io.open(_history_path(), "w", encoding="utf-8") as history_file:
            json.dump(history, history_file, ensure_ascii=False)
    except OSError:
        log("Failed to save search history", xbmc.LOGERROR)
        traceback.print_exc()


def storesearch(what):
    if not what:
        return

    try:
        max_items = max(1, int(_addon.getSetting("shistory") or 20))
    except ValueError:
        max_items = 20

    history = [item for item in loadsearch() if item != what]
    history.insert(0, what)
    _write_search_history(history[:max_items])


def removesearch(what):
    history = [item for item in loadsearch() if item != what]
    _write_search_history(history)


def dosearch(token, what, category, sort, limit, offset, action):
    try:
        xml = _client.search(
            token,
            "" if what == NONE_WHAT else what,
            category=category,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except WebshareError as exc:
        handle_webshare_error(exc)
        return

    if offset > 0:
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30206))
        listitem.setArt({"icon": "DefaultAddonsSearch.png"})
        previous_offset = max(0, offset - limit)
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(
                action=action,
                what=what,
                category=category,
                sort=sort,
                limit=limit,
                offset=previous_offset,
            ),
            listitem,
            True,
        )

    for file_element in xml.iter("file"):
        item = element_to_dict(file_element)
        ident = item.get("ident")
        name = item.get("name")
        if not ident or not name:
            continue

        commands = [
            (
                _addon.getLocalizedString(30214),
                "Container.Update("
                + get_url(
                    action="search",
                    toqueue=ident,
                    what=what,
                    category=category,
                    sort=sort,
                    limit=limit,
                    offset=offset,
                )
                + ")",
            )
        ]
        listitem = tolistitem(item, commands)
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="play", ident=ident, name=name),
            listitem,
            False,
        )

    try:
        total = int(xml.findtext("total") or 0)
    except ValueError:
        total = 0

    if offset + limit < total:
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30207))
        listitem.setArt({"icon": "DefaultAddonsSearch.png"})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(
                action=action,
                what=what,
                category=category,
                sort=sort,
                limit=limit,
                offset=offset + limit,
            ),
            listitem,
            True,
        )


def search(params):
    xbmcplugin.setPluginCategory(
        _handle,
        f"{_addon.getAddonInfo('name')} \\ {_addon.getLocalizedString(30201)}",
    )
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    update_listing = False

    if params.get("remove"):
        removesearch(params["remove"])
        update_listing = True

    if params.get("toqueue"):
        toqueue(params["toqueue"], token)
        update_listing = True

    what = params.get("what")
    if "ask" in params:
        previous = _addon.getSetting("slast")
        if previous != what:
            what = ask(what or "")
            if what is not None:
                storesearch(what)
            else:
                update_listing = True

    if what is not None:
        if "offset" not in params:
            _addon.setSetting("slast", what)
        else:
            _addon.setSetting("slast", NONE_WHAT)
            update_listing = True

        category = params.get(
            "category",
            CATEGORIES[int(_addon.getSetting("scategory") or 1)],
        )
        sort = params.get("sort", SORTS[int(_addon.getSetting("ssort") or 0)])
        limit = int(params.get("limit", _addon.getSetting("slimit") or 25))
        offset = int(params.get("offset", 0))
        dosearch(token, what, category, sort, limit, offset, "search")
    else:
        _addon.setSetting("slast", NONE_WHAT)

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30205))
        listitem.setArt({"icon": "DefaultAddSource.png"})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="search", ask=1),
            listitem,
            True,
        )

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30208))
        listitem.setArt({"icon": "DefaultAddonsRecentlyUpdated.png"})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="search", what=NONE_WHAT, sort="recent"),
            listitem,
            True,
        )

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30209))
        listitem.setArt({"icon": "DefaultHardDisk.png"})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="search", what=NONE_WHAT, sort="largest"),
            listitem,
            True,
        )

        for search_term in loadsearch():
            listitem = xbmcgui.ListItem(label=search_term)
            listitem.setArt({"icon": "DefaultAddonsSearch.png"})
            listitem.addContextMenuItems(
                [
                    (
                        _addon.getLocalizedString(30213),
                        "Container.Update("
                        + get_url(action="search", remove=search_term)
                        + ")",
                    )
                ]
            )
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action="search", what=search_term, ask=1),
                listitem,
                True,
            )

    xbmcplugin.endOfDirectory(_handle, updateListing=update_listing)


def queue(params):
    xbmcplugin.setPluginCategory(
        _handle,
        f"{_addon.getAddonInfo('name')} \\ {_addon.getLocalizedString(30202)}",
    )
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    update_listing = False

    if params.get("dequeue"):
        try:
            _client.dequeue_file(token, params["dequeue"])
            popinfo(_addon.getLocalizedString(30106))
        except WebshareError as exc:
            handle_webshare_error(exc)
        update_listing = True

    try:
        xml = _client.queue(token)
    except WebshareError as exc:
        handle_webshare_error(exc)
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    for file_element in xml.iter("file"):
        item = element_to_dict(file_element)
        ident = item.get("ident")
        name = item.get("name")
        if not ident or not name:
            continue

        commands = [
            (
                _addon.getLocalizedString(30215),
                "Container.Update(" + get_url(action="queue", dequeue=ident) + ")",
            )
        ]
        listitem = tolistitem(item, commands)
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="play", ident=ident, name=name),
            listitem,
            False,
        )

    xbmcplugin.endOfDirectory(_handle, updateListing=update_listing)


def toqueue(ident, token):
    try:
        _client.queue_file(token, ident)
        popinfo(_addon.getLocalizedString(30105))
    except WebshareError as exc:
        handle_webshare_error(exc)


def history(params):
    xbmcplugin.setPluginCategory(
        _handle,
        f"{_addon.getAddonInfo('name')} \\ {_addon.getLocalizedString(30203)}",
    )
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    update_listing = False

    if params.get("remove"):
        try:
            history_xml = _client.history(token)
            download_ids = [
                file_element.findtext("download_id")
                for file_element in history_xml.iter("file")
                if file_element.findtext("ident") == params["remove"]
                and file_element.findtext("download_id")
            ]
            if download_ids:
                _client.clear_history(token, download_ids)
                popinfo(_addon.getLocalizedString(30104))
        except WebshareError as exc:
            handle_webshare_error(exc)
        update_listing = True

    if params.get("toqueue"):
        toqueue(params["toqueue"], token)
        update_listing = True

    try:
        xml = _client.history(token)
    except WebshareError as exc:
        handle_webshare_error(exc)
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    seen = set()
    for file_element in xml.iter("file"):
        item = element_to_dict(
            file_element,
            skip={"ended_at", "download_id", "started_at"},
        )
        ident = item.get("ident")
        name = item.get("name")
        if not ident or not name or ident in seen:
            continue
        seen.add(ident)

        commands = [
            (
                _addon.getLocalizedString(30213),
                "Container.Update(" + get_url(action="history", remove=ident) + ")",
            ),
            (
                _addon.getLocalizedString(30214),
                "Container.Update(" + get_url(action="history", toqueue=ident) + ")",
            ),
        ]
        listitem = tolistitem(item, commands)
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action="play", ident=ident, name=name),
            listitem,
            False,
        )

    xbmcplugin.endOfDirectory(_handle, updateListing=update_listing)


def settings(_params):
    _addon.openSettings()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


def infonize(data, key, process=str, showkey=True, prefix="", suffix="\n"):
    value = data.get(key)
    if value is None:
        return ""
    label = f"{key.capitalize()}: " if showkey else ""
    return prefix + label + process(value) + suffix


def fpsize(fps):
    value = round(float(fps), 3)
    return str(int(value)) if int(value) == value else str(value)


def getinfo(ident, token):
    try:
        return _client.file_info_with_removed_fallback(token, ident)
    except WebshareError as exc:
        handle_webshare_error(exc)
        return None


def info(params):
    token = revalidate()
    if not token:
        return

    xml = getinfo(params["ident"], token)
    if xml is None:
        return

    info_data = element_to_dict(xml)
    text = ""
    text += infonize(info_data, "name")
    text += infonize(info_data, "size", sizelize)
    text += infonize(info_data, "type")
    text += infonize(info_data, "width")
    text += infonize(info_data, "height")
    text += infonize(info_data, "format")
    text += infonize(info_data, "fps", fpsize)
    text += infonize(
        info_data,
        "bitrate",
        lambda x: sizelize(x, ("bps", "Kbps", "Mbps", "Gbps")),
    )

    video = info_data.get("video", {})
    streams = video.get("stream", []) if isinstance(video, dict) else []
    if isinstance(streams, dict):
        streams = [streams]
    for stream in streams:
        text += "Video stream: "
        text += infonize(stream, "width", showkey=False, suffix="")
        text += infonize(stream, "height", showkey=False, prefix="x", suffix="")
        text += infonize(stream, "format", showkey=False, prefix=", ", suffix="")
        text += infonize(stream, "fps", fpsize, showkey=False, prefix=", ", suffix="")
        text += "\n"

    audio = info_data.get("audio", {})
    streams = audio.get("stream", []) if isinstance(audio, dict) else []
    if isinstance(streams, dict):
        streams = [streams]
    for stream in streams:
        text += "Audio stream: "
        text += infonize(stream, "format", showkey=False, suffix="")
        text += infonize(stream, "channels", showkey=False, prefix=", ", suffix="")
        text += infonize(
            stream,
            "bitrate",
            lambda x: sizelize(x, ("bps", "Kbps", "Mbps", "Gbps")),
            showkey=False,
            prefix=", ",
            suffix="",
        )
        text += "\n"

    text += infonize(info_data, "removed", lambda value: "Yes" if value == "1" else "No")
    xbmcgui.Dialog().textviewer(_addon.getAddonInfo("name"), text)


def _device_uuid():
    value = _addon.getSetting("duuid")
    if not value:
        value = str(uuid.uuid4())
        _addon.setSetting("duuid", value)
    return value


def getlink(ident, token, download_type="video_stream"):
    try:
        return _client.file_link(
            token,
            ident,
            download_type=download_type,
            device_uuid=_device_uuid(),
        )
    except WebshareError as exc:
        handle_webshare_error(exc)
        return None


def play(params):
    token = revalidate()
    if not token:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    link = getlink(params["ident"], token)
    if not link:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    headers = urlencode(_client.media_headers(token))
    playback_url = f"{link}|{headers}" if headers else link
    listitem = xbmcgui.ListItem(
        label=params.get("name", ""),
        path=playback_url,
    )
    listitem.setProperty("mimetype", "application/octet-stream")
    xbmcplugin.setResolvedUrl(_handle, True, listitem)


def _join_vfs(path, filename):
    separator = "" if path.endswith(("/", "\\")) else "/"
    return f"{path}{separator}{filename}"


def _open_download_file(folder, filename):
    if os.path.isdir(folder):
        return io.open(os.path.join(folder, filename), "wb")
    return xbmcvfs.File(_join_vfs(folder, filename), "w")


def download(params):
    token = revalidate()
    if not token:
        return

    folder = _addon.getSetting("dfolder")
    if not folder or not xbmcvfs.exists(folder):
        popinfo(_addon.getLocalizedString(30108), sound=True)
        _addon.openSettings()
        return

    normalize = _addon.getSettingBool("dnormalize")
    notify = _addon.getSettingBool("dnotify")

    try:
        notify_every = int(re.sub(r"\D+", "", _addon.getSetting("dnevery") or "10"))
    except ValueError:
        notify_every = 10

    info_xml = getinfo(params["ident"], token)
    if info_xml is None:
        return

    filename = info_xml.findtext("name") or params.get("name") or params["ident"]
    if normalize:
        filename = unidecode.unidecode(filename)

    link = getlink(params["ident"], token, "file_download")
    if not link:
        return

    target = None
    response = None
    try:
        target = _open_download_file(folder, filename)
        response = _client.open_stream(link)
        total_text = response.headers.get("content-length")
        total = int(total_text) if total_text and total_text.isdigit() else None
        downloaded = 0
        last_notified = -1

        popinfo(_addon.getLocalizedString(30302) + filename)

        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            target.write(chunk)
            downloaded += len(chunk)

            if notify and total:
                percent = min(100, int(downloaded * 100 / total))
                if percent // notify_every > last_notified // notify_every:
                    popinfo(f"{percent}% - {filename}")
                    last_notified = percent

        popinfo(_addon.getLocalizedString(30303) + filename, sound=True)
    except (OSError, WebshareError, ValueError) as exc:
        log(f"Download failed: {exc}", xbmc.LOGERROR)
        popinfo(
            _addon.getLocalizedString(30304) + filename,
            icon=xbmcgui.NOTIFICATION_ERROR,
            sound=True,
        )
    finally:
        if response is not None:
            response.close()
        if target is not None:
            target.close()


def menu():
    if not revalidate():
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo("name"))

    items = [
        (30201, "search", "DefaultAddonsSearch.png", True),
        (30202, "queue", "DefaultPlaylist.png", True),
        (30203, "history", "DefaultAddonsUpdates.png", True),
        (30401, "series", "DefaultTVShows.png", True),
        (30204, "settings", "DefaultAddonService.png", False),
    ]

    for label_id, action, icon, is_folder in items:
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(label_id))
        listitem.setArt({"icon": icon})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action=action),
            listitem,
            is_folder,
        )

    xbmcplugin.endOfDirectory(_handle)


def series_menu(_params):
    manager = series_manager.SeriesManager(_addon, _profile, _client)
    series_manager.create_series_menu(manager, _handle)


def series_search(_params):
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    series_name = ask()
    if not series_name:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    manager = series_manager.SeriesManager(_addon, _profile, _client)
    progress = xbmcgui.DialogProgress()
    progress.create(
        _addon.getAddonInfo("name"),
        _addon.getLocalizedString(30405).format(series_name),
    )

    try:
        series_data = manager.search_series(series_name, token)
        if not series_data.get("seasons"):
            popinfo(
                _addon.getLocalizedString(30406),
                icon=xbmcgui.NOTIFICATION_WARNING,
            )
            xbmcplugin.endOfDirectory(_handle, succeeded=False)
            return

        episode_count = sum(
            len(season) for season in series_data["seasons"].values()
        )
        popinfo(
            _addon.getLocalizedString(30407).format(
                episode_count,
                len(series_data["seasons"]),
            )
        )
        xbmc.executebuiltin(
            f"Container.Update({get_url(action='series_detail', series_name=series_name)})"
        )
    except WebshareError as exc:
        handle_webshare_error(exc)
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
    finally:
        progress.close()


def series_detail(params):
    series_name = params["series_name"]
    xbmcplugin.setPluginCategory(
        _handle,
        f"{_addon.getAddonInfo('name')} \\ {series_name}",
    )
    manager = series_manager.SeriesManager(_addon, _profile, _client)
    series_manager.create_seasons_menu(manager, _handle, series_name)


def series_season(params):
    series_name = params["series_name"]
    season = params["season"]
    xbmcplugin.setPluginCategory(
        _handle,
        f"{_addon.getAddonInfo('name')} \\ {series_name} \\ "
        + _addon.getLocalizedString(30408).format(season),
    )
    manager = series_manager.SeriesManager(_addon, _profile, _client)
    series_manager.create_episodes_menu(manager, _handle, series_name, season)


def series_refresh(params):
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    series_name = params["series_name"]
    manager = series_manager.SeriesManager(_addon, _profile, _client)
    progress = xbmcgui.DialogProgress()
    progress.create(
        _addon.getAddonInfo("name"),
        _addon.getLocalizedString(30409).format(series_name),
    )

    try:
        series_data = manager.search_series(series_name, token)
        if not series_data.get("seasons"):
            popinfo(
                _addon.getLocalizedString(30406),
                icon=xbmcgui.NOTIFICATION_WARNING,
            )
            xbmcplugin.endOfDirectory(_handle, succeeded=False)
            return

        xbmc.executebuiltin(
            f"Container.Update({get_url(action='series_detail', series_name=series_name)})"
        )
    except WebshareError as exc:
        handle_webshare_error(exc)
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
    finally:
        progress.close()


ROUTES = {
    "search": search,
    "queue": queue,
    "history": history,
    "settings": settings,
    "info": info,
    "play": play,
    "download": download,
    "series": series_menu,
    "series_search": series_search,
    "series_detail": series_detail,
    "series_season": series_season,
    "series_refresh": series_refresh,
}


def router(paramstring):
    params = dict(parse_qsl(paramstring))
    action = params.get("action")

    if not action:
        menu()
        return

    handler = ROUTES.get(action)
    if handler is None:
        log(f"Unknown route: {action}", xbmc.LOGWARNING)
        menu()
        return

    try:
        handler(params)
    except WebshareApiError as exc:
        handle_webshare_error(exc)
    except Exception as exc:
        log(f"Unhandled error in route {action}: {exc}", xbmc.LOGERROR)
        traceback.print_exc()
        popinfo(
            _addon.getLocalizedString(30107),
            icon=xbmcgui.NOTIFICATION_ERROR,
        )