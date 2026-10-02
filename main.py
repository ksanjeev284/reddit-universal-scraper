"""
🤖 Universal Reddit Scraper Suite
Full-featured scraper with analytics, dashboard, notifications, and scheduling.
"""
import requests
import pandas as pd
import datetime
import time
import os
import argparse
import sys
import subprocess
import tempfile
from urllib.parse import urlparse
from pathlib import Path


# Prevent Unicode encoding issues in Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from config import USER_AGENT, REDDIT_API_BASE, PROXY_URL, MAX_COMMENT_DEPTH, get_formatted_proxy_url
from scraper.reddit_client import RedditClient, RedditAPIError, normalize_target, listing_children, comments_url, comment_children, retry_delay
from scraper.media import extract_media_urls
from export.storage_lock import locked_storage

PROXY_TO_USE = PROXY_URL
API_CLIENT = None


def get_api_client():
    global API_CLIENT
    if API_CLIENT is None:
        API_CLIENT = RedditClient(proxy=get_formatted_proxy_url(PROXY_TO_USE))
    return API_CLIENT


def rotate_session_proxy(country=None, session_id=None, force_rotate=False):
    """Retain a stable optional network proxy without changing process environment."""
    SESSION.proxies = {}
    if PROXY_TO_USE and PROXY_TO_USE.lower() not in ("none", "direct", "disabled"):
        proxy = get_formatted_proxy_url(PROXY_TO_USE)
        SESSION.proxies.update({"http": proxy, "https": proxy})

SEEN_URLS = set()
SESSION = requests.Session()
SESSION.trust_env = False
SESSION.headers.update({"User-Agent": USER_AGENT or "reddit-universal-scraper/2.0", "Accept": "*/*"})


def request_with_retry(url, retries=3, backoff=2, warmup_url=None, **kwargs):
    """API requests use OAuth; media requests never receive bearer tokens."""
    if urlparse(url).hostname in ("reddit.com", "www.reddit.com", "old.reddit.com", "oauth.reddit.com"):
        return get_api_client().get(url, retries=retries)
    rotate_session_proxy()
    for attempt in range(max(1, retries)):
        try:
            response = SESSION.get(url, **kwargs)
            if response.status_code == 200:
                return response
            code = response.status_code
            response.close()
            if code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Media server returned HTTP {code}")
            if attempt + 1 == max(1, retries):
                raise RuntimeError("Media retries exhausted")
        except requests.RequestException:
            if attempt + 1 == max(1, retries):
                raise RuntimeError("Media connection failed") from None
        time.sleep(backoff * 2 ** attempt)

# --- DIRECTORY SETUP ---
def setup_directories(target, prefix):
    """Creates organized folder structure for scraped data."""
    base_dir = f"data/{prefix}_{target}"
    dirs = {
        "base": base_dir,
        "posts": f"{base_dir}/posts.csv",
        "comments": f"{base_dir}/comments.csv",
        "media": f"{base_dir}/media",
        "images": f"{base_dir}/media/images",
        "videos": f"{base_dir}/media/videos",
    }

    for key in ["base", "media", "images", "videos"]:
        if not os.path.exists(dirs[key]):
            os.makedirs(dirs[key])

    return dirs

def get_file_path(target, type_prefix):
    """Legacy function for backward compatibility."""
    if not os.path.exists("data"):
        os.makedirs("data")
    sanitized_target = target.replace("/", "_")
    return f"data/{type_prefix}_{sanitized_target}.csv"

def load_history(filepath):
    """Loads existing CSV history to prevent duplicates."""
    SEEN_URLS.clear()
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            for url in df['permalink']:
                SEEN_URLS.add(str(url))
            print(f"📚 Loaded {len(SEEN_URLS)} existing items from {filepath}")
        except:
            pass

@locked_storage
def save_posts_csv(posts, filepath):
    """Saves posts to CSV with all metadata."""
    if not posts:
        return 0

    # A browser import may have written new records since history was loaded.
    known_urls = set(SEEN_URLS)
    if os.path.exists(filepath):
        known_urls.update(pd.read_csv(filepath, usecols=['permalink'])['permalink'].astype(str))
    SEEN_URLS.update(known_urls)
    new_posts = [p for p in posts if p['permalink'] not in known_urls]

    if new_posts:
        df = pd.DataFrame(new_posts)
        if os.path.exists(filepath):
            df = df.reindex(columns=pd.read_csv(filepath, nrows=0).columns)
            df.to_csv(filepath, mode='a', header=False, index=False)
        else:
            df.to_csv(filepath, index=False)

        for p in new_posts:
            SEEN_URLS.add(p['permalink'])

        print(f"✅ Saved {len(new_posts)} new posts")
        return len(new_posts)
    else:
        print("💤 No new unique posts found.")
        return 0

@locked_storage
def save_comments_csv(comments, filepath):
    """Saves comments to CSV."""
    if not comments:
        return

    df = pd.DataFrame(comments)
    df = df.drop_duplicates(subset=['comment_id'])
    if os.path.exists(filepath):
        known_ids = set(pd.read_csv(filepath, usecols=['comment_id'])['comment_id'].astype(str))
        df = df[~df['comment_id'].astype(str).isin(known_ids)]
        if df.empty:
            return
        df = df.reindex(columns=pd.read_csv(filepath, nrows=0).columns)
        df.to_csv(filepath, mode='a', header=False, index=False)
    else:
        df.to_csv(filepath, index=False)

    print(f"💬 Saved {len(df)} comments")

# --- MEDIA DOWNLOAD ---
def get_media_urls(post_data):
    return extract_media_urls(post_data)


def download_media(url, save_path, media_type="image"):
    """Downloads a single media file."""
    try:
        if os.path.exists(save_path):
            return True

        response = request_with_retry(url, timeout=30, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
        pass
    return False

def download_reddit_video_with_audio(video_url, save_path):
    """
    Downloads Reddit video with audio by fetching both streams and merging.
    Reddit stores video and audio separately - this combines them.
    """
    try:
        if os.path.exists(save_path):
            return True

        # Try to find the audio URL by replacing video quality with audio
        # Reddit videos have audio at URLs like .../DASH_audio.mp4 or .../DASH_AUDIO_128.mp4
        base_url = video_url.rsplit('/', 1)[0]

        # Common audio URL patterns
        audio_urls = [
            f"{base_url}/DASH_audio.mp4",
            f"{base_url}/DASH_AUDIO_128.mp4",
            f"{base_url}/DASH_AUDIO_64.mp4",
            f"{base_url}/audio.mp4",
            f"{base_url}/audio"
        ]

        # Download video to temp file first
        with tempfile.NamedTemporaryFile(suffix='_video.mp4', delete=False) as video_temp:
            video_temp_path = video_temp.name
            response = request_with_retry(video_url, timeout=60, stream=True)
            if response.status_code != 200:
                return False
            for chunk in response.iter_content(chunk_size=8192):
                video_temp.write(chunk)

        # Try to download audio
        audio_temp_path = None
        for audio_url in audio_urls:
            try:
                response = request_with_retry(audio_url, timeout=30, stream=True)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(suffix='_audio.mp4', delete=False) as audio_temp:
                        audio_temp_path = audio_temp.name
                        for chunk in response.iter_content(chunk_size=8192):
                            audio_temp.write(chunk)
                    break
            except:
                continue

        if audio_temp_path:
            # Merge video and audio using ffmpeg
            try:
                cmd = [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', video_temp_path,
                    '-i', audio_temp_path,
                    '-c:v', 'copy', '-c:a', 'aac',
                    '-shortest', save_path
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=120)

                if result.returncode == 0:
                    # Cleanup temp files
                    os.unlink(video_temp_path)
                    os.unlink(audio_temp_path)
                    return True
                else:
                    # ffmpeg failed, fall back to video only
                    print(f"   ⚠️ ffmpeg merge failed, saving video without audio")
                    os.rename(video_temp_path, save_path)
                    os.unlink(audio_temp_path)
                    return True
            except FileNotFoundError:
                # ffmpeg not installed, save video only
                print(f"   ⚠️ ffmpeg not found, saving video without audio")
                os.rename(video_temp_path, save_path)
                if audio_temp_path:
                    os.unlink(audio_temp_path)
                return True
            except Exception as e:
                # Other error, save video only
                os.rename(video_temp_path, save_path)
                if audio_temp_path and os.path.exists(audio_temp_path):
                    os.unlink(audio_temp_path)
                return True
        else:
            # No audio found, just use video
            os.rename(video_temp_path, save_path)
            return True

    except Exception as e:
        # Cleanup any temp files on error
        pass
    return False

def download_post_media(post_data, dirs, post_id):
    """Downloads all media from a post."""
    media = get_media_urls(post_data)
    downloaded = {"images": 0, "videos": 0}

    for i, img_url in enumerate(media["images"][:5]):
        ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
        save_path = os.path.join(dirs["images"], f"{post_id}_{i}{ext}")
        if download_media(img_url, save_path, "image"):
            downloaded["images"] += 1

    for i, img_url in enumerate(media["galleries"][:10]):
        ext = '.jpg'
        save_path = os.path.join(dirs["images"], f"{post_id}_gallery_{i}{ext}")
        if download_media(img_url, save_path, "gallery"):
            downloaded["images"] += 1

    for i, vid_url in enumerate(media["videos"][:2]):
        if 'youtube' not in vid_url:
            ext = '.mp4'
            save_path = os.path.join(dirs["videos"], f"{post_id}_{i}{ext}")
            # Use enhanced download for Reddit videos (includes audio)
            if 'v.redd.it' in vid_url or 'reddit.com' in vid_url:
                if download_reddit_video_with_audio(vid_url, save_path):
                    downloaded["videos"] += 1
            elif download_media(vid_url, save_path, "video"):
                downloaded["videos"] += 1

    return downloaded

# --- COMMENT SCRAPING ---
def scrape_comments(permalink, max_depth=MAX_COMMENT_DEPTH):
    """Scrapes comments from a post."""
    comments = []

    try:
        data = get_api_client().get_json(comments_url(permalink))
        comments = parse_comments(comment_children(data), permalink, depth=0, max_depth=max_depth)

    except RedditAPIError:
        raise
    except Exception as e:
        raise RedditAPIError('Unexpected comment response; comments could not be fetched.') from e

    if len(comments) > 0:
        print(f"   + Scraped {len(comments)} comments")

    return comments

def parse_comments(comment_list, post_permalink, depth=0, max_depth=MAX_COMMENT_DEPTH):
    """Recursively parses comments."""
    comments = []

    if depth > max_depth:
        return comments

    for item in comment_list:
        if item['kind'] != 't1':
            continue

        c = item['data']

        comment = {
            "post_permalink": post_permalink,
            "comment_id": c.get('id'),
            "parent_id": c.get('parent_id'),
            "author": c.get('author'),
            "body": c.get('body', ''),
            "score": c.get('score', 0),
            "created_utc": datetime.datetime.fromtimestamp(c.get('created_utc', 0)).isoformat(),
            "depth": depth,
            "is_submitter": c.get('is_submitter', False),
        }
        comments.append(comment)

        replies = c.get('replies')
        if replies and isinstance(replies, dict):
            reply_children = replies.get('data', {}).get('children', [])
            comments.extend(parse_comments(reply_children, post_permalink, depth + 1, max_depth))

    return comments

# --- POST EXTRACTION ---
def extract_post_data(post_json):
    """Extracts comprehensive post data."""
    p = post_json

    post_type = "text"
    if p.get('is_video'):
        post_type = "video"
    elif p.get('is_gallery'):
        post_type = "gallery"
    elif any(ext in p.get('url', '').lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']) or 'i.redd.it' in p.get('url', ''):
        post_type = "image"
    elif p.get('is_self'):
        post_type = "text"
    else:
        post_type = "link"

    return {
        "id": p.get('id'),
        "title": p.get('title'),
        "author": p.get('author'),
        "created_utc": datetime.datetime.fromtimestamp(p.get('created_utc', 0)).isoformat(),
        "permalink": p.get('permalink'),
        "url": p.get('url_overridden_by_dest', p.get('url')),
        "score": p.get('score', 0),
        "upvote_ratio": p.get('upvote_ratio', 0),
        "num_comments": p.get('num_comments', 0),
        "num_crossposts": p.get('num_crossposts', 0),
        "selftext": p.get('selftext', ''),
        "post_type": post_type,
        "is_nsfw": p.get('over_18', False),
        "is_spoiler": p.get('spoiler', False),
        "flair": p.get('link_flair_text', ''),
        "total_awards": p.get('total_awards_received', 0),
        "has_media": p.get('is_video', False) or p.get('is_gallery', False) or 'i.redd.it' in p.get('url', ''),
        "media_downloaded": False,
        "source": "History-Full"
    }

# --- FULL HISTORY SCRAPE ---
def run_full_history(target, limit, is_user=False, download_media_flag=True,
                     scrape_comments_flag=True, dry_run=False, use_plugins=False):
    """
    Full scrape with images, videos, and comments.

    Args:
        target: Subreddit or username
        limit: Maximum posts to scrape
        is_user: True if target is a user
        download_media_flag: Download images/videos
        scrape_comments_flag: Scrape comments
        dry_run: Simulate without saving data
        use_plugins: Run post-processing plugins
    """
    target = normalize_target(target, is_user)
    if limit < 1:
        raise ValueError("Post limit must be positive.")
    prefix = "u" if is_user else "r"
    mode = "full" if download_media_flag and scrape_comments_flag else "history"

    # Display mode banner
    if dry_run:
        print("=" * 50)
        print("🧪 DRY RUN MODE - No data will be saved")
        print("=" * 50)

    print(f"🚀 Starting {'DRY RUN' if dry_run else 'FULL HISTORY'} scrape for {prefix}/{target}")
    print(f"   📊 Target posts: {limit}")
    print(f"   🖼️  Download media: {download_media_flag and not dry_run}")
    print(f"   💬 Scrape comments: {scrape_comments_flag}")
    print(f"   🔌 Plugins enabled: {use_plugins}")
    print("-" * 50)

    # A dry run writes neither content nor job records.
    job_id = None
    if not dry_run:
        try:
            from export.database import start_job_record, complete_job_record
            job_id = start_job_record(target, mode, is_user, dry_run)
        except Exception as e:
            print(f"⚠️ Job tracking unavailable: {e}")

    # Read existing history; dry runs do not create output directories.
    dirs = {"base": f"data/{prefix}_{target}",
            "posts": f"data/{prefix}_{target}/posts.csv",
            "comments": f"data/{prefix}_{target}/comments.csv"} if dry_run else setup_directories(target, prefix)
    load_history(dirs["posts"])

    after = None
    total_posts = 0
    total_media = {"images": 0, "videos": 0}
    total_comments = 0
    all_scraped_posts = []  # For plugin processing
    all_scraped_comments = []
    start_time = time.time()
    error_msg = None

    try:
        get_api_client().validate()
        seen_cursors = set()
        while total_posts < limit:
            path = f"/user/{target}/submitted.json" if is_user else f"/r/{target}/new.json"
            target_url = f"{REDDIT_API_BASE}{path}?limit={min(100, limit - total_posts)}&raw_json=1"
            if after:
                target_url += f"&after={after}"
            print(f"\n📡 Fetching from: {REDDIT_API_BASE}")
            data = get_api_client().get_json(target_url)
            children = listing_children(data)
            print(f"   Found {len(children)} posts in this batch")
            if not children:
                break
            posts, batch_comments = [], []
            batch_seen = set()
            for child in children:
                p = child['data']
                post = extract_post_data(p)
                if post['permalink'] in SEEN_URLS or post['permalink'] in batch_seen:
                    continue
                if len(posts) >= limit - total_posts:
                    break
                batch_seen.add(post['permalink'])
                posts.append(post)
                if download_media_flag and not dry_run:
                    downloaded = download_post_media(p, dirs, post['id'])
                    post['media_downloaded'] = any(downloaded.values())
                    total_media['images'] += downloaded['images']
                    total_media['videos'] += downloaded['videos']
                if scrape_comments_flag and post['num_comments'] > 0:
                    try:
                        batch_comments.extend(scrape_comments(post['permalink']))
                    except RedditAPIError as e:
                        error_msg = str(e)
                        print(f"   ❌ Comments unavailable: {e}")
                        break
            all_scraped_posts.extend(posts)
            all_scraped_comments.extend(batch_comments)
            total_comments += len(batch_comments)
            if dry_run:
                total_posts += len(posts)
                SEEN_URLS.update(batch_seen)
            else:
                total_posts += save_posts_csv(posts, dirs['posts'])
                if batch_comments:
                    save_comments_csv(batch_comments, dirs['comments'])
            print(f"\n📊 Progress: {total_posts}/{limit} posts | {total_comments} comments")
            if error_msg:
                break
            after = data['data'].get('after')
            if not after:
                print("🏁 Reached end of available history (listings are not a complete archive).")
                break
            if after in seen_cursors:
                raise RedditAPIError("Reddit repeated a pagination cursor; stopped to avoid an endless loop.")
            seen_cursors.add(after)

        # Run plugins on collected data
        if use_plugins and (all_scraped_posts or all_scraped_comments):
            print("\n🔌 Running post-processing plugins...")
            try:
                from plugins import load_plugins, run_plugins
                plugins = load_plugins()
                if plugins:
                    all_scraped_posts, all_scraped_comments = run_plugins(
                        all_scraped_posts, all_scraped_comments, plugins
                    )
                    print(f"   ✅ Processed {len(all_scraped_posts)} posts with {len(plugins)} plugins")
                else:
                    print("   ⚠️ No plugins found")
            except Exception as e:
                print(f"   ⚠️ Plugin error: {e}")

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ Scrape error: {e}")

    duration = time.time() - start_time

    # Complete job tracking
    if job_id:
        try:
            status = 'failed' if error_msg else 'completed'
            complete_job_record(
                job_id, status,
                total_posts, total_comments,
                total_media['images'] + total_media['videos'],
                error_msg
            )
        except Exception as e:
            print(f"⚠️ Failed to complete job record: {e}")

    # Summary
    print("\n" + "=" * 50)
    if dry_run:
        print("❌ DRY RUN FAILED!" if error_msg else "🧪 DRY RUN COMPLETE!")
        print(f"   📊 Would scrape: {total_posts} posts")
        print(f"   💬 Would scrape: {total_comments} comments")
    else:
        print("❌ SCRAPE INCOMPLETE!" if error_msg else "✅ SCRAPE COMPLETE!")
        print(f"   📁 Data saved to: {dirs['base']}")
        print(f"   📊 Total posts: {total_posts}")
        print(f"   🖼️  Total images: {total_media['images']}")
        print(f"   🎬 Total videos: {total_media['videos']}")
        print(f"   💬 Total comments: {total_comments}")
    print(f"   ⏱️  Duration: {duration:.1f}s")

    return {
        'posts': total_posts,
        'images': total_media['images'],
        'videos': total_media['videos'],
        'comments': total_comments,
        'duration': f"{duration:.1f}s",
        'dry_run': dry_run,
        'job_id': job_id,
        'status': 'failed' if error_msg else 'completed',
        'error': error_msg
    }

# --- MONITOR MODE ---
def run_monitor(target, is_user=False):
    """Poll through the same authenticated, rate-limited path as history jobs."""
    return run_full_history(target, 25, is_user, download_media_flag=False, scrape_comments_flag=False)

# --- CLI ---
def main():
    parser = argparse.ArgumentParser(
        description="🤖 Universal Reddit Scraper Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  SCRAPING:
    python main.py <target> --mode full --limit 100
    python main.py <target> --mode history --limit 500
    python main.py <target> --mode monitor
    python main.py <target> --dry-run           # Test without saving
    python main.py <target> --plugins           # Enable post-processing

  SEARCH:
    python main.py --search "keyword" --subreddit delhi
    python main.py --search "keyword" --min-score 100

  DASHBOARD:
    python main.py --dashboard

  SCHEDULE:
    python main.py --schedule delhi --every 60

  ANALYTICS:
    python main.py --analyze delhi --sentiment
    python main.py --analyze delhi --keywords

  MAINTENANCE:
    python main.py --job-history                # View job history
    python main.py --backup                     # Backup database
    python main.py --vacuum                     # Optimize database
    python main.py --export-parquet python      # Export to Parquet
    python main.py --list-plugins               # List available plugins

  REST API:
    python main.py --api                        # Start REST API server
        """
    )

    # Scraping args
    parser.add_argument("target", nargs='?', help="Subreddit or username to scrape")
    parser.add_argument("--mode", choices=["monitor", "history", "full"], default="full")
    parser.add_argument("--user", action="store_true", help="Target is a user")
    parser.add_argument("--limit", type=int, default=100, help="Max posts to scrape")
    parser.add_argument("--no-media", action="store_true", help="Skip media download")
    parser.add_argument("--no-comments", action="store_true", help="Skip comments")

    # Dashboard
    parser.add_argument("--dashboard", action="store_true", help="Launch web dashboard")

    # Search
    parser.add_argument("--search", type=str, help="Search scraped data")
    parser.add_argument("--subreddit", type=str, help="Filter by subreddit")
    parser.add_argument("--min-score", type=int, help="Filter by minimum score")
    parser.add_argument("--author", type=str, help="Filter by author")

    # Analytics
    parser.add_argument("--analyze", type=str, help="Run analytics on subreddit")
    parser.add_argument("--sentiment", action="store_true", help="Run sentiment analysis")
    parser.add_argument("--keywords", action="store_true", help="Extract keywords")

    # Schedule
    parser.add_argument("--schedule", type=str, help="Schedule scraping for target")
    parser.add_argument("--every", type=int, help="Interval in minutes")

    # Alerts
    parser.add_argument("--alert", type=str, help="Set keyword alert")
    parser.add_argument("--discord-webhook", type=str, help="Discord webhook URL")
    parser.add_argument("--telegram-token", type=str, help="Telegram bot token")
    parser.add_argument("--telegram-chat", type=str, help="Telegram chat ID")

    # New: Observability & Maintenance
    parser.add_argument("--dry-run", action="store_true", help="Simulate scrape without saving data")
    parser.add_argument("--plugins", action="store_true", help="Enable post-processing plugins")
    parser.add_argument("--list-plugins", action="store_true", help="List available plugins")
    parser.add_argument("--job-history", action="store_true", help="View job history")
    parser.add_argument("--backup", action="store_true", help="Backup SQLite database")
    parser.add_argument("--vacuum", action="store_true", help="Optimize SQLite database")
    parser.add_argument("--export-parquet", type=str, help="Export subreddit to Parquet format")
    parser.add_argument("--api", action="store_true", help="Start REST API server (port 8000)")
    parser.add_argument("--proxy", type=str, help="Proxy URL (e.g. http://username:password@host:port)")
    parser.add_argument("--proxy-country", type=str, help="Country code for a configured ScrapingAnt proxy")
    parser.add_argument("--proxy-session", type=str, help="Stable session ID for a configured ScrapingAnt proxy")
    parser.add_argument("--no-proxy-rotate", action="store_true", help="Compatibility option; rotation is always disabled")

    parser.add_argument("--check-access", action="store_true", help="Validate OAuth config and fetch one post without saving data")
    parser.add_argument("--import-browser", type=Path, help="Import a browser extension JSON export (no Reddit API needed)")
    parser.add_argument("--bridge-token", action="store_true", help="Show the local pairing token for the browser extension")
    args = parser.parse_args()

    if args.bridge_token:
        from export.browser_import import bridge_token
        print(bridge_token())
        return 0

    if args.import_browser:
        from export.browser_import import import_file
        try:
            result = import_file(args.import_browser)
        except (ValueError, OSError) as error:
            print(f"Browser import failed: {error}")
            return 1
        print(f"Browser import: {result['posts_added']} new posts, {result['comments_added']} new comments; "
              f"{result['duplicates']} duplicates skipped.")
        return 0

    # Configure Proxy
    global PROXY_TO_USE, API_CLIENT
    if API_CLIENT is not None:
        API_CLIENT.close()
        API_CLIENT = None
    PROXY_TO_USE = args.proxy if args.proxy is not None else PROXY_URL

    # Apply CLI overrides to configuration if provided
    if args.proxy_country:
        import config
        config.PROXY_COUNTRY = args.proxy_country
    if args.proxy_session:
        import config
        config.PROXY_SESSION_ID = args.proxy_session
    if args.no_proxy_rotate:
        import config
        config.PROXY_AUTO_ROTATE = False

    if PROXY_TO_USE and PROXY_TO_USE.lower() not in ["none", "direct", "disabled", ""]:
        # Configure a stable network proxy
        rotate_session_proxy(force_rotate=False)

        print("🔒 Using configured network proxy")
    else:
        SESSION.proxies = {}

    if args.check_access:
        try:
            target = normalize_target(args.target or "python", args.user)
            path = f"/user/{target}/submitted.json" if args.user else f"/r/{target}/new.json"
            data = get_api_client().get_json(f"{REDDIT_API_BASE}{path}?limit=1&raw_json=1")
            print(f"API access OK: {len(listing_children(data))} post(s) returned; no content saved.")
        except (RedditAPIError, ValueError) as e:
            print(f"API access failed: {e}")
            return 1
        return 0

    print("=" * 50)
    print("🤖 UNIVERSAL REDDIT SCRAPER SUITE")
    print("=" * 50)

    # Dashboard mode
    if args.dashboard:
        print("\n🌐 Launching Dashboard...")
        print("   Open: http://localhost:8501")
        os.system("streamlit run dashboard/app.py")
        return

    # REST API mode
    if args.api:
        print("\n🚀 Starting REST API server...")
        print("   📖 Docs: http://localhost:8000/docs")
        print("   📊 Connect Metabase/Grafana to http://localhost:8000")
        try:
            import uvicorn
            from api.server import app
            uvicorn.run(app, host="0.0.0.0", port=8000)
        except ImportError:
            print("❌ Install dependencies: pip install fastapi uvicorn")
        return

    # --- NEW: Maintenance & Observability Commands ---

    # Job history
    if args.job_history:
        from export.database import print_job_history
        print_job_history()
        return

    # Backup database
    if args.backup:
        from export.database import backup_database
        backup_database()
        return

    # Vacuum/optimize database
    if args.vacuum:
        from export.database import vacuum_database
        vacuum_database()
        return

    # Export to Parquet
    if args.export_parquet:
        from export.parquet import export_to_parquet
        prefix = "u" if args.user else "r"
        export_to_parquet(args.export_parquet, prefix=prefix)
        return

    # List plugins
    if args.list_plugins:
        from plugins import list_plugins
        list_plugins()
        return

    # Search mode
    if args.search:
        print(f"\n🔍 Searching for: {args.search}")
        from search.query import search_all_data, print_search_results

        results = search_all_data(
            query=args.search,
            min_score=args.min_score,
            author=args.author
        )
        print_search_results(results)
        return

    # Analytics mode
    if args.analyze:
        print(f"\n📊 Analyzing: {args.analyze}")

        # Load data
        data_dir = Path(f"data/r_{args.analyze}")
        if not data_dir.exists():
            print(f"❌ No data found for r/{args.analyze}")
            return

        posts_file = data_dir / "posts.csv"
        if not posts_file.exists():
            print(f"❌ No posts data found")
            return

        import pandas as pd
        df = pd.read_csv(posts_file)
        posts = df.to_dict('records')

        if args.sentiment:
            from analytics.sentiment import analyze_posts_sentiment
            analyzed, counts = analyze_posts_sentiment(posts)
            print(f"\n😀 Sentiment Analysis:")
            print(f"   Positive: {counts['positive']}")
            print(f"   Neutral:  {counts['neutral']}")
            print(f"   Negative: {counts['negative']}")

        if args.keywords:
            from analytics.sentiment import extract_keywords
            texts = [str(p.get('title', '') or '') + ' ' + str(p.get('selftext', '') or '') for p in posts]
            keywords = extract_keywords(texts, top_n=20)
            print(f"\n☁️ Top Keywords:")
            for word, count in keywords:
                print(f"   {word}: {count}")

        return

    # Schedule mode
    if args.schedule:
        if not args.every:
            print("❌ Please specify --every <minutes>")
            return

        from scheduler.cron import run_scheduled
        run_scheduled(args.schedule, args.every, args.mode, args.limit, args.user)
        return

    # Regular scraping mode
    if not args.target:
        parser.print_help()
        return

    if args.mode == "monitor":
        prefix = "u" if args.user else "r"
        print(f"🔄 Monitoring {prefix}/{args.target} every 5 mins...")
        while True:
            result = run_monitor(args.target, args.user)
            if result['error']:
                return 1
            time.sleep(300)
    elif args.mode == "history":
        result = run_full_history(args.target, args.limit, args.user,
                        download_media_flag=False, scrape_comments_flag=False,
                        dry_run=args.dry_run, use_plugins=args.plugins)
    else:
        result = run_full_history(args.target, args.limit, args.user,
                        download_media_flag=not args.no_media,
                        scrape_comments_flag=not args.no_comments,
                        dry_run=args.dry_run, use_plugins=args.plugins)

    return 1 if result.get('error') else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RedditAPIError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)
