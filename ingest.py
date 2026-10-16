"""Pull articles from the configured RSS feeds, tag them, and store new ones."""

import logging
import re
from calendar import timegm
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import requests

from config import KEYWORDS, RSS_FEEDS
from db import init_db, insert_article

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
USER_AGENT = "news-dashboard/1.0 (+https://github.com/)"

# Whole-word, case-insensitive matching so short keywords like "AI" don't match
# inside unrelated words (e.g. "daily", "email", "said").
_KEYWORD_PATTERNS = [
    (kw, re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)) for kw in KEYWORDS
]


def tag_article(text):
    """Return a comma-separated string of KEYWORDS found in text as whole words."""
    if not text:
        return ""
    matched = [kw for kw, pattern in _KEYWORD_PATTERNS if pattern.search(text)]
    return ", ".join(matched)


def parse_published_date(entry):
    """Return an ISO 8601 string for the entry's published/updated date, if available."""
    for field in ("published_parsed", "updated_parsed"):
        struct = entry.get(field)
        if struct:
            return datetime.fromtimestamp(timegm(struct), tz=timezone.utc).isoformat()
    return entry.get("published") or entry.get("updated") or ""


def fetch_feed(feed_url):
    """Download and parse a single feed. Raises on network errors."""
    response = requests.get(
        feed_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def ingest_feed(feed_url):
    """Fetch one feed and insert any new articles. Returns count of articles added."""
    parsed = fetch_feed(feed_url)

    if parsed.bozo and not parsed.entries:
        raise parsed.bozo_exception or ValueError("feed could not be parsed")

    source = parsed.feed.get("title") or urlparse(feed_url).netloc
    fetched_date = datetime.now(timezone.utc).isoformat()
    added = 0

    for entry in parsed.entries:
        title = entry.get("title", "")
        url = entry.get("link", "")
        if not url:
            continue

        article = {
            "title": title,
            "url": url,
            "source": source,
            "published_date": parse_published_date(entry),
            "fetched_date": fetched_date,
            "tags": tag_article(f"{title} {entry.get('summary', '')}"),
            "status": "new",
        }

        if insert_article(article):
            added += 1

    return added


def run():
    init_db()
    total_added = 0

    for feed_url in RSS_FEEDS:
        try:
            added = ingest_feed(feed_url)
            logger.info("%s: %d new article(s)", feed_url, added)
            total_added += added
        except Exception as exc:
            logger.error("Failed to ingest feed %s: %s", feed_url, exc)
            continue

    print(f"New articles added: {total_added}")
    return total_added


if __name__ == "__main__":
    run()
