"""
Async Reddit Scraper - rate-limited API access and concurrent media downloads
"""
import asyncio
import aiohttp
import aiofiles
import pandas as pd
import datetime
import time
import os
from pathlib import Path
from urllib.parse import urlparse
import sys

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import USER_AGENT, REDDIT_API_BASE, ASYNC_MAX_CONCURRENT, PROXY_URL, MAX_COMMENT_DEPTH, get_formatted_proxy_url
from scraper.reddit_client import RedditClient, RedditAPIError, normalize_target, listing_children, comments_url, comment_children
from scraper.media import extract_media_urls
from export.storage_lock import data_write_lock
import subprocess
import tempfile

# Semaphore to limit concurrent requests
semaphore = None

async def fetch_json(session, url, retries=3, proxy=None, warmup_url=None, api_client=None):
    """Run the shared, serialized API client without blocking the event loop."""
    client = api_client or RedditClient(proxy=proxy)
    try:
        return await asyncio.to_thread(client.get_json, url, retries)
    finally:
        if api_client is None:
            client.close()


async def fetch_posts_page(session, base_url, target, after=None, is_user=False, batch_size=100, proxy=None, api_client=None):
    path = f"/user/{target}/submitted.json" if is_user else f"/r/{target}/new.json"
    url = f"{REDDIT_API_BASE}{path}?limit={min(100, batch_size)}&raw_json=1"
    if after:
        url += f"&after={after}"
    return await fetch_json(session, url, proxy=proxy, api_client=api_client)

async def download_media_async(session, url, save_path, proxy=None):
    """Download media file asynchronously."""
    global semaphore

    if os.path.exists(save_path):
        return True

    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60), proxy=proxy) as response:
                if response.status == 200:
                    async with aiofiles.open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return True
        except:
            pass
    return False

async def download_reddit_video_with_audio_async(session, video_url, save_path, proxy=None):
    """
    Downloads Reddit video with audio asynchronously.
    Reddit stores video and audio separately - this combines them using ffmpeg.
    """
    global semaphore

    if os.path.exists(save_path):
        return True

    async with semaphore:
        try:
            # Find audio URL by replacing video quality with audio
            base_url = video_url.rsplit('/', 1)[0]
            audio_urls = [
                f"{base_url}/DASH_audio.mp4",
                f"{base_url}/DASH_AUDIO_128.mp4",
                f"{base_url}/DASH_AUDIO_64.mp4",
                f"{base_url}/audio.mp4",
                f"{base_url}/audio"
            ]

            # Download video to temp file
            video_temp = tempfile.NamedTemporaryFile(suffix='_video.mp4', delete=False)
            video_temp_path = video_temp.name
            video_temp.close()

            try:
                async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=60), proxy=proxy) as response:
                    if response.status != 200:
                        return False
                    async with aiofiles.open(video_temp_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
            except:
                if os.path.exists(video_temp_path):
                    os.unlink(video_temp_path)
                return False

            # Try to download audio
            audio_temp_path = None
            for audio_url in audio_urls:
                try:
                    async with session.get(audio_url, timeout=aiohttp.ClientTimeout(total=30), proxy=proxy) as response:
                        if response.status == 200:
                            audio_temp = tempfile.NamedTemporaryFile(suffix='_audio.mp4', delete=False)
                            audio_temp_path = audio_temp.name
                            audio_temp.close()
                            async with aiofiles.open(audio_temp_path, 'wb') as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    await f.write(chunk)
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
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await asyncio.wait_for(proc.wait(), timeout=120)

                    if proc.returncode == 0:
                        os.unlink(video_temp_path)
                        os.unlink(audio_temp_path)
                        return True
                    else:
                        # ffmpeg failed, use video only
                        os.rename(video_temp_path, save_path)
                        os.unlink(audio_temp_path)
                        return True
                except FileNotFoundError:
                    # ffmpeg not installed
                    os.rename(video_temp_path, save_path)
                    if audio_temp_path and os.path.exists(audio_temp_path):
                        os.unlink(audio_temp_path)
                    return True
                except Exception:
                    os.rename(video_temp_path, save_path)
                    if audio_temp_path and os.path.exists(audio_temp_path):
                        os.unlink(audio_temp_path)
                    return True
            else:
                # No audio found, just use video
                os.rename(video_temp_path, save_path)
                return True

        except Exception:
            pass
    return False

async def fetch_comments_async(session, permalink, proxy=None, api_client=None):
    """Fetch comments asynchronously."""
    global semaphore

    async with semaphore:
        data = await fetch_json(session, comments_url(permalink), proxy=proxy, api_client=api_client)
        return parse_comments_sync(comment_children(data), permalink)


def parse_comments_sync(comment_list, post_permalink, depth=0, max_depth=MAX_COMMENT_DEPTH):
    """Parse comments (sync helper)."""
    comments = []

    if depth > max_depth:
        return comments

    for item in comment_list:
        if item['kind'] != 't1':
            continue

        c = item['data']
        comments.append({
            "post_permalink": post_permalink,
            "comment_id": c.get('id'),
            "parent_id": c.get('parent_id'),
            "author": c.get('author'),
            "body": c.get('body', ''),
            "score": c.get('score', 0),
            "created_utc": datetime.datetime.fromtimestamp(c.get('created_utc', 0)).isoformat(),
            "depth": depth,
            "is_submitter": c.get('is_submitter', False),
        })

        replies = c.get('replies')
        if replies and isinstance(replies, dict):
            comments.extend(parse_comments_sync(
                replies.get('data', {}).get('children', []),
                post_permalink, depth + 1, max_depth
            ))

    return comments

def extract_post_data(p):
    """Extract post data from JSON."""
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
        "source": "Async-Scraper"
    }

async def scrape_async(target, limit=100, is_user=False, download_media=True, scrape_comments=True, proxy=None):
    """
    Main async scraping function.

    Args:
        target: Subreddit or username
        limit: Max posts to scrape
        is_user: True if scraping a user
        download_media: Download images/videos
        scrape_comments: Scrape comments
    """
    target = normalize_target(target, is_user)
    if limit < 1:
        raise ValueError("Post limit must be positive.")
    global semaphore
    semaphore = asyncio.Semaphore(ASYNC_MAX_CONCURRENT)

    proxy_url = proxy if proxy is not None else PROXY_URL
    if proxy_url and proxy_url.lower() in ["none", "direct", "disabled", ""]:
        proxy_url = None
    elif not proxy_url:
        proxy_url = None

    prefix = "u" if is_user else "r"
    print(f"🚀 ASYNC Scraper starting for {prefix}/{target}")
    if proxy_url:
        print("🔒 Using configured network proxy")
    print(f"   Target: {limit} posts | Media: {download_media} | Comments: {scrape_comments}")
    print(f"   Concurrency: {ASYNC_MAX_CONCURRENT} simultaneous requests")
    print("-" * 50)

    proxy_url = get_formatted_proxy_url(proxy_url)
    api_client = RedditClient(proxy=proxy_url)
    api_client.validate()
    error_msg = None

    # Setup directories
    base_dir = f"data/{prefix}_{target}"
    media_dir = f"{base_dir}/media"
    images_dir = f"{media_dir}/images"
    videos_dir = f"{media_dir}/videos"

    for d in [base_dir, media_dir, images_dir, videos_dir]:
        os.makedirs(d, exist_ok=True)

    start_time = time.time()
    all_posts = []
    all_comments = []
    media_tasks = []
    seen_permalinks = set()

    # Load existing data
    posts_file = f"{base_dir}/posts.csv"
    if os.path.exists(posts_file):
        try:
            df = pd.read_csv(posts_file)
            seen_permalinks = set(df['permalink'].astype(str).tolist())
            print(f"📚 Loaded {len(seen_permalinks)} existing posts")
        except:
            pass

    headers = {"User-Agent": USER_AGENT}
    with api_client.session:
        async with aiohttp.ClientSession(headers=headers) as session:
            after = None
            total_fetched = 0
            seen_cursors = set()

            while total_fetched < limit:
                try:
                    batch_size = min(100, limit - total_fetched)
                    data = await fetch_posts_page(session, REDDIT_API_BASE, target, after, is_user,
                                                  batch_size, proxy=proxy_url, api_client=api_client)
                    children = listing_children(data)
                except RedditAPIError as e:
                    error_msg = str(e)
                    print(f"❌ API request failed: {e}")
                    break

                if not children:
                    print("🏁 No more posts")
                    break

                print(f"   Processing {len(children)} posts...")

                # Process posts
                batch_posts = []
                comment_tasks = []

                for child in children:
                    if len(batch_posts) >= limit - total_fetched:
                        break
                    p = child['data']
                    post = extract_post_data(p)

                    if post['permalink'] in seen_permalinks:
                        continue

                    seen_permalinks.add(post['permalink'])
                    batch_posts.append(post)

                    # Queue media downloads
                    if download_media:
                        media = extract_media_urls(p)

                        for i, img_url in enumerate(media['images'][:5]):
                            ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                            save_path = f"{images_dir}/{post['id']}_{i}{ext}"
                            media_tasks.append(download_media_async(session, img_url, save_path, proxy=proxy_url))

                        for i, img_url in enumerate(media['galleries'][:10]):
                            save_path = f"{images_dir}/{post['id']}_gallery_{i}.jpg"
                            media_tasks.append(download_media_async(session, img_url, save_path, proxy=proxy_url))

                        for i, vid_url in enumerate(media['videos'][:2]):
                            if 'youtube' not in vid_url:
                                save_path = f"{videos_dir}/{post['id']}_{i}.mp4"
                                # Use enhanced download for Reddit videos (includes audio)
                                if 'v.redd.it' in vid_url or 'reddit.com' in vid_url:
                                    media_tasks.append(download_reddit_video_with_audio_async(session, vid_url, save_path, proxy=proxy_url))
                                else:
                                    media_tasks.append(download_media_async(session, vid_url, save_path, proxy=proxy_url))

                    # Queue comment fetching
                    if scrape_comments and post['num_comments'] > 0:
                        comment_tasks.append(fetch_comments_async(session, post['permalink'], proxy=proxy_url, api_client=api_client))

                all_posts.extend(batch_posts)
                total_fetched += len(batch_posts)

                # Fetch comments in parallel
                if comment_tasks:
                    print(f"   💬 Fetching comments for {len(comment_tasks)} posts...")
                    comment_results = await asyncio.gather(*comment_tasks, return_exceptions=True)
                    for result in comment_results:
                        if isinstance(result, list):
                            all_comments.extend(result)
                        elif isinstance(result, Exception):
                            error_msg = str(result)
                            print(f"❌ Comment request failed: {result}")

                print(f"   📊 Progress: {total_fetched}/{limit} posts | {len(all_comments)} comments")

                if error_msg:
                    break
                after = data.get('data', {}).get('after')
                if not after:
                    print("🏁 Reached end of available posts")
                    break

                if after in seen_cursors:
                    error_msg = "Reddit repeated a pagination cursor; stopped to avoid an endless loop."
                    break
                seen_cursors.add(after)

            # Download all media in parallel
            if media_tasks:
                print(f"\n🖼️ Downloading {len(media_tasks)} media files in parallel...")
                media_results = await asyncio.gather(*media_tasks, return_exceptions=True)
                downloaded = sum(1 for r in media_results if r is True)
                print(f"   ✅ Downloaded {downloaded}/{len(media_tasks)} files")

    with data_write_lock():
        # Save data
        if all_posts:
            df = pd.DataFrame(all_posts)
            if os.path.exists(posts_file):
                known = set(pd.read_csv(posts_file, usecols=['permalink'])['permalink'].astype(str))
                df = df[~df['permalink'].isin(known)]
                df = df.reindex(columns=pd.read_csv(posts_file, nrows=0).columns)
                df.to_csv(posts_file, mode='a', header=False, index=False)
            else:
                df.to_csv(posts_file, index=False)
            print(f"\n💾 Saved {len(all_posts)} posts to {posts_file}")

        if all_comments:
            comments_file = f"{base_dir}/comments.csv"
            df = pd.DataFrame(all_comments)
            if os.path.exists(comments_file):
                known = set(pd.read_csv(comments_file, usecols=['comment_id'])['comment_id'].astype(str))
                df = df.drop_duplicates(subset=['comment_id'])
                df = df[~df['comment_id'].astype(str).isin(known)]
                df = df.reindex(columns=pd.read_csv(comments_file, nrows=0).columns)
                df.to_csv(comments_file, mode='a', header=False, index=False)
            else:
                df.to_csv(comments_file, index=False)
            print(f"💾 Saved {len(all_comments)} comments")

    duration = time.time() - start_time

    print("\n" + "=" * 50)
    print("❌ ASYNC SCRAPE INCOMPLETE!" if error_msg else "✅ ASYNC SCRAPE COMPLETE!")
    print(f"   📊 Posts: {len(all_posts)}")
    print(f"   💬 Comments: {len(all_comments)}")
    print(f"   🖼️ Media: {len(media_tasks)} queued")
    print(f"   ⏱️ Duration: {duration:.1f}s")
    print(f"   ⚡ Speed: {len(all_posts) / max(duration, 0.001):.1f} posts/sec")

    return {
        'posts': len(all_posts),
        'comments': len(all_comments),
        'duration': duration,
        'status': 'failed' if error_msg else 'completed',
        'error': error_msg
    }

def run_async_scraper(target, limit=100, is_user=False, download_media=True, scrape_comments=True, proxy=None):
    """Wrapper to run async scraper from sync code."""
    return asyncio.run(scrape_async(target, limit, is_user, download_media, scrape_comments, proxy))

# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Async Reddit Scraper")
    parser.add_argument("target", help="Subreddit or username")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--user", action="store_true")
    parser.add_argument("--no-media", action="store_true")
    parser.add_argument("--no-comments", action="store_true")
    parser.add_argument("--proxy", help="Proxy URL (e.g. http://username:password@host:port)")
    parser.add_argument("--proxy-country", type=str, help="Country code for a configured ScrapingAnt proxy")
    parser.add_argument("--proxy-session", type=str, help="Stable session ID for a configured ScrapingAnt proxy")
    parser.add_argument("--no-proxy-rotate", action="store_true", help="Compatibility option; rotation is always disabled")

    args = parser.parse_args()

    if args.proxy_country:
        import config
        config.PROXY_COUNTRY = args.proxy_country
    if args.proxy_session:
        import config
        config.PROXY_SESSION_ID = args.proxy_session
    if args.no_proxy_rotate:
        import config
        config.PROXY_AUTO_ROTATE = False

    result = run_async_scraper(
        args.target,
        args.limit,
        args.user,
        not args.no_media,
        not args.no_comments,
        args.proxy
    )
    sys.exit(1 if result.get('error') else 0)
