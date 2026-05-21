# 🤖 Universal Reddit Scraper Suite

[![Docker Build & Publish](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml)

A full-featured Reddit scraper with a web dashboard, REST API, scheduled scraping, plugins, sentiment analysis, and more. **No Reddit API keys required.**

---

## 📖 Table of Contents

1. [Project Overview](#-project-overview)
2. [Project Structure](#-project-structure)
3. [File-by-File Breakdown](#-file-by-file-breakdown)
4. [How the Files Interact](#-how-the-files-interact)
5. [Recommended Reading Order](#-recommended-reading-order-for-new-developers)
6. [How to Run Locally](#-how-to-run-locally)
7. [Dependencies](#-dependencies)

---

## 🧠 Project Overview

This project scrapes Reddit posts, comments, images, and videos — without needing an official Reddit API key. It uses Reddit's public JSON endpoints and RSS feeds.

**What it can do:**
- Scrape any subreddit or user profile (posts, comments, media)
- Show scraped data in a live web dashboard (Streamlit)
- Expose data via a REST API (FastAPI) for tools like Metabase or Grafana
- Run scrapes on a schedule (cron-style)
- Send alerts to Discord or Telegram when keywords are found
- Analyze sentiment of posts and comments
- Export data to CSV, JSON, Excel, or Parquet
- Process data through a plugin system (sentiment tagging, deduplication, keyword extraction)
- Store everything in a local SQLite database

---

## 📁 Project Structure

```
reddit-universal-scraper/
│
├── main.py                  # CLI entry point — run everything from here
├── config.py                # Global settings (paths, rate limits, credentials)
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (Discord/Telegram tokens)
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Run dashboard + API together with Docker
│
├── dashboard/
│   └── app.py               # Streamlit web dashboard (7 tabs)
│
├── api/
│   └── server.py            # FastAPI REST API server
│
├── analytics/
│   ├── sentiment.py         # Sentiment analysis + keyword extraction
│   └── subreddit_stats.py   # Fetch subreddit metadata (subscribers, rules, mods)
│
├── export/
│   ├── database.py          # SQLite database: save, query, job tracking
│   ├── parquet.py           # Export data to Parquet format (for DuckDB/warehouses)
│   └── cloud.py             # Upload data to AWS S3 or Google Drive
│
├── plugins/
│   ├── __init__.py          # Plugin loader and base Plugin class
│   ├── sentiment_tagger.py  # Plugin: adds sentiment scores to posts
│   ├── deduplicator.py      # Plugin: removes duplicate posts
│   └── keyword_extractor.py # Plugin: extracts keywords from post text
│
├── alerts/
│   └── notifications.py     # Send Discord/Telegram alerts on keyword matches
│
├── scheduler/               # Cron-style scheduled scraping
├── search/
│   └── query.py             # Search and filter scraped CSV data
│
└── data/
    ├── reddit_scraper.db    # SQLite database (auto-created)
    ├── r_<subreddit>/       # Scraped data per subreddit
    │   ├── posts.csv
    │   ├── comments.csv
    │   └── media/
    │       ├── images/
    │       └── videos/
    └── parquet/             # Parquet exports (auto-created)
```

---

## 🗂 File-by-File Breakdown

### `main.py` — The Brain
This is the single entry point for the entire project. You run everything through this file using command-line arguments.

It handles:
- Scraping subreddits and user profiles (posts, comments, media)
- Launching the dashboard or API server
- Running analytics, search, scheduling, and alerts
- Dry-run mode (simulate a scrape without saving anything)
- Plugin execution after scraping

It directly contains the core scraping logic: fetching posts from Reddit's JSON API, downloading media (images/videos), scraping comments recursively, and saving everything to CSV files.

---

### `config.py` — Global Settings
Defines all shared configuration used across the project:
- File paths (`DATA_DIR`, `DB_PATH`)
- Reddit mirror URLs (fallback sources if one is blocked)
- Rate limiting settings (timeouts, cooldowns)
- Media limits (max images/videos per post)
- Notification credentials (read from environment variables)
- Dashboard and scheduler settings

Any module that needs a setting imports it from here.

---

### `dashboard/app.py` — Web Dashboard
A Streamlit app with 7 interactive tabs:

| Tab | What it shows |
|-----|---------------|
| 📊 Overview | Post counts, scores, post types, activity over time |
| 📈 Analytics | Sentiment analysis, top keywords, best posting times |
| 🔍 Search | Filter posts by keyword, score, type, author |
| 💬 Comments | Comment stats, top comments, top commenters |
| ⚙️ Scraper | Start new scrapes from the UI, monitor live progress |
| 📋 Job History | View all past scrape jobs with status and stats |
| 🔌 Integrations | REST API controls, export options, plugin runner |

The dashboard reads data from the `data/` folder (CSV files) and from the SQLite database via `export/database.py`.

---

### `api/server.py` — REST API
A FastAPI server that exposes scraped data as HTTP endpoints. Useful for connecting external tools like Metabase, Grafana, or DuckDB.

Key endpoints:
- `GET /posts` — list posts with filters (subreddit, author, score, type)
- `GET /comments` — list comments with filters
- `GET /subreddits` — all scraped subreddits
- `GET /jobs` — job history
- `GET /query?sql=...` — run a raw SQL SELECT query
- `GET /grafana/query` — time-series data for Grafana dashboards

---

### `analytics/sentiment.py` — Sentiment & Keywords
Uses the VADER sentiment library to score text as positive, neutral, or negative.

Functions:
- `analyze_sentiment(text)` — returns a score (-1.0 to 1.0) and a label
- `analyze_posts_sentiment(posts)` — runs sentiment on a list of posts
- `extract_keywords(texts)` — finds the most common meaningful words
- `calculate_engagement_metrics(posts)` — computes avg score, top posts, post type performance
- `find_best_posting_times(posts)` — finds which hours/days get the highest scores

---

### `analytics/subreddit_stats.py` — Subreddit Metadata
Fetches live metadata about a subreddit directly from Reddit (no API key needed):
- Subscriber count, active users, creation date
- Rules, moderators, available post flairs
- Icon and banner URLs

Results can be saved to `data/r_<subreddit>/subreddit_stats.json`.

---

### `export/database.py` — SQLite Storage
Manages the local SQLite database (`data/reddit_scraper.db`).

Handles:
- Creating all tables on first run (`posts`, `comments`, `job_history`, `alerts`, etc.)
- Saving posts and comments in bulk
- Searching posts/comments with filters
- Tracking scrape jobs (start time, duration, post count, errors)
- Database maintenance: backup, vacuum, auto-vacuum

This module auto-initializes the database when it is first imported.

---

### `export/parquet.py` — Parquet Export
Converts CSV data to Parquet format — a compressed, columnar format ideal for analytics tools like DuckDB, Apache Spark, or data warehouses.

- `export_to_parquet(subreddit)` — exports a single subreddit's CSVs
- `export_database_to_parquet()` — exports the entire SQLite database

---

### `export/cloud.py` — Cloud Upload
Optional module for uploading scraped data to:
- **AWS S3** via `boto3`
- **Google Drive** via the Google Drive API

Both uploaders support uploading individual files or entire subreddit data folders.

---

### `plugins/__init__.py` — Plugin System
Defines the base `Plugin` class and the plugin loader.

To create a custom plugin:
1. Create a `.py` file in the `plugins/` folder
2. Define a class that inherits from `Plugin`
3. Implement `process_posts(posts)` and optionally `process_comments(comments)`

The loader auto-discovers all plugin files and runs them in sequence after scraping.

---

### `plugins/sentiment_tagger.py`
Adds `sentiment_score` and `sentiment_label` fields to every post and comment.

### `plugins/deduplicator.py`
Removes duplicate posts (by permalink) and duplicate comments (by comment ID).

### `plugins/keyword_extractor.py`
Adds a `keywords` field to each post with the top 5 most relevant words from its title and body.

---

### `alerts/notifications.py` — Discord & Telegram Alerts
Sends notifications when keyword matches are found in scraped posts.

- `send_discord_alert(webhook_url, ...)` — sends a rich embed to a Discord channel
- `send_telegram_alert(bot_token, chat_id, ...)` — sends a formatted message to Telegram
- `check_keyword_alerts(posts, keywords, ...)` — scans posts for keywords and fires alerts
- `send_scrape_summary(subreddit, stats, ...)` — sends a summary when a scrape finishes
- `AlertMonitor` class — stateful monitor that tracks seen posts to avoid duplicate alerts

---

### `search/query.py` — Search Engine
Provides functions to search and filter scraped CSV data without needing the database.

- `search_csv(filepath, query, ...)` — search a single CSV with text/score/date/type filters
- `search_all_data(data_dir, query, ...)` — search across all scraped subreddits at once
- `advanced_search(...)` — supports regex patterns and custom sorting
- `get_top_posts(...)` — returns top N posts by score
- `export_search_results(...)` — saves results to CSV, JSON, or Excel

---

## 🔗 How the Files Interact

Here's the flow of data through the system:

```
User runs: python main.py python --mode full --limit 100
                │
                ▼
           main.py
           ├── Fetches posts from Reddit JSON API (using MIRRORS from config.py)
           ├── Downloads media (images/videos) to data/r_python/media/
           ├── Scrapes comments recursively
           ├── Saves posts → data/r_python/posts.csv
           ├── Saves comments → data/r_python/comments.csv
           ├── Tracks job in SQLite via export/database.py
           └── Optionally runs plugins via plugins/__init__.py
                    ├── sentiment_tagger.py  (adds sentiment scores)
                    ├── deduplicator.py      (removes duplicates)
                    └── keyword_extractor.py (adds keywords)

User runs: python main.py --dashboard
                │
                ▼
           dashboard/app.py (Streamlit)
           ├── Reads CSV files from data/r_*/
           ├── Calls analytics/sentiment.py for sentiment + keywords
           ├── Calls search/query.py for search tab
           ├── Calls export/database.py for job history tab
           └── Can launch new scrapes as background subprocesses

User runs: python main.py --api
                │
                ▼
           api/server.py (FastAPI)
           └── Calls export/database.py for all data queries

Alerts flow:
           main.py → alerts/notifications.py → Discord / Telegram

Export flow:
           main.py → export/parquet.py → data/parquet/*.parquet
           main.py → export/cloud.py  → AWS S3 / Google Drive
```

---

## 📚 Recommended Reading Order for New Developers

If you're new to this project, read the files in this order to build up your understanding:

1. **`config.py`** — understand all the settings and paths used everywhere
2. **`main.py`** — the CLI and core scraping logic; this is the heart of the project
3. **`export/database.py`** — understand how data is stored and queried
4. **`analytics/sentiment.py`** — understand how text analysis works
5. **`search/query.py`** — understand how data is searched and filtered
6. **`plugins/__init__.py`** — understand the plugin system
7. **`plugins/sentiment_tagger.py`** — a simple example plugin to learn from
8. **`dashboard/app.py`** — the full UI; reads from all the above modules
9. **`api/server.py`** — the REST API; also reads from `export/database.py`
10. **`alerts/notifications.py`** — optional alerting system
11. **`export/parquet.py`** and **`export/cloud.py`** — optional export integrations

---

## 🚀 How to Run Locally

### Prerequisites

- Python 3.8 or higher
- `ffmpeg` (optional, needed to merge audio into Reddit videos)

```bash
# Install ffmpeg on Windows (via Chocolatey)
choco install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### Step 1 — Clone the repo

```bash
git clone https://github.com/ksanjeev284/reddit-universal-scraper.git
cd reddit-universal-scraper
```

### Step 2 — Create a virtual environment

```bash
python -m venv .venv

# Activate on Windows
.venv\Scripts\activate

# Activate on macOS/Linux
source .venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — (Optional) Set up environment variables

Create a `.env` file or export these variables if you want Discord/Telegram alerts:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=987654321
```

### Step 5 — Run your first scrape

```bash
# Scrape 100 posts from r/python (with media and comments)
python main.py python --mode full --limit 100

# Scrape without downloading media
python main.py python --mode history --limit 500

# Scrape a user's posts
python main.py spez --user --mode full --limit 50

# Test without saving anything
python main.py python --dry-run --limit 50
```

### Step 6 — Launch the dashboard

```bash
python main.py --dashboard
# Opens at http://localhost:8501
```

### Step 7 — Start the REST API

```bash
python main.py --api
# API docs at http://localhost:8000/docs
```

### Running with Docker

```bash
# Build the image
docker build -t reddit-scraper .

# Run a scrape
docker run -v ./data:/app/data reddit-scraper python --limit 100

# Start dashboard + API together
docker-compose up -d
# Dashboard: http://localhost:8501
# API: http://localhost:8000/docs
```

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP requests to Reddit's JSON/RSS endpoints |
| `pandas` | Reading, writing, and filtering CSV data |
| `streamlit` | Web dashboard UI |
| `fastapi` | REST API server |
| `uvicorn` | ASGI server to run FastAPI |
| `vaderSentiment` | Sentiment analysis (positive/neutral/negative scoring) |
| `aiohttp` | Async HTTP (used in async scraping modes) |
| `aiofiles` | Async file I/O |
| `pyarrow` | Parquet file export |
| `openpyxl` | Excel file export |
| `psutil` | Check if background scrape processes are still running |

Install all at once:

```bash
pip install -r requirements.txt
```

---

## 📊 Output Data Format

### `posts.csv`

| Column | Description |
|--------|-------------|
| `id` | Reddit post ID |
| `title` | Post title |
| `author` | Reddit username |
| `score` | Net upvotes |
| `upvote_ratio` | Ratio of upvotes to total votes |
| `num_comments` | Number of comments |
| `post_type` | `text`, `image`, `video`, `gallery`, or `link` |
| `selftext` | Post body text |
| `permalink` | Relative URL to the post |
| `url` | Direct URL (media or link) |
| `is_nsfw` | Whether the post is marked NSFW |
| `has_media` | Whether media was found |
| `media_downloaded` | Whether media was saved locally |
| `sentiment_score` | -1.0 to 1.0 (added by sentiment plugin) |
| `keywords` | Top keywords (added by keyword plugin) |

### `comments.csv`

| Column | Description |
|--------|-------------|
| `comment_id` | Reddit comment ID |
| `post_permalink` | The post this comment belongs to |
| `parent_id` | Parent comment ID (for nested replies) |
| `author` | Reddit username |
| `body` | Comment text |
| `score` | Upvotes |
| `depth` | Nesting level (0 = top-level) |
| `is_submitter` | Whether the commenter is the post author |

---

## ⚙️ Environment Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Discord webhook for alerts |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID |
| `DATABASE_URL` | Override default SQLite path |

---

## 📜 License

MIT License — free to use, modify, and distribute.

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.
