#!/usr/bin/env python3
"""
Main script: fetch content, generate script with Gemini, save JSON, send email.
Run daily via GitHub Actions at UTC 21:00 (JST 06:00).
"""

import argparse
import json
import os
import random
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

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

def _svl(n): return [f"svl_{i:02d}.json" for i in range(1, n + 1)]
def _kyo(n): return [f"kyokugen_{i}.json" for i in range(13, n + 1)]
def _shu(n): return [f"shukyoku_{i}.json" for i in range(25, n + 1)]

VOCAB_LEVEL_FILES = {
    1:  _svl(3),
    2:  _svl(6),
    3:  _svl(9),
    4:  _svl(12),
    5:  _svl(12) + _kyo(15),
    6:  _svl(12) + _kyo(18),
    7:  _svl(12) + _kyo(21),
    8:  _svl(12) + _kyo(24),
    9:  _svl(12) + _kyo(24) + _shu(27),
    10: _svl(12) + _kyo(24) + _shu(30),
    11: _svl(12) + _kyo(24) + _shu(34),
}

ABOVE_LEVEL_FILES = {
    1:  [f"svl_{i:02d}.json" for i in range(4, 7)],
    2:  [f"svl_{i:02d}.json" for i in range(7, 10)],
    3:  [f"svl_{i:02d}.json" for i in range(10, 13)],
    4:  [f"kyokugen_{i}.json" for i in range(13, 16)],
    5:  [f"kyokugen_{i}.json" for i in range(16, 19)],
    6:  [f"kyokugen_{i}.json" for i in range(19, 22)],
    7:  [f"kyokugen_{i}.json" for i in range(22, 25)],
    8:  [f"shukyoku_{i}.json" for i in range(25, 28)],
    9:  [f"shukyoku_{i}.json" for i in range(28, 31)],
    10: [f"shukyoku_{i}.json" for i in range(31, 34)],
    11: [],
}

VOCAB_LEVEL_LABELS = {
    1:  "beginner (~3,000 words, junior high school level)",
    2:  "lower-intermediate (~6,000 words, high school level)",
    3:  "intermediate (~9,000 words, TOEIC 600-700 level)",
    4:  "upper-intermediate (~12,000 words, TOEIC 800 level)",
    5:  "pre-advanced (~15,000 words, TOEIC 850 level)",
    6:  "advanced (~18,000 words, TOEIC 900 level)",
    7:  "advanced+ (~21,000 words)",
    8:  "very advanced (~24,000 words, English newspaper level)",
    9:  "very advanced+ (~27,000 words)",
    10: "near-native (~30,000 words)",
    11: "native (~34,000 words)",
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
    level_label = VOCAB_LEVEL_LABELS.get(level, VOCAB_LEVEL_LABELS[4])
    host_m = cfg["show"]["host_male"]
    host_f = cfg["show"]["host_female"]
    show_name = cfg["show"].get("name", "The Daily Tanu-chan Show")
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

    prompt = f"""You are writing a morning radio show script for a Japanese adult learning English.

SHOW FORMAT:
- Show name: {show_name}
- Today's date: {today}
- Two hosts: {host_m} (male) and {host_f} (female)
- Duration: approximately {duration} minutes when read aloud at a natural pace
- Style: two real people having a natural conversation. Like colleagues catching up before work — not a performance, not a show.
- The hosts should mention the show name ("{show_name}") once, naturally.

HOST CHARACTERS:

{host_m} — Japanese man, early 30s, office worker (sales or planning type).
- His first child was born in June 2025. He is very much in it right now.
- Sleep-deprived but not dramatic about it. States facts flatly: "Baby was up at 3. And then 5."
- Coffee is non-negotiable. He will mention it.
- His humor: says something slightly off without realizing it. Not a comedian, just a bit scattered.
- On news: reacts honestly. "That's not going to change at my office." "I feel like I read this every year."
- On things he doesn't know: "Oh, I didn't know that." Not "Fascinating!" Just genuine.
- Sometimes goes slightly off-topic, then catches himself.
- Does NOT say: "Absolutely!" "For sure!" "That's a great point!" "I would like that very much."

{host_f} — Japanese woman, early 50s, experienced professional (education, healthcare, or similar).
- Two children, born 2000 and 2003. Both adults now. She's been through everything {host_m} is going through.
- Stable energy. Never flustered. Drinks tea, not coffee.
- Her advice: one sentence, practical, no lecture. "That's normal. It ends around two." Done.
- Her humor: quiet. Either corrects {host_m} with a flat statement or lets it go entirely.
- On news and social issues: has opinions, states them briefly, doesn't push.
- Occasionally mentions her kids as a passing reference: "Mine did the same. It passes."
- Does NOT deliver philosophical closing lines. Does NOT say "That's just how it goes" in a wise-mentor tone.
- Does NOT say: "Absolutely!" "Revolutionary concept." "That's so true!"

DYNAMIC:
{host_f} is a full generation older than {host_m}. She's seen it all. She doesn't need to prove it.
{host_m} sometimes asks her things expecting reassurance. Her answers are shorter than he expects.
The humor comes from the gap between his anxiety and her calm — not from jokes or wordplay.
Silences are fine. Short responses are fine. "...yeah." is a valid line.

DIALOGUE RULES — CRITICAL:
- Conversational exchanges (reactions, feelings, small talk): keep to 1-2 sentences. Short is natural.
- News, facts, or vocabulary explanations: can be a bit longer, but still spoken — not a lecture.
- Never stack unrelated observations in one turn. One topic, one reaction, then hand it back.
- Don't let one person go more than 4-5 sentences without the other responding.
- English must sound natural and spoken. Always use contractions: I'm, it's, that's, don't, can't, won't.
- Avoid formal or written-style constructions:
    BAD:  "I find that quite remarkable."
    GOOD: "That's kind of amazing, actually."
    BAD:  "Any sudden noise, I jump. Could be the baby."
    GOOD: "I jump at everything these days. Pretty sure it's the baby."
{vocab_guidance}

CONTENT TO COVER (weave naturally into conversation — do not announce each segment):
{content_section}

SCRIPT REQUIREMENTS:
1. Open simply — just greet, say the date, get into it. No fanfare.
2. Weather: one of them mentions it, the other reacts like a real person (not a weather anchor).
3. News: brief, honest reactions. Personal opinions over summaries. Skip anything too heavy for morning.
4. "On This Day": treat it as something one of them just found out. React naturally, not dramatically.
5. Parenting tip: make it feel relevant to {host_m}'s current situation. {host_f} adds lived experience briefly.
6. At least one moment where the humor lands quietly — not a joke, just an exchange where the gap between them is funny.
7. Vocabulary teaching: {host_m} hits an unfamiliar word naturally, {host_f} clarifies in one line, conversation moves on.

OUTPUT FORMAT:
Return ONLY a valid JSON array — no markdown, no explanation, no code fences.
Each element must have exactly these three fields:
  "speaker": "{host_m}" or "{host_f}"
  "text": the English line (what they say)
  "ja": natural Japanese translation of that line

Example format:
[
  {{"speaker": "{host_m}", "text": "Morning. June 17th.", "ja": "おはようございます。6月17日です。"}},
  {{"speaker": "{host_f}", "text": "You look tired.", "ja": "疲れてるね。"}}
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
        http_options=types.HttpOptions(api_version="v1beta"),
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
                    response_mime_type="application/json",
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


def build_email_html(date_str: str, script: list[dict], player_url: str, config: dict) -> tuple[str, str]:
    """Return (plain_text, html) for the success email."""
    show_name = config["show"].get("name", "The Daily Tanu-chan Show")
    level = config["user"]["vocab_level"]
    level_label = VOCAB_LEVEL_LABELS.get(level, "")

    # Plain text fallback
    lines_plain = []
    for line in script:
        lines_plain.append(f"[{line['speaker']}] {line['text']}")
        lines_plain.append(f"  {line['ja']}")
        lines_plain.append("")
    plain = (
        f"{show_name} — {date_str}\n"
        f"語彙レベル: {level} ({level_label})\n\n"
        f"▶ 再生: {player_url}\n\n"
        + "\n".join(lines_plain)
    )

    # HTML
    script_rows = []
    for line in script:
        is_alex = line["speaker"] == config["show"]["host_male"]
        bg = "#e8f4fd" if is_alex else "#fdf0e8"
        border = "#93c5fd" if is_alex else "#fca5a5"
        script_rows.append(f"""
        <div style="background:{bg};border-left:4px solid {border};border-radius:8px;
                    padding:10px 14px;margin-bottom:8px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;
                      letter-spacing:0.08em;color:#6b7280;margin-bottom:4px;">
            {line['speaker']}
          </div>
          <div style="font-size:15px;line-height:1.6;color:#1a1a1a;">
            {line['text']}
          </div>
          <div style="font-size:13px;color:#6b7280;margin-top:3px;line-height:1.5;">
            {line['ja']}
          </div>
        </div>""")

    script_html = "\n".join(script_rows)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f8f6f1;margin:0;padding:20px;">
  <div style="max-width:600px;margin:0 auto;">
    <div style="background:#2d6a4f;color:white;border-radius:12px 12px 0 0;
                padding:20px 24px;text-align:center;">
      <div style="font-size:20px;font-weight:700;">{show_name}</div>
      <div style="font-size:13px;opacity:0.85;margin-top:4px;">{date_str} ／ 語彙レベル {level}</div>
    </div>

    <div style="background:white;padding:16px 24px;border-left:1px solid #e5e7eb;
                border-right:1px solid #e5e7eb;">
      <a href="{player_url}"
         style="display:block;background:#2d6a4f;color:white;text-decoration:none;
                text-align:center;padding:12px;border-radius:8px;font-weight:700;
                font-size:15px;margin-bottom:16px;">
        ▶ ブラウザで再生する
      </a>
    </div>

    <div style="background:white;padding:16px 24px;border:1px solid #e5e7eb;
                border-radius:0 0 12px 12px;">
      {script_html}
    </div>

    <div style="text-align:center;font-size:12px;color:#9ca3af;margin-top:12px;">
      良い一日を！
    </div>
  </div>
</body>
</html>"""

    return plain, html


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


def send_daily_email(date_str: str, config: dict) -> None:
    path = CONTENT_DIR / f"{date_str}.json"
    if not path.exists():
        raise FileNotFoundError(f"No content for {date_str}. Was generation successful?")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    base_url = "https://yutamtam.github.io/english-daily"
    player_url = f"{base_url}/player.html?date={date_str}"
    show_name = config["show"].get("name", "The Daily Tanu-chan Show")
    plain, html = build_email_html(date_str, data["script"], player_url, config)
    send_email(
        to=config["email"]["to"],
        subject=f"[{show_name}] {date_str} の放送が届きました",
        body=plain,
        html=html,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["generate", "send", "full"],
        default="full",
        help="generate=content only, send=email only, full=both (default)",
    )
    args = parser.parse_args()

    config = load_config()

    env_level = os.environ.get("VOCAB_LEVEL", "").strip()
    if env_level and env_level.isdigit() and int(env_level) in range(1, 12):
        new_level = int(env_level)
        if new_level != config["user"]["vocab_level"]:
            print(f"  Overriding vocab_level: {config['user']['vocab_level']} → {new_level}")
            config["user"]["vocab_level"] = new_level
            save_config(config)

    date_str = datetime.now(JST).strftime("%Y-%m-%d")
    email_to = config["email"]["to"]

    if args.mode in ("generate", "full"):
        print(f"[{date_str}] Generating (vocab_level={config['user']['vocab_level']})...")
        sources = {}

        if config["content"].get("weather"):
            try:
                loc = config["user"]["location"]
                sources["weather"] = fetch_weather(loc["latitude"], loc["longitude"], loc["name"])
                print("  ✓ Weather fetched")
            except Exception as e:
                print(f"  ✗ Weather failed: {e}")

        if config["content"].get("nhk_news"):
            try:
                sources["news"] = fetch_nhk_news(count=3)
                print(f"  ✓ News fetched ({len(sources['news'])} articles)")
            except Exception as e:
                print(f"  ✗ News failed: {e}")

        if config["content"].get("wikipedia"):
            try:
                sources["wikipedia"] = fetch_on_this_day()
                print("  ✓ Wikipedia fetched")
            except Exception as e:
                print(f"  ✗ Wikipedia failed: {e}")

        if config["content"].get("parenting"):
            try:
                sources["parenting"] = fetch_parenting_topic()
                print("  ✓ Parenting topic fetched")
            except Exception as e:
                print(f"  ✗ Parenting failed: {e}")

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

        output_path = save_content(date_str, script, sources, config)
        print(f"  ✓ Saved to {output_path}")

    if args.mode in ("send", "full"):
        print(f"[{date_str}] Sending email...")
        try:
            send_daily_email(date_str, config)
            print("  ✓ Email sent")
        except Exception as e:
            print(f"  ✗ Email failed: {e}")
            traceback.print_exc()
            sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    main()
