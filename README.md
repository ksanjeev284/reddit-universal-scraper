# 🤖 Universal Reddit Scraper

[![Docker Build & Publish](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml)

A robust, dual-mode Reddit scraper designed to run on low-resource servers (like AWS Free Tier). 

## 🐳 Quick Start (No Installation Needed!)
```bash
# Pull the pre-built image and run
docker run -d -v $(pwd)/data:/app/data ghcr.io/ksanjeev284/reddit-universal-scraper:latest CreditCardsIndia --mode monitor
``` 

## Features
- **Zero API Keys Needed:** Uses RSS feeds and Public Mirrors (Redlib) to bypass API limits.
- **Dual Modes:**
  - `monitor`: Runs 24/7 to catch new posts via RSS.
  - `history`: Digs into the past using mirror rotation to bypass IP blocks.
- **Universal:** Works on any Subreddit (`r/name`) or User (`u/name`).
- **Dockerized:** Ready to deploy in an isolated container.

## Usage

### 1. Run via Docker (Recommended)
```bash
# Build
docker build -t reddit-scraper .

# Monitor a Subreddit (e.g., r/CreditCardsIndia)
docker run -d -v $(pwd)/data:/app/data reddit-scraper python main.py CreditCardsIndia --mode monitor

# Monitor a User (e.g., u/spez)
docker run -d -v $(pwd)/data:/app/data reddit-scraper python main.py spez --user --mode monitor

# Scrape History (Last 1000 posts)
docker run --rm -v $(pwd)/data:/app/data reddit-scraper python main.py CreditCardsIndia --mode history --limit 1000
```

### 2. Run Locally (Without Docker)
```bash
# Install dependencies
pip install -r requirements.txt

# Monitor a Subreddit
python main.py python --mode monitor

# Monitor a User
python main.py spez --user --mode monitor

# Scrape History
python main.py python --mode history --limit 500
```

## Output
Data is saved to the `/data` folder in CSV format:
- `data/r_CreditCardsIndia.csv`
- `data/u_spez.csv`

## Command Line Options
| Option | Description | Default |
|--------|-------------|---------|
| `target` | Name of Subreddit or User to scrape | Required |
| `--mode` | `monitor` or `history` | `monitor` |
| `--user` | Flag if target is a User, not Subreddit | `false` |
| `--limit` | Max posts to scrape (History mode only) | `500` |

## How It Works

### Monitor Mode (RSS)
- Polls Reddit's public RSS feed every 5 minutes
- Catches new posts in real-time
- Uses official Reddit RSS endpoints (no rate limits)

### History Mode (Mirrors)
- Uses public Redlib mirrors to access historical data
- Rotates between multiple mirrors to avoid IP blocks
- Implements cooldown periods to respect rate limits
- Automatically resumes from where it left off

## License
MIT License - Feel free to use, modify, and distribute.

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.
