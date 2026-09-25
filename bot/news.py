"""Context layer: find a current news item via Google News RSS (free, no key, no account)."""
import re
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .http import get_bytes

RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def search(phrase, limit=5, recent="when:60d"):
    """Return up to `limit` recent articles: headline, source, date, url."""
    q = urllib.parse.quote(f"{phrase} {recent}".strip())
    try:
        root = ET.fromstring(get_bytes(RSS.format(q=q)))
    except Exception:
        return []
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        # Google appends " - Source" to titles; strip it so the headline is clean.
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        items.append(
            {
                "headline": title,
                "source": source or "Unknown source",
                "date": _date(item.findtext("pubDate")),
                "url": (item.findtext("link") or "").strip(),
                "snippet": _strip_html(item.findtext("description") or "")[:300],
            }
        )
        if len(items) >= limit:
            break
    return items


def _date(raw):
    try:
        return parsedate_to_datetime(raw).strftime("%d %b %Y")
    except Exception:
        return raw or "date unknown"


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
