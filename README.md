# Not Another WebShare Plugin (NAWSP)

A Kodi video add-on for browsing, searching and playing content available through Webshare.cz.

This project is an independently maintained fork of **Yet Another Webshare Plugin (YAWSP)**. The initial codebase is based on the YAWSP 0.3.0 lineage by `cache-sk` with community/user extensions, including the series manager.

## Kodi add-on

- **Name:** Not Another WebShare Plugin
- **ID:** `plugin.video.nawsp`
- **Short name:** NAWSP
- **Current version:** 0.4.0
- **Kodi runtime:** Python 3 (`xbmc.python` 3.0.0+)
- **License:** GNU Affero General Public License v3.0

## Features

- Webshare account authentication
- Search and browsing
- Video playback
- Queue and download history
- File downloads
- Series manager with season/episode detection
- Czech, Slovak and English UI strings

## Architecture

The 0.4.0 refactor separates Kodi UI concerns from Webshare communication:

- `main.py` — Kodi entry point.
- `yawsp.py` — Kodi menus, routing, playback and download orchestration.
- `webshare_api.py` — Kodi-independent Webshare HTTP/XML client.
- `series_manager.py` — series discovery, local series metadata and season/episode menus.
- `md5crypt.py` — historical password-digest helper retained from upstream.
- `tests/test_webshare_api.py` — API-client regression tests.

This separation makes Webshare request behavior testable without importing Kodi modules.

## Webshare API modernization

Version 0.4.0 aligns the integration with the current Webshare API reference:

- login uses `username_or_email`, the salted password digest and `keep_logged_in`;
- queue removal uses the documented `ident` parameter;
- file links use `download_type`, `device_uuid` and HTTPS;
- network calls have explicit connect/read timeouts;
- malformed XML, HTTP failures and Webshare `FATAL` responses are handled separately;
- the obsolete Python 2 compatibility branches have been removed.

API reference: https://webshare.cz/apidoc/

The old experimental **Backup DB** code was removed. It downloaded and extracted a ZIP referenced by a hard-coded Webshare identifier, which is not appropriate for a production add-on.

## Development

The repository includes a GitHub Actions validation workflow. It:

1. compiles the Python sources;
2. runs the Kodi-independent `WebshareClient` unit tests on supported Python 3 versions.

Run the API tests locally with:

```bash
python -m pip install "requests>=2.31,<3"
python -m unittest discover -s tests -v
```

## Installation

Clone or download this repository and package its contents so that `addon.xml` is at the root of the Kodi add-on ZIP. The installed add-on identity is `plugin.video.nawsp`.

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
