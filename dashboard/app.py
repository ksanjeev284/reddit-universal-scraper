"""
Reddit Scraper Dashboard - Streamlit Web UI
Run with: streamlit run dashboard/app.py
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime
import time
import os
import json
import signal

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analytics.sentiment import (
    analyze_posts_sentiment, extract_keywords, 
    calculate_engagement_metrics, find_best_posting_times
)
from search.query import search_all_data, advanced_search, get_top_posts

# Page config
st.set_page_config(
    page_title="Reddit Scraper Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #FF4500, #FF6B6B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 10px 20px;
        background-color: #262730;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

def load_subreddit_data(subreddit_path):
    """Load all data for a subreddit."""
    data = {}
    
    posts_file = subreddit_path / 'posts.csv'
    if posts_file.exists():
        data['posts'] = pd.read_csv(posts_file)
    
    comments_file = subreddit_path / 'comments.csv'
    if comments_file.exists():
        data['comments'] = pd.read_csv(comments_file)
    
    return data

def get_available_data():
    """Get list of scraped subreddits and users."""
    data_dir = Path(__file__).parent.parent / 'data'
    data = {'subreddits': [], 'users': []}
    
    if data_dir.exists():
        for sub_dir in data_dir.iterdir():
            if sub_dir.is_dir() and (sub_dir / 'posts.csv').exists():
                if sub_dir.name.startswith('u_'):
                    data['users'].append(sub_dir.name)
                elif sub_dir.name.startswith('r_'):
                    data['subreddits'].append(sub_dir.name)
                else:
                    # Fallback for old/other folders, treat as subreddit
                    data['subreddits'].append(sub_dir.name)
    
    # Sort lists
    data['subreddits'].sort()
    data['users'].sort()
    return data

def main():
    # Header
    st.markdown('<h1 class="main-header">🤖 Reddit Scraper Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("📊 Navigation")
    
    if st.sidebar.button("🔄 Refresh List"):
        st.rerun()
    
    # Get available data
    available_data = get_available_data()
    
    # Source Selector
    source_type = st.sidebar.radio(
        "Source Type",
        ["Subreddits", "Users"],
        horizontal=True
    )
    
    # Filter list based on type
    if source_type == "Users":
        options = available_data['users']
        prefix_len = 2 # 'u_'
        empty_msg = "No scraped users found."
        icon = "👤"
    else:
        options = available_data['subreddits']
        prefix_len = 2 # 'r_' is 2 chars, but some might not have it if legacy? 
        # Actually standard scraper uses r_.
        empty_msg = "No scraped subreddits found."
        icon = "📁"
    
    if not options:
        st.sidebar.warning(empty_msg)
        if source_type == "Subreddits":
            st.sidebar.code("python main.py <sub_name> ...")
        else:
            st.sidebar.code("python main.py <user> --user ...")
        return # Stop execution if no data for selected type
    
    # Selector
    selected_sub = st.sidebar.selectbox(
        f"Select {source_type[:-1]}", # "Select Subreddit" or "Select User"
        options,
        format_func=lambda x: f"{icon} {x[2:] if x.startswith(('r_', 'u_')) else x}"
    )
    
    # Load data
    data_dir = Path(__file__).parent.parent / 'data'
    sub_path = data_dir / selected_sub
    data = load_subreddit_data(sub_path)
    
    if 'posts' not in data:
        st.error("No posts data found!")
        return
    
    posts_df = data['posts']
    comments_df = data.get('comments', pd.DataFrame())
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Overview", "📈 Analytics", "🔍 Search", "💬 Comments", "⚙️ Scraper", "📋 Job History", "🔌 Integrations"
    ])
    
    with tab1:
        st.header(f"📊 Overview: {selected_sub}")
        
        # Metrics row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total Posts", len(posts_df))
        with col2:
            st.metric("Total Comments", len(comments_df))
        with col3:
            total_score = posts_df['score'].sum() if 'score' in posts_df else 0
            st.metric("Total Score", f"{total_score:,}")
        with col4:
            avg_score = posts_df['score'].mean() if 'score' in posts_df else 0
            st.metric("Avg Score", f"{avg_score:.1f}")
        with col5:
            media_count = posts_df['has_media'].sum() if 'has_media' in posts_df else 0
            st.metric("Media Posts", int(media_count))
        
        st.divider()
        
        # Post type distribution
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📝 Post Types")
            if 'post_type' in posts_df:
                type_counts = posts_df['post_type'].value_counts()
                st.bar_chart(type_counts)
        
        with col2:
            st.subheader("📅 Posts Over Time")
            if 'created_utc' in posts_df:
                posts_df['date'] = pd.to_datetime(posts_df['created_utc']).dt.date
                daily = posts_df.groupby('date').size()
                st.line_chart(daily)
        
        st.divider()
        
        # Top posts
        st.subheader("🔥 Top Posts by Score")
        if 'score' in posts_df:
            top_posts = posts_df.nlargest(10, 'score')[['title', 'score', 'num_comments', 'post_type', 'created_utc']]
            st.dataframe(top_posts)
    
    with tab2:
        st.header("📈 Analytics")
        
        # Sentiment Analysis
        st.subheader("😀 Sentiment Analysis")
        
        if st.button("Run Sentiment Analysis"):
            with st.spinner("Analyzing sentiment..."):
                posts_list = posts_df.to_dict('records')
                analyzed_posts, sentiment_counts = analyze_posts_sentiment(posts_list)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Positive", sentiment_counts['positive'], delta=None)
                col2.metric("Neutral", sentiment_counts['neutral'], delta=None)
                col3.metric("Negative", sentiment_counts['negative'], delta=None)
                
                # Pie chart
                sentiment_df = pd.DataFrame({
                    'Sentiment': ['Positive', 'Neutral', 'Negative'],
                    'Count': [sentiment_counts['positive'], sentiment_counts['neutral'], sentiment_counts['negative']]
                })
                st.bar_chart(sentiment_df.set_index('Sentiment'))
        
        st.divider()
        
        # Keywords
        st.subheader("☁️ Top Keywords")
        texts = posts_df['title'].tolist()
        if 'selftext' in posts_df:
            texts.extend(posts_df['selftext'].dropna().tolist())
        
        keywords = extract_keywords(texts, top_n=30)
        
        if keywords:
            kw_df = pd.DataFrame(keywords, columns=['Word', 'Count'])
            st.bar_chart(kw_df.set_index('Word').head(20))
        
        st.divider()
        
        # Best posting times
        st.subheader("⏰ Best Posting Times")
        
        if 'created_utc' in posts_df:
            timing_data = find_best_posting_times(posts_df.to_dict('records'))
            
            if timing_data['best_hours']:
                st.write("**Best Hours to Post:**")
                for hour, avg_score in timing_data['best_hours']:
                    st.write(f"• {hour}:00 - Avg Score: {avg_score:.1f}")
            
            if timing_data['best_days']:
                st.write("**Best Days to Post:**")
                for day, avg_score in timing_data['best_days']:
                    st.write(f"• {day} - Avg Score: {avg_score:.1f}")
    
    with tab3:
        st.header("🔍 Search Posts")
        
        # Search form
        col1, col2 = st.columns([3, 1])
        
        with col1:
            search_query = st.text_input("Search query", placeholder="Enter keywords...")
        
        with col2:
            min_score = st.number_input("Min Score", min_value=0, value=0)
        
        col3, col4, col5 = st.columns(3)
        
        with col3:
            if 'post_type' in posts_df:
                post_types = ['All'] + posts_df['post_type'].dropna().unique().tolist()
                selected_type = st.selectbox("Post Type", post_types)
        
        with col4:
            if 'author' in posts_df:
                authors = ['All'] + posts_df['author'].dropna().unique().tolist()[:50]
                selected_author = st.selectbox("Author", authors)
        
        with col5:
            sort_by = st.selectbox("Sort by", ['score', 'num_comments', 'created_utc'])
        
        # Search button
        if st.button("🔍 Search"):
            filtered = posts_df.copy()
            
            if search_query:
                mask = filtered['title'].str.contains(search_query, case=False, na=False)
                if 'selftext' in filtered:
                    mask |= filtered['selftext'].str.contains(search_query, case=False, na=False)
                filtered = filtered[mask]
            
            if min_score > 0:
                filtered = filtered[filtered['score'] >= min_score]
            
            if selected_type != 'All' and 'post_type' in filtered:
                filtered = filtered[filtered['post_type'] == selected_type]
            
            if selected_author != 'All' and 'author' in filtered:
                filtered = filtered[filtered['author'] == selected_author]
            
            filtered = filtered.sort_values(sort_by, ascending=False)
            
            st.write(f"Found {len(filtered)} results")
            st.dataframe(filtered[['title', 'score', 'num_comments', 'post_type', 'author', 'created_utc']].head(50))
    
    with tab4:
        st.header("💬 Comments Analysis")
        
        if len(comments_df) == 0:
            st.warning("No comments data found for this subreddit")
        else:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Comments", len(comments_df))
            with col2:
                avg_score = comments_df['score'].mean() if 'score' in comments_df else 0
                st.metric("Avg Score", f"{avg_score:.1f}")
            with col3:
                unique_authors = comments_df['author'].nunique() if 'author' in comments_df else 0
                st.metric("Unique Commenters", unique_authors)
            
            st.divider()
            
            # Top comments
            st.subheader("🔥 Top Comments by Score")
            if 'score' in comments_df:
                top_comments = comments_df.nlargest(10, 'score')[['body', 'score', 'author', 'created_utc']]
                for _, row in top_comments.iterrows():
                    with st.expander(f"⬆️ {row['score']} - by u/{row['author']}"):
                        st.write(row['body'][:500])
            
            st.divider()
            
            # Top commenters
            st.subheader("👥 Top Commenters")
            if 'author' in comments_df:
                top_authors = comments_df['author'].value_counts().head(10)
                st.bar_chart(top_authors)
    
    with tab5:
        st.header("⚙️ Scraper Controls")
        
        # Persistence logic
        import json
        import signal
        
        JOB_FILE = Path("active_job.json")
        LOG_DIR = Path("logs")
        LOG_DIR.mkdir(exist_ok=True)

        def get_active_job():
            if JOB_FILE.exists():
                try:
                    with open(JOB_FILE, "r") as f:
                        return json.load(f)
                except:
                    return None
            return None

        # Check for active job
        active_job = get_active_job()
        
        # Monitor Section (Always visible if job exists)
        if active_job:
            st.info(f"🔄 **Scraping in Progress**: {active_job.get('target', 'Unknown')} (PID: {active_job.get('pid')})")
            
            # Stop button
            if st.button("🛑 Stop Scraping"):
                try:
                    os.kill(active_job['pid'], signal.SIGTERM)
                    st.warning("Stopped process.")
                except:
                    st.warning("Process already stopped.")
                
                if JOB_FILE.exists():
                    JOB_FILE.unlink()
                st.rerun()
            
            # Read logs
            log_file = Path(active_job['log_file'])
            if log_file.exists():
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                
                # Parse metrics from lines
                posts_saved = 0
                comments_count = 0
                images_count = 0
                videos_count = 0
                found_posts = 0
                processed_posts = 0
                
                for line in lines:
                    import re
                    # Progress: X/Y (Saved posts)
                    m = re.search(r'Progress: (\d+)/(\d+)', line)
                    if m: posts_saved = int(m.group(1))
                    
                    # Saved X posts
                    m = re.search(r'Saved (\d+)', line)
                    if m: posts_saved += int(m.group(1))
                    
                    # Found X posts
                    m = re.search(r'Found (\d+) posts', line)
                    if m: found_posts += int(m.group(1))
                    
                    # Processed posts (Fetching comments)
                    if "Fetching comments for:" in line: 
                        processed_posts += 1
                    
                    # Comments: X (Summary)
                    m = re.search(r'Comments:\s*(\d+)', line)
                    if m: 
                        comments_count = int(m.group(1))
                    else:
                        # Incremental comments
                        m = re.search(r'\+ Scraped (\d+) comments', line)
                        if m: comments_count += int(m.group(1))
                    
                    # Images/Videos (Summary line)
                    m = re.search(r'Images:\s*(\d+).*Videos:\s*(\d+)', line)
                    if m:
                        images_count = int(m.group(1))
                        videos_count = int(m.group(2))
                    
                    # Images/Videos (Real-time line)
                    m = re.search(r'\+ Downloaded: (\d+) images, (\d+) videos', line)
                    if m:
                        images_count += int(m.group(1))
                        videos_count += int(m.group(2))

                # Display Metrics
                col1, col2, col3, col4 = st.columns(4)
                
                # Posts Metric Logic
                if posts_saved > 0:
                     col1.metric("📊 Posts", f"{posts_saved} (Found {found_posts})")
                elif found_posts > 0:
                     col1.metric("📊 Posts", f"Processing: {processed_posts}/{found_posts}")
                else:
                     col1.metric("📊 Posts", "0")
                
                col2.metric("💬 Comments", comments_count)
                col3.metric("🖼️ Images", images_count)
                col4.metric("🎬 Videos", videos_count)
                
                # Show latest logs
                st.code("".join(lines[-20:]), language="text")
                
                # Auto-refresh
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Log file not found.")
                
        else:
            # Start New Scrape UI
            st.subheader("🚀 Start New Scrape")
            
            col1, col2 = st.columns(2)
            with col1:
                new_sub = st.text_input("Subreddit/User name", placeholder="e.g. python")
                is_user = st.checkbox("Is a User (not subreddit)")
            
            with col2:
                limit = st.number_input("Post Limit", min_value=10, max_value=5000, value=100)
                mode = st.selectbox("Mode", ['full', 'history'])
            
            no_media = st.checkbox("Skip media download")
            no_comments = st.checkbox("Skip comments")
            
            if st.button("🚀 Start Scraping"):
                if not new_sub:
                    st.error("Please enter a subreddit/user name!")
                else:
                    target_cmd = ["python", "-u", "main.py", new_sub, "--mode", mode, "--limit", str(limit)]
                    if is_user: target_cmd.append("--user")
                    if no_media: target_cmd.append("--no-media")
                    if no_comments: target_cmd.append("--no-comments")
                    
                    # Start background process
                    import subprocess
                    import os
                    
                    job_id = f"job_{int(time.time())}"
                    log_file = LOG_DIR / f"{job_id}.log"
                    
                    try:
                        with open(log_file, "w", encoding="utf-8") as f:
                            env = os.environ.copy()
                            env['PYTHONIOENCODING'] = 'utf-8'
                            env['PYTHONUNBUFFERED'] = '1'
                            
                            process = subprocess.Popen(
                                target_cmd,
                                stdout=f,
                                stderr=subprocess.STDOUT,
                                cwd=str(Path(__file__).parent.parent),
                                env=env
                            )
                        
                        # Save job state
                        job_info = {
                            "job_id": job_id,
                            "pid": process.pid,
                            "target": new_sub,
                            "log_file": str(log_file.absolute()),
                            "start_time": time.time()
                        }
                        
                        with open(JOB_FILE, "w") as f:
                            json.dump(job_info, f)
                            
                        st.success(f"Started job {job_id}!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Failed to start: {e}")
        
        st.divider()
        
        # Export options
        st.subheader("📤 Export Data")
        
        export_format = st.selectbox("Format", ['CSV', 'JSON', 'Excel'])
        
        if st.button("📥 Download Posts"):
            if export_format == 'CSV':
                csv = posts_df.to_csv(index=False)
                st.download_button(
                    "Download CSV",
                    csv,
                    f"{selected_sub}_posts.csv",
                    "text/csv"
                )
            elif export_format == 'JSON':
                json_data = posts_df.to_json(orient='records', indent=2)
                st.download_button(
                    "Download JSON",
                    json_data,
                    f"{selected_sub}_posts.json",
                    "application/json"
                )
        
        st.divider()
        
        # Media Export
        st.subheader("🖼️ Media Export")
        
        media_dir = Path(f"data/{selected_sub}/media")
        if media_dir.exists():
            images_dir = media_dir / "images"
            videos_dir = media_dir / "videos"
            
            images = list(images_dir.glob("*")) if images_dir.exists() else []
            videos = list(videos_dir.glob("*")) if videos_dir.exists() else []
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📷 Images", len(images))
            with col2:
                st.metric("🎬 Videos", len(videos))
            with col3:
                total_size = sum(f.stat().st_size for f in images + videos) / (1024 * 1024)
                st.metric("💾 Total Size", f"{total_size:.1f} MB")
            
            if images or videos:
                if st.button("📦 Download All Media (ZIP)"):
                    import zipfile
                    import io
                    
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for img in images:
                            zf.write(img, f"images/{img.name}")
                        for vid in videos:
                            zf.write(vid, f"videos/{vid.name}")
                    
                    st.download_button(
                        "💾 Download ZIP",
                        zip_buffer.getvalue(),
                        f"{selected_sub}_media.zip",
                        "application/zip"
                    )
                    st.success(f"✅ ZIP ready: {len(images)} images, {len(videos)} videos")
                
                # Preview recent images
                if images:
                    st.write("**Recent Images:**")
                    preview_cols = st.columns(min(5, len(images)))
                    for i, img in enumerate(images[:5]):
                        with preview_cols[i]:
                            try:
                                st.image(str(img), width=100)
                            except:
                                st.text(img.name[:15])
        else:
            st.info(f"No media found for {selected_sub}. Run with `--mode full` to download media.")
    
    with tab6:
        st.header("📋 Job History")
        
        try:
            from export.database import get_job_history, get_job_stats
            
            # Job stats
            stats = get_job_stats()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Jobs", stats.get('total_jobs', 0))
            with col2:
                st.metric("Completed", stats.get('completed', 0))
            with col3:
                st.metric("Failed", stats.get('failed', 0))
            with col4:
                avg_dur = stats.get('avg_duration')
                st.metric("Avg Duration", f"{avg_dur:.1f}s" if avg_dur else "-")
            
            st.divider()
            
            # Job history table
            st.subheader("Recent Jobs")
            
            col1, col2 = st.columns(2)
            with col1:
                filter_status = st.selectbox("Filter by Status", ['All', 'completed', 'failed', 'running'])
            with col2:
                limit = st.number_input("Show last N jobs", min_value=10, max_value=100, value=20)
            
            status_filter = None if filter_status == 'All' else filter_status
            jobs = get_job_history(limit=limit, status=status_filter)
            
            if jobs:
                jobs_df = pd.DataFrame(jobs)
                # Format for display
                display_cols = ['job_id', 'target', 'mode', 'status', 'posts_scraped', 
                               'comments_scraped', 'duration_seconds', 'started_at', 'dry_run']
                display_cols = [c for c in display_cols if c in jobs_df.columns]
                st.dataframe(jobs_df[display_cols])
                
                # Success rate chart
                st.subheader("Success Rate")
                if 'status' in jobs_df.columns:
                    status_counts = jobs_df['status'].value_counts()
                    st.bar_chart(status_counts)
            else:
                st.info("No job history found. Run some scrapes first!")
        
        except Exception as e:
            st.error(f"Failed to load job history: {e}")
            st.info("Make sure the database is initialized.")
    
    with tab7:
        st.header("🔌 Integrations & Settings")
        
        # REST API Section
        st.subheader("🚀 REST API")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            api_port = st.number_input("API Port", value=8000, min_value=1000, max_value=65535)
        
        with col2:
            if st.button("🚀 Start API Server"):
                st.info("Starting API server in background...")
                import subprocess
                try:
                    # Start API in background (non-blocking)
                    subprocess.Popen(
                        ["python", "main.py", "--api"],
                        cwd=str(Path(__file__).parent.parent),
                        creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                    )
                    st.success(f"✅ API server starting on port {api_port}!")
                    st.markdown(f"**Open:** [http://localhost:{api_port}/docs](http://localhost:{api_port}/docs)")
                except Exception as e:
                    st.error(f"❌ Failed to start API: {e}")
        
        with col3:
            # Check if API is running
            import requests
            try:
                resp = requests.get(f"http://localhost:{api_port}/health", timeout=1)
                if resp.status_code == 200:
                    st.success("🟢 API is running")
                else:
                    st.warning("🟡 API responded but not healthy")
            except:
                st.info("🔴 API not running")
        
        st.markdown("""
        **Available Endpoints:**
        | Endpoint | Description |
        |----------|-------------|
        | `/posts` | List posts with filters |
        | `/comments` | List comments |
        | `/subreddits` | All scraped subreddits |
        | `/jobs` | Job history |
        | `/query?sql=...` | Raw SQL queries |
        | `/docs` | Interactive Swagger UI |
        """)
        
        st.divider()
        
        # External Tools
        st.subheader("📊 External Tools Integration")
        
        tool_tabs = st.tabs(["📈 Metabase", "📊 Grafana", "🔗 DreamFactory", "🧦 DuckDB"])
        
        with tool_tabs[0]:
            st.markdown("""
            **Metabase Setup:**
            1. Start API: `python main.py --api`
            2. In Metabase: New Question → Native Query
            3. Use HTTP datasource with `http://localhost:8000`
            4. Query: `/posts?subreddit=python&limit=100`
            
            **Or use raw SQL:**
            ```
            /query?sql=SELECT title, score FROM posts ORDER BY score DESC
            ```
            """)
        
        with tool_tabs[1]:
            st.markdown("""
            **Grafana Setup:**
            1. Install "JSON API" or "Infinity" plugin
            2. Add datasource: `http://localhost:8000`
            3. Use `/grafana/query` for time-series
            
            **Example Panel Query:**
            ```sql
            SELECT date(created_utc) as time, COUNT(*) as posts 
            FROM posts GROUP BY date(created_utc)
            ```
            """)
        
        with tool_tabs[2]:
            st.markdown("""
            **DreamFactory Setup:**
            1. Point to SQLite file: `data/reddit_scraper.db`
            2. Or use REST API: `http://localhost:8000`
            3. Auto-generates API for all tables
            """)
        
        with tool_tabs[3]:
            st.markdown("""
            **DuckDB (Analytics):**
            1. Export to Parquet first (see below)
            2. Query directly:
            ```python
            import duckdb
            duckdb.query("SELECT * FROM 'data/parquet/*.parquet'").df()
            ```
            """)
        
        st.divider()
        
        # Parquet Export
        st.subheader("📦 Parquet Export")
        
        col1, col2 = st.columns(2)
        with col1:
            export_sub = st.selectbox("Select subreddit to export", subreddits, key="parquet_export")
        with col2:
            if st.button("📦 Export to Parquet"):
                target_name = export_sub.replace('r_', '').replace('u_', '')
                with st.spinner(f"Exporting {target_name} to Parquet..."):
                    import subprocess
                    result = subprocess.run(
                        ["python", "main.py", "--export-parquet", target_name],
                        capture_output=True,
                        text=True,
                        cwd=str(Path(__file__).parent.parent)
                    )
                    if result.returncode == 0:
                        st.success(f"✅ Exported {target_name} to Parquet!")
                        st.code(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
                    else:
                        st.error(f"❌ Export failed: {result.stderr}")
        
        # List existing parquet files
        parquet_dir = Path("data/parquet")
        if parquet_dir.exists():
            parquet_files = list(parquet_dir.glob("*.parquet"))
            if parquet_files:
                st.write("**Existing Parquet files:**")
                for f in parquet_files[:10]:
                    size_mb = f.stat().st_size / (1024 * 1024)
                    st.text(f"  • {f.name} ({size_mb:.2f} MB)")
        
        st.divider()
        
        # Database Maintenance
        st.subheader("🛠️ Database Maintenance")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Backup Database"):
                with st.spinner("Creating backup..."):
                    import subprocess
                    result = subprocess.run(
                        ["python", "main.py", "--backup"],
                        capture_output=True,
                        text=True,
                        cwd=str(Path(__file__).parent.parent)
                    )
                    if result.returncode == 0:
                        st.success("✅ Database backed up!")
                        st.code(result.stdout[-300:] if len(result.stdout) > 300 else result.stdout)
                    else:
                        st.error(f"❌ Backup failed: {result.stderr}")
        
        with col2:
            if st.button("🧹 Vacuum/Optimize"):
                with st.spinner("Optimizing database..."):
                    import subprocess
                    result = subprocess.run(
                        ["python", "main.py", "--vacuum"],
                        capture_output=True,
                        text=True,
                        cwd=str(Path(__file__).parent.parent)
                    )
                    if result.returncode == 0:
                        st.success("✅ Database optimized!")
                        st.code(result.stdout[-300:] if len(result.stdout) > 300 else result.stdout)
                    else:
                        st.error(f"❌ Vacuum failed: {result.stderr}")
        
        with col3:
            try:
                from export.database import get_database_info
                db_info = get_database_info()
                st.metric("DB Size", f"{db_info.get('size_mb', 0):.2f} MB")
            except:
                st.metric("DB Size", "N/A")
        
        # Show backup files
        backup_dir = Path("data/backups")
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("*.db"), reverse=True)[:5]
            if backups:
                st.write("**Recent Backups:**")
                for b in backups:
                    size_mb = b.stat().st_size / (1024 * 1024)
                    st.text(f"  • {b.name} ({size_mb:.2f} MB)")
        
        st.divider()
        
        # Plugin Configuration
        st.subheader("🔌 Plugins")
        
        try:
            from plugins import load_plugins
            plugins = load_plugins()
            
            if plugins:
                st.write("**Available Plugins:**")
                for plugin in plugins:
                    status = "✅" if plugin.enabled else "❌"
                    st.markdown(f"{status} **{plugin.name}** - {plugin.description}")
                
                st.info("💡 Enable plugins when scraping: `python main.py <target> --plugins`")
            else:
                st.warning("No plugins found in plugins/ directory")
        except Exception as e:
            st.error(f"Plugin loading error: {e}")
        
        st.divider()
        
        # Quick Commands Reference
        st.subheader("📋 Quick Commands")
        st.code("""
# Start REST API
python main.py --api

# Export to Parquet
python main.py --export-parquet <subreddit>

# Backup database
python main.py --backup

# Scrape with plugins
python main.py <target> --plugins

# Dry run (test without saving)
python main.py <target> --dry-run
        """, language="bash")

if __name__ == "__main__":
    main()
