"""Letterboxd feed parsing and fetching (spec 2026-09-28-letterboxd-sync). Offline."""

import urllib.error
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.letterboxd import feed
from app.letterboxd.errors import LetterboxdUnavailableError
from app.letterboxd.feed import FeedEntry, film_slug, parse_feed

_FIXTURE = Path(__file__).parent / "fixtures" / "letterboxd_feed.xml"


def _entries() -> list[FeedEntry]:
    return parse_feed(_FIXTURE.read_bytes())


def test_parses_only_diary_entries_in_feed_order() -> None:
    assert [entry.guid for entry in _entries()] == [
        "letterboxd-watch-1513860295",
        "letterboxd-watch-1490000001",
        "letterboxd-watch-1400000002",
    ]


def test_parses_every_field_of_a_rated_rewatch() -> None:
    assert _entries()[0] == FeedEntry(
        guid="letterboxd-watch-1513860295",
        film_title="The Good, the Bad and the Ugly",
        film_year=1966,
        film_slug="the-good-the-bad-and-the-ugly",
        watched_date=date(2026, 9, 27),
        rating=Decimal("4.5"),
        rewatch=True,
    )


def test_decodes_html_entities_in_titles() -> None:
    assert _entries()[1].film_title == "Don't Worry Darling"


def test_an_entry_without_a_member_rating_is_unrated() -> None:
    unrated = _entries()[2]
    assert unrated.rating is None
    assert unrated.rewatch is False


def test_film_url_is_the_canonical_film_page() -> None:
    assert _entries()[2].film_url == "https://letterboxd.com/film/wings-of-hope/"


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://letterboxd.com/film/princess-mononoke/", "princess-mononoke"),
        ("https://letterboxd.com/film/princess-mononoke", "princess-mononoke"),
        ("https://www.letterboxd.com/film/princess-mononoke/", "princess-mononoke"),
        ("https://letterboxd.com/janhy/film/pulse-2001/1/", "pulse-2001"),
        ("  https://letterboxd.com/film/Heat/  ", "heat"),
        ("https://boxd.it/2aBc", None),
        ("https://letterboxd.com/janhy/list/best-of-2025/", None),
        ("not a url", None),
    ],
)
def test_film_slug(url: str, slug: str | None) -> None:
    assert film_slug(url) == slug


def test_malformed_xml_is_unavailable() -> None:
    with pytest.raises(LetterboxdUnavailableError):
        parse_feed(b"<html>Cloudflare says no</html")


def test_an_item_with_an_unparseable_year_is_skipped() -> None:
    xml = _FIXTURE.read_bytes().replace(b"<letterboxd:filmYear>1966", b"<letterboxd:filmYear>n/a")
    assert [entry.film_year for entry in parse_feed(xml)] == [2022, 1999]


def test_fetch_failure_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(feed.urllib.request, "urlopen", refuse)
    with pytest.raises(LetterboxdUnavailableError):
        feed.fetch_feed("janhy")
