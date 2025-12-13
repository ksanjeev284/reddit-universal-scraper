# 🤖 Universal Reddit Scraper Suite

[![Docker Build & Publish](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml)

A **full-featured** Reddit scraper suite with analytics dashboard, sentiment analysis, scheduled scraping, notifications, and more!

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Full Scraping** | Posts, comments, images, videos, galleries |
| 📈 **Analytics Dashboard** | Beautiful Streamlit web UI |
| 😀 **Sentiment Analysis** | Analyze post/comment sentiment |
| ☁️ **Keyword Extraction** | Generate word clouds |
| 🔍 **Search & Filter** | Query scraped data with filters |
| 📅 **Scheduled Scraping** | Cron-style job scheduling |
| 📧 **Notifications** | Discord & Telegram alerts |
| 🗄️ **SQLite Database** | Structured data storage |
| 📤 **Multiple Exports** | CSV, JSON, Excel |

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Scrape a subreddit (posts + media + comments)
python main.py delhi --mode full --limit 100

# Launch analytics dashboard
python main.py --dashboard
```

## 📖 Usage Guide

### 🔄 Scraping Modes

```bash
# Full scrape with everything
python main.py delhi --mode full --limit 100

# History only (no media/comments - faster)
python main.py delhi --mode history --limit 500

# Live monitor (checks every 5 min)
python main.py delhi --mode monitor

# Scrape a user's posts
python main.py spez --user --mode full --limit 50

# Skip media or comments
python main.py delhi --mode full --no-media --limit 200
python main.py delhi --mode full --no-comments --limit 200
```

### 📊 Analytics Dashboard

```bash
# Launch the web dashboard
python main.py --dashboard

# Opens at http://localhost:8501
```

**Dashboard Features:**
- 📈 Post statistics & charts
- 😀 Sentiment analysis
- ☁️ Keyword extraction
- 🔍 Search & filter interface
- 📤 Export data

### 🔍 Search Data

```bash
# Search all scraped data
python main.py --search "credit card"

# Search with filters
python main.py --search "laptop" --min-score 100
python main.py --search "advice" --author username
python main.py --search "help" --subreddit delhi
```

### 😀 Analytics

```bash
# Run sentiment analysis
python main.py --analyze delhi --sentiment

# Extract top keywords
python main.py --analyze delhi --keywords
```

### 📅 Scheduled Scraping

```bash
# Scrape every 60 minutes
python main.py --schedule delhi --every 60

# Scrape with options
python main.py --schedule delhi --every 30 --mode full --limit 50
```

### 📧 Notifications (Discord/Telegram)

**Discord:**
```bash
python main.py delhi --mode monitor --discord-webhook "YOUR_WEBHOOK_URL"
```

**Telegram:**
```bash
python main.py delhi --mode monitor \
  --telegram-token "YOUR_BOT_TOKEN" \
  --telegram-chat "YOUR_CHAT_ID"
```

## 📁 Project Structure

```
reddit-scraper/
├── main.py              # Main CLI entry point
├── config.py            # Configuration settings
├── analytics/           # Sentiment & keyword analysis
│   └── sentiment.py
├── alerts/              # Discord & Telegram notifications
│   └── notifications.py
├── dashboard/           # Streamlit web UI
│   └── app.py
├── export/              # Database & export functions
│   └── database.py
├── scheduler/           # Cron-style scheduling
│   └── cron.py
├── search/              # Search & filter engine
│   └── query.py
└── data/                # Scraped data
    └── r_subreddit/
        ├── posts.csv
        ├── comments.csv
        └── media/
            ├── images/
            └── videos/
```

## 📊 Data Output

### posts.csv
| Column | Description |
|--------|-------------|
| id | Reddit post ID |
| title | Post title |
| author | Username |
| score | Net upvotes |
| num_comments | Comment count |
| post_type | text/image/video/gallery |
| selftext | Post body |
| flair | Post flair |
| is_nsfw | NSFW flag |
| created_utc | Timestamp |

### comments.csv
| Column | Description |
|--------|-------------|
| comment_id | Comment ID |
| post_permalink | Parent post |
| author | Username |
| body | Comment text |
| score | Upvotes |
| depth | Nesting level |

## 🐳 Docker

```bash
# Build
docker build -t reddit-scraper .

# Full scrape
docker run -v $(pwd)/data:/app/data reddit-scraper delhi --mode full --limit 100

# Monitor mode
docker run -d -v $(pwd)/data:/app/data reddit-scraper delhi --mode monitor
```

## ⚙️ Configuration

Edit `config.py` or use environment variables:

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="987654321"
```

## 📜 License

MIT License - Feel free to use, modify, and distribute.

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.
