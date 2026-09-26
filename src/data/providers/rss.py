"""RSS news provider (W2) — live Vietnamese financial news without credentials.

CaféF's market feed returns **valid RSS 2.0** over HTTPS (verified 2026-09-25), so
news can go live before any paid provider is available (KI-006/KI-007 block
market/fundamental feeds, not news).

Design notes:

* the feed is fetched with redirect following (CaféF answers ``302``) and a
  descriptive User-Agent;
* parsing uses the standard library only (``xml.etree`` + ``email.utils``) so no
  new dependency is required;
* symbol linking is a *deterministic heuristic*: an exact, uppercase,
  alphanumeric-boundary match against the reference universe. Vietnamese
  tickers are published in uppercase, so case-insensitive matching would add
  false positives (``docs/DATA_SOURCES.md`` §8.5 keeps this flagged as needing
  accuracy measurement).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from xml.etree import ElementTree

import httpx

from src.data.providers.base import DataProvider
from src.data.records import NewsItem

#: Descriptive UA — some news sites reject the default httpx agent.
DEFAULT_USER_AGENT = "DTCK/0.1 (+https://github.com/dvtung/DTCK)"
#: Stored content length cap (news bodies are long; the DB keeps text, not pages).
CONTENT_LIMIT = 4000

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """HTML/CDATA → plain text (single-spaced, trimmed)."""
    if not text:
        return ""
    plain = unescape(_TAG_RE.sub(" ", text))
    return _WS_RE.sub(" ", plain).strip()


def parse_pub_date(value: str) -> datetime | None:
    """Parse an RSS ``pubDate`` (RFC 822) or an Atom ISO timestamp, as UTC."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def match_symbols(text: str, universe: frozenset[str]) -> list[str]:
    """Exact, boundary-delimited ticker matches, sorted (deterministic)."""
    if not text or not universe:
        return []
    found = [
        symbol
        for symbol in universe
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])", text)
    ]
    return sorted(found)


def parse_feed(
    xml_text: str,
    *,
    source: str,
    universe: frozenset[str] = frozenset(),
    content_limit: int = CONTENT_LIMIT,
) -> list[NewsItem]:
    """Parse an RSS/Atom document into provider-agnostic ``NewsItem`` records.

    Items without a usable title or published timestamp are skipped (they cannot
    be stored honestly — ``news.title``/``published_at`` are NOT NULL).
    """
    root = ElementTree.fromstring(xml_text)  # provider feed we chose to trust
    items: list[NewsItem] = []
    for node in root.iter():
        if not node.tag.endswith("item") and not node.tag.endswith("entry"):
            continue
        fields: dict[str, str] = {}
        for child in node:
            if not isinstance(child.tag, str):
                continue
            key = child.tag.rsplit("}", 1)[-1]
            fields.setdefault(key, child.text or "")
        title = strip_html(fields.get("title", ""))
        published_at = parse_pub_date(fields.get("pubDate", "") or fields.get("updated", ""))
        if not title or published_at is None:
            continue
        content = strip_html(fields.get("description", "") or fields.get("summary", ""))
        items.append(
            NewsItem(
                source=source,
                title=title[:500],
                content=content[:content_limit],
                published_at=published_at,
                symbols=tuple(match_symbols(f"{title} {content}", universe)),
            )
        )
    items.sort(key=lambda item: item.published_at)
    return items


class RssNewsProvider(DataProvider):
    """Fetches news items from an RSS/Atom feed (``endpoints.news`` in the registry)."""

    id: str

    def __init__(
        self,
        *,
        provider_id: str,
        source: str,
        feed_url: str,
        timeout: float,
        max_retries: int,
        retry_backoff: float,
        universe: frozenset[str] = frozenset(),
        user_agent: str = DEFAULT_USER_AGENT,
        transport: Any | None = None,
    ) -> None:
        self.id = provider_id
        self._source = source
        self._url = feed_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._universe = universe
        self._user_agent = user_agent
        self._transport = transport  # injectable for tests (httpx.MockTransport)
        self.SUPPORTED_DATASETS = frozenset({"news"})

    def _fetch_text(self) -> str:
        """GET the feed, following redirects, with bounded retries."""
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        }
        last_error: Exception | None = None
        with httpx.Client(
            timeout=self._timeout, follow_redirects=True, transport=self._transport
        ) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = client.get(self._url, headers=headers)
                    response.raise_for_status()
                    return response.text
                except httpx.HTTPError as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    time.sleep(min(self._retry_backoff * (attempt + 1), 30))
        raise ConnectionError(
            f"provider '{self.id}' failed after {self._max_retries + 1} attempts: {last_error}"
        )

    def fetch_news(self, since: datetime) -> list[NewsItem]:
        """News items published strictly after ``since`` (oldest first)."""
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)
        items = parse_feed(self._fetch_text(), source=self._source, universe=self._universe)
        return [item for item in items if item.published_at > since]


__all__ = [
    "CONTENT_LIMIT",
    "DEFAULT_USER_AGENT",
    "RssNewsProvider",
    "match_symbols",
    "parse_feed",
    "parse_pub_date",
    "strip_html",
]
