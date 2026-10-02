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
    
    # Job history table for observability
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE,
            target TEXT,
            is_user BOOLEAN DEFAULT 0,
            mode TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            duration_seconds REAL,
            posts_scraped INTEGER DEFAULT 0,
            comments_scraped INTEGER DEFAULT 0,
            media_downloaded INTEGER DEFAULT 0,
            errors TEXT,
            error_count INTEGER DEFAULT 0,
            dry_run BOOLEAN DEFAULT 0
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
    print("Database initialized")

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

# --- JOB HISTORY FUNCTIONS ---

def start_job_record(target, mode, is_user=False, dry_run=False):
    """
    Start tracking a new scrape job.
    
    Returns:
        job_id: Unique identifier for the job
    """
    import uuid
    
    conn = get_connection()
    cursor = conn.cursor()
    
    job_id = str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO job_history (job_id, target, is_user, mode, status, started_at, dry_run)
        VALUES (?, ?, ?, ?, 'running', ?, ?)
    """, (job_id, target, is_user, mode, started_at, dry_run))
    
    conn.commit()
    conn.close()
    
    print(f"📋 Job started: {job_id}")
    return job_id

def complete_job_record(job_id, status, posts=0, comments=0, media=0, errors=None):
    """
    Complete a job record with results.
    
    Args:
        job_id: Job ID from start_job_record
        status: 'completed' or 'failed'
        posts: Number of posts scraped
        comments: Number of comments scraped
        media: Number of media files downloaded
        errors: Error message if failed
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    completed_at = datetime.now().isoformat()
    
    # Calculate duration
    cursor.execute("SELECT started_at FROM job_history WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    
    duration = 0
    error_count = 0
    if row:
        started = datetime.fromisoformat(row['started_at'])
        duration = (datetime.now() - started).total_seconds()
    
    if errors:
        error_count = 1
    
    cursor.execute("""
        UPDATE job_history 
        SET status = ?, completed_at = ?, duration_seconds = ?,
            posts_scraped = ?, comments_scraped = ?, media_downloaded = ?,
            errors = ?, error_count = ?
        WHERE job_id = ?
    """, (status, completed_at, duration, posts, comments, media, errors, error_count, job_id))
    
    conn.commit()
    conn.close()
    
    if status == 'completed':
        print(f"✅ Job {job_id} completed: {posts} posts, {comments} comments in {duration:.1f}s")
    else:
        print(f"❌ Job {job_id} failed: {errors}")

def get_job_history(limit=50, target=None, status=None):
    """Get recent job history."""
    conn = get_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM job_history WHERE 1=1"
    params = []
    
    if target:
        sql += " AND target = ?"
        params.append(target)
    
    if status:
        sql += " AND status = ?"
        params.append(status)
    
    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_job_stats():
    """Get aggregated job statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    stats = {}
    
    # Overall counts
    cursor.execute("""
        SELECT 
            COUNT(*) as total_jobs,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
            AVG(duration_seconds) as avg_duration,
            SUM(posts_scraped) as total_posts,
            SUM(comments_scraped) as total_comments
        FROM job_history
    """)
    row = cursor.fetchone()
    if row:
        stats.update(dict(row))
    
    # Recent jobs
    cursor.execute("""
        SELECT target, status, duration_seconds, posts_scraped, started_at
        FROM job_history ORDER BY started_at DESC LIMIT 10
    """)
    stats['recent_jobs'] = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return stats

def print_job_history(limit=20):
    """Pretty print job history."""
    jobs = get_job_history(limit)
    
    print("\n📋 Job History")
    print("-" * 80)
    print(f"{'ID':<10} {'Target':<15} {'Status':<10} {'Posts':<8} {'Duration':<10} {'Started':<20}")
    print("-" * 80)
    
    for job in jobs:
        status_icon = "✅" if job['status'] == 'completed' else "❌" if job['status'] == 'failed' else "🔄"
        duration = f"{job['duration_seconds']:.1f}s" if job['duration_seconds'] else "-"
        started = job['started_at'][:19] if job['started_at'] else "-"
        dry = " (dry)" if job['dry_run'] else ""
        
        print(f"{status_icon} {job['job_id']:<8} {job['target']:<15} {job['status']:<10} "
              f"{job['posts_scraped']:<8} {duration:<10} {started}{dry}")
    
    print("-" * 80)
    
    stats = get_job_stats()
    success_rate = (stats['completed'] / stats['total_jobs'] * 100) if stats['total_jobs'] else 0
    print(f"\n📊 Stats: {stats['total_jobs']} jobs | {success_rate:.0f}% success | "
          f"{stats['total_posts'] or 0} posts total")

# --- SQLITE MAINTENANCE FUNCTIONS ---

def enable_auto_vacuum():
    """Enable incremental auto-vacuum on SQLite database."""
    conn = get_connection()
    try:
        conn.execute("PRAGMA auto_vacuum = INCREMENTAL")
        conn.execute("PRAGMA incremental_vacuum")
        conn.commit()
        print("✅ Auto-vacuum enabled")
    finally:
        conn.close()

def vacuum_database():
    """Run VACUUM to optimize and compact the database."""
    conn = get_connection()
    try:
        print("🔧 Running VACUUM...")
        conn.execute("VACUUM")
        print("✅ Database optimized")
    finally:
        conn.close()

def backup_database(backup_path=None):
    """
    Create a backup of the SQLite database.
    
    Args:
        backup_path: Optional custom backup path
    
    Returns:
        Path to the backup file
    """
    import shutil
    
    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"reddit_scraper_{timestamp}.db"
    
    shutil.copy2(DB_PATH, backup_path)
    
    # Get file size
    size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
    print(f"✅ Backup created: {backup_path} ({size_mb:.2f} MB)")
    
    return str(backup_path)

def get_database_info():
    """Get database size and table info."""
    info = {}
    
    # File size
    if DB_PATH.exists():
        info['size_mb'] = DB_PATH.stat().st_size / (1024 * 1024)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table counts
    tables = ['posts', 'comments', 'job_history', 'alerts', 'subreddits']
    info['tables'] = {}
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            info['tables'][table] = cursor.fetchone()[0]
        except:
            info['tables'][table] = 0
    
    conn.close()
    return info

# Initialize on import
init_database()

