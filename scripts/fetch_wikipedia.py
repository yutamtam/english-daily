import json
import re
import requests


def fetch_on_this_day() -> dict | None:
    """Fetch today's theme from Yahoo! Kids Japan (今日は何の日)."""
    resp = requests.get(
        "https://kids.yahoo.co.jp/today",
        timeout=10,
        headers={"User-Agent": "EnglishDaily/1.0"},
    )
    resp.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', resp.text, re.DOTALL)
    if not match:
        return None

    data = json.loads(match.group(1))
    memories = (
        data.get("props", {})
            .get("pageProps", {})
            .get("todayResponse", {})
            .get("results", {})
            .get("memories", [])
    )
    if not memories:
        return None

    memory = memories[0]
    return {
        "title": memory.get("title", ""),
        "description": memory.get("description", ""),
    }
