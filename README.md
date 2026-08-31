# Not Another WebShare Plugin (NAWSP)

A Kodi video add-on for browsing, searching and playing content available through Webshare.cz.

This project is a renamed and independently maintained fork of **Yet Another Webshare Plugin (YAWSP)**. The initial codebase is based on the YAWSP 0.3.0 lineage by `cache-sk` with community/user extensions, including the series manager.

## Kodi add-on

- **Name:** Not Another WebShare Plugin
- **ID:** `plugin.video.nawsp`
- **Short name:** NAWSP
- **Base version:** 0.3.0
- **License:** GNU Affero General Public License v3.0

## Features

- Webshare account authentication
- Search and browsing
- Video playback
- Queue and download history
- File downloads
- Series manager with season/episode detection

## Installation

Clone or download this repository and package its contents so that `addon.xml` is at the root of the Kodi add-on ZIP. The installed add-on identity is `plugin.video.nawsp`.

## Configuration

Open the add-on settings in Kodi and enter your Webshare account credentials. This add-on does not provide or host content itself; it acts as a client for Webshare.

## Upstream and attribution

This fork derives from **Yet Another Webshare Plugin (YAWSP)**, originally authored by `cache-sk`, with later community/user extensions. Historical source metadata references `https://github.com/cache-sk/plugin.video.yawsp`; Kodi repository packaging is available at `https://github.com/lukyno999/yaws-repo`.

Original author and license headers are retained in the source files. Changes made for this fork include the NAWSP name, add-on ID, provider/source metadata, and branding references.

## License

This project is distributed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**, matching the license declared by the actual YAWSP add-on source. See [LICENSE](LICENSE).

The bundled `md5crypt.py` also contains its own historical license/attribution notice, which is preserved in that file.

## Disclaimer

The add-on does not provide, host, or curate media content. It interfaces with Webshare.cz. Users are responsible for complying with applicable laws, service terms, and rights associated with content they access.
