import copy
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from fastapi.testclient import TestClient

# The database module initializes on import; isolate that initialization too.
with tempfile.TemporaryDirectory() as initial_directory:
    with patch.multiple(config, DATA_DIR=Path(initial_directory), DB_PATH=Path(initial_directory) / "initial.db"):
        from export import database
        from export.browser_import import bridge_token, import_bundle, validate_bundle
        from api.server import app
database.DATA_DIR, database.DB_PATH = config.DATA_DIR, config.DB_PATH


def bundle():
    return {"schema_version": 1, "posts": [{"id": "abc123", "title": "Browser test", "author": "tester",
            "permalink": "/r/python/comments/abc123/browser_test/", "score": 42,
            "created_utc": "2026-10-02T08:00:00Z", "media_urls": ["https://i.redd.it/test.png"]}],
            "comments": [{"comment_id": "def456", "post_permalink": "/r/python/comments/abc123/browser_test/",
                          "body": "A test comment", "parent_id": "t3_abc123", "score": 2}]}


class BrowserImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for patcher in (patch.multiple(config, DATA_DIR=root, DB_PATH=root / "test.db"),
                        patch.multiple(database, DATA_DIR=root, DB_PATH=root / "test.db"),
                        patch.dict(os.environ, {"BROWSER_BRIDGE_TOKEN": "test-pairing-token-at-least-24-characters"})):
            patcher.start()
            self.addCleanup(patcher.stop)
        database.init_database()
        self.api = TestClient(app)
        self.addCleanup(self.api.close)
        self.auth = {"Authorization": "Bearer " + os.environ["BROWSER_BRIDGE_TOKEN"]}

    def test_import_updates_database_and_dashboard_csv(self):
        result = import_bundle(bundle())
        self.assertEqual((result["posts_added"], result["comments_added"]), (1, 1))
        self.assertEqual(database.search_posts(subreddit="python")[0]["title"], "Browser test")
        self.assertEqual(database.search_comments(post_id="abc123")[0]["body"], "A test comment")
        with (config.DATA_DIR / "r_python/posts.csv").open(encoding="utf-8", newline="") as handle:
            posts = list(csv.DictReader(handle))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["source"], "Browser-Collector")
        snapshots = list((config.DATA_DIR / "browser-imports").glob("*.json"))
        self.assertEqual(json.loads(snapshots[0].read_text(encoding="utf-8"))["posts"][0]["media_urls"], ["https://i.redd.it/test.png"])

    def test_repeat_import_is_idempotent(self):
        import_bundle(bundle())
        result = import_bundle(bundle())
        self.assertEqual(result["duplicates"], 2)
        self.assertEqual(result["posts_added"], 0)
        self.assertEqual(len(list((config.DATA_DIR / "browser-imports").glob("*.json"))), 1)

    def test_invalid_item_does_not_partially_write(self):
        data = bundle()
        data["comments"][0]["comment_id"] = "../outside"
        with self.assertRaises(ValueError):
            import_bundle(data)
        self.assertEqual(database.search_posts(), [])
        self.assertFalse((config.DATA_DIR / "r_python").exists())

    def test_path_traversal_and_external_urls_rejected(self):
        for permalink in ("/r/../comments/abc123/title/", "https://evil.test/r/python/comments/abc123/title/", "/r/python/comments/abc123/title/?secret=1"):
            data = bundle()
            data["posts"][0]["permalink"] = permalink
            with self.assertRaises(ValueError):
                validate_bundle(data)

    def test_wrong_post_id_is_rejected(self):
        data = bundle()
        data["posts"][0]["id"] = "different"
        with self.assertRaisesRegex(ValueError, "do not match"):
            validate_bundle(data)

    def test_secrets_are_not_retained_in_snapshots(self):
        data = bundle()
        data["cookies"] = "private-cookie"
        data["posts"][0]["access_token"] = "private-token"
        import_bundle(data)
        snapshot = next((config.DATA_DIR / "browser-imports").glob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn("private-cookie", snapshot)
        self.assertNotIn("private-token", snapshot)

    def test_bridge_requires_pairing_token(self):
        self.assertEqual(self.api.get("/bridge/status").status_code, 401)
        self.assertEqual(self.api.post("/bridge/import", json=bundle()).status_code, 401)
        self.assertEqual(self.api.get("/bridge/status", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.api.get("/bridge/status", headers=self.auth).status_code, 200)

    def test_bridge_import_and_deduplication(self):
        response = self.api.post("/bridge/import", json=bundle(), headers=self.auth)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["posts_added"], 1)
        response = self.api.post("/bridge/import", json=bundle(), headers=self.auth)
        self.assertEqual(response.json()["duplicates"], 2)

    def test_bridge_size_and_record_limits(self):
        response = self.api.post("/bridge/import", content=b"x" * (2 * 1024 * 1024 + 1), headers=self.auth)
        self.assertEqual(response.status_code, 413)
        data = bundle()
        data["posts"] = [copy.deepcopy(data["posts"][0]) for _ in range(501)]
        response = self.api.post("/bridge/import", json=data, headers=self.auth)
        self.assertEqual(response.status_code, 422)

    def test_invalid_json_is_rejected(self):
        response = self.api.post("/bridge/import", content=b"not JSON", headers=self.auth)
        self.assertEqual(response.status_code, 422)

    def test_scraper_writes_after_import_preserve_schema_and_skip_duplicates(self):
        import main
        import_bundle(bundle())
        path = config.DATA_DIR / "r_python/posts.csv"
        duplicate = main.extract_post_data({"id": "abc123", "permalink": "/r/python/comments/abc123/browser_test/", "title": "Duplicate"})
        new_post = main.extract_post_data({"id": "new123", "permalink": "/r/python/comments/new123/new/", "title": "New post"})
        with patch.object(main, "SEEN_URLS", set()):
            self.assertEqual(main.save_posts_csv([duplicate, new_post], path), 1)
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual([row["title"] for row in rows], ["Browser test", "New post"])
        self.assertTrue(all(None not in row for row in rows))
        comment_path = config.DATA_DIR / "r_python/comments.csv"
        main.save_comments_csv(bundle()["comments"], comment_path)
        with comment_path.open(encoding="utf-8", newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 1)

    def test_local_token_generated_once(self):
        with patch.dict(os.environ, {"BROWSER_BRIDGE_TOKEN": ""}):
            token = bridge_token()
            self.assertGreaterEqual(len(token), 24)
            self.assertEqual(bridge_token(), token)

    def test_proxy_support_keeps_generic_url_and_stable_targeting(self):
        generic = "http://user:pass@proxy.example:8080"
        self.assertEqual(config.get_formatted_proxy_url(generic), generic)
        proxy = "https://customer-demo-country-us-sessionid-my_session:p%40ss@datacenter.scrapingant.com:443"
        with patch.multiple(config, PROXY_COUNTRY="", PROXY_SESSION_ID=""):
            self.assertEqual(config.get_formatted_proxy_url(proxy), proxy)
            first = config.get_formatted_proxy_url(proxy, country="IN", session_id="stable")
            self.assertIn("customer-demo-country-in-sessionid-stable", first)
            self.assertEqual(first, config.get_formatted_proxy_url(proxy, country="IN", session_id="stable", force_rotate=True))


if __name__ == "__main__":
    unittest.main()
