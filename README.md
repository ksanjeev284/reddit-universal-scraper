# 🤖 Universal Reddit Scraper Suite

[![Docker Build & Publish](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml)

A **full-featured** Reddit scraper with analytics dashboard, REST API, scheduled scraping, plugins, and more. **No API keys required!**

<img width="2558" height="1331" alt="image" src="https://github.com/user-attachments/assets/180b89ce-db02-4cd2-922d-aa3d1b8eeda7" />

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Full Scraping** | Posts, comments, images, videos, galleries |
| 📈 **Web Dashboard** | Beautiful Streamlit UI with 7 tabs |
| 🚀 **REST API** | Connect Metabase, Grafana, DuckDB |
| 🔌 **Plugin System** | Extensible post-processing (sentiment, dedupe, keywords) |
| 📋 **Job Tracking** | Full history with status, duration, errors |
| 🧪 **Dry Run Mode** | Test scrape rules without saving data |
| 📦 **Parquet Export** | Analytics-ready format for DuckDB/warehouses |
| 😀 **Sentiment Analysis** | Analyze post/comment sentiment |
| 📅 **Scheduled Scraping** | Cron-style job scheduling |
| 📧 **Notifications** | Discord & Telegram alerts |
| 🗄️ **SQLite Database** | Structured storage with auto-backup |

---

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Scrape a subreddit
python main.py python --mode full --limit 100

# Launch dashboard
python main.py --dashboard
# Opens at http://localhost:8501
```

### 📋 Requirements

- **Python 3.8+**
- **ffmpeg** (optional, for video with audio)

```bash
# Windows (via chocolatey)
choco install ffmpeg

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

---

## 🔒 Proxies

To prevent IP blocks, rate limits, and captcha challenges when scraping Reddit at scale, you can configure proxies. Both the standard synchronous scraper and the asynchronous scraper support HTTP and HTTPS proxies.

### Configuration

You can configure proxies in four ways:

1. **Command Line / CLI**:
   Pass the `--proxy` flag to override global configurations:
   ```bash
   python main.py python --limit 100 --proxy "http://username:password@host:port"
   ```
2. **Environment Variable**:
   ```bash
   export PROXY_URL="http://username:password@host:port"
   ```
3. **Configuration File**:
   Update `config.py` with your default proxy URL:
   ```python
   PROXY_URL = "http://username:password@host:port"
   ```
4. **Web Dashboard**:
   Provide the **Proxy URL (Optional)** in the Scraper control tab when starting a scrape.

---

### Recommended Proxy Providers

#### ScrapingAnt Proxies

For reliable scraping performance, we recommend **[ScrapingAnt](https://scrapingant.com/?ref=yjk4mme)**. They provide high-performance datacenter proxies (for speed and economy) and residential proxies (for bypassing strict blocks).

> [!TIP]
> **ScrapingAnt Integration Note**: ScrapingAnt usernames must be prefixed with `customer-` (e.g., `customer-YOUR_USERNAME`). When integrating ScrapingAnt with Python `requests` or `aiohttp`, use the **HTTPS** proxy protocol on port **443** (e.g., `https://customer-YOUR_USERNAME:PASSWORD@datacenter.scrapingant.com:443`) for correct secure SSL tunnel authentication.

#### 🛜 Datacenter Proxies (Fast & Cost-Effective)
Great for scraping mirrors and moderate-volume queries:
* **[Get ScrapingAnt Datacenter Proxies](https://scrapingant.com/datacenter-proxies?ref=yjk4mme)**
* Apply coupon code **`ENTHUSIAST_50`** during checkout for a **50% discount** on the Enthusiast plan.

[![ScrapingAnt Datacenter Proxies](docs/datacenterproxies.png)](https://scrapingant.com/datacenter-proxies?ref=yjk4mme)

#### 🏠 Residential Proxies (Highly Anonymous)
The gold standard for undetected scraping. Bypasses strict anti-scraping protections:
* **[Get ScrapingAnt Residential Proxies](https://scrapingant.com/residential-proxies?ref=yjk4mme)**
* Apply coupon code **`MICRO_50`** during checkout for a **50% discount** on the Micro residential plan.

[![ScrapingAnt Residential Proxies](docs/ResidentialProxies.png)](https://scrapingant.com/residential-proxies?ref=yjk4mme)

---

## 📖 All Commands

### 🔄 Scraping

```bash
# Full scrape (posts + media + comments)
python main.py delhi --mode full --limit 100

# Fast history-only (no media/comments)
python main.py delhi --mode history --limit 500

# Live monitor (checks every 5 min)
python main.py delhi --mode monitor

# Scrape a user's posts
python main.py spez --user --mode full --limit 50

# Skip media or comments
python main.py delhi --no-media --limit 200
python main.py delhi --no-comments --limit 200
```

### 🧪 Dry Run Mode

Test scrape rules without saving any data:

```bash
python main.py python --mode full --limit 50 --dry-run
```

Output:
```
🧪 DRY RUN MODE - No data will be saved
🧪 DRY RUN COMPLETE!
   📊 Would scrape: 100 posts
   💬 Would scrape: 245 comments
```

### 🔌 Plugins

Enable post-processing plugins:

```bash
# List available plugins
python main.py --list-plugins

# Run with plugins enabled
python main.py python --mode full --plugins
```

**Built-in Plugins:**
| Plugin | Description |
|--------|-------------|
| `sentiment_tagger` | Adds sentiment scores to posts |
| `deduplicator` | Removes duplicate posts |
| `keyword_extractor` | Extracts top keywords |

Create custom plugins in `plugins/` folder.

### 📊 Dashboard

```bash
python main.py --dashboard
# Opens at http://localhost:8501
```

**Dashboard Tabs:**
- 📊 Overview - Stats & charts
- 📈 Analytics - Sentiment & keywords
- 🔍 Search - Query scraped data
- 💬 Comments - Comment analysis
- ⚙️ Scraper - Start new scrapes
- 📋 Job History - View all jobs
- 🔌 Integrations - API, export, plugins

### 🚀 REST API

```bash
python main.py --api
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /posts` | List posts with filters |
| `GET /comments` | List comments |
| `GET /subreddits` | All scraped subreddits |
| `GET /jobs` | Job history |
| `GET /query?sql=...` | Raw SQL queries |
| `GET /grafana/query` | Grafana time-series |

### 📦 Export & Maintenance

```bash
# Export to Parquet (for DuckDB/warehouses)
python main.py --export-parquet python

# View job history
python main.py --job-history

# Backup database
python main.py --backup

# Optimize database
python main.py --vacuum
```

### 📅 Scheduled Scraping

```bash
# Scrape every 60 minutes
python main.py --schedule delhi --every 60

# With options
python main.py --schedule delhi --every 30 --mode full --limit 50
```

### 🔍 Search & Analytics

```bash
# Search scraped data
python main.py --search "credit card" --min-score 100

# Run sentiment analysis
python main.py --analyze delhi --sentiment

# Extract keywords
python main.py --analyze delhi --keywords
```

---

## 🐳 Docker

### Quick Start

```bash
# Build
docker build -t reddit-scraper .

# Run scrape
docker run -v ./data:/app/data reddit-scraper python --limit 100

# Run with plugins
docker run -v ./data:/app/data reddit-scraper python --plugins
```

### Docker Compose (Full Stack)

```bash
# Start API + Dashboard
docker-compose up -d

# Access:
# Dashboard: http://localhost:8501
# API: http://localhost:8000/docs
```

### Deploy to AWS/VPS

```bash
# SSH into your server
ssh user@your-server-ip

# Clone repo
git clone https://github.com/ksanjeev284/reddit-universal-scraper.git
cd reddit-universal-scraper

# Start services
docker-compose up -d

# Open firewall ports
sudo ufw allow 8000
sudo ufw allow 8501
```

Access:
- `http://your-server-ip:8501` → Dashboard
- `http://your-server-ip:8000/docs` → API

---

## 🔗 External Integrations

### Metabase

1. Start API: `python main.py --api`
2. Add HTTP datasource: `http://localhost:8000`
3. Query: `/posts?subreddit=python&limit=100`

### Grafana

1. Install "JSON API" or "Infinity" plugin
2. Add datasource: `http://localhost:8000`
3. Use `/grafana/query` for time-series

### DuckDB

```python
import duckdb

# Export to Parquet first
# python main.py --export-parquet python

# Query directly
duckdb.query("SELECT * FROM 'data/parquet/*.parquet'").df()
```

---

## 📁 Project Structure

```
reddit-scraper/
├── main.py              # CLI entry point
├── config.py            # Settings
├── analytics/           # Sentiment & keywords
├── alerts/              # Discord/Telegram
├── api/                 # REST API server
├── dashboard/           # Streamlit UI
├── export/              # Database & exports
├── plugins/             # Post-processing plugins
├── scheduler/           # Cron scheduling
├── search/              # Search engine
└── data/
    ├── r_subreddit/     # Scraped data
    ├── backups/         # DB backups
    └── parquet/         # Parquet exports
```

---

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
| sentiment_score | -1.0 to 1.0 (with plugins) |

### comments.csv
| Column | Description |
|--------|-------------|
| comment_id | Comment ID |
| post_permalink | Parent post |
| author | Username |
| body | Comment text |
| score | Upvotes |

---

## ⚙️ Environment Variables

```bash
# Notifications
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="987654321"
```

---

## 📜 License

MIT License - Feel free to use, modify, and distribute.

## 🤝 Contributing

Pull requests welcome! For major changes, please open an issue first.

## Pairing: RedditAPIs (optional managed Reddit data backend)

Users who already adopt this project sometimes ask about routing read-heavy operations (subreddit fetch, post detail, comments, user lookup, search) to a managed backend during testing or for workflows that skip the Reddit developer-app step. The [RedditAPIs code samples repo](https://github.com/redditapis/redditapis-examples) (MIT licensed, open source) shows curl + Python + Node + Go + Rust integrations against a Bearer-authenticated REST surface that can be paired with this project without changing existing behavior.

Two integration patterns:

1. **Side-by-side in your application.** Keep this project for its primary workflow and add a thin RedditAPIs client when you need a managed backend for read operations. Each call maps to whichever backend the user has configured.

2. **PRAW-style migration reference.** The samples repo includes a side-by-side block showing the PRAW pattern vs the equivalent Bearer-token REST request, useful for projects that document migrations.

Subset that pairs cleanly with this project's read path:

- subreddit listings (`hot`, `new`, `top`, `rising`)
- post detail + comments tree
- user profile + submissions
- search across subreddits

Repository: https://github.com/redditapis/redditapis-examples

This pairing is fully optional. No behavior change for existing users of this project.

