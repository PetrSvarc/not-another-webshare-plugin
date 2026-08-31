# License: AGPL-3.0

import unittest
from unittest.mock import Mock

import requests

from webshare_api import WebshareApiError, WebshareClient


def response(xml):
    result = Mock()
    result.content = xml.encode("utf-8")
    result.raise_for_status = Mock()
    return result


class WebshareTokenStateTests(unittest.TestCase):
    def setUp(self):
        self.session = requests.Session()
        self.session.post = Mock()
        self.client = WebshareClient(session=self.session, timeout=(1, 1))

    def test_empty_token_clears_session_cookie(self):
        self.client.set_token("stale-token")
        self.assertTrue(any(cookie.name == "wst" for cookie in self.session.cookies))

        self.client.set_token("")

        self.assertFalse(any(cookie.name == "wst" for cookie in self.session.cookies))

    def test_user_data_rejection_clears_session_cookie(self):
        self.session.post.return_value = response(
            "<response>"
            "<status>FATAL</status>"
            "<code>USER_DATA_FATAL_1</code>"
            "<message>Invalid token</message>"
            "</response>"
        )

        with self.assertRaises(WebshareApiError):
            self.client.user_data("stale-token")

        self.assertFalse(any(cookie.name == "wst" for cookie in self.session.cookies))


if __name__ == "__main__":
    unittest.main()
