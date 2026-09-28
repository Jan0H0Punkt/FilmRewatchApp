"""Fetch and parse the Letterboxd member RSS feed (REQ §5.7, FR-LBX-01/02).

Stdlib only — ``urllib`` as in ``films/service/poster_palette.py``, ``xml.etree``
for the parse. The feed holds the member's last 50 diary entries, newest-logged
first, followed by list posts; list posts carry no watch date and are skipped.
"""

import http.client
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from app.letterboxd.errors import LetterboxdUnavailableError

_NS = "{https://letterboxd.com}"
_TIMEOUT_SECONDS = 10
_USER_AGENT = "Mozilla/5.0 (compatible; FilmRewatchApp/1.0; Letterboxd sync)"
_LETTERBOXD_HOSTS = frozenset({"letterboxd.com", "www.letterboxd.com"})
# Matches the canonical ``/film/<slug>/`` and a member's diary link
# ``/<user>/film/<slug>/<n>/`` alike.
_SLUG_PATTERN = re.compile(r"/film/([^/]+)")


def film_slug(url: str) -> str | None:
    """The film slug of a letterboxd.com URL; ``None`` for anything else, e.g. a ``boxd.it`` short link."""
    parts = urlsplit(url.strip())
    if parts.hostname not in _LETTERBOXD_HOSTS:
        return None
    match = _SLUG_PATTERN.search(parts.path)
    return match.group(1).lower() if match else None


def canonical_film_url(slug: str) -> str:
    """The film's own Letterboxd page — the form stored in ``films.letterboxd_url``."""
    return f"https://letterboxd.com/film/{slug}/"


@dataclass(frozen=True)
class FeedEntry:
    """One diary entry of the feed."""

    guid: str
    film_title: str
    film_year: int
    film_slug: str
    watched_date: date
    rating: Decimal | None  # None: logged without a rating (FR-LBX-08)
    rewatch: bool

    @property
    def film_url(self) -> str:
        return canonical_film_url(self.film_slug)


def parse_feed(xml: bytes) -> list[FeedEntry]:
    """The feed's diary entries in feed order; an item missing a field the sync needs is skipped."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as error:
        raise LetterboxdUnavailableError("The Letterboxd feed could not be parsed.") from error
    return [entry for item in root.iter("item") if (entry := _entry_from(item)) is not None]


def _entry_from(item: ET.Element) -> FeedEntry | None:
    guid = item.findtext("guid")
    link = item.findtext("link")
    watched = item.findtext(f"{_NS}watchedDate")
    title = item.findtext(f"{_NS}filmTitle")
    year = item.findtext(f"{_NS}filmYear")
    if guid is None or link is None or watched is None or title is None or year is None:
        return None
    slug = film_slug(link)
    if slug is None:
        return None
    rating = item.findtext(f"{_NS}memberRating")
    try:
        return FeedEntry(
            guid=guid.strip(),
            film_title=title.strip(),
            film_year=int(year),
            film_slug=slug,
            watched_date=date.fromisoformat(watched.strip()),
            rating=Decimal(rating) if rating else None,
            rewatch=item.findtext(f"{_NS}rewatch") == "Yes",
        )
    except (ValueError, InvalidOperation):
        return None


def fetch_feed(username: str) -> list[FeedEntry]:
    """Download and parse the member's feed; any network failure is :class:`LetterboxdUnavailableError`."""
    url = f"https://letterboxd.com/{urllib.parse.quote(username, safe='')}/rss/"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body: bytes = response.read()
    # OSError covers URLError/TimeoutError/ConnectionResetError (connect-time
    # failures); HTTPException covers a connection dropped mid-read, e.g.
    # IncompleteRead or RemoteDisconnected.
    except (OSError, http.client.HTTPException) as error:
        raise LetterboxdUnavailableError() from error
    return parse_feed(body)
