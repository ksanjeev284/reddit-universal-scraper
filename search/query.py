"""
Search & Query module - Search and filter scraped data
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import re

def search_csv(filepath, query=None, column=None, min_score=None, max_score=None,
               start_date=None, end_date=None, post_type=None, author=None, limit=50):
    """
    Search within a CSV file with various filters.
    
    Args:
        filepath: Path to CSV file
        query: Text to search for
        column: Specific column to search in (default: all text columns)
        min_score: Minimum score filter
        max_score: Maximum score filter
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        post_type: Filter by post type (image, video, text, etc.)
        author: Filter by author
        limit: Maximum results to return
    
    Returns:
        DataFrame with matching results
    """
    if not Path(filepath).exists():
        print(f"❌ File not found: {filepath}")
        return pd.DataFrame()
    
    df = pd.read_csv(filepath)
    
    # Text search
    if query:
        if column and column in df.columns:
            mask = df[column].astype(str).str.contains(query, case=False, na=False)
        else:
            # Search in all text columns
            text_cols = ['title', 'selftext', 'body']
            mask = pd.Series([False] * len(df))
            for col in text_cols:
                if col in df.columns:
                    mask |= df[col].astype(str).str.contains(query, case=False, na=False)
        df = df[mask]
    
    # Score filter
    if min_score is not None and 'score' in df.columns:
        df = df[df['score'] >= min_score]
    if max_score is not None and 'score' in df.columns:
        df = df[df['score'] <= max_score]
    
    # Date filter
    if 'created_utc' in df.columns:
        if start_date:
            df = df[df['created_utc'] >= start_date]
        if end_date:
            df = df[df['created_utc'] <= end_date]
    
    # Post type filter
    if post_type and 'post_type' in df.columns:
        df = df[df['post_type'] == post_type]
    
    # Author filter
    if author and 'author' in df.columns:
        df = df[df['author'] == author]
    
    return df.head(limit)

def search_all_data(data_dir='data', query=None, **kwargs):
    """
    Search across all scraped data.
    
    Args:
        data_dir: Data directory path
        query: Text to search for
        **kwargs: Additional filters passed to search_csv
    
    Returns:
        Dictionary with results from each subreddit
    """
    results = {}
    data_path = Path(data_dir)
    
    if not data_path.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return results
    
    # Find all posts.csv files
    for sub_dir in data_path.iterdir():
        if sub_dir.is_dir():
            posts_file = sub_dir / 'posts.csv'
            if posts_file.exists():
                df = search_csv(str(posts_file), query=query, **kwargs)
                if len(df) > 0:
                    results[sub_dir.name] = df
    
    # Also check legacy format
    for csv_file in data_path.glob('*.csv'):
        if csv_file.stem not in [r.replace('r_', '').replace('u_', '') for r in results.keys()]:
            df = search_csv(str(csv_file), query=query, **kwargs)
            if len(df) > 0:
                results[csv_file.stem] = df
    
    return results

def print_search_results(results, show_preview=True):
    """Pretty print search results."""
    total = sum(len(df) for df in results.values())
    
    print(f"\n🔍 Found {total} results across {len(results)} sources\n")
    print("=" * 70)
    
    for source, df in results.items():
        print(f"\n📁 {source} ({len(df)} matches)")
        print("-" * 50)
        
        for _, row in df.iterrows():
            title = str(row.get('title', row.get('body', 'N/A')))[:60]
            score = row.get('score', 0)
            date = str(row.get('created_utc', ''))[:10]
            
            print(f"  [{score:>4}⬆] {title}...")
            if show_preview and 'selftext' in row and row['selftext']:
                preview = str(row['selftext'])[:100].replace('\n', ' ')
                print(f"         └─ {preview}...")
            print()

def advanced_search(data_dir='data', query=None, regex=False, sort_by='score', 
                   ascending=False, **kwargs):
    """
    Advanced search with regex support and sorting.
    
    Args:
        data_dir: Data directory path
        query: Search query (text or regex pattern)
        regex: Treat query as regex pattern
        sort_by: Column to sort results by
        ascending: Sort ascending (default: descending)
        **kwargs: Additional filters
    
    Returns:
        Combined DataFrame of all results
    """
    all_results = []
    data_path = Path(data_dir)
    
    for sub_dir in data_path.iterdir():
        if sub_dir.is_dir():
            posts_file = sub_dir / 'posts.csv'
            if posts_file.exists():
                df = pd.read_csv(posts_file)
                df['source'] = sub_dir.name
                all_results.append(df)
    
    if not all_results:
        return pd.DataFrame()
    
    combined = pd.concat(all_results, ignore_index=True)
    
    # Apply query
    if query:
        if regex:
            pattern = query
        else:
            pattern = re.escape(query)
        
        mask = pd.Series([False] * len(combined))
        for col in ['title', 'selftext']:
            if col in combined.columns:
                mask |= combined[col].astype(str).str.contains(pattern, case=False, na=False, regex=True)
        combined = combined[mask]
    
    # Apply other filters
    if kwargs.get('min_score') and 'score' in combined.columns:
        combined = combined[combined['score'] >= kwargs['min_score']]
    
    if kwargs.get('author') and 'author' in combined.columns:
        combined = combined[combined['author'] == kwargs['author']]
    
    if kwargs.get('post_type') and 'post_type' in combined.columns:
        combined = combined[combined['post_type'] == kwargs['post_type']]
    
    # Sort
    if sort_by in combined.columns:
        combined = combined.sort_values(sort_by, ascending=ascending)
    
    limit = kwargs.get('limit', 100)
    return combined.head(limit)

def get_top_posts(data_dir='data', n=10, by='score'):
    """Get top N posts across all scraped data."""
    df = advanced_search(data_dir, sort_by=by, ascending=False, limit=n)
    return df

def get_recent_posts(data_dir='data', n=10):
    """Get most recent posts across all scraped data."""
    df = advanced_search(data_dir, sort_by='created_utc', ascending=False, limit=n)
    return df

def find_author_posts(data_dir='data', author=None):
    """Find all posts by a specific author."""
    return advanced_search(data_dir, author=author, limit=1000)

def export_search_results(results, output_path, format='csv'):
    """Export search results to file."""
    if isinstance(results, dict):
        combined = pd.concat(results.values(), ignore_index=True)
    else:
        combined = results
    
    if format == 'csv':
        combined.to_csv(output_path, index=False)
    elif format == 'json':
        combined.to_json(output_path, orient='records', indent=2)
    elif format == 'excel':
        combined.to_excel(output_path, index=False)
    
    print(f"💾 Exported {len(combined)} results to {output_path}")
