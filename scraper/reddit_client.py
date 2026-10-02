"""Approved Reddit Data API access, shared by sync and async entry points."""
import math
import re
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import requests
import config


class RedditAPIError(RuntimeError):
    """An actionable API failure (without credentials or response content)."""


def normalize_target(target, is_user=False):
    target = target.strip()
    prefix = "u/" if is_user else "r/"
    if target.lower().startswith(prefix):
        target = target[2:]
    if not re.fullmatch(r"[A-Za-z0-9_+-]{1,100}", target):
        raise ValueError("Enter a subreddit/user name, without URLs or path separators.")
    if is_user and "+" in target:
        raise ValueError("Only one username can be requested at a time.")
    return target


def api_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "oauth.reddit.com", "www.reddit.com", "old.reddit.com", "reddit.com"
    } or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise RedditAPIError("Reddit API requests must use an official HTTPS Reddit host.")
    return urlunsplit(("https", "oauth.reddit.com", parsed.path, parsed.query, ""))


def retry_delay(headers, fallback):
    """Honor both seconds and HTTP-date Retry-After, and Reddit reset headers."""
    delays = [float(fallback)]
    for key in ("Retry-After", "X-Ratelimit-Reset"):
        value = headers.get(key)
        if value is None:
            continue
        try:
            delay = float(value)
        except (TypeError, ValueError):
            try:
                delay = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                continue
        if math.isfinite(delay):
            delays.append(max(0, delay))
    return max(delays)


def comments_url(permalink):
    if permalink.startswith("/"):
        permalink = config.REDDIT_API_BASE + permalink
    parsed = urlsplit(api_url(permalink))
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path += ".json"
    return urlunsplit(("https", "oauth.reddit.com", path, "limit=100&raw_json=1", ""))


def comment_children(data):
    if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], dict):
        raise RedditAPIError("Unexpected Reddit comment response.")
    children = (data[1].get("data") or {}).get("children")
    if not isinstance(children, list):
        raise RedditAPIError("Unexpected Reddit comment response.")
    return children


class RedditClient:
    def __init__(self, proxy=None, session=None):
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
        if proxy and proxy.lower() not in ("none", "direct", "disabled"):
            self.session.proxies.update({"http": proxy, "https": proxy})
        self.token = config.REDDIT_ACCESS_TOKEN
        self.expires_at = float("inf") if self.token else 0
        self.next_request = 0
        self.lock = threading.Lock()

    def validate(self):
        if not config.USER_AGENT.strip() or config.USER_AGENT.startswith("Mozilla/"):
            raise RedditAPIError("Set REDDIT_USER_AGENT to a descriptive app/version and Reddit username in .env.")
        if not self.token and not config.REDDIT_CLIENT_ID:
            raise RedditAPIError("Approved Reddit API access is required. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET "
                                 "(or REDDIT_ACCESS_TOKEN) in .env. See docs/reddit-access.md.")

    def _wait(self):
        delay = self.next_request - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def _request(self, method, url, retries=3, **kwargs):
        for attempt in range(max(1, retries)):
            self._wait()
            try:
                response = self.session.request(method, url, timeout=config.REQUEST_TIMEOUT,
                                                allow_redirects=False, **kwargs)
            except requests.RequestException:
                if attempt + 1 >= max(1, retries):
                    raise RedditAPIError("Reddit API connection failed after bounded retries; check network/proxy connectivity.") from None
                self.next_request = time.monotonic() + 2 ** (attempt + 1)
                continue
            self.next_request = time.monotonic() + 60 / config.REDDIT_REQUESTS_PER_MINUTE
            try:
                if float(response.headers.get("X-Ratelimit-Remaining", "1")) < 1:
                    self.next_request = time.monotonic() + retry_delay(response.headers, 1)
            except (TypeError, ValueError):
                pass
            if response.status_code == 429 or response.status_code in (500, 502, 503, 504):
                delay = retry_delay(response.headers, 2 ** (attempt + 1))
                self.next_request = max(self.next_request, time.monotonic() + delay)
                response.close()
                if attempt + 1 >= max(1, retries):
                    raise RedditAPIError("Reddit API rate limit/transient failure persists; retry later.")
                continue
            return response
        raise RedditAPIError("Reddit API retries exhausted.")

    @staticmethod
    def _check(response):
        code = response.status_code
        if code == 401:
            raise RedditAPIError("Reddit rejected OAuth credentials/token. Check credentials and approved app access.")
        if code == 403:
            raise RedditAPIError("Reddit denied access (403). Check app approval, scopes and community/content restrictions.")
        if code == 404:
            raise RedditAPIError("Reddit resource is unavailable (404); check the subreddit/user name or content availability.")
        if code != 200:
            raise RedditAPIError(f"Reddit API returned HTTP {code}.")
        try:
            payload = response.json()
        except ValueError:
            raise RedditAPIError("Reddit returned non-JSON content; access may be blocked. No mirror fallback is attempted.") from None
        if isinstance(payload, dict) and payload.get("error"):
            raise RedditAPIError("Reddit returned an API error; check access and request parameters.")
        return payload

    def _authorize(self):
        if self.token and time.monotonic() < self.expires_at:
            return
        if not config.REDDIT_CLIENT_ID:
            raise RedditAPIError("Access token expired/revoked; provide a new token or client credentials.")
        data = {"grant_type": "client_credentials"}
        if config.REDDIT_REFRESH_TOKEN:
            data = {"grant_type": "refresh_token", "refresh_token": config.REDDIT_REFRESH_TOKEN}
        response = self._request("POST", "https://www.reddit.com/api/v1/access_token",
                                 auth=(config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET), data=data)
        try:
            payload = self._check(response)
            if not isinstance(payload, dict) or not payload.get("access_token"):
                raise RedditAPIError("Reddit did not issue an OAuth token; check app approval and grant configuration.")
            self.token = payload["access_token"]
            try:
                lifetime = float(payload.get("expires_in", 3600))
            except (TypeError, ValueError):
                raise RedditAPIError("Reddit returned an invalid token expiry.") from None
            if not math.isfinite(lifetime) or lifetime <= 0:
                raise RedditAPIError("Reddit returned an invalid token expiry.")
            self.expires_at = time.monotonic() + max(1, lifetime - 30)
        finally:
            response.close()

    def get(self, url, retries=3):
        url = api_url(url)  # Validate before acquiring or sending any credentials.
        self.validate()
        with self.lock:
            self._authorize()
            for refresh in range(2):
                response = self._request("GET", url, retries=retries,
                                         headers={"Authorization": f"Bearer {self.token}"})
                if response.status_code == 401 and refresh == 0 and config.REDDIT_CLIENT_ID:
                    response.close()
                    self.token = ""
                    self.expires_at = 0
                    self._authorize()
                    continue
                try:
                    self._check(response)
                except RedditAPIError:
                    response.close()
                    raise
                return response
        raise RedditAPIError("OAuth refresh failed.")

    def get_json(self, url, retries=3):
        response = self.get(url, retries)
        try:
            return response.json()
        finally:
            response.close()

    def close(self):
        self.session.close()


def listing_children(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict) or not isinstance(data["data"].get("children"), list):
        raise RedditAPIError("Unexpected Reddit listing response; no data was silently discarded.")
    children = data["data"]["children"]
    if any(not isinstance(item, dict) or not isinstance(item.get("data"), dict) for item in children):
        raise RedditAPIError("Unexpected Reddit listing item.")
    return [item for item in children if item.get("kind") == "t3"]
