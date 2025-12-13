# 🤖 Universal Reddit Scraper

[![Docker Build & Publish](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/ksanjeev284/reddit-universal-scraper/actions/workflows/docker-publish.yml)

A robust, full-featured Reddit scraper that downloads **posts, images, videos, galleries, and comments**. Designed to run on low-resource servers (like AWS Free Tier).

## 🐳 Quick Start (No Installation Needed!)
```bash
docker run -d -v $(pwd)/data:/app/data ghcr.io/ksanjeev284/reddit-universal-scraper:latest delhi --mode full --limit 100
```

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📊 **Full Metadata** | Title, author, score, upvotes, awards, flair, NSFW flags |
| 🖼️ **Image Download** | Automatically downloads all images from posts |
| 🎬 **Video Download** | Downloads Reddit-hosted videos |
| 🖼️ **Gallery Support** | Extracts and downloads all images from gallery posts |
| 💬 **Comment Scraping** | Recursively scrapes all comments with threading info |
| 🔄 **Dual Sources** | Uses old.reddit.com + Redlib mirrors for reliability |
| 📁 **Organized Output** | Clean folder structure per subreddit |

## 📁 Output Structure

```
data/
└── r_delhi/
    ├── posts.csv           # All post metadata
    ├── comments.csv        # All comments with threading
    └── media/
        ├── images/         # Downloaded images & galleries
        │   ├── abc123_0.jpg
        │   ├── abc123_gallery_0.jpg
        │   └── ...
        └── videos/         # Downloaded videos
            └── xyz789_0.mp4
```

## 🚀 Usage

### Full Scrape (Posts + Media + Comments)
```bash
# Scrape r/delhi with everything
python main.py delhi --mode full --limit 100

# Scrape a user's posts
python main.py spez --user --mode full --limit 50
```

### Posts Only (No Media Download)
```bash
python main.py python --mode full --no-media --limit 200
```

### Posts Only (No Comments)
```bash
python main.py india --mode full --no-comments --limit 100
```

### Live Monitor Mode
```bash
python main.py delhi --mode monitor
```

### Legacy History Mode (Posts Only, No Media)
```bash
python main.py delhi --mode history --limit 500
```

## 🐳 Docker Usage

```bash
# Build the image
docker build -t reddit-scraper .

# Full scrape with media
docker run -d -v $(pwd)/data:/app/data reddit-scraper delhi --mode full --limit 100

# Scrape without media (faster)
docker run -d -v $(pwd)/data:/app/data reddit-scraper delhi --mode full --no-media --limit 500

# Monitor mode (runs continuously)
docker run -d -v $(pwd)/data:/app/data reddit-scraper delhi --mode monitor
```

## 📊 CSV Output Format

### posts.csv
| Column | Description |
|--------|-------------|
| id | Reddit post ID |
| title | Post title |
| author | Username |
| created_utc | Timestamp (ISO format) |
| permalink | Reddit URL path |
| url | External/media URL |
| score | Net upvotes |
| upvote_ratio | Percentage upvoted |
| num_comments | Comment count |
| selftext | Post body text |
| post_type | text/image/video/gallery/link |
| flair | Post flair text |
| has_media | Boolean |
| media_downloaded | Boolean |

### comments.csv
| Column | Description |
|--------|-------------|
| post_permalink | Parent post URL |
| comment_id | Reddit comment ID |
| parent_id | Parent comment/post ID |
| author | Username |
| body | Comment text |
| score | Net upvotes |
| created_utc | Timestamp |
| depth | Nesting level (0 = top-level) |
| is_submitter | Is the post author |

## ⚙️ Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `target` | Subreddit or username | Required |
| `--mode` | `full`, `history`, or `monitor` | `full` |
| `--user` | Target is a user, not subreddit | `false` |
| `--limit` | Max posts to scrape | `100` |
| `--no-media` | Skip downloading images/videos | `false` |
| `--no-comments` | Skip scraping comments | `false` |

## 🛠️ Requirements

```bash
pip install pandas requests
```

## 📜 License
MIT License - Feel free to use, modify, and distribute.

## 🤝 Contributing
Pull requests are welcome! For major changes, please open an issue first.
