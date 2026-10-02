"""Import the browser collector's portable format into the existing app stores."""
import csv
import json
import os
import re
import secrets
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import config
from export.storage_lock import data_write_lock

IMPORT_LOCK = threading.Lock()
MAX_IMPORT_BYTES = 20 * 1024 * 1024
POST_FIELDS = ["id", "title", "author", "created_utc", "permalink", "url", "score", "upvote_ratio",
               "num_comments", "num_crossposts", "selftext", "post_type", "is_nsfw", "is_spoiler", "flair",
               "total_awards", "has_media", "media_downloaded", "source"]
COMMENT_FIELDS = ["post_permalink", "comment_id", "parent_id", "author", "body", "score", "created_utc",
                  "depth", "is_submitter"]


def bridge_token():
    """Use a configured token or create a local pairing secret without changing .env."""
    configured = os.getenv("BROWSER_BRIDGE_TOKEN", "").strip()
    if configured:
        if len(configured) < 24:
            raise ValueError("BROWSER_BRIDGE_TOKEN must contain at least 24 characters.")
        return configured
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / ".browser_bridge_token"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        token = path.read_text(encoding="utf-8").strip()
        if len(token) < 24:
            raise ValueError("Local bridge token is invalid; configure BROWSER_BRIDGE_TOKEN.")
        return token
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        token = secrets.token_urlsafe(32)
        handle.write(token)
    return token


def _text(value, maximum=40000):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Invalid or oversized text field in browser export.")
    return value.replace("\x00", "")


def _number(value):
    if value is None or value == "":
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (-10**9 <= value <= 10**9):
        raise ValueError("Invalid numeric field in browser export.")
    return value


def _permalink(value):
    value = _text(value, 2000)
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.hostname not in ("www.reddit.com", "old.reddit.com", "reddit.com") or parsed.username:
            raise ValueError("Browser export contains a non-Reddit permalink.")
        value = parsed.path
    match = re.fullmatch(r"/r/([A-Za-z0-9_]{1,100})/comments/([A-Za-z0-9]+)/[^/?#]*(?:/[A-Za-z0-9]+)?/?", value)
    if not match:
        raise ValueError("Browser export contains an invalid post/comment permalink.")
    return value, match.group(1), match.group(2)


def _date(value):
    value = _text(value, 80)
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Browser export contains an invalid timestamp.") from None
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat()


def validate_bundle(bundle, maximum=10000):
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("Expected a browser collector JSON export with schema_version 1.")
    posts, comments = bundle.get("posts", []), bundle.get("comments", [])
    if not isinstance(posts, list) or not isinstance(comments, list) or len(posts) + len(comments) > maximum:
        raise ValueError(f"Import must contain at most {maximum} post/comment records.")
    normalized_posts, normalized_comments = {}, {}
    for item in posts:
        if not isinstance(item, dict):
            raise ValueError("Invalid browser post.")
        permalink, subreddit, identifier = _permalink(item.get("permalink"))
        if _text(item.get("id"), 80).removeprefix("t3_") != identifier:
            raise ValueError("Post ID and permalink do not match.")
        media = item.get("media_urls", [])
        if not isinstance(media, list) or len(media) > 50:
            raise ValueError("Invalid media link list.")
        media = [_text(url, 4000) for url in media]
        if any(urlsplit(url).scheme not in ("http", "https") for url in media):
            raise ValueError("Media links must use HTTP or HTTPS.")
        post_type = item.get("post_type", "link")
        if post_type not in ("text", "link", "image", "video", "gallery", "unknown"):
            raise ValueError("Invalid post type.")
        post = {field: "" for field in POST_FIELDS}
        post.update(id=identifier, subreddit=subreddit, permalink=permalink, title=_text(item.get("title"), 2000),
                    author=_text(item.get("author"), 100), created_utc=_date(item.get("created_utc")),
                    url=_text(item.get("url"), 4000), selftext=_text(item.get("selftext")),
                    post_type=post_type, source="Browser-Collector", media_urls=media,
                    has_media=bool(media), media_downloaded=False, is_nsfw=bool(item.get("is_nsfw")),
                    is_spoiler=bool(item.get("is_spoiler")), flair=_text(item.get("flair"), 1000))
        for field in ("score", "upvote_ratio", "num_comments", "num_crossposts", "total_awards"):
            post[field] = _number(item.get(field))
        normalized_posts[identifier] = post
    for item in comments:
        if not isinstance(item, dict):
            raise ValueError("Invalid browser comment.")
        permalink, subreddit, post_id = _permalink(item.get("post_permalink"))
        identifier = _text(item.get("comment_id"), 80).removeprefix("t1_")
        if not re.fullmatch(r"[A-Za-z0-9]+", identifier):
            raise ValueError("Invalid comment ID.")
        parent = _text(item.get("parent_id"), 80)
        if parent and not re.fullmatch(r"t[13]_[A-Za-z0-9]+", parent):
            raise ValueError("Invalid parent ID.")
        comment = {"comment_id": identifier, "post_id": post_id, "subreddit": subreddit,
                   "post_permalink": permalink, "parent_id": parent, "author": _text(item.get("author"), 100),
                   "body": _text(item.get("body")), "score": _number(item.get("score")),
                   "created_utc": _date(item.get("created_utc")), "depth": _number(item.get("depth")),
                   "is_submitter": bool(item.get("is_submitter"))}
        normalized_comments[identifier] = comment
    return list(normalized_posts.values()), list(normalized_comments.values())


def _merge_csv(path, incoming, fields, key):
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or fields
            rows = list(reader)
    seen = {row.get(key) for row in rows}
    for row in incoming:
        if row[key] not in seen:
            rows.append(row)
            seen.add(row[key])
    temporary = path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def import_bundle(bundle, maximum=10000):
    posts, comments = validate_bundle(bundle, maximum)
    from export.database import get_connection
    with IMPORT_LOCK, data_write_lock():
        connection = get_connection()
        added_posts = added_comments = 0
        try:
            with connection:
                for post in posts:
                    fields = ["subreddit"] + POST_FIELDS
                    cursor = connection.execute(f"INSERT OR IGNORE INTO posts ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                                                [post[field] for field in fields])
                    added_posts += cursor.rowcount
                for comment in comments:
                    fields = ["post_id"] + COMMENT_FIELDS
                    cursor = connection.execute(f"INSERT OR IGNORE INTO comments ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                                                [comment[field] for field in fields])
                    added_comments += cursor.rowcount
        finally:
            connection.close()
        grouped_posts, grouped_comments = defaultdict(list), defaultdict(list)
        for post in posts:
            grouped_posts[post["subreddit"]].append(post)
        for comment in comments:
            grouped_comments[comment["subreddit"]].append(comment)
        for subreddit in grouped_posts.keys() | grouped_comments.keys():
            directory = config.DATA_DIR / f"r_{subreddit}"
            directory.mkdir(parents=True, exist_ok=True)
            if grouped_posts[subreddit]:
                _merge_csv(directory / "posts.csv", grouped_posts[subreddit], POST_FIELDS, "id")
            if grouped_comments[subreddit]:
                _merge_csv(directory / "comments.csv", grouped_comments[subreddit], COMMENT_FIELDS, "comment_id")
        # Preserve media links in a sanitized portable snapshot (no session data).
        if added_posts or added_comments:
            directory = config.DATA_DIR / "browser-imports"
            directory.mkdir(parents=True, exist_ok=True)
            snapshot = {"schema_version": 1, "posts": posts, "comments": comments}
            (directory / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}.json").write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"posts_received": len(posts), "comments_received": len(comments), "posts_added": added_posts,
            "comments_added": added_comments, "duplicates": len(posts) + len(comments) - added_posts - added_comments}


def import_file(path):
    path = Path(path)
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ValueError("Browser export exceeds the 20 MB file import limit.")
    with path.open("r", encoding="utf-8") as handle:
        return import_bundle(json.load(handle))
