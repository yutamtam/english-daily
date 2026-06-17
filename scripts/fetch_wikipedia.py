import random
import requests
from datetime import datetime


def fetch_on_this_day() -> dict | None:
    today = datetime.now()
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{today.month}/{today.day}"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "EnglishDaily/1.0"})
        resp.raise_for_status()
        events = resp.json().get("events", [])
        if not events:
            return None
        # Pick from first 10 events to avoid very obscure ones
        event = random.choice(events[:10])
        return {
            "year": event.get("year"),
            "text": event.get("text", ""),
        }
    except Exception:
        return None
