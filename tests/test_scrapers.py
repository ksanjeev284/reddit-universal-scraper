import asyncio
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import config
import main
from scraper import async_scraper
from scraper.media import extract_media_urls
from scraper.reddit_client import RedditAPIError


def post(identifier="one", comments=0):
    return {"kind": "t3", "data": {"id": identifier, "title": identifier, "url": "https://example.com",
            "permalink": f"/r/python/comments/{identifier}/title/", "num_comments": comments}}


def page(items, after=None):
    return {"data": {"children": items, "after": after}}


class ScraperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous_cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.previous_cwd)
        directory_patch = patch.object(config, "DATA_DIR", Path(self.temp.name) / "data")
        directory_patch.start()
        self.addCleanup(directory_patch.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)
        self.client = Mock()
        self.client.session = contextlib.nullcontext()
        self.db = Mock()
        self.db.start_job_record.return_value = "testjob"
        for patcher in (patch.object(main, "get_api_client", return_value=self.client),
                        patch.object(async_scraper, "RedditClient", return_value=self.client),
                        patch.dict(sys.modules, {"export.database": self.db})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def sync(self, limit=10, dry_run=False, comments=False):
        return main.run_full_history("python", limit, download_media_flag=False,
                                     scrape_comments_flag=comments, dry_run=dry_run)

    def test_failed_first_page_records_failed_job(self):
        self.client.get_json.side_effect = RedditAPIError("denied access")
        result = self.sync()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["posts"], 0)
        self.assertEqual(self.db.complete_job_record.call_args.args[1], "failed")

    def test_later_failure_keeps_saved_posts(self):
        self.client.get_json.side_effect = [page([post()], "t3_one"), RedditAPIError("rate limit")]
        result = self.sync()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(pd.read_csv("data/r_python/posts.csv")), 1)

    def test_duplicate_page_cursor_cannot_loop_forever(self):
        self.client.get_json.return_value = page([post()], "t3_one")
        result = self.sync()
        self.assertEqual(self.client.get_json.call_count, 2)
        self.assertIn("cursor", result["error"])

    def test_limit_and_duplicate_ids_are_respected(self):
        self.client.get_json.return_value = page([post(), post(), post("two"), post("three")])
        result = self.sync(limit=2)
        self.assertEqual(result["posts"], 2)
        self.assertEqual(len(pd.read_csv("data/r_python/posts.csv")), 2)

    def test_dry_run_does_not_write_content_or_job(self):
        self.client.get_json.return_value = page([post()])
        self.assertEqual(self.sync(dry_run=True)["posts"], 1)
        self.assertFalse(Path("data").exists())
        self.db.start_job_record.assert_not_called()

    def test_comment_denial_is_reported_and_post_preserved(self):
        self.client.get_json.side_effect = [page([post(comments=1)]), RedditAPIError("comment denied")]
        result = self.sync(comments=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(pd.read_csv("data/r_python/posts.csv")), 1)

    def test_malformed_listing_does_not_look_like_empty_success(self):
        self.client.get_json.return_value = {"data": {"error": "wrong"}}
        self.assertEqual(self.sync()["status"], "failed")

    def test_async_failed_first_page(self):
        self.client.get_json.side_effect = RedditAPIError("denied")
        result = asyncio.run(async_scraper.scrape_async("python", download_media=False, scrape_comments=False))
        self.assertEqual(result["status"], "failed")

    def test_async_preserves_partial_results_and_stops_repeated_cursor(self):
        self.client.get_json.return_value = page([post()], "t3_one")
        result = asyncio.run(async_scraper.scrape_async("python", limit=10, download_media=False, scrape_comments=False))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.client.get_json.call_count, 2)
        self.assertEqual(len(pd.read_csv("data/r_python/posts.csv")), 1)

    def test_async_comment_error_does_not_disappear(self):
        self.client.get_json.side_effect = [page([post(comments=1)]), RedditAPIError("comments blocked")]
        result = asyncio.run(async_scraper.scrape_async("python", download_media=False))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["posts"], 1)

    def test_async_and_sync_comment_shapes_agree(self):
        comment = {"kind": "t1", "data": {"id": "c", "body": "text", "replies": ""}}
        self.assertEqual(main.parse_comments([comment], "/post/"), async_scraper.parse_comments_sync([comment], "/post/"))

    def test_media_crossposts_secure_video_and_duplicate_cleanup(self):
        media = extract_media_urls({"url": "https://i.redd.it/a.jpg",
                    "preview": {"images": [{"source": {"url": "https://i.redd.it/a.jpg"}}]},
                    "crosspost_parent_list": [{"secure_media": {"reddit_video": {"fallback_url": "https://v.redd.it/v/DASH_720.mp4?x=1&amp;y=2"}}}]})
        self.assertEqual(media["images"], ["https://i.redd.it/a.jpg"])
        self.assertEqual(media["videos"], ["https://v.redd.it/v/DASH_720.mp4?x=1&y=2"])


if __name__ == "__main__":
    unittest.main()
