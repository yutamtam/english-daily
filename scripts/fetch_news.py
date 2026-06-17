import random
import feedparser


NHK_FEED_URL = "https://www3.nhk.or.jp/nhkworld/en/news/feeds/all/"


def fetch_nhk_news(count: int = 3) -> list[dict]:
    feed = feedparser.parse(NHK_FEED_URL)
    articles = []
    for entry in feed.entries[:20]:
        articles.append({
            "title": entry.title,
            "summary": entry.get("summary", "")[:300],
            "link": entry.link,
        })
    if not articles:
        return []
    return random.sample(articles, min(count, len(articles)))
