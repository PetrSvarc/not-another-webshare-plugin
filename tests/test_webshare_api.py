# License: AGPL-3.0

import unittest
from unittest.mock import Mock

import requests

from webshare_api import (
    WebshareApiError,
    WebshareClient,
    WebshareTransportError,
)


def response(xml, status_code=200):
    result = Mock()
    result.content = xml.encode("utf-8")
    result.status_code = status_code
    result.raise_for_status = Mock()
    return result


class WebshareClientTests(unittest.TestCase):
    def setUp(self):
        self.session = requests.Session()
        self.session.post = Mock()
        self.client = WebshareClient(session=self.session, timeout=(1, 1))

    def test_login_uses_current_documented_payload(self):
        self.session.post.side_effect = [
            response("<response><status>OK</status><salt>12345678</salt></response>"),
            response("<response><status>OK</status><token>token-1</token></response>"),
        ]

        token = self.client.login("demo", "secret")

        self.assertEqual("token-1", token)
        login_payload = self.session.post.call_args_list[1].kwargs["data"]
        self.assertEqual("demo", login_payload["username_or_email"])
        self.assertEqual(1, login_payload["keep_logged_in"])
        self.assertIn("password", login_payload)
        self.assertNotIn("digest", login_payload)

    def test_api_error_is_exposed_with_code_and_message(self):
        self.session.post.return_value = response(
            "<response>"
            "<status>FATAL</status>"
            "<code>SEARCH_FATAL_1</code>"
            "<message>Bad search</message>"
            "</response>"
        )

        with self.assertRaises(WebshareApiError) as caught:
            self.client.search("token", "query")

        self.assertEqual("SEARCH_FATAL_1", caught.exception.code)
        self.assertEqual("Bad search", caught.exception.message)

    def test_invalid_xml_becomes_transport_error(self):
        self.session.post.return_value = response("<not-closed>")

        with self.assertRaises(WebshareTransportError):
            self.client.queue("token")

    def test_dequeue_sends_only_ident_plus_authentication(self):
        self.session.post.return_value = response(
            "<response><status>OK</status></response>"
        )

        self.client.dequeue_file("token", "ABC")

        payload = self.session.post.call_args.kwargs["data"]
        self.assertEqual({"ident": "ABC", "wst": "token"}, payload)

    def test_file_link_requests_https_and_device_uuid(self):
        self.session.post.return_value = response(
            "<response><status>OK</status><link>https://cdn.example/video</link></response>"
        )

        link = self.client.file_link(
            "token",
            "ABC",
            download_type="video_stream",
            device_uuid="device-1",
        )

        self.assertEqual("https://cdn.example/video", link)
        payload = self.session.post.call_args.kwargs["data"]
        self.assertEqual("ABC", payload["ident"])
        self.assertEqual("video_stream", payload["download_type"])
        self.assertEqual("device-1", payload["device_uuid"])
        self.assertEqual(1, payload["force_https"])

    def test_search_does_not_send_legacy_maybe_removed_parameter(self):
        self.session.post.return_value = response(
            "<response><status>OK</status><total>0</total></response>"
        )

        self.client.search("token", "query", category="video")

        payload = self.session.post.call_args.kwargs["data"]
        self.assertNotIn("maybe_removed", payload)


if __name__ == "__main__":
    unittest.main()
