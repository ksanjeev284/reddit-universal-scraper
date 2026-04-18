"""
REST API Module - Expose Reddit Scraper data as a REST API
For integration with Metabase, Grafana, DreamFactory, and other tools.

Start with: python api/server.py
Or: uvicorn api.server:app --reload --port 8000
"""
import os
import sys
from pathlib import Path
from typing import Optional, List

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from export.database import (
    get_connection, search_posts, search_comments,
    get_subreddit_stats, get_all_subreddits,
    get_job_history, get_job_stats, get_database_info
)


API_KEY = os.getenv("X_API_KEY", "").strip()
api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)


def require_api_key(x_api_key: str = Security(api_key_header)):
    """Validate x-api-key when authentication is configured."""
    if not API_KEY:
        return None

    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing x-api-key")

    return x_api_key

# Create FastAPI app
app = FastAPI(
    title="Reddit Scraper API",
    description="REST API for Reddit Scraper data. Use with Metabase, Grafana, or any tool.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(require_api_key)] if API_KEY else []
)

# Enable CORS for external tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local tools
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HEALTH & INFO ---

@app.get("/", tags=["Info"])
def root():
    """API root - basic info."""
    return {
        "name": "Reddit Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "auth": "x-api-key" if API_KEY else "disabled",
        "endpoints": ["/posts", "/comments", "/subreddits", "/jobs", "/stats"]
    }


@app.get("/health", tags=["Info"])
def health_check():
    """Health check endpoint."""
    try:
        info = get_database_info()
        return {"status": "healthy", "database": info}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/info", tags=["Info"])
def database_info():
    """Get database info and table counts."""
    return get_database_info()


# --- POSTS ---

@app.get("/posts", tags=["Posts"])
def list_posts(
    q: Optional[str] = Query(None, description="Search query"),
    subreddit: Optional[str] = Query(None, description="Filter by subreddit"),
    author: Optional[str] = Query(None, description="Filter by author"),
    min_score: Optional[int] = Query(None, description="Minimum score"),
    post_type: Optional[str] = Query(None, description="Post type filter"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """
    Get posts with optional filters.
    
    Use for Grafana dashboards, Metabase queries, or custom integrations.
    """
    return search_posts(
        query=q,
        subreddit=subreddit,
        author=author,
        min_score=min_score,
        post_type=post_type,
        limit=limit
    )


@app.get("/posts/{post_id}", tags=["Posts"])
def get_post(post_id: str):
    """Get a single post by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(row)


# --- COMMENTS ---

@app.get("/comments", tags=["Comments"])
def list_comments(
    q: Optional[str] = Query(None, description="Search in comment body"),
    post_id: Optional[str] = Query(None, description="Filter by post ID"),
    author: Optional[str] = Query(None, description="Filter by author"),
    min_score: Optional[int] = Query(None, description="Minimum score"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """Get comments with optional filters."""
    return search_comments(
        query=q,
        post_id=post_id,
        author=author,
        min_score=min_score,
        limit=limit
    )


# --- SUBREDDITS ---

@app.get("/subreddits", tags=["Subreddits"])
def list_subreddits():
    """Get all scraped subreddits with post counts."""
    return get_all_subreddits()


@app.get("/subreddits/{subreddit}/stats", tags=["Subreddits"])
def subreddit_stats(subreddit: str):
    """Get detailed statistics for a subreddit."""
    stats = get_subreddit_stats(subreddit)
    if not stats.get('total_posts'):
        raise HTTPException(status_code=404, detail=f"No data for r/{subreddit}")
    return stats


# --- JOBS ---

@app.get("/jobs", tags=["Jobs"])
def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    target: Optional[str] = Query(None, description="Filter by target"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get job history."""
    return get_job_history(limit=limit, target=target, status=status)


@app.get("/jobs/stats", tags=["Jobs"])
def job_stats():
    """Get aggregated job statistics."""
    return get_job_stats()


# --- RAW SQL (for advanced users) ---

@app.get("/query", tags=["Advanced"])
def raw_query(
    sql: str = Query(..., description="SQL SELECT query"),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Execute a raw SQL SELECT query.
    
    ⚠️ Only SELECT queries allowed. Use for custom Grafana/Metabase queries.
    
    Example: /query?sql=SELECT title, score FROM posts ORDER BY score DESC
    """
    # Security: Only allow SELECT
    if not sql.strip().upper().startswith("SELECT"):
        raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
    
    # Add limit if not present
    if "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT {limit}"
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"query": sql, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {e}")


# --- GRAFANA COMPATIBLE ENDPOINTS ---

@app.get("/grafana/search", tags=["Grafana"])
def grafana_search():
    """Grafana SimpleJSON datasource - search endpoint."""
    subs = get_all_subreddits()
    return [s['subreddit'] for s in subs]


@app.post("/grafana/query", tags=["Grafana"])
def grafana_query(body: dict):
    """Grafana SimpleJSON datasource - query endpoint."""
    # Return time series data for Grafana
    results = []
    
    for target in body.get('targets', []):
        subreddit = target.get('target')
        if subreddit:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date(created_utc) as time, COUNT(*) as value
                FROM posts WHERE subreddit = ?
                GROUP BY date(created_utc)
                ORDER BY time
            """, (subreddit,))
            
            datapoints = [[row['value'], row['time']] for row in cursor.fetchall()]
            conn.close()
            
            results.append({
                "target": subreddit,
                "datapoints": datapoints
            })
    
    return results


# --- CLI ---

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Reddit Scraper API...")
    print("   📖 Docs: http://localhost:8000/docs")
    print("   📊 Use with Metabase, Grafana, or any REST client")
    uvicorn.run(app, host="0.0.0.0", port=8000)
