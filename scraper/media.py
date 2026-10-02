"""Consistent media extraction for both scraper entry points."""
from html import unescape
from urllib.parse import urlsplit


def extract_media_urls(post):
    result = {"images": [], "videos": [], "galleries": []}
    url = post.get("url_overridden_by_dest") or post.get("url") or ""
    parsed = urlsplit(url)
    if parsed.hostname == "i.redd.it" or parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        result["images"].append(url)
    video = (post.get("secure_media") or post.get("media") or {}).get("reddit_video") or {}
    if video.get("fallback_url"):
        result["videos"].append(video["fallback_url"])
    for image in (post.get("preview") or {}).get("images", []):
        source = (image.get("source") or {}).get("url")
        if source:
            result["images"].append(source)
    metadata = post.get("media_metadata") or {}
    for item in (post.get("gallery_data") or {}).get("items", []):
        source = (metadata.get(item.get("media_id")) or {}).get("s") or {}
        source_url = source.get("u") or source.get("gif") or source.get("mp4")
        if source_url:
            bucket = "videos" if urlsplit(source_url).path.lower().endswith(".mp4") else "galleries"
            result[bucket].append(source_url)
    if parsed.hostname in ("youtube.com", "www.youtube.com", "youtu.be"):
        result["videos"].append(url)
    for parent in post.get("crosspost_parent_list") or []:
        # Parents are expanded only once to avoid cyclic/unbounded input.
        parent = dict(parent)
        parent.pop("crosspost_parent_list", None)
        for bucket, urls in extract_media_urls(parent).items():
            result[bucket].extend(urls)
    for bucket, urls in result.items():
        result[bucket] = list(dict.fromkeys(unescape(u) for u in urls if urlsplit(u).scheme in ("http", "https")))
    return result
