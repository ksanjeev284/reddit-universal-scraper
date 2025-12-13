"""
Reddit Scraper Dashboard - Streamlit Web UI
Run with: streamlit run dashboard/app.py
"""
import streamlit as st
import pandas as pd
from pathlib import Path
import sys
from datetime import datetime

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

def get_available_subreddits():
    """Get list of scraped subreddits."""
    data_dir = Path(__file__).parent.parent / 'data'
    subs = []
    
    if data_dir.exists():
        for sub_dir in data_dir.iterdir():
            if sub_dir.is_dir() and (sub_dir / 'posts.csv').exists():
                subs.append(sub_dir.name)
    
    return sorted(subs)

def main():
    # Header
    st.markdown('<h1 class="main-header">🤖 Reddit Scraper Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("📊 Navigation")
    
    # Get available subreddits
    subreddits = get_available_subreddits()
    
    if not subreddits:
        st.warning("No scraped data found! Run the scraper first:")
        st.code("python main.py <subreddit> --mode full --limit 100")
        return
    
    # Subreddit selector
    selected_sub = st.sidebar.selectbox(
        "Select Subreddit",
        subreddits,
        format_func=lambda x: f"📁 {x}"
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", "📈 Analytics", "🔍 Search", "💬 Comments", "⚙️ Scraper"
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
            st.dataframe(top_posts, use_container_width=True)
    
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
            st.dataframe(filtered[['title', 'score', 'num_comments', 'post_type', 'author', 'created_utc']].head(50), use_container_width=True)
    
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
            st.info(f"Run this command in terminal:")
            cmd = f"python main.py {new_sub} --mode {mode} --limit {limit}"
            if is_user:
                cmd += " --user"
            if no_media:
                cmd += " --no-media"
            if no_comments:
                cmd += " --no-comments"
            st.code(cmd)
        
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

if __name__ == "__main__":
    main()
