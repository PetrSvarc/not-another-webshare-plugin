# Not Another WebShare Plugin (NAWSP)

A Kodi video add-on for browsing, searching and playing content available through Webshare.cz.

This project is an independently maintained fork of **Yet Another Webshare Plugin (YAWSP)**. The initial codebase is based on the YAWSP 0.3.0 lineage by `cache-sk` with community/user extensions, including the series manager.

## Kodi add-on

- **Name:** Not Another WebShare Plugin
- **ID:** `plugin.video.nawsp`
- **Short name:** NAWSP
- **Current version:** 0.5.0
- **Kodi runtime:** Python 3 (`xbmc.python` 3.0.0+)
- **License:** GNU Affero General Public License v3.0

## Features

- Webshare account authentication
- Search and browsing
- Grouped movie/episode search results with ranked media versions
- Preferred language, quality and HEVC search ranking
- Video playback
- Queue and download history
- File downloads
- Series manager with season/episode detection
- Czech, Slovak and English UI strings

## Architecture

NAWSP separates Kodi UI concerns from Webshare communication and keeps filename parsing/ranking independently testable:

- `main.py` — Kodi entry point.
- `yawsp.py` — Kodi menus, routing, playback and download orchestration.
- `webshare_api.py` — Kodi-independent Webshare HTTP/XML client.
- `media_results.py` — Kodi-independent media filename parsing, conservative grouping and deterministic ranking.
- `search_results_ui.py` — Kodi grouped-search and versions-view integration.
- `series_manager.py` — series discovery, local series metadata and season/episode menus.
- `md5crypt.py` — historical password-digest helper retained from upstream.
- `tests/` — API-client and media parsing/ranking regression tests.

This separation makes Webshare request behavior and media matching/ranking testable without importing Kodi modules.

## Media grouping and ranking

Version 0.5.0 makes video search behave more like a media browser than a raw filename list:

- movie releases are conservatively grouped by normalized title and release year;
- TV releases are conservatively grouped by series, season and episode;
- ambiguous filenames remain normal individual search results;
- grouped items open a versions view with a deterministic **Best match** first;
- ranking can prefer Czech, Slovak or English, a target resolution and HEVC;
- password-protected files can optionally be hidden;
- original Webshare filename, size and context actions remain available.

## Webshare API modernization

Version 0.4.0 aligned the integration with the current Webshare API reference:

- login uses `username_or_email`, the salted password digest and `keep_logged_in`;
- queue removal uses the documented `ident` parameter;
- file links use `download_type`, `device_uuid` and HTTPS;
- network calls have explicit connect/read timeouts;
- malformed XML, HTTP failures and Webshare `FATAL` responses are handled separately;
- the obsolete Python 2 compatibility branches have been removed.

API reference: https://webshare.cz/apidoc/

The old experimental **Backup DB** code was removed. It downloaded and extracted a ZIP referenced by a hard-coded Webshare identifier, which is not appropriate for a production add-on.

## Development

The repository includes GitHub Actions validation. It:

1. compiles the Python sources;
2. runs the Kodi-independent unit tests on supported Python 3 versions;
3. validates the generated Kodi repository/package structure when distribution files change.

Run the tests locally with:

```bash
python -m pip install "requests>=2.31,<3"
python -m unittest discover -s tests -v
```

## Installation from the NAWSP repository

The Kodi repository is published at:

`https://petrsvarc.github.io/not-another-webshare-plugin/`

In Kodi:

1. Open **Settings → File manager → Add source**.
2. Enter `https://petrsvarc.github.io/not-another-webshare-plugin/` and name it `NAWSP`.
3. Open **Add-ons → Install from zip file → NAWSP** and install `repository.nawsp-1.0.0.zip`.
4. Open **Install from repository → NAWSP Repository → Video add-ons → Not Another WebShare Plugin**.
5. Install NAWSP. Future versions can then be delivered through Kodi's normal add-on update mechanism.

The repository add-on ID is `repository.nawsp`.

## Publishing releases

`scripts/build_kodi_repository.py` builds the static Kodi repository used by GitHub Pages. It creates:

- `addons.xml` and `addons.xml.md5`;
- `zips/plugin.video.nawsp/plugin.video.nawsp-X.Y.Z.zip`;
- `zips/repository.nawsp/repository.nawsp-X.Y.Z.zip`;
- a root-level repository ZIP used for the one-time Kodi File Manager bootstrap.

The `Publish Kodi repository` GitHub Actions workflow validates these artifacts and deploys them to GitHub Pages.

Normal releases are tag-driven:

1. update the version in `addon.xml`;
2. merge the release changes to `main`;
3. create a matching tag such as `v0.5.0`;
4. the workflow verifies that the tag matches the add-on version, builds the ZIPs and publishes the repository automatically.

The workflow can also be started explicitly with `workflow_dispatch`. Normal feature merges do not deploy a Kodi release, which prevents changed code from being republished under an existing version number.

## Configuration

Open the add-on settings in Kodi and enter your Webshare account credentials. This add-on does not provide or host content itself; it acts as a client for Webshare.

## Upstream and attribution

This fork derives from **Yet Another Webshare Plugin (YAWSP)**, originally authored by `cache-sk`, with later community/user extensions. Historical source metadata references `https://github.com/cache-sk/plugin.video.yawsp`; Kodi repository packaging is available at `https://github.com/lukyno999/yaws-repo`.

Original author and license headers are retained in the source files. Changes made for this fork are clearly marked.

## License

This project is distributed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**, matching the license declared by the actual YAWSP add-on source. See [LICENSE](LICENSE).

The bundled `md5crypt.py` also contains its own historical license/attribution notice, which is preserved in that file.

## Disclaimer

The add-on does not provide, host, or curate media content. It interfaces with Webshare.cz. Users are responsible for complying with applicable laws, service terms, and rights associated with content they access.
