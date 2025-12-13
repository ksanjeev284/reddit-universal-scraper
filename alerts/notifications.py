"""
Notification module - Discord & Telegram alerts
"""
import requests
import json
from datetime import datetime

def send_discord_alert(webhook_url, title, message, posts=None, color=0x5865F2):
    """
    Send alert to Discord via webhook.
    
    Args:
        webhook_url: Discord webhook URL
        title: Alert title
        message: Alert message
        posts: Optional list of posts to include
        color: Embed color (default: Discord blue)
    """
    if not webhook_url:
        print("⚠️ Discord webhook URL not configured")
        return False
    
    embeds = [{
        "title": f"🤖 {title}",
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Reddit Scraper Alert"}
    }]
    
    # Add post previews
    if posts:
        fields = []
        for post in posts[:5]:  # Max 5 posts
            fields.append({
                "name": post.get('title', 'No Title')[:100],
                "value": f"Score: {post.get('score', 0)} | Comments: {post.get('num_comments', 0)}\n[View Post](https://reddit.com{post.get('permalink', '')})",
                "inline": False
            })
        embeds[0]["fields"] = fields
    
    payload = {"embeds": embeds}
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 204:
            print("✅ Discord alert sent!")
            return True
        else:
            print(f"❌ Discord error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Discord error: {e}")
        return False

def send_telegram_alert(bot_token, chat_id, title, message, posts=None):
    """
    Send alert to Telegram via bot.
    
    Args:
        bot_token: Telegram bot token
        chat_id: Chat/Channel ID to send to
        title: Alert title
        message: Alert message
        posts: Optional list of posts to include
    """
    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials not configured")
        return False
    
    # Build message
    text = f"🤖 *{title}*\n\n{message}"
    
    if posts:
        text += "\n\n📝 *New Posts:*\n"
        for post in posts[:5]:
            title_text = post.get('title', 'No Title')[:80]
            score = post.get('score', 0)
            permalink = post.get('permalink', '')
            text += f"\n• [{title_text}](https://reddit.com{permalink}) (⬆️ {score})"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Telegram alert sent!")
            return True
        else:
            print(f"❌ Telegram error: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def check_keyword_alerts(posts, keywords, webhook_url=None, telegram_token=None, telegram_chat=None):
    """
    Check posts for keyword matches and send alerts.
    
    Args:
        posts: List of posts to check
        keywords: List of keywords to monitor
        webhook_url: Discord webhook URL
        telegram_token: Telegram bot token
        telegram_chat: Telegram chat ID
    
    Returns:
        List of matching posts
    """
    if not keywords:
        return []
    
    keywords_lower = [k.lower() for k in keywords]
    matching_posts = []
    
    for post in posts:
        text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
        
        matched_keywords = []
        for keyword in keywords_lower:
            if keyword in text:
                matched_keywords.append(keyword)
        
        if matched_keywords:
            post['matched_keywords'] = matched_keywords
            matching_posts.append(post)
    
    if matching_posts:
        title = f"Keyword Alert: {len(matching_posts)} matches!"
        message = f"Found posts matching: {', '.join(set(k for p in matching_posts for k in p.get('matched_keywords', [])))}"
        
        if webhook_url:
            send_discord_alert(webhook_url, title, message, matching_posts, color=0xFF6B6B)
        
        if telegram_token and telegram_chat:
            send_telegram_alert(telegram_token, telegram_chat, title, message, matching_posts)
    
    return matching_posts

def send_scrape_summary(subreddit, stats, webhook_url=None, telegram_token=None, telegram_chat=None):
    """
    Send a summary after scraping completes.
    
    Args:
        subreddit: Subreddit name
        stats: Dictionary with scrape statistics
        webhook_url: Discord webhook URL
        telegram_token: Telegram bot token
        telegram_chat: Telegram chat ID
    """
    title = f"Scrape Complete: r/{subreddit}"
    message = f"""
📊 **Statistics:**
• Posts: {stats.get('posts', 0)}
• Comments: {stats.get('comments', 0)}
• Images: {stats.get('images', 0)}
• Videos: {stats.get('videos', 0)}
• Duration: {stats.get('duration', 'N/A')}
    """.strip()
    
    if webhook_url:
        send_discord_alert(webhook_url, title, message, color=0x00D166)
    
    if telegram_token and telegram_chat:
        send_telegram_alert(telegram_token, telegram_chat, title, message)

class AlertMonitor:
    """Monitor for keyword-based alerts."""
    
    def __init__(self, keywords, discord_webhook=None, telegram_token=None, telegram_chat=None):
        self.keywords = keywords
        self.discord_webhook = discord_webhook
        self.telegram_token = telegram_token
        self.telegram_chat = telegram_chat
        self.seen_posts = set()
    
    def check_posts(self, posts):
        """Check new posts for keyword matches."""
        new_posts = [p for p in posts if p.get('id') not in self.seen_posts]
        
        if not new_posts:
            return []
        
        # Mark as seen
        for p in new_posts:
            self.seen_posts.add(p.get('id'))
        
        # Check for keywords
        matches = check_keyword_alerts(
            new_posts, 
            self.keywords,
            self.discord_webhook,
            self.telegram_token,
            self.telegram_chat
        )
        
        return matches
