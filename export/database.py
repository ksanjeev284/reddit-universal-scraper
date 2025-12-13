"""
Database module - SQLite storage for scraped data
"""
import sqlite3
from pathlib import Path
from datetime import datetime
import json
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, DATA_DIR

def get_connection():
    """Get database connection."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Posts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            title TEXT,
            author TEXT,
            created_utc TEXT,
            permalink TEXT UNIQUE,
            url TEXT,
            score INTEGER DEFAULT 0,
            upvote_ratio REAL DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            num_crossposts INTEGER DEFAULT 0,
            selftext TEXT,
            post_type TEXT,
            is_nsfw BOOLEAN DEFAULT 0,
            is_spoiler BOOLEAN DEFAULT 0,
            flair TEXT,
            total_awards INTEGER DEFAULT 0,
            has_media BOOLEAN DEFAULT 0,
            media_downloaded BOOLEAN DEFAULT 0,
            source TEXT,
            scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sentiment_score REAL,
            sentiment_label TEXT
        )
    """)
    
    # Comments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE,
            post_id TEXT,
            post_permalink TEXT,
            parent_id TEXT,
            author TEXT,
            body TEXT,
            score INTEGER DEFAULT 0,
            created_utc TEXT,
            depth INTEGER DEFAULT 0,
            is_submitter BOOLEAN DEFAULT 0,
            scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sentiment_score REAL,
            sentiment_label TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    """)
    
    # Subreddits table (for tracking)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subreddits (
            name TEXT PRIMARY KEY,
            last_scraped TEXT,
            total_posts INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_media INTEGER DEFAULT 0
        )
    """)
    
    # Scheduled jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT,
            is_user BOOLEAN DEFAULT 0,
            mode TEXT DEFAULT 'full',
            limit_posts INTEGER DEFAULT 100,
            cron_expression TEXT,
            last_run TEXT,
            next_run TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            subreddit TEXT,
            alert_type TEXT DEFAULT 'discord',
            webhook_url TEXT,
            enabled BOOLEAN DEFAULT 1,
            last_triggered TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_subreddit ON posts(subreddit)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_utc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(score)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author)")
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def save_post(post_data, subreddit):
    """Save a single post to database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO posts 
            (id, subreddit, title, author, created_utc, permalink, url, score, 
             upvote_ratio, num_comments, num_crossposts, selftext, post_type,
             is_nsfw, is_spoiler, flair, total_awards, has_media, media_downloaded, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post_data.get('id'),
            subreddit,
            post_data.get('title'),
            post_data.get('author'),
            post_data.get('created_utc'),
            post_data.get('permalink'),
            post_data.get('url'),
            post_data.get('score', 0),
            post_data.get('upvote_ratio', 0),
            post_data.get('num_comments', 0),
            post_data.get('num_crossposts', 0),
            post_data.get('selftext', ''),
            post_data.get('post_type'),
            post_data.get('is_nsfw', False),
            post_data.get('is_spoiler', False),
            post_data.get('flair', ''),
            post_data.get('total_awards', 0),
            post_data.get('has_media', False),
            post_data.get('media_downloaded', False),
            post_data.get('source', '')
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False
    finally:
        conn.close()

def save_posts_batch(posts, subreddit):
    """Save multiple posts efficiently."""
    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    
    for post in posts:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO posts 
                (id, subreddit, title, author, created_utc, permalink, url, score, 
                 upvote_ratio, num_comments, num_crossposts, selftext, post_type,
                 is_nsfw, is_spoiler, flair, total_awards, has_media, media_downloaded, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.get('id'),
                subreddit,
                post.get('title'),
                post.get('author'),
                post.get('created_utc'),
                post.get('permalink'),
                post.get('url'),
                post.get('score', 0),
                post.get('upvote_ratio', 0),
                post.get('num_comments', 0),
                post.get('num_crossposts', 0),
                post.get('selftext', ''),
                post.get('post_type'),
                post.get('is_nsfw', False),
                post.get('is_spoiler', False),
                post.get('flair', ''),
                post.get('total_awards', 0),
                post.get('has_media', False),
                post.get('media_downloaded', False),
                post.get('source', '')
            ))
            if cursor.rowcount > 0:
                saved += 1
        except:
            continue
    
    conn.commit()
    conn.close()
    return saved

def save_comments_batch(comments, post_id):
    """Save multiple comments efficiently."""
    conn = get_connection()
    cursor = conn.cursor()
    saved = 0
    
    for comment in comments:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO comments 
                (comment_id, post_id, post_permalink, parent_id, author, body, 
                 score, created_utc, depth, is_submitter)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comment.get('comment_id'),
                post_id,
                comment.get('post_permalink'),
                comment.get('parent_id'),
                comment.get('author'),
                comment.get('body'),
                comment.get('score', 0),
                comment.get('created_utc'),
                comment.get('depth', 0),
                comment.get('is_submitter', False)
            ))
            if cursor.rowcount > 0:
                saved += 1
        except:
            continue
    
    conn.commit()
    conn.close()
    return saved

def search_posts(query=None, subreddit=None, author=None, min_score=None, 
                 start_date=None, end_date=None, post_type=None, limit=100):
    """Search posts with filters."""
    conn = get_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM posts WHERE 1=1"
    params = []
    
    if query:
        sql += " AND (title LIKE ? OR selftext LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%"])
    
    if subreddit:
        sql += " AND subreddit = ?"
        params.append(subreddit)
    
    if author:
        sql += " AND author = ?"
        params.append(author)
    
    if min_score:
        sql += " AND score >= ?"
        params.append(min_score)
    
    if start_date:
        sql += " AND created_utc >= ?"
        params.append(start_date)
    
    if end_date:
        sql += " AND created_utc <= ?"
        params.append(end_date)
    
    if post_type:
        sql += " AND post_type = ?"
        params.append(post_type)
    
    sql += " ORDER BY created_utc DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def search_comments(query=None, post_id=None, author=None, min_score=None, limit=100):
    """Search comments with filters."""
    conn = get_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM comments WHERE 1=1"
    params = []
    
    if query:
        sql += " AND body LIKE ?"
        params.append(f"%{query}%")
    
    if post_id:
        sql += " AND post_id = ?"
        params.append(post_id)
    
    if author:
        sql += " AND author = ?"
        params.append(author)
    
    if min_score:
        sql += " AND score >= ?"
        params.append(min_score)
    
    sql += " ORDER BY score DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_subreddit_stats(subreddit):
    """Get statistics for a subreddit."""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Post stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_posts,
            AVG(score) as avg_score,
            MAX(score) as max_score,
            SUM(num_comments) as total_comments,
            AVG(upvote_ratio) as avg_upvote_ratio
        FROM posts WHERE subreddit = ?
    """, (subreddit,))
    row = cursor.fetchone()
    if row:
        stats.update(dict(row))
    
    # Post type distribution
    cursor.execute("""
        SELECT post_type, COUNT(*) as count 
        FROM posts WHERE subreddit = ? 
        GROUP BY post_type
    """, (subreddit,))
    stats['post_types'] = {row['post_type']: row['count'] for row in cursor.fetchall()}
    
    # Top authors
    cursor.execute("""
        SELECT author, COUNT(*) as post_count, SUM(score) as total_score
        FROM posts WHERE subreddit = ? AND author != '[deleted]'
        GROUP BY author ORDER BY post_count DESC LIMIT 10
    """, (subreddit,))
    stats['top_authors'] = [dict(row) for row in cursor.fetchall()]
    
    # Activity by hour
    cursor.execute("""
        SELECT strftime('%H', created_utc) as hour, COUNT(*) as count
        FROM posts WHERE subreddit = ?
        GROUP BY hour ORDER BY hour
    """, (subreddit,))
    stats['hourly_activity'] = {row['hour']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    return stats

def get_all_subreddits():
    """Get list of all scraped subreddits."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT subreddit, COUNT(*) as post_count, 
               MAX(created_utc) as latest_post,
               MIN(created_utc) as oldest_post
        FROM posts GROUP BY subreddit ORDER BY post_count DESC
    """)
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

# Initialize on import
init_database()
