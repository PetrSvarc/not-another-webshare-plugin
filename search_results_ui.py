# -*- coding: utf-8 -*-
# Grouped search-result UI integration for NAWSP.
# License: AGPL-3.0

from __future__ import annotations

import xbmcgui
import xbmcplugin

from media_results import MediaPreferences, group_results
from webshare_api import WebshareError


LANGUAGE_PREFERENCES = ("", "CZ", "SK", "EN")
QUALITY_PREFERENCES = ("", "2160p", "1080p", "720p")


def _selected(values, raw_value):
    try:
        index = int(raw_value or 0)
    except (TypeError, ValueError):
        index = 0
    return values[index] if 0 <= index < len(values) else values[0]


def _preferences(app):
    return MediaPreferences(
        preferred_language=_selected(
            LANGUAGE_PREFERENCES,
            app._addon.getSetting("spreflang"),
        ),
        preferred_resolution=_selected(
            QUALITY_PREFERENCES,
            app._addon.getSetting("sprefquality"),
        ),
        prefer_hevc=app._addon.getSettingBool("spreferhevc"),
        hide_password_protected=app._addon.getSettingBool("shidepassword"),
    )


def _search_xml(app, token, what, category, sort, limit, offset):
    try:
        return app._client.search(
            token,
            "" if what == app.NONE_WHAT else what,
            category=category,
            sort=sort,
            limit=limit,
            offset=offset,
        )
    except WebshareError as exc:
        app.handle_webshare_error(exc)
        return None


def _search_items(app, xml):
    items = []
    for file_element in xml.iter("file"):
        item = app.element_to_dict(file_element)
        if item.get("ident") and item.get("name"):
            items.append(item)
    return items


def _queue_command(app, ident, action, what, category, sort, limit, offset, **extra):
    params = {
        "action": action,
        "toqueue": ident,
        "what": what,
        "category": category,
        "sort": sort,
        "limit": limit,
        "offset": offset,
    }
    params.update(extra)
    return (
        app._addon.getLocalizedString(30214),
        "Container.Update(" + app.get_url(**params) + ")",
    )


def _add_previous_page(app, what, category, sort, limit, offset, action):
    if offset <= 0:
        return

    listitem = xbmcgui.ListItem(label=app._addon.getLocalizedString(30206))
    listitem.setArt({"icon": "DefaultAddonsSearch.png"})
    xbmcplugin.addDirectoryItem(
        app._handle,
        app.get_url(
            action=action,
            what=what,
            category=category,
            sort=sort,
            limit=limit,
            offset=max(0, offset - limit),
        ),
        listitem,
        True,
    )


def _add_next_page(app, xml, what, category, sort, limit, offset, action):
    try:
        total = int(xml.findtext("total") or 0)
    except ValueError:
        total = 0

    if offset + limit >= total:
        return

    listitem = xbmcgui.ListItem(label=app._addon.getLocalizedString(30207))
    listitem.setArt({"icon": "DefaultAddonsSearch.png"})
    xbmcplugin.addDirectoryItem(
        app._handle,
        app.get_url(
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


def _add_single_result(app, item, queue_command=None, label=None, label2=None):
    commands = [queue_command] if queue_command else []
    if label is None:
        listitem = app.tolistitem(item, commands)
    else:
        listitem = xbmcgui.ListItem(label=label)
        if label2 and hasattr(listitem, "setLabel2"):
            listitem.setLabel2(label2)
        if item.get("img"):
            listitem.setArt({"thumb": item["img"]})
        listitem.setInfo("video", {"title": item.get("name", label)})
        listitem.setProperty("IsPlayable", "true")

        ident = item.get("ident")
        context = []
        if ident:
            context.extend(
                [
                    (
                        app._addon.getLocalizedString(30211),
                        f"RunPlugin({app.get_url(action='info', ident=ident)})",
                    ),
                    (
                        app._addon.getLocalizedString(30212),
                        f"RunPlugin({app.get_url(action='download', ident=ident)})",
                    ),
                ]
            )
        if queue_command:
            context.append(queue_command)
        if context:
            listitem.addContextMenuItems(context)

    xbmcplugin.addDirectoryItem(
        app._handle,
        app.get_url(
            action="play",
            ident=item["ident"],
            name=item["name"],
        ),
        listitem,
        False,
    )


def _group_label(app, group):
    template = app._addon.getLocalizedString(30501) or "{} — {} versions"
    return template.format(group.best.media.display_title, len(group.versions))


def _add_group_result(app, group, what, category, sort, limit, offset):
    best_item = group.best.item
    listitem = xbmcgui.ListItem(label=_group_label(app, group))
    if best_item.get("img"):
        listitem.setArt({"thumb": best_item["img"]})
    listitem.setInfo("video", {"title": group.best.media.display_title})
    listitem.setProperty("IsPlayable", "false")

    xbmcplugin.addDirectoryItem(
        app._handle,
        app.get_url(
            action="versions",
            group=group.key,
            what=what,
            category=category,
            sort=sort,
            limit=limit,
            offset=offset,
        ),
        listitem,
        True,
    )


def dosearch(app, token, what, category, sort, limit, offset, action):
    xml = _search_xml(app, token, what, category, sort, limit, offset)
    if xml is None:
        return

    _add_previous_page(app, what, category, sort, limit, offset, action)
    items = _search_items(app, xml)

    # Group only explicit video searches. "Everything" can contain non-video files
    # whose names happen to look like releases, so grouping them would be unsafe.
    if category == "video":
        result_groups = group_results(items, _preferences(app))
    else:
        result_groups = group_results(items, MediaPreferences())
        result_groups = [group for group in result_groups for _ in (0,)]
        # Force non-video categories back to individual rows.
        result_groups = [
            type(group)(key=None, versions=[version])
            for group in result_groups
            for version in group.versions
        ]

    for group in result_groups:
        if group.grouped:
            _add_group_result(app, group, what, category, sort, limit, offset)
            continue

        item = group.best.item
        queue_command = _queue_command(
            app,
            item["ident"],
            action,
            what,
            category,
            sort,
            limit,
            offset,
        )
        _add_single_result(app, item, queue_command=queue_command)

    _add_next_page(app, xml, what, category, sort, limit, offset, action)


def _version_label(app, version, is_best):
    parts = [
        value
        for value in (
            version.media.resolution,
            version.media.language,
            version.media.codec,
        )
        if value
    ]
    size = version.item.get("size")
    if size:
        parts.append(app.sizelize(size))
    details = " · ".join(parts) or version.item.get("name", "?")
    if is_best:
        prefix = app._addon.getLocalizedString(30502) or "Best match"
        return f"{prefix} — {details}"
    return details


def versions(app, params):
    token = app.revalidate()
    if not token:
        xbmcplugin.endOfDirectory(app._handle, succeeded=False)
        return

    what = params.get("what", app.NONE_WHAT)
    category = params.get("category", "video")
    sort = params.get("sort", "")
    try:
        limit = int(params.get("limit", app._addon.getSetting("slimit") or 25))
        offset = int(params.get("offset", 0))
    except ValueError:
        limit = int(app._addon.getSetting("slimit") or 25)
        offset = 0

    if params.get("toqueue"):
        app.toqueue(params["toqueue"], token)

    xml = _search_xml(app, token, what, category, sort, limit, offset)
    if xml is None:
        xbmcplugin.endOfDirectory(app._handle, succeeded=False)
        return

    target_key = params.get("group")
    groups = group_results(_search_items(app, xml), _preferences(app))
    group = next((candidate for candidate in groups if candidate.key == target_key), None)
    if group is None:
        xbmcplugin.endOfDirectory(app._handle, succeeded=False)
        return

    xbmcplugin.setPluginCategory(
        app._handle,
        f"{app._addon.getAddonInfo('name')} \\ {group.best.media.display_title}",
    )

    for index, version in enumerate(group.versions):
        item = version.item
        queue_command = _queue_command(
            app,
            item["ident"],
            "versions",
            what,
            category,
            sort,
            limit,
            offset,
            group=target_key,
        )
        _add_single_result(
            app,
            item,
            queue_command=queue_command,
            label=_version_label(app, version, index == 0),
            label2=item.get("name"),
        )

    xbmcplugin.endOfDirectory(app._handle, updateListing=bool(params.get("toqueue")))


def install(app):
    """Install grouped-search rendering into the existing NAWSP router."""

    app.dosearch = lambda token, what, category, sort, limit, offset, action: dosearch(
        app,
        token,
        what,
        category,
        sort,
        limit,
        offset,
        action,
    )
    app.ROUTES["versions"] = lambda params: versions(app, params)
