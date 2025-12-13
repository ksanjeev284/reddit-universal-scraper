"""
🤖 Universal Reddit Scraper Suite
Full-featured scraper with analytics, dashboard, notifications, and scheduling.
"""
import requests
import pandas as pd
import datetime
import time
import os
import xml.etree.ElementTree as ET
import argparse
import random
import sys
import json
from urllib.parse import urlparse
from pathlib import Path

# --- CONFIGURATION ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

MIRRORS = [
    "https://old.reddit.com",
    "https://redlib.catsarch.com",
    "https://redlib.vsls.cz",
    "https://r.nf",
    "https://libreddit.northboot.xyz",
    "https://redlib.tux.pizza"
]

SEEN_URLS = set()
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

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

def save_posts_csv(posts, filepath):
    """Saves posts to CSV with all metadata."""
    if not posts:
        return 0
    
    new_posts = [p for p in posts if p['permalink'] not in SEEN_URLS]
    
    if new_posts:
        df = pd.DataFrame(new_posts)
        if os.path.exists(filepath):
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

def save_comments_csv(comments, filepath):
    """Saves comments to CSV."""
    if not comments:
        return
    
    df = pd.DataFrame(comments)
    if os.path.exists(filepath):
        df.to_csv(filepath, mode='a', header=False, index=False)
    else:
        df.to_csv(filepath, index=False)
    
    print(f"💬 Saved {len(comments)} comments")

# --- MEDIA DOWNLOAD ---
def get_media_urls(post_data):
    """Extracts all media URLs from a post."""
    media = {"images": [], "videos": [], "galleries": []}
    
    url = post_data.get('url', '')
    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        media["images"].append(url)
    
    if 'i.redd.it' in url:
        media["images"].append(url)
    
    if post_data.get('is_video'):
        reddit_video = post_data.get('media', {})
        if reddit_video and 'reddit_video' in reddit_video:
            video_url = reddit_video['reddit_video'].get('fallback_url', '')
            if video_url:
                media["videos"].append(video_url.split('?')[0])
    
    preview = post_data.get('preview', {})
    if preview and 'images' in preview:
        for img in preview['images']:
            source = img.get('source', {})
            if source.get('url'):
                clean_url = source['url'].replace('&amp;', '&')
                media["images"].append(clean_url)
    
    if post_data.get('is_gallery'):
        gallery_data = post_data.get('gallery_data', {})
        media_metadata = post_data.get('media_metadata', {})
        
        if gallery_data and media_metadata:
            for item in gallery_data.get('items', []):
                media_id = item.get('media_id')
                if media_id and media_id in media_metadata:
                    meta = media_metadata[media_id]
                    if meta.get('s', {}).get('u'):
                        clean_url = meta['s']['u'].replace('&amp;', '&')
                        media["galleries"].append(clean_url)
    
    if 'youtube.com' in url or 'youtu.be' in url:
        media["videos"].append(url)
    
    return media

def download_media(url, save_path, media_type="image"):
    """Downloads a single media file."""
    try:
        if os.path.exists(save_path):
            return True
        
        response = SESSION.get(url, timeout=30, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
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
            if download_media(vid_url, save_path, "video"):
                downloaded["videos"] += 1
    
    return downloaded

# --- COMMENT SCRAPING ---
def scrape_comments(permalink, max_depth=3):
    """Scrapes comments from a post."""
    comments = []
    
    try:
        if not permalink.startswith('http'):
            url = f"https://old.reddit.com{permalink}.json?limit=100"
        else:
            url = f"{permalink}.json?limit=100"
        
        response = SESSION.get(url, timeout=15)
        if response.status_code != 200:
            return comments
        
        data = response.json()
        
        if len(data) > 1:
            comment_data = data[1]['data']['children']
            comments = parse_comments(comment_data, permalink, depth=0, max_depth=max_depth)
    
    except Exception as e:
        pass
    
    return comments

def parse_comments(comment_list, post_permalink, depth=0, max_depth=3):
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
def run_full_history(target, limit, is_user=False, download_media_flag=True, scrape_comments_flag=True):
    """Full scrape with images, videos, and comments."""
    prefix = "u" if is_user else "r"
    print(f"🚀 Starting FULL HISTORY scrape for {prefix}/{target}")
    print(f"   📊 Target posts: {limit}")
    print(f"   🖼️  Download media: {download_media_flag}")
    print(f"   💬 Scrape comments: {scrape_comments_flag}")
    print("-" * 50)
    
    dirs = setup_directories(target, prefix)
    load_history(dirs["posts"])
    
    after = None
    total_posts = 0
    total_media = {"images": 0, "videos": 0}
    total_comments = 0
    start_time = time.time()
    
    while total_posts < limit:
        random.shuffle(MIRRORS)
        success = False
        
        for base_url in MIRRORS:
            try:
                if is_user:
                    path = f"/user/{target}/submitted.json"
                else:
                    path = f"/r/{target}/new.json"
                
                target_url = f"{base_url}{path}?limit=100&raw_json=1"
                if after:
                    target_url += f"&after={after}"
                
                print(f"\n📡 Fetching from: {base_url}")
                response = SESSION.get(target_url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = []
                    all_comments = []
                    
                    children = data['data']['children']
                    print(f"   Found {len(children)} posts in this batch")
                    
                    for child in children:
                        p = child['data']
                        post = extract_post_data(p)
                        
                        if post['permalink'] in SEEN_URLS:
                            continue
                        
                        if download_media_flag:
                            downloaded = download_post_media(p, dirs, post['id'])
                            post['media_downloaded'] = downloaded['images'] > 0 or downloaded['videos'] > 0
                            total_media['images'] += downloaded['images']
                            total_media['videos'] += downloaded['videos']
                        
                        posts.append(post)
                        
                        if scrape_comments_flag and post['num_comments'] > 0:
                            print(f"   💬 Fetching comments for: {post['title'][:40]}...")
                            comments = scrape_comments(post['permalink'])
                            all_comments.extend(comments)
                            total_comments += len(comments)
                            time.sleep(1)
                    
                    saved = save_posts_csv(posts, dirs["posts"])
                    total_posts += saved
                    
                    if all_comments:
                        save_comments_csv(all_comments, dirs["comments"])
                    
                    print(f"\n📊 Progress: {total_posts}/{limit} posts")
                    print(f"   🖼️  Images: {total_media['images']} | 🎬 Videos: {total_media['videos']}")
                    print(f"   💬 Comments: {total_comments}")
                    
                    after = data['data'].get('after')
                    if not after:
                        print("\n🏁 Reached end of available history.")
                        break
                    
                    success = True
                    break
                    
            except Exception as e:
                print(f"   ⚠️ Error with {base_url}: {e}")
                continue
        
        if not after:
            break
            
        if not success:
            print("\n❌ All sources failed. Waiting 30s...")
            time.sleep(30)
        else:
            print(f"\n⏸️ Cooling down (3s)...")
            time.sleep(3)
    
    duration = time.time() - start_time
    
    print("\n" + "=" * 50)
    print("✅ SCRAPE COMPLETE!")
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
        'duration': f"{duration:.1f}s"
    }

# --- MONITOR MODE ---
def run_monitor(target, is_user=False):
    prefix = "u" if is_user else "r"
    if is_user:
        rss_url = f"https://www.reddit.com/user/{target}/submitted.rss?limit=100"
    else:
        rss_url = f"https://www.reddit.com/r/{target}/new.rss?limit=100"

    print(f"[{datetime.datetime.now()}] 📡 Checking RSS for {prefix}/{target}...")
    
    try:
        response = SESSION.get(rss_url, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ RSS blocked (Status {response.status_code}), trying JSON...")
            run_full_history(target, 25, is_user, download_media_flag=False, scrape_comments_flag=False)
            return

        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        posts = []
        
        for entry in root.findall('atom:entry', namespace):
            posts.append({
                "id": "",
                "title": entry.find('atom:title', namespace).text,
                "author": "",
                "created_utc": entry.find('atom:published', namespace).text,
                "permalink": entry.find('atom:link', namespace).attrib['href'],
                "url": entry.find('atom:link', namespace).attrib['href'],
                "score": 0,
                "upvote_ratio": 0,
                "num_comments": 0,
                "num_crossposts": 0,
                "selftext": "",
                "post_type": "unknown",
                "is_nsfw": False,
                "is_spoiler": False,
                "flair": "",
                "total_awards": 0,
                "has_media": False,
                "media_downloaded": False,
                "source": "Monitor-RSS"
            })
        
        dirs = setup_directories(target, prefix)
        save_posts_csv(posts, dirs["posts"])

    except Exception as e:
        print(f"❌ Monitor Error: {e}")

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
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("🤖 UNIVERSAL REDDIT SCRAPER SUITE")
    print("=" * 50)
    
    # Dashboard mode
    if args.dashboard:
        print("\n🌐 Launching Dashboard...")
        print("   Open: http://localhost:8501")
        os.system("streamlit run dashboard/app.py")
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
        dirs = setup_directories(args.target, prefix)
        load_history(dirs["posts"])
        print(f"🔄 Monitoring {prefix}/{args.target} every 5 mins...")
        while True:
            run_monitor(args.target, args.user)
            time.sleep(300)
    elif args.mode == "history":
        run_full_history(args.target, args.limit, args.user, 
                        download_media_flag=False, scrape_comments_flag=False)
    else:
        run_full_history(args.target, args.limit, args.user,
                        download_media_flag=not args.no_media,
                        scrape_comments_flag=not args.no_comments)

if __name__ == "__main__":
    main()
