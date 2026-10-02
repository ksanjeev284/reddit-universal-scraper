"""
Reddit Scraper Suite - Configuration
"""
import os
from pathlib import Path

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# --- PATHS ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "reddit_scraper.db"

# --- SCRAPER SETTINGS ---
USER_AGENT = os.getenv("REDDIT_USER_AGENT", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_REFRESH_TOKEN = os.getenv("REDDIT_REFRESH_TOKEN", "")
REDDIT_ACCESS_TOKEN = os.getenv("REDDIT_ACCESS_TOKEN", "")
REDDIT_API_BASE = "https://oauth.reddit.com"
# Compatibility for integrations importing MIRRORS: only the official API is used.
MIRRORS = [REDDIT_API_BASE]
REDDIT_REQUESTS_PER_MINUTE = min(100, max(1, int(os.getenv("REDDIT_REQUESTS_PER_MINUTE", "60"))))

# Rate limiting
REQUEST_TIMEOUT = 15
COOLDOWN_SECONDS = 3
RETRY_WAIT = 30

# Media settings
MAX_IMAGES_PER_POST = 10
MAX_VIDEOS_PER_POST = 2
MAX_GALLERY_IMAGES = 15

# Comment settings
MAX_COMMENT_DEPTH = 5

# --- ASYNC SETTINGS ---
ASYNC_MAX_CONCURRENT = 10
ASYNC_BATCH_SIZE = 50

# --- NOTIFICATION SETTINGS ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- DASHBOARD SETTINGS ---
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8501

# --- SCHEDULER SETTINGS ---
SCHEDULER_TIMEZONE = "Asia/Kolkata"

# --- PROXY SETTINGS ---
# Generic proxy URL (e.g. http://username:password@host:port)
PROXY_URL = os.getenv("PROXY_URL", "")
PROXY_COUNTRY = os.getenv("PROXY_COUNTRY", "")
PROXY_SESSION_ID = os.getenv("PROXY_SESSION_ID", "")
PROXY_AUTO_ROTATE = False  # A stable route is used; rate limits must not be bypassed.

def get_formatted_proxy_url(proxy_url, country=None, session_id=None, force_rotate=False):
    """Retain proxy support, including stable ScrapingAnt country/session targeting."""
    from urllib.parse import urlsplit, urlunsplit, unquote, quote
    import re
    if not proxy_url:
        return proxy_url
    parsed = urlsplit(proxy_url)
    if not (parsed.hostname or "").endswith(".scrapingant.com") or not unquote(parsed.username or "").startswith("customer-"):
        return proxy_url
    username = unquote(parsed.username)
    original_country = re.search(r"-country-([a-zA-Z]{2})(?=-|$)", username)
    original_session = re.search(r"-sessionid-([A-Za-z0-9_]+)(?=-|$)", username)
    username = re.sub(r"-country-[a-zA-Z]{2}(?=-|$)|-sessionid-[A-Za-z0-9_]+(?=-|$)", "", username)
    target_country = country if country is not None else PROXY_COUNTRY or (original_country.group(1) if original_country else "")
    target_session = session_id if session_id is not None else PROXY_SESSION_ID or (original_session.group(1) if original_session else "")
    if target_country and target_country.lower() != "none":
        if not re.fullmatch(r"[A-Za-z]{2}", target_country):
            raise ValueError("Proxy country must be a two-letter country code.")
        username += f"-country-{target_country.lower()}"
    if target_session and target_session.lower() not in ("none", "auto"):
        if not re.fullmatch(r"[A-Za-z0-9_]+", target_session):
            raise ValueError("Proxy session ID may contain letters, digits and underscores.")
        username += f"-sessionid-{target_session}"
    netloc = quote(username, safe="-")
    if parsed.password is not None:
        netloc += ":" + quote(unquote(parsed.password), safe="")
    netloc += "@" + parsed.hostname
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

# --- DATABASE SETTINGS ---
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)
