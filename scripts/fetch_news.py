import random
import feedparser

FEEDS = [
    "https://japantoday.com/category/national/feed",
    "https://japantoday.com/category/features/feed",
]

DARK_KEYWORDS = [
    "dead", "death", "died", "killed", "murder", "suicide", "shooting",
    "stabbing", "assault", "arrested", "convicted", "sentenced", "crime",
    "criminal", "disaster", "earthquake", "tsunami", "explosion", "terror",
    "attack", "abuse", "victim", "tragedy", "crash", "accident", "fire",
    "war", "battle", "conflict",
]


def _is_dark(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in DARK_KEYWORDS)


def fetch_nhk_news(count: int = 3) -> list[dict]:
    articles = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            if _is_dark(entry.title):
                continue
            articles.append({
                "title": entry.title,
                "summary": entry.get("summary", "")[:300],
                "link": entry.link,
            })
    if not articles:
        return []
    return random.sample(articles, min(count, len(articles)))
