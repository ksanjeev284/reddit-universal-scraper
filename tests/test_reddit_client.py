import threading
import unittest
from unittest.mock import Mock, patch

import requests
import config
from scraper.reddit_client import RedditClient, RedditAPIError, api_url, normalize_target, retry_delay


def response(code=200, payload=None, headers=None):
    result = Mock(status_code=code, headers=headers or {})
    result.json.return_value = payload if payload is not None else {"data": {"children": [], "after": None}}
    return result


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch.multiple(config, USER_AGENT="python:test:2.0 (by /u/test)",
                                      REDDIT_CLIENT_ID="client", REDDIT_CLIENT_SECRET="secret",
                                      REDDIT_REFRESH_TOKEN="", REDDIT_ACCESS_TOKEN="",
                                      REDDIT_REQUESTS_PER_MINUTE=60)
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.session = Mock(headers={}, proxies={})
        self.client = RedditClient(session=self.session)
        self.client._wait = Mock()

    def test_token_cached_and_not_put_in_session_headers(self):
        self.session.request.side_effect = [response(payload={"access_token": "token", "expires_in": 3600}), response(), response()]
        self.client.get_json("https://old.reddit.com/r/python/new.json")
        self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        calls = self.session.request.call_args_list
        self.assertEqual([c.args[0] for c in calls], ["POST", "GET", "GET"])
        self.assertEqual(calls[1].args[1], "https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(calls[1].kwargs["headers"]["Authorization"], "Bearer token")
        self.assertNotIn("Authorization", self.session.headers)
        self.assertFalse(calls[1].kwargs["allow_redirects"])

    def test_refresh_token_grant(self):
        with patch.object(config, "REDDIT_REFRESH_TOKEN", "refresh"):
            self.session.request.side_effect = [response(payload={"access_token": "token"}), response()]
            self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.session.request.call_args_list[0].kwargs["data"],
                         {"grant_type": "refresh_token", "refresh_token": "refresh"})

    def test_401_renews_once(self):
        self.client.token = "old"
        self.client.expires_at = float("inf")
        self.session.request.side_effect = [response(401), response(payload={"access_token": "new"}), response()]
        self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.session.request.call_count, 3)
        self.assertEqual(self.session.request.call_args.kwargs["headers"]["Authorization"], "Bearer new")

    def test_persistent_401_stops(self):
        self.client.token, self.client.expires_at = "old", float("inf")
        self.session.request.side_effect = [response(401), response(payload={"access_token": "new"}), response(401)]
        with self.assertRaisesRegex(RedditAPIError, "rejected OAuth"):
            self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.session.request.call_count, 3)

    def test_403_is_not_retried_or_sent_to_mirrors(self):
        self.client.token, self.client.expires_at = "token", float("inf")
        self.session.request.return_value = response(403)
        with self.assertRaisesRegex(RedditAPIError, "denied access"):
            self.client.get_json("https://old.reddit.com/r/private/new.json")
        self.assertEqual(self.session.request.call_count, 1)

    def test_html_response_is_actionable(self):
        self.client.token, self.client.expires_at = "token", float("inf")
        result = response()
        result.json.side_effect = ValueError("html")
        self.session.request.return_value = result
        with self.assertRaisesRegex(RedditAPIError, "non-JSON"):
            self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        result.close.assert_called_once()

    def test_quota_headers_schedule_next_request(self):
        self.client.token, self.client.expires_at = "token", float("inf")
        self.session.request.return_value = response(headers={"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "120"})
        with patch("scraper.reddit_client.time.monotonic", return_value=10):
            self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.client.next_request, 130)

    def test_429_bounded_and_honors_server_wait(self):
        self.client.token, self.client.expires_at = "token", float("inf")
        self.session.request.return_value = response(429, headers={"Retry-After": "30"})
        with patch("scraper.reddit_client.time.monotonic", return_value=10):
            with self.assertRaisesRegex(RedditAPIError, "rate limit"):
                self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.session.request.call_count, 3)
        self.assertGreaterEqual(self.client.next_request, 40)

    def test_network_errors_are_bounded_and_sanitized(self):
        self.client.token, self.client.expires_at = "token", float("inf")
        self.session.request.side_effect = requests.ConnectionError("proxy-password")
        with self.assertRaises(RedditAPIError) as caught:
            self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertNotIn("proxy-password", str(caught.exception))
        self.assertEqual(self.session.request.call_count, 3)

    def test_wrong_host_rejected_before_credentials(self):
        for url in ("https://mirror.example/r/python/new.json", "https://oauth.reddit.com.evil/r/python",
                    "http://oauth.reddit.com/r/python", "https://user:pass@oauth.reddit.com/r/python"):
            with self.assertRaises(RedditAPIError):
                self.client.get_json(url)
        self.session.request.assert_not_called()

    def test_expired_token_renewed(self):
        self.client.token, self.client.expires_at = "expired", 0
        self.session.request.side_effect = [response(payload={"access_token": "fresh"}), response()]
        self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.assertEqual(self.client.token, "fresh")

    def test_concurrent_requests_share_single_authorization(self):
        self.session.request.side_effect = [response(payload={"access_token": "token"}), response(), response(), response()]
        errors = []
        def fetch():
            try:
                self.client.get_json("https://oauth.reddit.com/r/python/new.json")
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=fetch) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum(c.args[0] == "POST" for c in self.session.request.call_args_list), 1)

    def test_no_credentials_fails_before_network(self):
        with patch.object(config, "REDDIT_CLIENT_ID", ""):
            with self.assertRaisesRegex(RedditAPIError, "Approved"):
                self.client.get_json("https://oauth.reddit.com/r/python/new.json")
        self.session.request.assert_not_called()

    def test_retry_after_http_date(self):
        with patch("scraper.reddit_client.time.time", return_value=0):
            self.assertEqual(retry_delay({"Retry-After": "Thu, 01 Jan 1970 00:01:00 GMT"}, 2), 60)
        self.assertEqual(retry_delay({"Retry-After": "garbage", "X-Ratelimit-Reset": "nan"}, 2), 2)

    def test_target_validation(self):
        self.assertEqual(normalize_target("r/python"), "python")
        self.assertEqual(normalize_target("u/spez", True), "spez")
        for target in ("../outside", "https://reddit.com/r/python", "python?limit=1"):
            with self.assertRaises(ValueError):
                normalize_target(target)


if __name__ == "__main__":
    unittest.main()
