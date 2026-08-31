# -*- coding: utf-8 -*-
# Webshare API client for Not Another WebShare Plugin (NAWSP).
# Based on the Webshare integration from YAWSP by cache-sk.
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html
# Modified for NAWSP, 2026-08-31.

from __future__ import annotations

import hashlib
from typing import Iterable, Optional
from xml.etree import ElementTree as ET

import requests

from md5crypt import md5crypt


BASE_URL = "https://webshare.cz"
API_URL = f"{BASE_URL}/api/"
DEFAULT_TIMEOUT = (10, 30)
USER_AGENT = (
    "Mozilla/5.0 (Kodi; NAWSP) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class WebshareError(RuntimeError):
    """Base exception for Webshare communication failures."""


class WebshareTransportError(WebshareError):
    """Network, HTTP, or malformed-response failure."""


class WebshareApiError(WebshareError):
    """A valid Webshare XML response with a non-OK status."""

    def __init__(self, endpoint: str, code: str, message: str):
        self.endpoint = endpoint
        self.code = code
        self.message = message
        super().__init__(f"{endpoint}: {code}: {message}")


class WebshareClient:
    """Small, Kodi-independent wrapper around the Webshare XML API."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout=DEFAULT_TIMEOUT,
    ):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Referer": BASE_URL,
                "Accept": "text/xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def set_token(self, token: str) -> None:
        if token:
            self.session.cookies.set("wst", token, domain="webshare.cz", path="/")

    def _post(self, endpoint: str, data: Optional[dict] = None) -> ET.Element:
        try:
            response = self.session.post(
                f"{API_URL}{endpoint}/",
                data=data or {},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise WebshareTransportError(
                f"Webshare request failed for {endpoint}: {exc}"
            ) from exc

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise WebshareTransportError(
                f"Webshare returned invalid XML for {endpoint}"
            ) from exc

        status = root.findtext("status")
        if status != "OK":
            raise WebshareApiError(
                endpoint=endpoint,
                code=root.findtext("code") or "UNKNOWN",
                message=root.findtext("message") or "Unknown Webshare API error",
            )

        return root

    @staticmethod
    def _auth(token: str, data: Optional[dict] = None) -> dict:
        payload = dict(data or {})
        if token:
            payload["wst"] = token
        return payload

    @staticmethod
    def _password_digest(password: str, salt: str) -> str:
        crypted = md5crypt(password.encode("utf-8"), salt.encode("utf-8"))
        return hashlib.sha1(crypted.encode("utf-8")).hexdigest()

    def login(self, username: str, password: str) -> str:
        salt_xml = self._post("salt", {"username_or_email": username})
        salt = salt_xml.findtext("salt")
        if not salt:
            raise WebshareTransportError("Webshare salt response did not contain a salt")

        login_xml = self._post(
            "login",
            {
                "username_or_email": username,
                "password": self._password_digest(password, salt),
                "keep_logged_in": 1,
            },
        )
        token = login_xml.findtext("token")
        if not token:
            raise WebshareTransportError("Webshare login response did not contain a token")

        self.set_token(token)
        return token

    def user_data(self, token: str) -> ET.Element:
        self.set_token(token)
        return self._post("user_data", self._auth(token))

    def search(
        self,
        token: str,
        what: str,
        category: str = "video",
        sort: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> ET.Element:
        return self._post(
            "search",
            self._auth(
                token,
                {
                    "what": what,
                    "category": category,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset,
                },
            ),
        )

    def queue(self, token: str) -> ET.Element:
        return self._post("queue", self._auth(token))

    def queue_file(self, token: str, ident: str) -> ET.Element:
        return self._post("queue_file", self._auth(token, {"ident": ident}))

    def dequeue_file(self, token: str, ident: str) -> ET.Element:
        return self._post("dequeue_file", self._auth(token, {"ident": ident}))

    def history(self, token: str, offset: int = 0, limit: int = 100) -> ET.Element:
        return self._post(
            "history",
            self._auth(token, {"offset": offset, "limit": limit}),
        )

    def clear_history(self, token: str, download_ids: Iterable[str]) -> ET.Element:
        return self._post(
            "clear_history",
            self._auth(token, {"ids[]": list(download_ids)}),
        )

    def file_info(
        self,
        token: str,
        ident: str,
        maybe_removed: bool = False,
    ) -> ET.Element:
        payload = {"ident": ident}
        if maybe_removed:
            payload["maybe_removed"] = 1
        return self._post("file_info", self._auth(token, payload))

    def file_info_with_removed_fallback(self, token: str, ident: str) -> ET.Element:
        try:
            return self.file_info(token, ident)
        except WebshareApiError:
            return self.file_info(token, ident, maybe_removed=True)

    def file_link(
        self,
        token: str,
        ident: str,
        download_type: str = "video_stream",
        device_uuid: Optional[str] = None,
    ) -> str:
        payload = {
            "ident": ident,
            "download_type": download_type,
            "force_https": 1,
        }
        if device_uuid:
            payload["device_uuid"] = device_uuid

        root = self._post("file_link", self._auth(token, payload))
        link = root.findtext("link")
        if not link:
            raise WebshareTransportError("Webshare file_link response did not contain a link")
        return link

    def media_headers(self, token: str) -> dict:
        headers = {
            "User-Agent": self.session.headers.get("User-Agent", USER_AGENT),
            "Referer": BASE_URL,
        }
        if token:
            headers["Cookie"] = f"wst={token}"
        return headers

    def open_stream(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise WebshareTransportError(f"Webshare media request failed: {exc}") from exc
