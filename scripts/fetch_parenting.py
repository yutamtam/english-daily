import random
import feedparser


ZERO_TO_THREE_FEED = "https://www.zerotothree.org/feed/"

# Fallback topics if RSS is unavailable
FALLBACK_TOPICS = [
    "The importance of reading aloud to babies every day",
    "How to respond to a toddler's tantrums calmly",
    "Screen time guidelines for children under 2 years old",
    "Why outdoor play is essential for child development",
    "How to build a healthy sleep routine for infants",
    "The role of play in developing social skills",
    "How to encourage language development in toddlers",
    "Understanding separation anxiety in young children",
    "The benefits of skin-to-skin contact for newborns",
    "How to introduce solid foods safely to your baby",
    "Why praising effort matters more than praising intelligence",
    "How to handle picky eating in young children",
    "The importance of consistent daily routines for toddlers",
    "How music supports brain development in early childhood",
    "Understanding and supporting your child's emotional development",
    "How fathers can bond with newborns",
    "The benefits of baby-led weaning",
    "How to manage sibling rivalry",
    "Why imaginative play is crucial for cognitive development",
    "How to talk to children about difficult emotions",
]


def fetch_parenting_topic() -> dict:
    try:
        feed = feedparser.parse(ZERO_TO_THREE_FEED)
        entries = [e for e in feed.entries if e.get("title") and e.get("summary")]
        if entries:
            entry = random.choice(entries[:10])
            return {
                "source": "Zero to Three",
                "title": entry.title,
                "summary": entry.get("summary", "")[:400],
            }
    except Exception:
        pass

    # Fallback to curated topics
    topic = random.choice(FALLBACK_TOPICS)
    return {
        "source": "parenting tip",
        "title": topic,
        "summary": "",
    }
