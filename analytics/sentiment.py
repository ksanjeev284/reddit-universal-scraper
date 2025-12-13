"""
Analytics module - Sentiment Analysis, Word Clouds, Statistics
"""
import re
from collections import Counter
from pathlib import Path
import sys

# Simple sentiment analysis without external dependencies
POSITIVE_WORDS = {
    'good', 'great', 'awesome', 'excellent', 'amazing', 'love', 'best', 'perfect',
    'nice', 'wonderful', 'fantastic', 'brilliant', 'superb', 'outstanding', 'happy',
    'beautiful', 'helpful', 'thanks', 'thank', 'appreciate', 'recommend', 'interesting',
    'useful', 'cool', 'fun', 'enjoy', 'like', 'loved', 'impressive', 'incredible'
}

NEGATIVE_WORDS = {
    'bad', 'terrible', 'awful', 'horrible', 'hate', 'worst', 'poor', 'disappointing',
    'useless', 'waste', 'annoying', 'boring', 'ugly', 'stupid', 'dumb', 'fail',
    'wrong', 'broken', 'sad', 'angry', 'frustrated', 'scam', 'fake', 'trash',
    'pathetic', 'ridiculous', 'disgusting', 'overpriced', 'avoid', 'never'
}

INTENSIFIERS = {'very', 'really', 'extremely', 'absolutely', 'totally', 'completely'}

def analyze_sentiment(text):
    """
    Simple sentiment analysis.
    Returns: (score, label)
    - score: -1.0 to 1.0
    - label: 'positive', 'negative', or 'neutral'
    """
    if not text:
        return 0.0, 'neutral'
    
    # Clean and tokenize
    words = re.findall(r'\b[a-z]+\b', text.lower())
    
    if not words:
        return 0.0, 'neutral'
    
    positive_count = 0
    negative_count = 0
    intensifier_next = False
    
    for word in words:
        multiplier = 1.5 if intensifier_next else 1.0
        
        if word in POSITIVE_WORDS:
            positive_count += multiplier
        elif word in NEGATIVE_WORDS:
            negative_count += multiplier
        
        intensifier_next = word in INTENSIFIERS
    
    total = positive_count + negative_count
    if total == 0:
        return 0.0, 'neutral'
    
    score = (positive_count - negative_count) / len(words)
    score = max(-1.0, min(1.0, score * 5))  # Normalize
    
    if score > 0.1:
        label = 'positive'
    elif score < -0.1:
        label = 'negative'
    else:
        label = 'neutral'
    
    return round(score, 3), label

def analyze_posts_sentiment(posts):
    """Analyze sentiment for a list of posts."""
    results = []
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    for post in posts:
        text = f"{post.get('title', '')} {post.get('selftext', '')}"
        score, label = analyze_sentiment(text)
        post['sentiment_score'] = score
        post['sentiment_label'] = label
        sentiment_counts[label] += 1
        results.append(post)
    
    return results, sentiment_counts

def analyze_comments_sentiment(comments):
    """Analyze sentiment for comments."""
    results = []
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    for comment in comments:
        score, label = analyze_sentiment(comment.get('body', ''))
        comment['sentiment_score'] = score
        comment['sentiment_label'] = label
        sentiment_counts[label] += 1
        results.append(comment)
    
    return results, sentiment_counts

def extract_keywords(texts, top_n=50):
    """Extract most common keywords from texts."""
    # Stopwords
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
        'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until',
        'while', 'this', 'that', 'these', 'those', 'i', 'me', 'my', 'myself',
        'we', 'our', 'you', 'your', 'he', 'she', 'it', 'they', 'them', 'what',
        'which', 'who', 'whom', 'its', 'his', 'her', 'their', 'our', 'up',
        'out', 'about', 'any', 'also', 'get', 'got', 'like', 'one', 'two',
        'know', 'even', 'new', 'want', 'way', 'people', 'time', 'year', 'think',
        'amp', 'http', 'https', 'www', 'com', 'reddit', 'deleted', 'removed', 'nan'
    }
    
    all_words = []
    for text in texts:
        if text:
            words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            all_words.extend([w for w in words if w not in stopwords])
    
    return Counter(all_words).most_common(top_n)

def generate_wordcloud_data(texts, top_n=100):
    """Generate word frequency data for word cloud visualization."""
    keywords = extract_keywords(texts, top_n)
    
    if not keywords:
        return []
    
    max_count = keywords[0][1]
    
    return [
        {"text": word, "value": count, "size": int(10 + (count / max_count) * 90)}
        for word, count in keywords
    ]

def calculate_engagement_metrics(posts):
    """Calculate engagement metrics for posts."""
    if not posts:
        return {}
    
    total_posts = len(posts)
    total_score = sum(p.get('score', 0) for p in posts)
    total_comments = sum(p.get('num_comments', 0) for p in posts)
    total_awards = sum(p.get('total_awards', 0) for p in posts)
    
    # Posts with engagement
    engaged_posts = [p for p in posts if p.get('score', 0) > 0 or p.get('num_comments', 0) > 0]
    
    # Top performers
    top_by_score = sorted(posts, key=lambda x: x.get('score', 0), reverse=True)[:10]
    top_by_comments = sorted(posts, key=lambda x: x.get('num_comments', 0), reverse=True)[:10]
    
    # Post type performance
    type_performance = {}
    for post in posts:
        ptype = post.get('post_type', 'unknown')
        if ptype not in type_performance:
            type_performance[ptype] = {'count': 0, 'total_score': 0, 'total_comments': 0}
        type_performance[ptype]['count'] += 1
        type_performance[ptype]['total_score'] += post.get('score', 0)
        type_performance[ptype]['total_comments'] += post.get('num_comments', 0)
    
    for ptype in type_performance:
        count = type_performance[ptype]['count']
        type_performance[ptype]['avg_score'] = type_performance[ptype]['total_score'] / count
        type_performance[ptype]['avg_comments'] = type_performance[ptype]['total_comments'] / count
    
    return {
        'total_posts': total_posts,
        'total_score': total_score,
        'total_comments': total_comments,
        'total_awards': total_awards,
        'avg_score': total_score / total_posts if total_posts else 0,
        'avg_comments': total_comments / total_posts if total_posts else 0,
        'engagement_rate': len(engaged_posts) / total_posts if total_posts else 0,
        'top_by_score': top_by_score,
        'top_by_comments': top_by_comments,
        'type_performance': type_performance
    }

def find_best_posting_times(posts):
    """Analyze best times to post based on engagement."""
    hourly_stats = {}
    daily_stats = {}
    
    for post in posts:
        created = post.get('created_utc', '')
        if not created:
            continue
        
        try:
            # Parse ISO format
            from datetime import datetime
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            hour = dt.hour
            day = dt.strftime('%A')
            
            # Hourly
            if hour not in hourly_stats:
                hourly_stats[hour] = {'count': 0, 'total_score': 0}
            hourly_stats[hour]['count'] += 1
            hourly_stats[hour]['total_score'] += post.get('score', 0)
            
            # Daily
            if day not in daily_stats:
                daily_stats[day] = {'count': 0, 'total_score': 0}
            daily_stats[day]['count'] += 1
            daily_stats[day]['total_score'] += post.get('score', 0)
        except:
            continue
    
    # Calculate averages
    for hour in hourly_stats:
        hourly_stats[hour]['avg_score'] = hourly_stats[hour]['total_score'] / hourly_stats[hour]['count']
    
    for day in daily_stats:
        daily_stats[day]['avg_score'] = daily_stats[day]['total_score'] / daily_stats[day]['count']
    
    # Find best times
    best_hours = sorted(hourly_stats.items(), key=lambda x: x[1]['avg_score'], reverse=True)[:5]
    best_days = sorted(daily_stats.items(), key=lambda x: x[1]['avg_score'], reverse=True)[:3]
    
    return {
        'hourly_stats': hourly_stats,
        'daily_stats': daily_stats,
        'best_hours': [(h, s['avg_score']) for h, s in best_hours],
        'best_days': [(d, s['avg_score']) for d, s in best_days]
    }
