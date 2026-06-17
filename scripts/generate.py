#!/usr/bin/env python3
"""
Main script: fetch content, generate script with Gemini, save JSON, send email.
Run daily via GitHub Actions at UTC 21:00 (JST 06:00).
"""

import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types

# Allow imports from scripts/ when running directly
sys.path.insert(0, str(Path(__file__).parent))

from fetch_weather import fetch_weather
from fetch_news import fetch_nhk_news
from fetch_wikipedia import fetch_on_this_day
from fetch_parenting import fetch_parenting_topic
from send_email import send_email

REPO_ROOT = Path(__file__).parent.parent
CONTENT_DIR = REPO_ROOT / "content"
CONFIG_PATH = REPO_ROOT / "config.json"
VOCAB_DIR = REPO_ROOT / "data" / "vocab"

VOCAB_LEVEL_FILES = {
    1: ["svl_01.json", "svl_02.json", "svl_03.json"],
    2: ["svl_01.json", "svl_02.json", "svl_03.json",
        "svl_04.json", "svl_05.json", "svl_06.json"],
    3: [f"svl_{i:02d}.json" for i in range(1, 13)],
    4: [f"svl_{i:02d}.json" for i in range(1, 13)] +
       [f"kyokugen_{i}.json" for i in range(13, 25)],
    5: [f"svl_{i:02d}.json" for i in range(1, 13)] +
       [f"kyokugen_{i}.json" for i in range(13, 25)] +
       [f"shukyoku_{i}.json" for i in range(25, 35)],
}

# Files that contain words ABOVE a given level (used to sample "unknown" words)
ABOVE_LEVEL_FILES = {
    1: ["svl_04.json", "svl_05.json", "svl_06.json"],
    2: ["svl_07.json", "svl_08.json", "svl_09.json"],
    3: [f"kyokugen_{i}.json" for i in range(13, 17)],
    4: [f"shukyoku_{i}.json" for i in range(25, 29)],
    5: [],  # native level — nothing above
}

VOCAB_LEVEL_LABELS = {
    1: "beginner (~3,000 words, junior high school level)",
    2: "intermediate (~6,000 words, high school level)",
    3: "advanced (~12,000 words, TOEIC 900 level)",
    4: "very advanced (~24,000 words, English newspaper level)",
    5: "near-native (~34,000 words)",
}


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_words_from_files(filenames: list[str]) -> list[str]:
    words = []
    for filename in filenames:
        path = VOCAB_DIR / filename
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                words.extend(w.lower() for w in data.get("words", []))
    return words


def sample_unknown_words(vocab_level: int, n: int = 40) -> list[str]:
    """Sample words from the level just above the listener's current level."""
    above_files = ABOVE_LEVEL_FILES.get(vocab_level, [])
    if not above_files:
        return []
    words = load_words_from_files(above_files)
    if not words:
        return []
    return random.sample(words, min(n, len(words)))


def build_gemini_prompt(config: dict, sources: dict) -> str:
    cfg = config
    level = cfg["user"]["vocab_level"]
    level_label = VOCAB_LEVEL_LABELS.get(level, VOCAB_LEVEL_LABELS[3])
    host_m = cfg["show"]["host_male"]
    host_f = cfg["show"]["host_female"]
    duration = cfg["show"]["duration_minutes"]
    today = datetime.now().strftime("%B %d, %Y")

    weather = sources.get("weather")
    news = sources.get("news", [])
    wikipedia = sources.get("wikipedia")
    parenting = sources.get("parenting")

    content_blocks = []

    if weather:
        content_blocks.append(f"""[TODAY'S WEATHER in {weather['location']}]
Condition: {weather['description']}
High: {weather['temp_max']}°C / Low: {weather['temp_min']}°C
Rain probability: {weather['rain_probability']}%""")

    if news:
        news_text = "\n".join(
            f"- {a['title']}: {a['summary']}" for a in news
        )
        content_blocks.append(f"[NHK WORLD NEWS HEADLINES]\n{news_text}")

    if wikipedia:
        content_blocks.append(
            f"[ON THIS DAY]\nIn {wikipedia['year']}: {wikipedia['text']}"
        )

    if parenting:
        content_blocks.append(
            f"[PARENTING TIP from {parenting['source']}]\n"
            f"Topic: {parenting['title']}\n"
            f"{parenting['summary']}"
        )

    content_section = "\n\n".join(content_blocks)

    # Sample unknown words for calibration
    unknown_words = sample_unknown_words(level)
    if unknown_words:
        unknown_sample = ", ".join(unknown_words[:40])
        vocab_guidance = f"""
VOCABULARY CALIBRATION:
- Write all dialogue naturally at the {level_label} level.
- Do NOT simplify unnecessarily — maintain natural, engaging {level_label} English throughout.
- Words like these are ABOVE the listener's level: {unknown_sample}
- Choose 1 to 4 of these (or similar above-level words) to naturally weave into the conversation as "teaching moments": {host_m} encounters the word, asks {host_f} what it means, and {host_f} explains it simply and memorably within the flow of the conversation.
- For all other above-level words you might want to use, choose a natural {level_label}-appropriate alternative instead — do not water down the overall language level."""
    else:
        vocab_guidance = f"""
VOCABULARY:
- Write all dialogue naturally at the {level_label} level throughout."""

    prompt = f"""You are writing a fun, engaging morning radio show script for a Japanese adult learning English.

SHOW FORMAT:
- Today's date: {today}
- Two hosts: {host_m} (male) and {host_f} (female)
- Duration: approximately {duration} minutes when read aloud at a natural pace
- Style: warm, witty, entertaining radio banter — like two genuinely funny friends who also happen to be informative

HOST PERSONALITIES:
- {host_m}: Curious, slightly goofy, asks the questions listeners are thinking. Occasionally makes a bad pun or joke that {host_f} gently teases him about. Enthusiastic and likeable.
- {host_f}: Sharp, knowledgeable, warmly sarcastic. Enjoys correcting {host_m} with a smile. Brings the facts but never sounds like a textbook.
- Their dynamic: playful back-and-forth, light teasing, genuine warmth. NOT a straight news read — more like a podcast with personality.
{vocab_guidance}

CONTENT TO COVER (weave all sections naturally into the conversation):
{content_section}

SCRIPT REQUIREMENTS:
1. Open with a warm, energetic greeting — mention today's date and something immediately interesting or funny
2. Cover the weather with personality, not just facts (e.g., {host_m} complains, {host_f} teases)
3. Discuss news headlines conversationally — brief reactions, genuine opinions, not just summaries
4. Include the "On This Day" fact as a fun discovery moment, let the hosts react to it naturally
5. End with the parenting tip warmly and practically
6. Sprinkle in at least one genuine laugh moment (a joke, a funny reaction, an unexpected observation)
7. Handle vocabulary teaching moments naturally — they should feel like real conversation, not a lesson

OUTPUT FORMAT:
Return ONLY a valid JSON array — no markdown, no explanation, no code fences.
Each element must have exactly these three fields:
  "speaker": "{host_m}" or "{host_f}"
  "text": the English line (what they say)
  "ja": natural Japanese translation of that line

Example format:
[
  {{"speaker": "{host_m}", "text": "Good morning, everyone!", "ja": "みなさん、おはようございます！"}},
  {{"speaker": "{host_f}", "text": "Good morning, {host_m}!", "ja": "おはよう、{host_m}！"}}
]
"""
    return prompt


def generate_script(prompt: str) -> list[dict]:
    import time

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1"),
    )

    last_error = None
    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.9,
                    max_output_tokens=16384,
                ),
            )
            break
        except Exception as e:
            last_error = e
            wait = 15 * (attempt + 1)
            print(f"  Gemini attempt {attempt + 1} failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    else:
        raise last_error

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    # Extract JSON array if there's surrounding text
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]

    return json.loads(raw)


def save_content(date_str: str, script: list[dict], sources: dict, config: dict) -> Path:
    CONTENT_DIR.mkdir(exist_ok=True)
    output = {
        "date": date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vocab_level": config["user"]["vocab_level"],
        "script": script,
        "sources": sources,
    }
    path = CONTENT_DIR / f"{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return path


def main():
    config = load_config()

    # Override vocab_level from environment variable if provided (set by workflow_dispatch input)
    env_level = os.environ.get("VOCAB_LEVEL", "").strip()
    if env_level and env_level.isdigit() and int(env_level) in VOCAB_LEVEL_FILES:
        new_level = int(env_level)
        if new_level != config["user"]["vocab_level"]:
            print(f"  Overriding vocab_level: {config['user']['vocab_level']} → {new_level}")
            config["user"]["vocab_level"] = new_level
            save_config(config)

    date_str = datetime.now().strftime("%Y-%m-%d")
    email_to = config["email"]["to"]

    print(f"[{date_str}] Starting generation (vocab_level={config['user']['vocab_level']})...")

    sources = {}

    # Fetch weather
    if config["content"].get("weather"):
        try:
            loc = config["user"]["location"]
            sources["weather"] = fetch_weather(
                loc["latitude"], loc["longitude"], loc["name"]
            )
            print("  ✓ Weather fetched")
        except Exception as e:
            print(f"  ✗ Weather failed: {e}")

    # Fetch NHK news
    if config["content"].get("nhk_news"):
        try:
            sources["news"] = fetch_nhk_news(count=3)
            print(f"  ✓ News fetched ({len(sources['news'])} articles)")
        except Exception as e:
            print(f"  ✗ News failed: {e}")

    # Fetch Wikipedia On This Day
    if config["content"].get("wikipedia"):
        try:
            sources["wikipedia"] = fetch_on_this_day()
            print("  ✓ Wikipedia fetched")
        except Exception as e:
            print(f"  ✗ Wikipedia failed: {e}")

    # Fetch parenting topic
    if config["content"].get("parenting"):
        try:
            sources["parenting"] = fetch_parenting_topic()
            print("  ✓ Parenting topic fetched")
        except Exception as e:
            print(f"  ✗ Parenting failed: {e}")

    # Generate script with Gemini
    try:
        print("  Calling Gemini API...")
        prompt = build_gemini_prompt(config, sources)
        script = generate_script(prompt)
        print(f"  ✓ Script generated ({len(script)} lines)")
    except Exception as e:
        print(f"  ✗ Gemini failed: {e}")
        traceback.print_exc()
        send_email(
            to=email_to,
            subject=f"[English Daily] {date_str} — 生成に失敗しました",
            body=f"今日のコンテンツ生成に失敗しました。\n\nエラー:\n{traceback.format_exc()}",
        )
        sys.exit(1)

    # Save JSON
    output_path = save_content(date_str, script, sources, config)
    print(f"  ✓ Saved to {output_path}")

    # Send success email
    base_url = "https://yutamtam.github.io/english-daily"
    player_url = f"{base_url}/player.html?date={date_str}"

    send_email(
        to=email_to,
        subject=f"[English Daily] {date_str} の放送が届きました",
        body=f"今日の English Daily が生成されました。\n\n▶ 再生はこちら:\n{player_url}\n\n良い一日を！",
    )
    print("  ✓ Email sent")
    print("Done!")


if __name__ == "__main__":
    main()
