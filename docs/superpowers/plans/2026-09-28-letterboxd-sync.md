# Letterboxd Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read the user's Letterboxd RSS feed once a day and queue every new diary entry in a review list, where the user approves, reassigns, creates or dismisses it.

**Architecture:** A new backend module `app/letterboxd/` (feed parser, sync + review service, one table, four routes, a lifespan background loop) and a new frontend domain `domain/letterboxd/` plus review view `views/letterboxd/`. The sync never writes a watch; only the user's review actions do, through the existing `FilmService.add_rating`/`update`. "Create film" reuses the existing film form through query-param prefill.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 strict, pytest (backend, `uv run`); Angular 22 standalone + signals + Angular Material M3, vitest (frontend, `npm`).

**Spec:** `docs/superpowers/specs/2026-09-28-letterboxd-sync-design.md`

## Global Constraints

- One-way only: Letterboxd → app. Nothing is written to Letterboxd.
- **The sync never adds a watch or edits a film.** Only `assign` (approve/assign) does.
- No new dependency on either tier. Feed: `urllib.request` + `xml.etree.ElementTree`.
- Unrated stays unrated: an absent `memberRating` is `NULL`, never imputed (FR-RAT-12).
- Stop rule: stop at the first diary entry whose `guid` is already in `letterboxd_entries`, or whose matched film already has a watch on its `watched_date`. Future-dated entries are skipped, not stopped at.
- Config: `LETTERBOXD_USERNAME`; empty disables the sync (no loop; `POST /letterboxd/sync` → `409 LETTERBOXD_DISABLED`).
- Error codes: `LETTERBOXD_DISABLED` 409, `LETTERBOXD_UNAVAILABLE` 502, `ENTRY_RESOLVED` 409, `NOT_FOUND` 404. All in the single envelope (NFR-MAINT-03).
- Backend gate (from `backend/`): `make typecheck`, `make lint`, `make format-check`, `make test`. Frontend gate (from `frontend/`): `npm run build`, `npm test`, `npm run lint`, `npm run format:check`. **Never `npx`.**
- Backend tests need the composed Postgres (`docker compose up -d postgres` from the repo root).
- Commit subjects: one line, `<type>(<area>): <effect>`, no trailers. Stage files by name.
- All code, comments and docs in English. Docstrings cite spec/REQ IDs as pointers; keep them short (code-docs skill).

## Review Focus

1. **Titles with HTML entities or non-ASCII characters** (`Don&#039;t Worry Darling`, `回路`): the parser must decode them and the title match must compare decoded, case-insensitive, trimmed text. → Task 2 parser test, Task 4 match test.
2. **Letterboxd links in other shapes on existing films** (`boxd.it/abc`, `www.letterboxd.com`, no trailing slash, member-scoped `/<user>/film/<slug>/`): `film_slug` must return the slug for every letterboxd.com shape and `None` for `boxd.it`. → Task 2 `film_slug` tests.
3. **Letterboxd unreachable or answering garbage** (timeout, 403, HTML error page): `fetch_feed` raises `LetterboxdUnavailableError`; the background loop logs and retries next hour instead of dying. → Task 2 fetch-failure test, Task 6 scheduler test.
4. **Sync run twice over the same feed** (button pressed while the daily run just finished): the second run queues nothing. → Task 4 idempotency test.
5. **Suggested film deleted before review**: the FK nulls out, the entry stays open without a suggestion. → Task 3 DB test.

---

## File Structure

**Backend (create)**
- `backend/app/letterboxd/__init__.py` — empty.
- `backend/app/letterboxd/errors.py` — the four domain errors.
- `backend/app/letterboxd/feed.py` — `FeedEntry`, `film_slug`, `canonical_film_url`, `parse_feed`, `fetch_feed`.
- `backend/app/letterboxd/models.py` — `LetterboxdEntry` ORM model.
- `backend/app/letterboxd/repository.py` — `LetterboxdRepository`.
- `backend/app/letterboxd/service.py` — `match_film`, `run_sync`, `LetterboxdService`.
- `backend/app/letterboxd/schemas.py` — read/write schemas.
- `backend/app/letterboxd/dependencies.py` — DI wiring.
- `backend/app/letterboxd/router.py` — the four routes.
- `backend/app/letterboxd/scheduler.py` — `sync_once`, `run_periodically`.
- `backend/migrations/versions/0011_letterboxd_entries.py`
- `backend/tests/fixtures/letterboxd_feed.xml`
- `backend/tests/test_letterboxd_feed.py`, `test_letterboxd_repository.py`, `test_letterboxd_service.py`, `test_letterboxd_api.py`, `test_letterboxd_scheduler.py`

**Backend (modify)**
- `backend/app/core/config.py` (+ `letterboxd_username`), `backend/.env.example`, `.env.example` (root), `docker-compose.yml`
- `backend/app/main.py` (router + lifespan)
- `backend/app/core/errors.py` (docstring inventory table)
- `backend/tests/test_db_plumbing.py` (table guard), `backend/tests/test_openapi_contract.py` (expected routes)

**Frontend (create)**
- `frontend/src/app/domain/letterboxd/{model.ts,api.ts,mapper.ts,facade.ts,letterboxd-facade.spec.ts}`
- `frontend/src/app/views/letterboxd/{letterboxd.ts,letterboxd.html,letterboxd.scss,letterboxd.spec.ts,assign-dialog.ts}`

**Frontend (modify)**
- `frontend/src/app/views/film-form/film-form.ts` (+ spec) — prefill inputs, return target.
- `frontend/src/app/core/route-registry.ts` (`navBadge`), `core/routes.registry.ts` (entry), `app.ts`, `app.html`, `app.spec.ts`.

**Docs (modify)**
- `docs/requirements/REQUIREMENTS_V1.md`, `docs/designs/DESIGN_V1.md`

---

### Task 1: Requirements and design docs

**Files:**
- Modify: `docs/requirements/REQUIREMENTS_V1.md` (§1.3 scope lists ~line 48-72, new §5.7 before `## 6. Extensibility Requirements` ~line 555, Table of Contents ~line 11-32, Revision History at the end)
- Modify: `docs/designs/DESIGN_V1.md` (new §5.9 after §5.8 ~line 394-423, §6.5 view list ~line 515, Table of Contents)

**Interfaces:** none (docs only). Later tasks cite `FR-LBX-01..08` exactly as defined here.

- [ ] **Step 1: REQ §1.3 scope**

In the in-scope list, after the "Write operations performed while offline…" bullet, add:

```markdown
- A one-way Letterboxd sync: new Letterboxd diary entries are queued for the user's review (see §5.7).
```

In the out-of-scope list, replace `- Export or import of data.` with:

```markdown
- Export of data; import of data other than the Letterboxd sync (§5.7).
```

- [ ] **Step 2: REQ new §5.7**

Insert before `## 6. Extensibility Requirements` (and add `5.7 Letterboxd Sync` to the Table of Contents in the same style as its neighbours):

```markdown
### 5.7 Letterboxd Sync

The user also logs films on Letterboxd. New Letterboxd diary entries are brought into the app one way (Letterboxd → app) and
**only with the user's approval**. Design: `docs/superpowers/specs/2026-09-28-letterboxd-sync-design.md`.

- **FR-LBX-01:** The source is the public RSS feed of the Letterboxd member named by the `LETTERBOXD_USERNAME` setting. With no
  username set, the sync is off. The backend checks hourly and syncs when the last sync is more than 24 hours old, and once on every
  start; the user can also trigger a sync manually.
- **FR-LBX-02:** Only diary entries (items with a watch date) are read, newest-logged first. The sync stops at the first entry already
  known: its Letterboxd id is already in the review list (open or resolved), or its matched film already has a watch on that date.
- **FR-LBX-03:** An entry dated after the server's current date is skipped without stopping and retried by the next sync.
- **FR-LBX-04:** An entry is matched to a film by its Letterboxd link first (the film's `letterboxd_url` slug on letterboxd.com), then
  by title and year against every title of a film (case-insensitive, trimmed). Exactly one match becomes the entry's suggested film;
  zero or several leave it without one.
- **FR-LBX-05:** The sync never adds a watch or edits a film. Every new entry is stored in the review list.
- **FR-LBX-06:** Per open entry the user can **approve** the suggestion or **assign** another film (both add the watch with the entry's
  date and rating, and set the film's `letterboxd_url` when it has none), **create** the film through the prefilled film form, or
  **dismiss** the entry. A resolved entry cannot be acted on again.
- **FR-LBX-07:** An open entry whose film now has a watch on the entry's date (e.g. the user created the film from the form) is
  resolved automatically the next time the list is read.
- **FR-LBX-08:** An entry without a Letterboxd rating is an unrated watch (FR-RAT-12); no rating is imputed.
```

- [ ] **Step 3: REQ revision history**

Add a row at the end of the Revision History table:

```markdown
| 1.5     | 2026-09-28 | Letterboxd sync (§5.7, FR-LBX-01..08): a one-way, approval-first import of Letterboxd diary entries through the member RSS feed. "Import of data" leaves the out-of-scope list only for this path (§1.3). |
```

- [ ] **Step 4: DESIGN new §5.9 and §6.5**

After §5.8 (before `## 6. Frontend Design`) insert, and add it to the Table of Contents:

```markdown
### 5.9 Letterboxd Sync

`app/letterboxd/` (REQ §5.7) reads `https://letterboxd.com/<LETTERBOXD_USERNAME>/rss/` with `urllib` and `xml.etree`, no
dependency. `run_sync` walks the diary entries newest-logged first and stores each new one in `letterboxd_entries` (with a
`suggested_film_id` when exactly one film matches) until the FR-LBX-02 stop rule fires; it never writes a watch. The review routes
under `/api/v1/letterboxd` (`GET /entries`, `POST /entries/{id}/assign`, `POST /entries/{id}/dismiss`, `POST /sync`) resolve entries;
`assign` goes service-to-service through `FilmService.add_rating`/`update`, so the rewatch projection is invalidated as for any
other watch. The FastAPI lifespan starts one asyncio task (`scheduler.run_periodically`) when a username is set: an hourly wall-clock
check that runs the sync in a worker thread once the last success is 24 h old. A module-level lock keeps the scheduled and the
manual sync from overlapping; the `guid` unique constraint is the backstop.
```

In §6.5 (Views & Navigation), add the review view to the list of primary destinations in the same style as the Statistics/Settings entries: `letterboxd` — the Letterboxd review list (REQ §5.7), a primary navigation destination whose icon carries the number of open entries.

- [ ] **Step 5: Commit**

```bash
git add docs/requirements/REQUIREMENTS_V1.md docs/designs/DESIGN_V1.md
git commit -m "docs(letterboxd): specify the approval-first Letterboxd sync (FR-LBX-01..08)"
```

---

### Task 2: Feed parser and domain errors

**Files:**
- Create: `backend/app/letterboxd/__init__.py` (empty), `backend/app/letterboxd/errors.py`, `backend/app/letterboxd/feed.py`
- Create: `backend/tests/fixtures/letterboxd_feed.xml`, `backend/tests/test_letterboxd_feed.py`

**Interfaces:**
- Produces:
  - `errors.LetterboxdDisabledError()`, `errors.LetterboxdUnavailableError(message: str | None = None)`, `errors.EntryNotFoundError(entry_id: uuid.UUID)`, `errors.EntryResolvedError(entry_id: uuid.UUID)` — all `AppError` subclasses.
  - `feed.FeedEntry` (frozen dataclass): `guid: str`, `film_title: str`, `film_year: int`, `film_slug: str`, `watched_date: date`, `rating: Decimal | None`, `rewatch: bool`, property `film_url -> str`.
  - `feed.film_slug(url: str) -> str | None`, `feed.canonical_film_url(slug: str) -> str`, `feed.parse_feed(xml: bytes) -> list[FeedEntry]`, `feed.fetch_feed(username: str) -> list[FeedEntry]`.

- [ ] **Step 1: Create the fixture** `backend/tests/fixtures/letterboxd_feed.xml` (a trimmed copy of the real feed):

```xml
<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:letterboxd="https://letterboxd.com" xmlns:tmdb="https://themoviedb.org">
	<channel>
		<title>Letterboxd - Jan</title>
		<link>https://letterboxd.com/janhy/</link>
		<item> <title>The Good, the Bad and the Ugly, 1966 - ★★★★½</title> <link>https://letterboxd.com/janhy/film/the-good-the-bad-and-the-ugly/1/</link> <guid isPermaLink="false">letterboxd-watch-1513860295</guid> <pubDate>Mon, 28 Sep 2026 09:51:45 +1300</pubDate> <letterboxd:watchedDate>2026-09-27</letterboxd:watchedDate> <letterboxd:rewatch>Yes</letterboxd:rewatch> <letterboxd:filmTitle>The Good, the Bad and the Ugly</letterboxd:filmTitle> <letterboxd:filmYear>1966</letterboxd:filmYear> <letterboxd:memberRating>4.5</letterboxd:memberRating> <tmdb:movieId>429</tmdb:movieId> </item>
		<item> <title>Don&#039;t Worry Darling, 2022 - ★★★½</title> <link>https://letterboxd.com/janhy/film/dont-worry-darling/1/</link> <guid isPermaLink="false">letterboxd-watch-1490000001</guid> <letterboxd:watchedDate>2026-09-13</letterboxd:watchedDate> <letterboxd:rewatch>Yes</letterboxd:rewatch> <letterboxd:filmTitle>Don&#039;t Worry Darling</letterboxd:filmTitle> <letterboxd:filmYear>2022</letterboxd:filmYear> <letterboxd:memberRating>3.5</letterboxd:memberRating> <tmdb:movieId>619730</tmdb:movieId> </item>
		<item> <title>Wings of Hope, 1999</title> <link>https://letterboxd.com/janhy/film/wings-of-hope/</link> <guid isPermaLink="false">letterboxd-watch-1400000002</guid> <letterboxd:watchedDate>2026-05-28</letterboxd:watchedDate> <letterboxd:rewatch>No</letterboxd:rewatch> <letterboxd:filmTitle>Wings of Hope</letterboxd:filmTitle> <letterboxd:filmYear>1999</letterboxd:filmYear> <tmdb:movieId>99657</tmdb:movieId> </item>
		<item> <title>My all-time favorites</title> <link>https://letterboxd.com/janhy/list/my-all-time-favorites/</link> <guid isPermaLink="false">letterboxd-list-123</guid> </item>
	</channel>
</rss>
```

- [ ] **Step 2: Write the failing tests** `backend/tests/test_letterboxd_feed.py`:

```python
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
```

- [ ] **Step 3: Run to verify failure**

Run (from `backend/`): `uv run pytest tests/test_letterboxd_feed.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.letterboxd'`.

- [ ] **Step 4: Implement** `backend/app/letterboxd/__init__.py` (empty file), then `backend/app/letterboxd/errors.py`:

```python
"""The letterboxd module's domain error types (NFR-MAINT-03, REQ §5.7)."""

import uuid

from fastapi import status

from app.core.errors import AppError


class LetterboxdDisabledError(AppError):
    """No ``LETTERBOXD_USERNAME`` is configured, so there is no feed to sync (FR-LBX-01)."""

    code = "LETTERBOXD_DISABLED"
    status_code = status.HTTP_409_CONFLICT
    message = "The Letterboxd sync is off: LETTERBOXD_USERNAME is not set."


class LetterboxdUnavailableError(AppError):
    """The feed could not be fetched or parsed."""

    code = "LETTERBOXD_UNAVAILABLE"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "The Letterboxd feed could not be read."


class EntryNotFoundError(AppError):
    """No review-list entry with the requested id."""

    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Letterboxd entry not found."

    def __init__(self, entry_id: uuid.UUID) -> None:
        super().__init__(f"Letterboxd entry {entry_id} not found.")


class EntryResolvedError(AppError):
    """The entry was already approved, assigned, dismissed or auto-resolved (FR-LBX-06)."""

    code = "ENTRY_RESOLVED"
    status_code = status.HTTP_409_CONFLICT
    message = "This Letterboxd entry has already been resolved."

    def __init__(self, entry_id: uuid.UUID) -> None:
        super().__init__(f"Letterboxd entry {entry_id} has already been resolved.")
```

Then `backend/app/letterboxd/feed.py`:

```python
"""Fetch and parse the Letterboxd member RSS feed (REQ §5.7, FR-LBX-01/02).

Stdlib only — ``urllib`` as in ``films/service/poster_palette.py``, ``xml.etree``
for the parse. The feed holds the member's last 50 diary entries, newest-logged
first, followed by list posts; list posts carry no watch date and are skipped.
"""

import re
import urllib.error
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
    except (urllib.error.URLError, TimeoutError) as error:
        raise LetterboxdUnavailableError() from error
    return parse_feed(body)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_letterboxd_feed.py -q` → all PASS.
Then: `make typecheck && make lint && make format-check` → clean (run `make format` first if format-check complains).

- [ ] **Step 6: Commit**

```bash
git add backend/app/letterboxd/__init__.py backend/app/letterboxd/errors.py backend/app/letterboxd/feed.py backend/tests/fixtures/letterboxd_feed.xml backend/tests/test_letterboxd_feed.py
git commit -m "feat(letterboxd): parse diary entries from the member RSS feed"
```

---

### Task 3: `letterboxd_entries` table and migration

**Files:**
- Create: `backend/app/letterboxd/models.py`, `backend/migrations/versions/0011_letterboxd_entries.py`
- Modify: `backend/tests/test_db_plumbing.py` (table guard)
- Create: `backend/tests/test_letterboxd_repository.py` (first test only; Task 4 adds more)

**Interfaces:**
- Produces: `models.LetterboxdEntry` with columns `id: uuid.UUID`, `guid: str`, `film_title: str`, `film_year: int`, `film_url: str`, `watched_date: date`, `rating: Decimal | None`, `rewatch: bool`, `suggested_film_id: uuid.UUID | None`, `created_at: datetime`, `resolved_at: datetime | None`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_db_plumbing.py`, add the import `from app.letterboxd.models import LetterboxdEntry`, rename the guard test to `test_metadata_defines_exactly_the_domain_tables_plus_the_projection_settings_and_letterboxd`, and extend the final assertion set with `LetterboxdEntry.__tablename__`:

```python
    assert set(Base.metadata.tables) == {model.__tablename__ for model in domain_models} | {
        RewatchSuggestion.__tablename__,
        Settings.__tablename__,
        LetterboxdEntry.__tablename__,
    }
```

Create `backend/tests/test_letterboxd_repository.py`:

```python
"""Letterboxd data access against a real Postgres (DESIGN §9). Rolls back per test."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.letterboxd.models import LetterboxdEntry


def _add_film(session: Session, title: str, year: int, letterboxd_url: str | None = None) -> Film:
    film = Film(
        natural_key=f"{title.lower()}|{year}|someone",
        release_year=year,
        director="Someone",
        runtime_minutes=100,
        letterboxd_url=letterboxd_url,
    )
    session.add(film)
    session.flush()
    session.add(Title(film_id=film.id, value=title, is_primary=True, is_original=False))
    session.flush()
    return film


def _entry(guid: str = "letterboxd-watch-1", **overrides: object) -> LetterboxdEntry:
    fields: dict[str, object] = {
        "guid": guid,
        "film_title": "Heat",
        "film_year": 1995,
        "film_url": "https://letterboxd.com/film/heat/",
        "watched_date": date(2026, 9, 1),
        "rating": Decimal("4.0"),
        "rewatch": False,
    }
    fields.update(overrides)
    return LetterboxdEntry(**fields)


def test_deleting_the_suggested_film_keeps_the_entry_without_a_suggestion(
    db_session: Session,
) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _entry(suggested_film_id=film.id)
    db_session.add(entry)
    db_session.flush()

    db_session.delete(film)
    db_session.flush()
    db_session.refresh(entry)

    assert entry.suggested_film_id is None
    assert entry.resolved_at is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_db_plumbing.py tests/test_letterboxd_repository.py -q`
Expected: FAIL — `No module named 'app.letterboxd.models'`.

- [ ] **Step 3: Implement** `backend/app/letterboxd/models.py`:

```python
"""Letterboxd review-list table (REQ §5.7, FR-LBX-02/05).

Every new feed entry is stored here until the user resolves it. Resolved rows
are kept forever: their ``guid`` is what stops the next sync (FR-LBX-02).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utc_now


class LetterboxdEntry(Base):
    """One Letterboxd diary entry awaiting (or past) the user's review."""

    __tablename__ = "letterboxd_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    guid: Mapped[str] = mapped_column(String(100), unique=True)
    film_title: Mapped[str] = mapped_column(String(255))
    film_year: Mapped[int] = mapped_column(Integer)
    film_url: Mapped[str] = mapped_column(String(2048))
    watched_date: Mapped[date] = mapped_column(Date)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    rewatch: Mapped[bool] = mapped_column(Boolean)
    # The sync's match when exactly one film fitted (FR-LBX-04); nulled if that
    # film is deleted before the review.
    suggested_film_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("films.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    # NULL = open. Set by approve/assign, dismiss, or auto-resolve (FR-LBX-06/07).
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Create `backend/migrations/versions/0011_letterboxd_entries.py`:

```python
"""letterboxd_entries (REQ §5.7)

The Letterboxd review list: every new feed entry until the user resolves it.

Revision ID: 0011_letterboxd_entries
Revises: 0010_film_poster_palette
Create Date: 2026-09-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_letterboxd_entries"
down_revision: str | None = "0010_film_poster_palette"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "letterboxd_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("guid", sa.String(length=100), nullable=False),
        sa.Column("film_title", sa.String(length=255), nullable=False),
        sa.Column("film_year", sa.Integer(), nullable=False),
        sa.Column("film_url", sa.String(length=2048), nullable=False),
        sa.Column("watched_date", sa.Date(), nullable=False),
        sa.Column("rating", sa.Numeric(precision=2, scale=1), nullable=True),
        sa.Column("rewatch", sa.Boolean(), nullable=False),
        sa.Column("suggested_film_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["suggested_film_id"], ["films.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guid"),
    )


def downgrade() -> None:
    op.drop_table("letterboxd_entries")
```

- [ ] **Step 4: Run to verify pass, and check the migration matches the model**

Run: `uv run pytest tests/test_db_plumbing.py tests/test_letterboxd_repository.py -q` → PASS.

Then check autogenerate parity against the dev database (from `backend/`, Postgres running):

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m parity_check
```

Expected: the generated file's `upgrade()` body is only `pass`. Delete that generated file (`backend/migrations/versions/*parity_check*.py`) — it must not be committed. If it is not empty, fix the migration (not the model) until it is.

Then `make typecheck && make lint && make format-check`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/letterboxd/models.py backend/migrations/versions/0011_letterboxd_entries.py backend/tests/test_db_plumbing.py backend/tests/test_letterboxd_repository.py
git commit -m "feat(letterboxd): add the letterboxd_entries review-list table"
```

---

### Task 4: Repository, matching and `run_sync`

**Files:**
- Create: `backend/app/letterboxd/repository.py`, `backend/app/letterboxd/service.py` (sync half; Task 5 adds `LetterboxdService`)
- Modify: `backend/tests/test_letterboxd_repository.py`
- Create: `backend/tests/test_letterboxd_service.py`

**Interfaces:**
- Consumes: `feed.FeedEntry`, `feed.film_slug`, `models.LetterboxdEntry`.
- Produces:
  - `repository.LetterboxdRepository(session: Session)` with `is_known_guid(guid: str) -> bool`, `add(entry: LetterboxdEntry) -> None`, `get(entry_id: uuid.UUID) -> LetterboxdEntry | None`, `list_open() -> list[LetterboxdEntry]`, `film_ids_by_slug(slug: str) -> list[uuid.UUID]`, `film_ids_by_title_year(title: str, year: int) -> list[uuid.UUID]`, `has_watch_on(film_id: uuid.UUID, watch_date: date) -> bool`, `primary_titles(film_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]`, `commit() -> None`.
  - `service.LetterboxdRepositoryProtocol` (same methods), `service.match_film(repository, slug: str | None, title: str, year: int) -> uuid.UUID | None`, `service.run_sync(repository, entries: Sequence[FeedEntry], today: date) -> int` (returns the number queued).

- [ ] **Step 1: Write the failing repository tests** — append to `backend/tests/test_letterboxd_repository.py` (add imports `from app.core.db import utc_now`, `from app.letterboxd.repository import LetterboxdRepository` and `from app.ratings.models import RatingEntry`):

```python
def test_is_known_guid(db_session: Session) -> None:
    db_session.add(_entry("letterboxd-watch-7"))
    db_session.flush()
    repository = LetterboxdRepository(db_session)

    assert repository.is_known_guid("letterboxd-watch-7")
    assert not repository.is_known_guid("letterboxd-watch-8")


def test_film_ids_by_slug_matches_every_letterboxd_url_shape_but_not_a_longer_slug(
    db_session: Session,
) -> None:
    exact = _add_film(db_session, "Heat", 1995, "https://letterboxd.com/film/heat")
    _add_film(db_session, "Heat 2", 2026, "https://letterboxd.com/film/heat-2/")
    _add_film(db_session, "Short", 2000, "https://boxd.it/heat")

    assert LetterboxdRepository(db_session).film_ids_by_slug("heat") == [exact.id]


def test_film_ids_by_title_year_searches_every_title_case_insensitively(
    db_session: Session,
) -> None:
    pulse = _add_film(db_session, "回路", 2001)
    db_session.add(Title(film_id=pulse.id, value=" Pulse ", is_primary=False, is_original=False))
    _add_film(db_session, "Pulse", 2006)
    db_session.flush()

    assert LetterboxdRepository(db_session).film_ids_by_title_year("pulse", 2001) == [pulse.id]


def test_has_watch_on(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 9, 1)))
    db_session.flush()
    repository = LetterboxdRepository(db_session)

    assert repository.has_watch_on(film.id, date(2026, 9, 1))
    assert not repository.has_watch_on(film.id, date(2026, 9, 2))


def test_list_open_skips_resolved_entries_newest_watch_first(db_session: Session) -> None:
    db_session.add(_entry("a", watched_date=date(2026, 9, 1)))
    db_session.add(_entry("b", watched_date=date(2026, 9, 5)))
    db_session.add(_entry("c", watched_date=date(2026, 9, 9), resolved_at=utc_now()))
    db_session.flush()

    assert [entry.guid for entry in LetterboxdRepository(db_session).list_open()] == ["b", "a"]


def test_primary_titles(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    assert LetterboxdRepository(db_session).primary_titles({film.id}) == {film.id: "Heat"}
```

- [ ] **Step 2: Write the failing sync tests** `backend/tests/test_letterboxd_service.py`:

```python
"""Letterboxd matching and sync against a real Postgres (REQ §5.7). Rolls back per test."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.letterboxd.feed import FeedEntry
from app.letterboxd.models import LetterboxdEntry
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import match_film, run_sync
from app.ratings.models import RatingEntry

TODAY = date(2026, 9, 28)


def _add_film(session: Session, title: str, year: int, letterboxd_url: str | None = None) -> Film:
    film = Film(
        natural_key=f"{title.lower()}|{year}|someone",
        release_year=year,
        director="Someone",
        runtime_minutes=100,
        letterboxd_url=letterboxd_url,
    )
    session.add(film)
    session.flush()
    session.add(Title(film_id=film.id, value=title, is_primary=True, is_original=False))
    session.flush()
    return film


def _feed_entry(
    guid: str,
    title: str = "Heat",
    year: int = 1995,
    slug: str = "heat",
    watched: date = date(2026, 9, 20),
    rating: Decimal | None = Decimal("4.0"),
) -> FeedEntry:
    return FeedEntry(
        guid=guid,
        film_title=title,
        film_year=year,
        film_slug=slug,
        watched_date=watched,
        rating=rating,
        rewatch=False,
    )


def _queued(session: Session) -> list[LetterboxdEntry]:
    return list(session.scalars(select(LetterboxdEntry).order_by(LetterboxdEntry.created_at)))


def _watch_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(RatingEntry)) or 0


# --- match_film ---------------------------------------------------------------


def test_link_match_beats_a_title_match(db_session: Session) -> None:
    linked = _add_film(db_session, "Heat (linked)", 1995, "https://letterboxd.com/film/heat/")
    _add_film(db_session, "Heat", 1995)

    assert match_film(LetterboxdRepository(db_session), "heat", "Heat", 1995) == linked.id


def test_title_match_when_no_link_matches(db_session: Session) -> None:
    film = _add_film(db_session, "Don't Worry Darling", 2022)

    found = match_film(LetterboxdRepository(db_session), "dont-worry-darling", "don't worry darling", 2022)
    assert found == film.id


def test_two_title_matches_are_no_match(db_session: Session) -> None:
    _add_film(db_session, "Godzilla", 1954)
    twin = _add_film(db_session, "Gojira", 1954)
    db_session.add(Title(film_id=twin.id, value="Godzilla", is_primary=False, is_original=False))
    db_session.flush()

    assert match_film(LetterboxdRepository(db_session), "godzilla", "Godzilla", 1954) is None


def test_no_slug_falls_through_to_the_title(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    assert match_film(LetterboxdRepository(db_session), None, "Heat", 1995) == film.id


# --- run_sync -----------------------------------------------------------------


def test_queues_new_entries_with_a_suggestion_and_writes_no_watch(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)

    queued = run_sync(
        LetterboxdRepository(db_session),
        [_feed_entry("g2"), _feed_entry("g1", title="Unknown", slug="unknown")],
        TODAY,
    )

    assert queued == 2
    rows = _queued(db_session)
    assert [(row.guid, row.suggested_film_id) for row in rows] == [("g2", film.id), ("g1", None)]
    assert rows[0].film_url == "https://letterboxd.com/film/heat/"
    assert rows[0].rating == Decimal("4.0")
    assert _watch_count(db_session) == 0


def test_an_unrated_entry_is_queued_unrated(db_session: Session) -> None:
    run_sync(LetterboxdRepository(db_session), [_feed_entry("g1", rating=None)], TODAY)

    assert _queued(db_session)[0].rating is None


def test_stops_at_a_known_guid(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    run_sync(repository, [_feed_entry("g1", slug="a", title="A")], TODAY)

    queued = run_sync(
        repository,
        [_feed_entry("g3", slug="c", title="C"), _feed_entry("g1", slug="a", title="A"), _feed_entry("g0")],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g1", "g3"]


def test_running_twice_over_the_same_feed_queues_nothing_new(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    feed = [_feed_entry("g2", slug="b", title="B"), _feed_entry("g1", slug="a", title="A")]
    run_sync(repository, feed, TODAY)

    assert run_sync(repository, feed, TODAY) == 0
    assert len(_queued(db_session)) == 2


def test_stops_at_an_entry_whose_watch_is_already_in_the_app(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    db_session.add(RatingEntry(film_id=film.id, value=None, watch_date=date(2026, 9, 20)))
    db_session.flush()

    queued = run_sync(
        LetterboxdRepository(db_session),
        [_feed_entry("g3", slug="c", title="C"), _feed_entry("g2"), _feed_entry("g1", slug="a", title="A")],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g3"]


def test_a_future_entry_is_skipped_without_stopping(db_session: Session) -> None:
    queued = run_sync(
        LetterboxdRepository(db_session),
        [_feed_entry("g2", watched=date(2026, 9, 29)), _feed_entry("g1", slug="a", title="A")],
        TODAY,
    )

    assert queued == 1
    assert [row.guid for row in _queued(db_session)] == ["g1"]


def test_a_skipped_future_entry_is_queued_once_its_date_arrives(db_session: Session) -> None:
    repository = LetterboxdRepository(db_session)
    feed = [_feed_entry("g2", watched=date(2026, 9, 29)), _feed_entry("g1", slug="a", title="A")]
    run_sync(repository, feed, TODAY)

    assert run_sync(repository, feed, date(2026, 9, 29)) == 1
    assert {row.guid for row in _queued(db_session)} == {"g1", "g2"}


def test_suggestion_is_unset_for_an_unknown_film(db_session: Session) -> None:
    run_sync(LetterboxdRepository(db_session), [_feed_entry("g1")], TODAY)

    assert _queued(db_session)[0].suggested_film_id is None

```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_letterboxd_repository.py tests/test_letterboxd_service.py -q`
Expected: FAIL — `No module named 'app.letterboxd.repository'`.

- [ ] **Step 4: Implement** `backend/app/letterboxd/repository.py`:

```python
"""Data-access layer for the letterboxd module (DESIGN §5.1, REQ §5.7).

Reads the films, titles and rating tables directly (as ``stats`` does) but
never writes them — watches are added through ``FilmService`` (FR-LBX-05/06).
"""

import uuid
from collections.abc import Collection
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.letterboxd.feed import film_slug
from app.letterboxd.models import LetterboxdEntry
from app.ratings.models import RatingEntry


class LetterboxdRepository:
    """SQLAlchemy-backed Letterboxd data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def is_known_guid(self, guid: str) -> bool:
        statement = select(LetterboxdEntry.id).where(LetterboxdEntry.guid == guid)
        return self._session.scalar(statement) is not None

    def add(self, entry: LetterboxdEntry) -> None:
        self._session.add(entry)

    def get(self, entry_id: uuid.UUID) -> LetterboxdEntry | None:
        return self._session.get(LetterboxdEntry, entry_id)

    def list_open(self) -> list[LetterboxdEntry]:
        statement = (
            select(LetterboxdEntry)
            .where(LetterboxdEntry.resolved_at.is_(None))
            .order_by(LetterboxdEntry.watched_date.desc(), LetterboxdEntry.created_at.desc())
        )
        return list(self._session.scalars(statement))

    def film_ids_by_slug(self, slug: str) -> list[uuid.UUID]:
        """Films whose ``letterboxd_url`` points at ``slug`` (FR-LBX-04 rule 1)."""
        # The LIKE narrows the scan; ``film_slug`` then rejects near misses
        # such as ``/film/heat-2/`` for ``heat``.
        statement = select(Film.id, Film.letterboxd_url).where(
            Film.letterboxd_url.contains(f"/film/{slug}", autoescape=True)
        )
        return [
            film_id
            for film_id, url in self._session.execute(statement)
            if url is not None and film_slug(url) == slug
        ]

    def film_ids_by_title_year(self, title: str, year: int) -> list[uuid.UUID]:
        """Films with any title equal to ``title`` (case-insensitive, trimmed) and that year (FR-LBX-04 rule 2)."""
        statement = (
            select(Title.film_id)
            .distinct()
            .join(Film, Film.id == Title.film_id)
            .where(
                func.lower(func.trim(Title.value)) == title.strip().lower(),
                Film.release_year == year,
            )
        )
        return list(self._session.scalars(statement))

    def has_watch_on(self, film_id: uuid.UUID, watch_date: date) -> bool:
        statement = select(RatingEntry.id).where(
            RatingEntry.film_id == film_id, RatingEntry.watch_date == watch_date
        )
        return self._session.scalar(statement.limit(1)) is not None

    def primary_titles(self, film_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not film_ids:
            return {}
        statement = select(Title.film_id, Title.value).where(
            and_(Title.film_id.in_(film_ids), Title.is_primary)
        )
        return {film_id: value for film_id, value in self._session.execute(statement)}

    def commit(self) -> None:
        self._session.commit()
```

Create `backend/app/letterboxd/service.py`:

```python
"""Business logic for the Letterboxd sync (REQ §5.7).

:func:`run_sync` is the sync itself — module-level so the background loop can
call it without the request-scoped ``FilmService`` it never needs (FR-LBX-05).
"""

import threading
import uuid
from collections.abc import Collection, Sequence
from datetime import date
from typing import Protocol

from app.letterboxd.feed import FeedEntry
from app.letterboxd.models import LetterboxdEntry

# Keeps the scheduled and a manual sync from interleaving; the ``guid`` unique
# constraint is the backstop. ponytail: one process only — a second backend
# worker would need a database advisory lock instead.
_SYNC_LOCK = threading.Lock()


class LetterboxdRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1)."""

    def is_known_guid(self, guid: str) -> bool: ...

    def add(self, entry: LetterboxdEntry) -> None: ...

    def get(self, entry_id: uuid.UUID) -> LetterboxdEntry | None: ...

    def list_open(self) -> list[LetterboxdEntry]: ...

    def film_ids_by_slug(self, slug: str) -> list[uuid.UUID]: ...

    def film_ids_by_title_year(self, title: str, year: int) -> list[uuid.UUID]: ...

    def has_watch_on(self, film_id: uuid.UUID, watch_date: date) -> bool: ...

    def primary_titles(self, film_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]: ...

    def commit(self) -> None: ...


def match_film(
    repository: LetterboxdRepositoryProtocol, slug: str | None, title: str, year: int
) -> uuid.UUID | None:
    """The one film an entry belongs to, or ``None`` for zero or several (FR-LBX-04)."""
    if slug is not None:
        by_slug = repository.film_ids_by_slug(slug)
        if len(by_slug) == 1:
            return by_slug[0]
    by_title = repository.film_ids_by_title_year(title, year)
    return by_title[0] if len(by_title) == 1 else None


def run_sync(
    repository: LetterboxdRepositoryProtocol, entries: Sequence[FeedEntry], today: date
) -> int:
    """Queue the feed's new entries for review; returns how many were queued (FR-LBX-02..05)."""
    with _SYNC_LOCK:
        queued = 0
        for entry in entries:
            if repository.is_known_guid(entry.guid):
                break
            film_id = match_film(repository, entry.film_slug, entry.film_title, entry.film_year)
            if film_id is not None and repository.has_watch_on(film_id, entry.watched_date):
                break
            if entry.watched_date > today:
                continue  # FR-LBX-03: the next sync picks it up
            repository.add(
                LetterboxdEntry(
                    guid=entry.guid,
                    film_title=entry.film_title,
                    film_year=entry.film_year,
                    film_url=entry.film_url,
                    watched_date=entry.watched_date,
                    rating=entry.rating,
                    rewatch=entry.rewatch,
                    suggested_film_id=film_id,
                )
            )
            queued += 1
        repository.commit()
        return queued
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_letterboxd_repository.py tests/test_letterboxd_service.py -q` → PASS.
Then `make typecheck && make lint && make format-check`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/letterboxd/repository.py backend/app/letterboxd/service.py backend/tests/test_letterboxd_repository.py backend/tests/test_letterboxd_service.py
git commit -m "feat(letterboxd): queue new feed entries with a matched-film suggestion"
```

---

### Task 5: Review actions — list with auto-resolve, assign, dismiss

**Files:**
- Create: `backend/app/letterboxd/schemas.py`
- Modify: `backend/app/letterboxd/service.py` (add `FilmWriter`, `LetterboxdService`)
- Modify: `backend/tests/test_letterboxd_service.py`

**Interfaces:**
- Consumes: `LetterboxdRepositoryProtocol`, `match_film`, `run_sync`, `feed.film_slug`, `FeedEntry`; `app.films.schemas.FilmUpdate`, `FilmDetailRead`; `app.ratings.schemas.RatingEntryRead`; errors from Task 2.
- Produces:
  - `schemas.SuggestedFilmRead(id: UUID, title: str)`, `schemas.LetterboxdEntryRead(id, film_title, film_year, film_url, watched_date, rating: float | None, rewatch, suggested_film: SuggestedFilmRead | None)`, `schemas.AssignBody(film_id: JsonUUID)`, `schemas.SyncResult(queued: int)`.
  - `service.FilmWriter` protocol: `add_rating(film_id, value: Decimal | None, watch_date: date) -> RatingEntryRead`, `get_detail(film_id) -> FilmDetailRead`, `update(film_id, data: FilmUpdate) -> FilmDetailRead`.
  - `service.LetterboxdService(repository, films: FilmWriter, fetch: Callable[[], list[FeedEntry]], today: Callable[[], date] = date.today)` with `sync() -> int`, `list_open() -> list[LetterboxdEntryRead]`, `assign(entry_id: uuid.UUID, film_id: uuid.UUID) -> None`, `dismiss(entry_id: uuid.UUID) -> None`.

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_letterboxd_service.py` (add imports `from datetime import UTC, datetime`, `import pytest`, `from app.films.schemas import FilmUpdate`, `from app.letterboxd.errors import EntryNotFoundError, EntryResolvedError`, `from app.letterboxd.service import LetterboxdService`):

```python
# --- LetterboxdService ----------------------------------------------------------


class FakeFilms:
    """Records the FilmService calls; the real one is covered by the films tests."""

    def __init__(self, letterboxd_url: str | None = None) -> None:
        self.letterboxd_url = letterboxd_url
        self.ratings: list[tuple[uuid.UUID, Decimal | None, date]] = []
        self.updates: list[tuple[uuid.UUID, FilmUpdate]] = []

    def add_rating(self, film_id: uuid.UUID, value: Decimal | None, watch_date: date) -> object:
        self.ratings.append((film_id, value, watch_date))
        return object()

    def get_detail(self, film_id: uuid.UUID) -> object:
        url = self.letterboxd_url

        class Detail:
            letterboxd_url = url

        return Detail()

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> object:
        self.updates.append((film_id, data))
        return object()


def _service(session: Session, films: FakeFilms | None = None, feed: list[FeedEntry] | None = None) -> LetterboxdService:
    return LetterboxdService(
        LetterboxdRepository(session),
        films or FakeFilms(),  # pyright: ignore[reportArgumentType] - structural fake
        lambda: feed or [],
        lambda: TODAY,
    )


def _open_entry(session: Session, guid: str = "g1", **overrides: object) -> LetterboxdEntry:
    fields: dict[str, object] = {
        "guid": guid,
        "film_title": "Heat",
        "film_year": 1995,
        "film_url": "https://letterboxd.com/film/heat/",
        "watched_date": date(2026, 9, 20),
        "rating": Decimal("4.5"),
        "rewatch": True,
    }
    fields.update(overrides)
    entry = LetterboxdEntry(**fields)
    session.add(entry)
    session.flush()
    return entry


def test_sync_runs_the_fetched_feed(db_session: Session) -> None:
    assert _service(db_session, feed=[_feed_entry("g1")]).sync() == 1


def test_list_open_carries_the_suggested_films_primary_title(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    _open_entry(db_session, suggested_film_id=film.id)
    _open_entry(db_session, "g2", film_title="Unknown", film_url="https://letterboxd.com/film/unknown/")

    rows = _service(db_session).list_open()

    suggested = next(row for row in rows if row.film_title == "Heat").suggested_film
    assert suggested is not None and (suggested.id, suggested.title) == (film.id, "Heat")
    assert next(row for row in rows if row.film_title == "Unknown").suggested_film is None


def test_list_open_auto_resolves_an_entry_whose_watch_now_exists(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995, "https://letterboxd.com/film/heat/")
    entry = _open_entry(db_session)
    db_session.add(RatingEntry(film_id=film.id, value=Decimal("4.5"), watch_date=date(2026, 9, 20)))
    db_session.flush()

    assert _service(db_session).list_open() == []
    assert entry.resolved_at is not None


def test_assign_adds_the_watch_and_resolves(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _open_entry(db_session)
    films = FakeFilms()

    _service(db_session, films).assign(entry.id, film.id)

    assert films.ratings == [(film.id, Decimal("4.5"), date(2026, 9, 20))]
    assert entry.resolved_at is not None


def test_assign_sets_the_letterboxd_url_only_when_the_film_has_none(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    first = _open_entry(db_session)
    second = _open_entry(db_session, "g2")

    empty = FakeFilms(letterboxd_url=None)
    _service(db_session, empty).assign(first.id, film.id)
    linked = FakeFilms(letterboxd_url="https://boxd.it/x")
    _service(db_session, linked).assign(second.id, film.id)

    assert [(film_id, data.letterboxd_url) for film_id, data in empty.updates] == [
        (film.id, "https://letterboxd.com/film/heat/")
    ]
    assert linked.updates == []


def test_assign_keeps_an_unrated_entry_unrated(db_session: Session) -> None:
    film = _add_film(db_session, "Heat", 1995)
    entry = _open_entry(db_session, rating=None)
    films = FakeFilms()

    _service(db_session, films).assign(entry.id, film.id)

    assert films.ratings[0][1] is None


def test_dismiss_resolves_without_a_watch(db_session: Session) -> None:
    entry = _open_entry(db_session)
    films = FakeFilms()

    _service(db_session, films).dismiss(entry.id)

    assert entry.resolved_at is not None
    assert films.ratings == []


def test_acting_on_an_unknown_entry_is_not_found(db_session: Session) -> None:
    with pytest.raises(EntryNotFoundError):
        _service(db_session).dismiss(uuid.uuid4())


def test_acting_on_a_resolved_entry_is_rejected(db_session: Session) -> None:
    entry = _open_entry(db_session, resolved_at=datetime(2026, 9, 21, tzinfo=UTC))

    with pytest.raises(EntryResolvedError):
        _service(db_session).assign(entry.id, uuid.uuid4())
    with pytest.raises(EntryResolvedError):
        _service(db_session).dismiss(entry.id)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_letterboxd_service.py -q`
Expected: FAIL — `cannot import name 'LetterboxdService'`.

- [ ] **Step 3: Implement** `backend/app/letterboxd/schemas.py`:

```python
"""Pydantic schemas for the letterboxd routes (REQ §5.7)."""

from typing import Annotated

from pydantic import Field

from app.core.schemas import JsonDate, JsonUUID, StrictSchema


class SuggestedFilmRead(StrictSchema):
    """The film the sync matched (FR-LBX-04), by its primary title."""

    id: JsonUUID
    title: str


class LetterboxdEntryRead(StrictSchema):
    """One open review-list entry."""

    id: JsonUUID
    film_title: str
    film_year: int
    film_url: str
    watched_date: JsonDate
    # A JSON number like ``RatingEntryRead.value``; null = unrated (FR-LBX-08).
    rating: Annotated[float, Field(strict=False)] | None
    rewatch: bool
    suggested_film: SuggestedFilmRead | None


class AssignBody(StrictSchema):
    """The film to add the entry's watch to — the suggestion or another one (FR-LBX-06)."""

    film_id: JsonUUID


class SyncResult(StrictSchema):
    """How many entries a manual sync queued."""

    queued: int
```

Append to `backend/app/letterboxd/service.py` (and extend its imports: `from collections.abc import Callable, Collection, Sequence`, `from decimal import Decimal`, `from app.core.db import utc_now`, `from app.films.schemas import FilmDetailRead, FilmUpdate`, `from app.letterboxd.errors import EntryNotFoundError, EntryResolvedError`, `from app.letterboxd.feed import FeedEntry, film_slug`, `from app.letterboxd.schemas import LetterboxdEntryRead, SuggestedFilmRead`, `from app.ratings.schemas import RatingEntryRead`):

```python
class FilmWriter(Protocol):
    """The ``FilmService`` calls the review actions need (service-to-service, §5.1)."""

    def add_rating(
        self, film_id: uuid.UUID, value: Decimal | None, watch_date: date
    ) -> RatingEntryRead: ...

    def get_detail(self, film_id: uuid.UUID) -> FilmDetailRead: ...

    def update(self, film_id: uuid.UUID, data: FilmUpdate) -> FilmDetailRead: ...


class LetterboxdService:
    """The review list's reads and actions (FR-LBX-05..07), plus the manual sync."""

    def __init__(
        self,
        repository: LetterboxdRepositoryProtocol,
        films: FilmWriter,
        fetch: Callable[[], list[FeedEntry]],
        today: Callable[[], date] = date.today,
    ) -> None:
        self._repository = repository
        self._films = films
        self._fetch = fetch
        self._today = today

    def sync(self) -> int:
        """Fetch the feed and queue its new entries; returns how many were queued."""
        return run_sync(self._repository, self._fetch(), self._today())

    def list_open(self) -> list[LetterboxdEntryRead]:
        """Open entries, newest watch first, after auto-resolving the ones now in the app (FR-LBX-07)."""
        still_open: list[LetterboxdEntry] = []
        resolved_any = False
        for entry in self._repository.list_open():
            film_id = match_film(
                self._repository, film_slug(entry.film_url), entry.film_title, entry.film_year
            )
            if film_id is not None and self._repository.has_watch_on(film_id, entry.watched_date):
                entry.resolved_at = utc_now()
                resolved_any = True
            else:
                still_open.append(entry)
        if resolved_any:
            self._repository.commit()

        titles = self._repository.primary_titles(
            {entry.suggested_film_id for entry in still_open if entry.suggested_film_id is not None}
        )
        return [
            LetterboxdEntryRead(
                id=entry.id,
                film_title=entry.film_title,
                film_year=entry.film_year,
                film_url=entry.film_url,
                watched_date=entry.watched_date,
                rating=float(entry.rating) if entry.rating is not None else None,
                rewatch=entry.rewatch,
                suggested_film=(
                    SuggestedFilmRead(id=entry.suggested_film_id, title=titles[entry.suggested_film_id])
                    if entry.suggested_film_id is not None and entry.suggested_film_id in titles
                    else None
                ),
            )
            for entry in still_open
        ]

    def assign(self, entry_id: uuid.UUID, film_id: uuid.UUID) -> None:
        """Add the entry's watch to ``film_id`` and resolve it (FR-LBX-06).

        An unknown film raises ``FilmNotFoundError`` from ``add_rating`` before
        anything is committed, so the entry stays open.
        """
        entry = self._open_entry(entry_id)
        entry.resolved_at = utc_now()
        self._films.add_rating(film_id, entry.rating, entry.watched_date)
        if self._films.get_detail(film_id).letterboxd_url is None:
            self._films.update(film_id, FilmUpdate(letterboxd_url=entry.film_url))
        self._repository.commit()

    def dismiss(self, entry_id: uuid.UUID) -> None:
        """Resolve the entry without adding anything (FR-LBX-06)."""
        self._open_entry(entry_id).resolved_at = utc_now()
        self._repository.commit()

    def _open_entry(self, entry_id: uuid.UUID) -> LetterboxdEntry:
        entry = self._repository.get(entry_id)
        if entry is None:
            raise EntryNotFoundError(entry_id)
        if entry.resolved_at is not None:
            raise EntryResolvedError(entry_id)
        return entry
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_letterboxd_service.py -q` → PASS.
Then `make typecheck && make lint && make format-check`. If pyright rejects `FakeFilms` as a `FilmWriter`, keep the targeted `# pyright: ignore[reportArgumentType]` shown in `_service` (the fake returns `object`, not the read models) — do not loosen `FilmWriter`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/letterboxd/schemas.py backend/app/letterboxd/service.py backend/tests/test_letterboxd_service.py
git commit -m "feat(letterboxd): approve, assign and dismiss review-list entries"
```

---

### Task 6: Routes, config, background sync

**Files:**
- Create: `backend/app/letterboxd/dependencies.py`, `backend/app/letterboxd/router.py`, `backend/app/letterboxd/scheduler.py`
- Create: `backend/tests/test_letterboxd_api.py`, `backend/tests/test_letterboxd_scheduler.py`
- Modify: `backend/app/core/config.py`, `backend/.env.example`, `.env.example` (repo root), `docker-compose.yml`, `backend/app/main.py`, `backend/app/core/errors.py` (docstring table), `backend/tests/test_openapi_contract.py`

**Interfaces:**
- Consumes: `LetterboxdService`, `LetterboxdRepository`, `run_sync`, `fetch_feed`, schemas, errors; `app.films.dependencies.get_film_service`; `app.core.db.session_scope`.
- Produces: routes `GET /api/v1/letterboxd/entries`, `POST /api/v1/letterboxd/entries/{entry_id}/assign` (204), `POST /api/v1/letterboxd/entries/{entry_id}/dismiss` (204), `POST /api/v1/letterboxd/sync` (200 `{queued}`); `dependencies.get_letterboxd_service`; `scheduler.sync_once(username: str) -> int`, `scheduler.run_periodically(username: str) -> Coroutine`; setting `Settings.letterboxd_username: str`.

- [ ] **Step 1: Write the failing tests** `backend/tests/test_letterboxd_api.py`:

```python
"""The letterboxd routes end to end, with the service stubbed (offline)."""

import uuid
from datetime import date

from fastapi.testclient import TestClient

from app.films.service import FilmNotFoundError
from app.letterboxd.dependencies import get_letterboxd_service
from app.letterboxd.errors import (
    EntryNotFoundError,
    EntryResolvedError,
    LetterboxdDisabledError,
    LetterboxdUnavailableError,
)
from app.letterboxd.schemas import LetterboxdEntryRead, SuggestedFilmRead
from app.main import create_app

ENTRY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FILM_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class StubService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, object]] = []

    def _maybe_fail(self) -> None:
        if self.error is not None:
            raise self.error

    def list_open(self) -> list[LetterboxdEntryRead]:
        return [
            LetterboxdEntryRead(
                id=ENTRY_ID,
                film_title="Heat",
                film_year=1995,
                film_url="https://letterboxd.com/film/heat/",
                watched_date=date(2026, 9, 20),
                rating=None,
                rewatch=True,
                suggested_film=SuggestedFilmRead(id=FILM_ID, title="Heat"),
            )
        ]

    def assign(self, entry_id: uuid.UUID, film_id: uuid.UUID) -> None:
        self._maybe_fail()
        self.calls.append(("assign", (entry_id, film_id)))

    def dismiss(self, entry_id: uuid.UUID) -> None:
        self._maybe_fail()
        self.calls.append(("dismiss", entry_id))

    def sync(self) -> int:
        self._maybe_fail()
        return 3


def _client(service: StubService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_letterboxd_service] = lambda: service
    return TestClient(app)


def test_lists_open_entries() -> None:
    response = _client(StubService()).get("/api/v1/letterboxd/entries")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(ENTRY_ID),
            "film_title": "Heat",
            "film_year": 1995,
            "film_url": "https://letterboxd.com/film/heat/",
            "watched_date": "2026-09-20",
            "rating": None,
            "rewatch": True,
            "suggested_film": {"id": str(FILM_ID), "title": "Heat"},
        }
    ]


def test_assign() -> None:
    service = StubService()
    response = _client(service).post(
        f"/api/v1/letterboxd/entries/{ENTRY_ID}/assign", json={"film_id": str(FILM_ID)}
    )

    assert response.status_code == 204
    assert service.calls == [("assign", (ENTRY_ID, FILM_ID))]


def test_dismiss() -> None:
    service = StubService()
    response = _client(service).post(f"/api/v1/letterboxd/entries/{ENTRY_ID}/dismiss")

    assert response.status_code == 204
    assert service.calls == [("dismiss", ENTRY_ID)]


def test_sync_reports_the_queued_count() -> None:
    response = _client(StubService()).post("/api/v1/letterboxd/sync")

    assert response.status_code == 200
    assert response.json() == {"queued": 3}


def test_error_codes() -> None:
    cases: list[tuple[Exception, str, str, int, str]] = [
        (EntryNotFoundError(ENTRY_ID), "post", f"/entries/{ENTRY_ID}/dismiss", 404, "NOT_FOUND"),
        (EntryResolvedError(ENTRY_ID), "post", f"/entries/{ENTRY_ID}/dismiss", 409, "ENTRY_RESOLVED"),
        (FilmNotFoundError(FILM_ID), "post", f"/entries/{ENTRY_ID}/assign", 404, "NOT_FOUND"),
        (LetterboxdDisabledError(), "post", "/sync", 409, "LETTERBOXD_DISABLED"),
        (LetterboxdUnavailableError(), "post", "/sync", 502, "LETTERBOXD_UNAVAILABLE"),
    ]
    for error, method, path, status, code in cases:
        client = _client(StubService(error))
        body = {"film_id": str(FILM_ID)} if path.endswith("assign") else None
        response = client.request(method, f"/api/v1/letterboxd{path}", json=body)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), path


def test_assign_rejects_a_malformed_film_id() -> None:
    response = _client(StubService()).post(
        f"/api/v1/letterboxd/entries/{ENTRY_ID}/assign", json={"film_id": "nope"}
    )

    assert response.status_code == 422
```

`backend/tests/test_letterboxd_scheduler.py`:

```python
"""The background loop's timing and failure handling (offline)."""

import asyncio

import pytest

from app.letterboxd import scheduler
from app.letterboxd.errors import LetterboxdUnavailableError


def test_syncs_at_start_retries_a_failure_then_waits_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    outcomes: list[int | Exception] = [LetterboxdUnavailableError(), 3]

    def fake_sync(username: str) -> int:
        calls.append(username)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    sleeps = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(scheduler, "sync_once", fake_sync)
    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_periodically("janhy"))

    # Check 1 fails, check 2 retries and succeeds, check 3 is within 24 h.
    assert calls == ["janhy", "janhy"]
```

In `backend/tests/test_openapi_contract.py`, add to `_EXPECTED_ROUTES`:

```python
    # The Letterboxd sync (2026-09-28-letterboxd-sync-design.md, REQ §5.7).
    ("GET", "/api/v1/letterboxd/entries"),
    ("POST", "/api/v1/letterboxd/entries/{entry_id}/assign"),
    ("POST", "/api/v1/letterboxd/entries/{entry_id}/dismiss"),
    ("POST", "/api/v1/letterboxd/sync"),
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_letterboxd_api.py tests/test_letterboxd_scheduler.py tests/test_openapi_contract.py -q`
Expected: FAIL — `No module named 'app.letterboxd.dependencies'` / missing routes.

- [ ] **Step 3: Implement config** — in `backend/app/core/config.py`, after `cors_allowed_origins`:

```python
    # Letterboxd member whose RSS feed is synced into the review list (REQ §5.7,
    # FR-LBX-01). Empty turns the sync off.
    letterboxd_username: str = ""
```

Append to `backend/.env.example`:

```bash

# --- Letterboxd sync (REQ §5.7) -------------------------------------------------
# Letterboxd member name whose public RSS feed is synced into the review list,
# e.g. `janhy` for https://letterboxd.com/janhy/. Empty (the default) turns the
# sync off.
LETTERBOXD_USERNAME=
```

Append to the root `.env.example` (compose reads the root `.env`):

```bash

# Letterboxd member whose RSS feed the backend syncs (REQ §5.7). Empty = off.
LETTERBOXD_USERNAME=
```

In `docker-compose.yml`, under `backend.environment`, after `CORS_ALLOWED_ORIGINS`:

```yaml
      # Letterboxd member to sync (REQ §5.7); empty keeps the sync off.
      LETTERBOXD_USERNAME: ${LETTERBOXD_USERNAME:-}
```

- [ ] **Step 4: Implement** `backend/app/letterboxd/dependencies.py`:

```python
"""FastAPI dependency providers for the letterboxd module (DESIGN §5.1)."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.films.dependencies import get_film_service
from app.films.service import FilmService
from app.letterboxd.errors import LetterboxdDisabledError
from app.letterboxd.feed import FeedEntry, fetch_feed
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import LetterboxdService


def get_letterboxd_repository(
    session: Annotated[Session, Depends(get_session)],
) -> LetterboxdRepository:
    """Repository bound to the request's session (shared with ``FilmService``)."""
    return LetterboxdRepository(session)


def get_feed_fetcher() -> Callable[[], list[FeedEntry]]:
    """The configured member's feed; raises :class:`LetterboxdDisabledError` without one (FR-LBX-01)."""
    username = get_settings().letterboxd_username

    def fetch() -> list[FeedEntry]:
        if not username:
            raise LetterboxdDisabledError()
        return fetch_feed(username)

    return fetch


def get_letterboxd_service(
    repository: Annotated[LetterboxdRepository, Depends(get_letterboxd_repository)],
    films: Annotated[FilmService, Depends(get_film_service)],
    fetch: Annotated[Callable[[], list[FeedEntry]], Depends(get_feed_fetcher)],
) -> LetterboxdService:
    """The review-list service (the seam tests override)."""
    return LetterboxdService(repository, films, fetch)
```

`backend/app/letterboxd/router.py`:

```python
"""Presentation layer for the letterboxd module (REQ §5.7, FR-LBX-01/05..07)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.errors import error_responses
from app.letterboxd.dependencies import get_letterboxd_service
from app.letterboxd.schemas import AssignBody, LetterboxdEntryRead, SyncResult
from app.letterboxd.service import LetterboxdService

router = APIRouter()

Service = Annotated[LetterboxdService, Depends(get_letterboxd_service)]


@router.get(
    "/entries",
    summary="List open Letterboxd entries",
    description=(
        "Open review-list entries, newest watch first. Entries whose watch is "
        "already in the app are resolved first (FR-LBX-07)."
    ),
)
def list_entries(service: Service) -> list[LetterboxdEntryRead]:
    return service.list_open()


@router.post(
    "/entries/{entry_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add an entry's watch to a film",
    description=(
        "Approves the suggestion or assigns another film (FR-LBX-06): adds the "
        "watch with the entry's date and rating and sets the film's Letterboxd "
        "link when it has none."
    ),
    responses=error_responses(
        {
            404: ["NOT_FOUND"],
            409: ["ENTRY_RESOLVED"],
            422: ["VALIDATION_ERROR", "FUTURE_WATCH_DATE"],
        }
    ),
)
def assign_entry(entry_id: UUID, body: AssignBody, service: Service) -> None:
    service.assign(entry_id, body.film_id)


@router.post(
    "/entries/{entry_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss an entry",
    description="Resolves the entry without adding anything (FR-LBX-06).",
    responses=error_responses({404: ["NOT_FOUND"], 409: ["ENTRY_RESOLVED"]}),
)
def dismiss_entry(entry_id: UUID, service: Service) -> None:
    service.dismiss(entry_id)


@router.post(
    "/sync",
    summary="Sync Letterboxd now",
    description="Reads the feed and queues its new entries for review (FR-LBX-01/02).",
    responses=error_responses({409: ["LETTERBOXD_DISABLED"], 502: ["LETTERBOXD_UNAVAILABLE"]}),
)
def sync_now(service: Service) -> SyncResult:
    return SyncResult(queued=service.sync())
```

`backend/app/letterboxd/scheduler.py`:

```python
"""The background Letterboxd sync (FR-LBX-01), started by the app lifespan when a username is set.

Checks hourly against the wall clock rather than sleeping 24 h, so a laptop
that slept through the night still syncs the morning after.
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from app.core.db import session_scope
from app.letterboxd.feed import fetch_feed
from app.letterboxd.repository import LetterboxdRepository
from app.letterboxd.service import run_sync

CHECK_INTERVAL = timedelta(hours=1)
SYNC_INTERVAL = timedelta(hours=24)

logger = logging.getLogger(__name__)


def sync_once(username: str) -> int:
    """One sync in its own session; returns how many entries were queued."""
    with session_scope() as session:
        return run_sync(LetterboxdRepository(session), fetch_feed(username), date.today())


async def run_periodically(username: str) -> None:
    """Sync now, then whenever the last success is a day old; failures retry at the next check."""
    last_synced: datetime | None = None
    while True:
        now = datetime.now(UTC)
        if last_synced is None or now - last_synced >= SYNC_INTERVAL:
            try:
                queued = await asyncio.to_thread(sync_once, username)
            except Exception:
                logger.warning("Letterboxd sync failed, retrying in an hour", exc_info=True)
            else:
                last_synced = now
                logger.info("Letterboxd sync queued %d entries", queued)
        await asyncio.sleep(CHECK_INTERVAL.total_seconds())
```

- [ ] **Step 5: Wire into `backend/app/main.py`**

Add imports:

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.letterboxd.router import router as letterboxd_router
from app.letterboxd.scheduler import run_periodically
```

In `build_api_router()`, after the settings router:

```python
    api.include_router(letterboxd_router, prefix="/letterboxd", tags=["letterboxd"])
```

Above `create_app()`:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run the daily Letterboxd sync while the app is up (FR-LBX-01); off without a username."""
    username = get_settings().letterboxd_username
    task = asyncio.create_task(run_periodically(username)) if username else None
    yield
    if task is not None:
        task.cancel()
```

and pass `lifespan=lifespan` to the `FastAPI(...)` constructor. Bump `version="0.3.0"` to `"0.4.0"` (new routes, nothing broken → MINOR).

In `backend/app/core/errors.py`'s module docstring table, add rows (keep the RST table aligned):

```
``ENTRY_RESOLVED``          409    ``EntryResolvedError`` (FR-LBX-06)
``LETTERBOXD_DISABLED``     409    ``LetterboxdDisabledError`` (FR-LBX-01)
``LETTERBOXD_UNAVAILABLE``  502    ``LetterboxdUnavailableError``
```

and add `EntryNotFoundError` to the `NOT_FOUND` row's "Raised by" list. Widen the table's first column if needed so every row lines up.

- [ ] **Step 6: Run to verify pass, then the full gate**

Run: `uv run pytest tests/test_letterboxd_api.py tests/test_letterboxd_scheduler.py tests/test_openapi_contract.py -q` → PASS.
Then the whole backend gate: `make typecheck && make lint && make format-check && make test` → all clean/green.

- [ ] **Step 7: Manual smoke test against the real feed**

```bash
cd backend && LETTERBOXD_USERNAME=janhy uv run python -c "from app.letterboxd.feed import fetch_feed; e = fetch_feed('janhy'); print(len(e), e[0])"
```

Expected: `50 FeedEntry(guid='letterboxd-watch-…', …)`. Report the output; do not run the sync against the dev database.

- [ ] **Step 8: Commit**

```bash
git add backend/app/letterboxd/dependencies.py backend/app/letterboxd/router.py backend/app/letterboxd/scheduler.py backend/app/core/config.py backend/app/core/errors.py backend/app/main.py backend/.env.example .env.example docker-compose.yml backend/tests/test_letterboxd_api.py backend/tests/test_letterboxd_scheduler.py backend/tests/test_openapi_contract.py
git commit -m "feat(letterboxd): serve the review list and sync the feed daily in the background"
```

---

### Task 7: Frontend domain `letterboxd`

**Files:**
- Create: `frontend/src/app/domain/letterboxd/model.ts`, `api.ts`, `mapper.ts`, `facade.ts`, `letterboxd-facade.spec.ts`

**Interfaces:**
- Consumes: backend routes from Task 6; `FilmFacade.reload()` (`domain/film/facade.ts`).
- Produces:
  - `LetterboxdEntry { id, filmTitle, filmYear, filmUrl, watchedDate: string /* yyyy-MM-dd */, rating: number | null, rewatch, suggestedFilm: { id, title } | null }`
  - `LetterboxdFacade`: `entries: Signal<readonly LetterboxdEntry[]>`, `openCount: Signal<number>`, `isLoading: Signal<boolean>`, `loadFailed: Signal<boolean>`, `isBusy: Signal<boolean>`, `actionError: Signal<string | null>`, `onViewOpened(): void`, `reload(): void`, `assign(entryId: string, filmId: string): void`, `dismiss(entryId: string): void`, `sync(): void`.

- [ ] **Step 1: Write the failing spec** `frontend/src/app/domain/letterboxd/letterboxd-facade.spec.ts`:

```ts
/** Loading and mapping the review list, the three actions, and their failure message. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import { FilmFacade } from '../film/facade';
import type { LetterboxdEntryDto } from './api';
import { LetterboxdFacade } from './facade';

const BASE = `${environment.apiBaseUrl}/letterboxd`;

const DTO: LetterboxdEntryDto = {
  id: 'e1',
  film_title: 'Heat',
  film_year: 1995,
  film_url: 'https://letterboxd.com/film/heat/',
  watched_date: '2026-09-20',
  rating: null,
  rewatch: true,
  suggested_film: { id: 'f1', title: 'Heat' },
};

/** `httpResource`'s loader is async — same settle helper as the settings facade spec. */
async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  TestBed.tick();
}

describe('LetterboxdFacade', () => {
  let facade: LetterboxdFacade;
  let http: HttpTestingController;
  const films = { reload: vi.fn() };

  beforeEach(() => {
    films.reload.mockReset();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: FilmFacade, useValue: films }],
    });
    facade = TestBed.inject(LetterboxdFacade);
    http = TestBed.inject(HttpTestingController);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('maps the open entries and counts them', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    expect(facade.entries()).toEqual([
      {
        id: 'e1',
        filmTitle: 'Heat',
        filmYear: 1995,
        filmUrl: 'https://letterboxd.com/film/heat/',
        watchedDate: '2026-09-20',
        rating: null,
        rewatch: true,
        suggestedFilm: { id: 'f1', title: 'Heat' },
      },
    ]);
    expect(facade.openCount()).toBe(1);
  });

  it('reads as empty with loadFailed when the list cannot load', async () => {
    http.expectOne(`${BASE}/entries`).flush('down', { status: 500, statusText: 'Server Error' });
    await settle();

    expect(facade.entries()).toEqual([]);
    expect(facade.loadFailed()).toBe(true);
  });

  it('assigns, then reloads the list and the film library', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.assign('e1', 'f1');
    const request = http.expectOne({ url: `${BASE}/entries/e1/assign`, method: 'POST' });
    expect(request.request.body).toEqual({ film_id: 'f1' });
    request.flush(null, { status: 204, statusText: 'No Content' });
    await settle();

    expect(films.reload).toHaveBeenCalled();
    http.expectOne(`${BASE}/entries`).flush([]);
    await settle();
    expect(facade.openCount()).toBe(0);
  });

  it('dismisses, then reloads the list', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.dismiss('e1');
    http.expectOne({ url: `${BASE}/entries/e1/dismiss`, method: 'POST' }).flush(null, { status: 204, statusText: 'No Content' });
    await settle();

    http.expectOne(`${BASE}/entries`).flush([]);
  });

  it('syncs, then reloads the list', async () => {
    http.expectOne(`${BASE}/entries`).flush([]);
    await settle();

    facade.sync();
    expect(facade.isBusy()).toBe(true);
    http.expectOne({ url: `${BASE}/sync`, method: 'POST' }).flush({ queued: 1 });
    await settle();

    expect(facade.isBusy()).toBe(false);
    http.expectOne(`${BASE}/entries`).flush([DTO]);
  });

  it('surfaces a failed action and clears it on the next one', async () => {
    http.expectOne(`${BASE}/entries`).flush([DTO]);
    await settle();

    facade.sync();
    http.expectOne({ url: `${BASE}/sync`, method: 'POST' }).flush('down', { status: 502, statusText: 'Bad Gateway' });
    await settle();
    expect(facade.actionError()).toBe('Letterboxd could not be reached.');
    expect(facade.isBusy()).toBe(false);

    facade.dismiss('e1');
    expect(facade.actionError()).toBeNull();
    http.expectOne({ url: `${BASE}/entries/e1/dismiss`, method: 'POST' }).flush(null, { status: 204, statusText: 'No Content' });
    await settle();
    http.expectOne(`${BASE}/entries`).flush([]);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `frontend/`): `npm test -- --include src/app/domain/letterboxd` (if the builder rejects `--include`, run plain `npm test`).
Expected: FAIL — cannot resolve `./facade` / `./api`.

- [ ] **Step 3: Implement**

`frontend/src/app/domain/letterboxd/model.ts`:

```ts
/** Letterboxd review-list domain model (DESIGN §6.1, REQ §5.7). */

/** The film the sync matched (FR-LBX-04), by its primary title. */
export interface SuggestedFilm {
  readonly id: string;
  readonly title: string;
}

/** One open Letterboxd diary entry awaiting review. */
export interface LetterboxdEntry {
  readonly id: string;
  readonly filmTitle: string;
  readonly filmYear: number;
  readonly filmUrl: string;
  /** `yyyy-MM-dd`, as on the wire. */
  readonly watchedDate: string;
  /** `null` = logged without a rating (FR-LBX-08). */
  readonly rating: number | null;
  readonly rewatch: boolean;
  readonly suggestedFilm: SuggestedFilm | null;
}
```

`frontend/src/app/domain/letterboxd/api.ts`:

```ts
/** Letterboxd data access (DESIGN §6.1) — the only place that speaks the `/letterboxd` wire shape. */
import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

const BASE = `${environment.apiBaseUrl}/letterboxd`;

export interface LetterboxdEntryDto {
  readonly id: string;
  readonly film_title: string;
  readonly film_year: number;
  readonly film_url: string;
  readonly watched_date: string;
  readonly rating: number | null;
  readonly rewatch: boolean;
  readonly suggested_film: { readonly id: string; readonly title: string } | null;
}

@Injectable({ providedIn: 'root' })
export class LetterboxdApi {
  private readonly http = inject(HttpClient);

  /** `GET /letterboxd/entries` — the open review list. */
  readonly entries = httpResource<LetterboxdEntryDto[]>(() => `${BASE}/entries`);

  /** `POST …/assign` — approve the suggestion or assign another film (FR-LBX-06). */
  assign(entryId: string, filmId: string): Observable<unknown> {
    return this.http.post(`${BASE}/entries/${entryId}/assign`, { film_id: filmId });
  }

  /** `POST …/dismiss`. */
  dismiss(entryId: string): Observable<unknown> {
    return this.http.post(`${BASE}/entries/${entryId}/dismiss`, null);
  }

  /** `POST /letterboxd/sync` — read the feed now. */
  sync(): Observable<unknown> {
    return this.http.post(`${BASE}/sync`, null);
  }
}
```

`frontend/src/app/domain/letterboxd/mapper.ts`:

```ts
/** `LetterboxdEntryDto` → `LetterboxdEntry` (DESIGN §6.1). */
import type { LetterboxdEntryDto } from './api';
import type { LetterboxdEntry } from './model';

export function toLetterboxdEntry(dto: LetterboxdEntryDto): LetterboxdEntry {
  return {
    id: dto.id,
    filmTitle: dto.film_title,
    filmYear: dto.film_year,
    filmUrl: dto.film_url,
    watchedDate: dto.watched_date,
    rating: dto.rating,
    rewatch: dto.rewatch,
    suggestedFilm: dto.suggested_film,
  };
}
```

`frontend/src/app/domain/letterboxd/facade.ts`:

```ts
/**
 * The Letterboxd facade (DESIGN §6.1) — the single API `views/letterboxd/`
 * and the navigation badge call (REQ §5.7).
 */
import { Injectable, computed, inject, signal } from '@angular/core';
import type { Observable } from 'rxjs';

import { FilmFacade } from '../film/facade';
import { LetterboxdApi } from './api';
import { toLetterboxdEntry } from './mapper';
import type { LetterboxdEntry } from './model';

@Injectable({ providedIn: 'root' })
export class LetterboxdFacade {
  private readonly api = inject(LetterboxdApi);
  private readonly films = inject(FilmFacade);

  /** Empty while loading and on error — `hasValue()` guards `value()`, which throws once the resource has errored. */
  readonly entries = computed<readonly LetterboxdEntry[]>(() =>
    this.api.entries.hasValue() ? this.api.entries.value().map(toLetterboxdEntry) : [],
  );
  readonly openCount = computed(() => this.entries().length);
  readonly isLoading = computed(() => this.api.entries.isLoading());
  readonly loadFailed = computed(() => this.api.entries.error() !== undefined);
  /** True while an action runs — the view disables every action button meanwhile. */
  readonly isBusy = signal(false);
  readonly actionError = signal<string | null>(null);

  private hasOpened = false;

  /** Re-fetches on every open after the first — same rule as `StatsFacade.onViewOpened`. */
  onViewOpened(): void {
    if (this.hasOpened) this.api.entries.reload();
    this.hasOpened = true;
  }

  reload(): void {
    this.api.entries.reload();
  }

  /** Adds the watch to `filmId` (FR-LBX-06); the library reloads so the film's new watch shows everywhere. */
  assign(entryId: string, filmId: string): void {
    this.run(this.api.assign(entryId, filmId), 'The watch could not be added.', () => this.films.reload());
  }

  dismiss(entryId: string): void {
    this.run(this.api.dismiss(entryId), 'The entry could not be dismissed.');
  }

  sync(): void {
    this.run(this.api.sync(), 'Letterboxd could not be reached.');
  }

  private run(request: Observable<unknown>, failure: string, onSuccess: () => void = () => undefined): void {
    this.actionError.set(null);
    this.isBusy.set(true);
    request.subscribe({
      next: () => {
        this.isBusy.set(false);
        onSuccess();
        this.api.entries.reload();
      },
      error: () => {
        this.isBusy.set(false);
        this.actionError.set(failure);
      },
    });
  }
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npm test` → the new spec passes and nothing else regresses. Then `npm run lint` and `npm run format:check` (fix with `npm run format`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/domain/letterboxd
git commit -m "feat(letterboxd): add the review-list domain facade"
```

---

### Task 8: Film form prefill from a Letterboxd entry

**Files:**
- Modify: `frontend/src/app/views/film-form/film-form.ts` (inputs near line 118-125; `releaseYear`, `letterboxdUrl`, `watchDate`, `watchedBefore`, `selectedValue` near lines 250-290; `submit()` near line 400)
- Modify: `frontend/src/app/views/film-form/film-form.spec.ts`

**Interfaces:**
- Consumes: query params `title`, `year`, `letterboxdLink`, `watchedOn` (`yyyy-MM-dd`), `rating` (`0.5`…`5`), `rewatch` (`'true'`) bound by `withComponentInputBinding()`.
- Produces: the query-param contract Task 9's "Create film" link uses; after a create reached with `letterboxdLink`, the form navigates to `/letterboxd` instead of `/library`.

- [ ] **Step 1: Write the failing spec** — add to `film-form.spec.ts` inside `describe('FilmForm', …)`:

```ts
  describe('prefilled from a Letterboxd entry', () => {
    async function renderFromLetterboxd(facade = stubFilmFacade()): Promise<{ element: HTMLElement; harness: RouterTestingHarness }> {
      TestBed.configureTestingModule({
        providers: [
          provideRouter(
            [
              { path: 'films/new', loadComponent: () => Promise.resolve(FilmForm) },
              { path: 'letterboxd', component: BlankComponent },
              { path: 'library', component: BlankComponent },
            ],
            withComponentInputBinding(),
          ),
          provideNativeDateAdapter(),
          { provide: FilmFacade, useValue: facade },
          { provide: TagFacade, useValue: stubLabelFacade([]) },
          { provide: GenreFacade, useValue: stubLabelFacade([]) },
        ],
      });
      const harness = await RouterTestingHarness.create(
        '/films/new?title=Heat&year=1995&letterboxdLink=https%3A%2F%2Fletterboxd.com%2Ffilm%2Fheat%2F&watchedOn=2026-09-20&rating=4.5&rewatch=true',
      );
      return { element: harness.routeNativeElement!, harness };
    }

    it('prefills title, year, link, watch date, rating and watched-before', async () => {
      const facade = stubFilmFacade();
      const { element, harness } = await renderFromLetterboxd(facade);

      setValue(element, '.film-form__director input', 'Michael Mann');
      setValue(element, '.film-form__runtime input', '170');
      await harness.fixture.whenStable();
      for (const [row, value] of [
        ['film-form__genres', 'Crime'],
        ['film-form__tags', 'heist'],
      ] as const) {
        const input = element.querySelector<HTMLInputElement>(`.${row} input`)!;
        input.value = value;
        input.dispatchEvent(new Event('input'));
        pressEnter(input);
        await harness.fixture.whenStable();
      }
      element.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
      await harness.fixture.whenStable();

      const payload = facade.create.mock.calls[0]![0] as FilmCreateInput;
      expect(payload.titles[0]!.value).toBe('Heat');
      expect(payload.releaseYear).toBe(1995);
      expect(payload.letterboxdUrl).toBe('https://letterboxd.com/film/heat/');
      expect(payload.watchDate).toBe('2026-09-20');
      expect(payload.rating).toBe(4.5);
      expect(payload.watchedBefore).toBe(true);
    });

    it('returns to the review list after saving', async () => {
      const { element, harness } = await renderFromLetterboxd();
      setValue(element, '.film-form__director input', 'Michael Mann');
      setValue(element, '.film-form__runtime input', '170');
      await harness.fixture.whenStable();
      for (const [row, value] of [
        ['film-form__genres', 'Crime'],
        ['film-form__tags', 'heist'],
      ] as const) {
        const input = element.querySelector<HTMLInputElement>(`.${row} input`)!;
        input.value = value;
        input.dispatchEvent(new Event('input'));
        pressEnter(input);
        await harness.fixture.whenStable();
      }
      element.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit'));
      await harness.fixture.whenStable();

      expect(TestBed.inject(Router).url).toBe('/letterboxd');
    });

    it('ignores a rating that is not a half step', async () => {
      TestBed.configureTestingModule({
        providers: [
          provideRouter([{ path: 'films/new', loadComponent: () => Promise.resolve(FilmForm) }], withComponentInputBinding()),
          provideNativeDateAdapter(),
          { provide: FilmFacade, useValue: stubFilmFacade() },
          { provide: TagFacade, useValue: stubLabelFacade([]) },
          { provide: GenreFacade, useValue: stubLabelFacade([]) },
        ],
      });
      const harness = await RouterTestingHarness.create('/films/new?title=Heat&rating=7');

      expect(harness.routeNativeElement!.textContent).toContain('Unrated');
    });
  });
```

If the form's submit is wired to a button click rather than the `form` `submit` event, or the unrated state is labelled differently, adapt those two lines to what the existing create-mode specs in this file already do (search the file for how they submit and how they assert "unrated") — do not change production markup for the test.

- [ ] **Step 2: Run to verify failure**

Run: `npm test` → the three new specs FAIL (year/link/date/rating not prefilled; navigates to `/library`).

- [ ] **Step 3: Implement** in `film-form.ts`

Below the existing `title` input, add:

```ts
  /**
   * Prefill from a Letterboxd review-list entry (REQ §5.7, FR-LBX-06), bound
   * from query params like `title`. All strings, since they come off the URL;
   * each is parsed where it seeds its field and ignored when malformed.
   */
  readonly year = input<string>();
  readonly letterboxdLink = input<string>();
  readonly watchedOn = input<string>();
  readonly rating = input<string>();
  readonly rewatch = input<string>();
```

Add these module-level helpers next to `toIsoDate`:

```ts
/** Parses a `yyyy-MM-dd` query param into a local-time `Date`; `null` when absent or malformed. */
function parseIsoDate(value: string | undefined): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

/** A rating query param as a half step in 0.5..5 (FR-RAT-02), or `null`. */
function parseRating(value: string | undefined): number | null {
  const parsed = Number(value);
  return value && parsed >= 0.5 && parsed <= 5 && Number.isInteger(parsed * 2) ? parsed : null;
}
```

Change the seeded fields (keep their existing comments):

```ts
  protected readonly releaseYear = linkedSignal<number | null>(() => {
    const film = this.film();
    if (film !== null) return film.releaseYear;
    const year = Number(this.year());
    return this.year() && Number.isInteger(year) ? year : null;
  });
```

```ts
  protected readonly letterboxdUrl = linkedSignal(() => this.film()?.letterboxdUrl ?? this.letterboxdLink() ?? '');
```

Replace `protected readonly watchDate = signal<Date | null>(this.today);` with:

```ts
  protected readonly watchDate = linkedSignal<Date | null>(() => parseIsoDate(this.watchedOn()) ?? this.today);
```

Replace `protected readonly watchedBefore = signal(false);` with the following, and update its doc comment's "a plain `signal`" sentence to say it seeds only from the Letterboxd `rewatch` param:

```ts
  protected readonly watchedBefore = linkedSignal(() => this.rewatch() === 'true');
```

Replace `protected readonly selectedValue = signal<number | 'unrated'>('unrated');` with:

```ts
  protected readonly selectedValue = linkedSignal<number | 'unrated'>(() => parseRating(this.rating()) ?? 'unrated');
```

In `submit()`, change the create call's target:

```ts
    // Back to the review list when the form was opened from a Letterboxd entry (FR-LBX-06).
    const target = this.letterboxdLink() ? '/letterboxd' : '/library';
    this.send(this.films.create(payload), target, 'The film could not be created.');
```

Remove `signal` from the `@angular/core` import only if nothing else in the file still uses it (`isSubmitting`/`submitError`/`hoverValue` probably do).

- [ ] **Step 4: Run to verify pass**

Run: `npm test` → all green (existing film-form specs included). Then `npm run build`, `npm run lint`, `npm run format:check`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/views/film-form/film-form.ts frontend/src/app/views/film-form/film-form.spec.ts
git commit -m "feat(film-form): prefill a new film from a Letterboxd entry"
```

---

### Task 9: Review view, route and navigation badge

**Files:**
- Create: `frontend/src/app/views/letterboxd/letterboxd.ts`, `letterboxd.html`, `letterboxd.scss`, `assign-dialog.ts`, `letterboxd.spec.ts`
- Modify: `frontend/src/app/core/route-registry.ts` (`navBadge`), `frontend/src/app/core/routes.registry.ts`, `frontend/src/app/app.ts`, `frontend/src/app/app.html`, `frontend/src/app/app.spec.ts`

**Interfaces:**
- Consumes: `LetterboxdFacade` (Task 7); `FilmFacade.films: Signal<readonly Film[]>` (`Film.id`, `Film.primaryTitle`, `Film.releaseYear`); `ConfirmDialog` (`shared/confirm-dialog/confirm-dialog.ts`, data `{ title, message, confirmLabel }`, closes with `true` on confirm); `ratingStarsFor(rating: number | null): readonly string[] | null` and `ratingLabelFor(rating: number | null): string` (`shared/rating-stars.ts`); film-form query params from Task 8.
- Produces: route `letterboxd`; `RouteRegistryEntry.navBadge?: () => Signal<number>`.

- [ ] **Step 1: Write the failing specs**

`frontend/src/app/views/letterboxd/letterboxd.spec.ts`:

```ts
/** The review list: rows, the Approve-only-with-a-suggestion rule, the create link, dismiss, sync. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MatDialog } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

import type { LetterboxdEntry } from '../../domain/letterboxd/model';
import { FilmFacade } from '../../domain/film/facade';
import { LetterboxdFacade } from '../../domain/letterboxd/facade';
import { Letterboxd } from './letterboxd';

const SUGGESTED: LetterboxdEntry = {
  id: 'e1',
  filmTitle: 'Heat',
  filmYear: 1995,
  filmUrl: 'https://letterboxd.com/film/heat/',
  watchedDate: '2026-09-20',
  rating: 4.5,
  rewatch: true,
  suggestedFilm: { id: 'f1', title: 'Heat' },
};
const UNMATCHED: LetterboxdEntry = { ...SUGGESTED, id: 'e2', filmTitle: 'Pulse', filmYear: 2001, rating: null, rewatch: false, suggestedFilm: null };

function stubFacade(entries: readonly LetterboxdEntry[]) {
  return {
    entries: signal(entries),
    isLoading: signal(false),
    loadFailed: signal(false),
    isBusy: signal(false),
    actionError: signal<string | null>(null),
    onViewOpened: vi.fn(),
    reload: vi.fn(),
    assign: vi.fn(),
    dismiss: vi.fn(),
    sync: vi.fn(),
  };
}

async function render(facade: ReturnType<typeof stubFacade>, confirm = true): Promise<HTMLElement> {
  TestBed.configureTestingModule({
    imports: [Letterboxd],
    providers: [
      provideRouter([]),
      { provide: LetterboxdFacade, useValue: facade },
      { provide: FilmFacade, useValue: { films: signal([]) } },
      { provide: MatDialog, useValue: { open: () => ({ afterClosed: () => of(confirm) }) } },
    ],
  });
  const fixture = TestBed.createComponent(Letterboxd);
  await fixture.whenStable();
  return fixture.nativeElement as HTMLElement;
}

function rows(element: HTMLElement): HTMLElement[] {
  return [...element.querySelectorAll<HTMLElement>('.entry')];
}

describe('Letterboxd', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('opens the list on creation', async () => {
    const facade = stubFacade([]);
    await render(facade);

    expect(facade.onViewOpened).toHaveBeenCalled();
  });

  it('shows the empty state with nothing to review', async () => {
    expect((await render(stubFacade([]))).textContent).toContain('Nothing to review');
  });

  it('offers Approve only for an entry with a suggestion', async () => {
    const [suggested, unmatched] = rows(await render(stubFacade([SUGGESTED, UNMATCHED])));

    expect(suggested!.querySelector('.entry__approve')).not.toBeNull();
    expect(unmatched!.querySelector('.entry__approve')).toBeNull();
  });

  it('approves with the suggested film', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade));

    row!.querySelector<HTMLButtonElement>('.entry__approve')!.click();

    expect(facade.assign).toHaveBeenCalledWith('e1', 'f1');
  });

  it('links Create film to the prefilled form', async () => {
    const [row] = rows(await render(stubFacade([SUGGESTED])));
    const href = row!.querySelector<HTMLAnchorElement>('.entry__create')!.getAttribute('href')!;
    const params = new URL(href, 'http://x').searchParams;

    expect(href.startsWith('/films/new?')).toBe(true);
    expect(Object.fromEntries(params)).toEqual({
      title: 'Heat',
      year: '1995',
      letterboxdLink: 'https://letterboxd.com/film/heat/',
      watchedOn: '2026-09-20',
      rating: '4.5',
      rewatch: 'true',
    });
  });

  it('dismisses after confirmation', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade, true));

    row!.querySelector<HTMLButtonElement>('.entry__dismiss')!.click();

    expect(facade.dismiss).toHaveBeenCalledWith('e1');
  });

  it('keeps the entry when the dismiss is cancelled', async () => {
    const facade = stubFacade([SUGGESTED]);
    const [row] = rows(await render(facade, false));

    row!.querySelector<HTMLButtonElement>('.entry__dismiss')!.click();

    expect(facade.dismiss).not.toHaveBeenCalled();
  });

  it('syncs on demand', async () => {
    const facade = stubFacade([]);
    (await render(facade)).querySelector<HTMLButtonElement>('.letterboxd__sync')!.click();

    expect(facade.sync).toHaveBeenCalled();
  });

  it('shows an unrated entry as unrated', async () => {
    const [row] = rows(await render(stubFacade([UNMATCHED])));

    expect(row!.textContent).toContain('Unrated');
  });
});
```

In `frontend/src/app/app.spec.ts`:
1. Add imports `import { signal } from '@angular/core';` (merge with the existing `@angular/core` import) and `import { LetterboxdFacade } from './domain/letterboxd/facade';`.
2. Add below the imports:

```ts
/** The Letterboxd badge's facade, stubbed so the shell needs no HTTP. */
const LETTERBOXD_STUB = { provide: LetterboxdFacade, useValue: { openCount: signal(2) } };
```

3. Add `LETTERBOXD_STUB` to the `providers` array of **every** `TestBed.configureTestingModule` call in the file (the `render` helper and each test that configures its own module).
4. Update the destination expectations: labels become `['Rewatch', 'Library', 'Statistics', 'Letterboxd', 'Settings']`, icons `['replay', 'video_library', 'bar_chart', 'sync', 'settings']`.
5. Add:

```ts
  it('names the open Letterboxd count on its navigation link', async () => {
    const links = [...(await render()).querySelectorAll<HTMLAnchorElement>('nav a')];
    const letterboxd = links.find((link) => link.textContent?.includes('Letterboxd'))!;

    expect(letterboxd.getAttribute('aria-label')).toBe('Letterboxd, 2 to review');
    expect(links.find((link) => link.textContent?.includes('Library'))!.getAttribute('aria-label')).toBeNull();
  });
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test` → FAIL (no `./letterboxd` component; nav lists four destinations).

- [ ] **Step 3: Implement the registry badge**

In `core/route-registry.ts`, add to `RouteRegistryEntry` after `navLabel`:

```ts
  /**
   * A count shown on the destination's navigation icon; 0 hides it. Called
   * once in the app shell's injection context, so it may `inject` a facade.
   */
  readonly navBadge?: () => Signal<number>;
```

and change the import line to `import type { Signal, Type } from '@angular/core';`.

In `core/routes.registry.ts`, add the loader and entry (entry between Statistics and Settings):

```ts
const letterboxd = (): Promise<typeof import('../views/letterboxd/letterboxd').Letterboxd> =>
  import('../views/letterboxd/letterboxd').then((module) => module.Letterboxd);
```

```ts
  {
    path: 'letterboxd',
    title: 'Letterboxd',
    loadComponent: letterboxd,
    navIcon: 'sync',
    navLabel: 'Letterboxd',
    // Open review-list entries (REQ §5.7).
    navBadge: () => inject(LetterboxdFacade).openCount,
  },
```

with imports `import { inject } from '@angular/core';` and `import { LetterboxdFacade } from '../domain/letterboxd/facade';`.

In `app.ts`: import `MatBadgeModule` from `@angular/material/badge` and add it to `imports`; add `type Signal` to the `@angular/core` import; add to the class:

```ts
  /** Each destination's `navBadge`, resolved once here, in the injection context it may `inject` from. */
  private readonly badges = new Map<string, Signal<number>>(
    ROUTE_REGISTRY.flatMap((entry) => (entry.navBadge ? [[entry.path, entry.navBadge()] as const] : [])),
  );

  protected badgeCount(path: string): number {
    return this.badges.get(path)?.() ?? 0;
  }
```

In `app.html`, replace the nav `@for` body with:

```html
  @for (destination of destinations; track destination.path) {
    @let count = badgeCount(destination.path);
    <a
      class="app-nav__link"
      routerLinkActive="app-nav__link--active"
      #active="routerLinkActive"
      [routerLink]="['/', destination.path]"
      [attr.aria-current]="active.isActive ? 'page' : null"
      [attr.aria-label]="count ? destination.label + ', ' + count + ' to review' : null"
    >
      <mat-icon aria-hidden="true" [matBadge]="count" [matBadgeHidden]="!count" matBadgeSize="small">{{
        destination.icon
      }}</mat-icon>
      <span class="app-nav__label">{{ destination.label }}</span>
    </a>
  }
```

- [ ] **Step 4: Implement the view**

`frontend/src/app/views/letterboxd/assign-dialog.ts`:

```ts
/** Picks the film a Letterboxd entry's watch goes to (FR-LBX-06), searching the cached library by title. */
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { FilmFacade } from '../../domain/film/facade';
import type { Film } from '../../domain/film/model';

export interface AssignDialogData {
  readonly filmTitle: string;
}

const MAX_OPTIONS = 20;

@Component({
  selector: 'app-assign-dialog',
  imports: [MatAutocompleteModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 matDialogTitle>Assign “{{ data.filmTitle }}”</h2>
    <mat-dialog-content>
      <mat-form-field class="assign__field">
        <mat-label>Film</mat-label>
        <input
          #query
          matInput
          [value]="data.filmTitle"
          [matAutocomplete]="films"
          (input)="search.set(query.value)"
        />
        <mat-autocomplete #films="matAutocomplete" (optionSelected)="choose($event.option.value)">
          @for (film of matches(); track film.id) {
            <mat-option [value]="film">{{ film.primaryTitle }} ({{ film.releaseYear }})</mat-option>
          }
        </mat-autocomplete>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button matButton type="button" [mat-dialog-close]="undefined">Cancel</button>
    </mat-dialog-actions>
  `,
  styles: '.assign__field { width: 100%; }',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AssignDialog {
  protected readonly data = inject<AssignDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject<MatDialogRef<AssignDialog, string>>(MatDialogRef);
  private readonly films = inject(FilmFacade).films;

  protected readonly search = signal(this.data.filmTitle);
  protected readonly matches = computed<readonly Film[]>(() => {
    const query = this.search().trim().toLowerCase();
    return this.films()
      .filter((film) => film.primaryTitle.toLowerCase().includes(query))
      .slice(0, MAX_OPTIONS);
  });

  protected choose(film: Film): void {
    this.dialogRef.close(film.id);
  }
}
```

`frontend/src/app/views/letterboxd/letterboxd.ts`:

```ts
/**
 * The Letterboxd review list (REQ §5.7, FR-LBX-06): every new Letterboxd diary
 * entry waits here for approval. Per §6.1 the view calls facades only.
 */
import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDialog } from '@angular/material/dialog';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { LetterboxdFacade } from '../../domain/letterboxd/facade';
import type { LetterboxdEntry } from '../../domain/letterboxd/model';
import { ConfirmDialog, type ConfirmDialogData } from '../../shared/confirm-dialog/confirm-dialog';
import { ratingLabelFor, ratingStarsFor } from '../../shared/rating-stars';
import { AssignDialog, type AssignDialogData } from './assign-dialog';

@Component({
  selector: 'app-letterboxd',
  imports: [DatePipe, MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  templateUrl: './letterboxd.html',
  styleUrl: './letterboxd.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Letterboxd {
  private readonly letterboxd = inject(LetterboxdFacade);
  private readonly dialog = inject(MatDialog);

  protected readonly entries = this.letterboxd.entries;
  protected readonly isLoading = this.letterboxd.isLoading;
  protected readonly loadFailed = this.letterboxd.loadFailed;
  protected readonly isBusy = this.letterboxd.isBusy;
  protected readonly actionError = this.letterboxd.actionError;
  protected readonly stars = ratingStarsFor;
  protected readonly ratingLabel = ratingLabelFor;

  constructor() {
    this.letterboxd.onViewOpened();
  }

  /** The film form's Letterboxd prefill params (FR-LBX-06) — names match its inputs. */
  protected createParams(entry: LetterboxdEntry): Record<string, string> {
    return {
      title: entry.filmTitle,
      year: String(entry.filmYear),
      letterboxdLink: entry.filmUrl,
      watchedOn: entry.watchedDate,
      ...(entry.rating !== null ? { rating: String(entry.rating) } : {}),
      ...(entry.rewatch ? { rewatch: 'true' } : {}),
    };
  }

  protected approve(entry: LetterboxdEntry): void {
    if (entry.suggestedFilm !== null) this.letterboxd.assign(entry.id, entry.suggestedFilm.id);
  }

  protected assign(entry: LetterboxdEntry): void {
    this.dialog
      .open<AssignDialog, AssignDialogData, string>(AssignDialog, { data: { filmTitle: entry.filmTitle }, width: '32rem' })
      .afterClosed()
      .subscribe((filmId) => {
        if (filmId) this.letterboxd.assign(entry.id, filmId);
      });
  }

  protected dismiss(entry: LetterboxdEntry): void {
    this.dialog
      .open<ConfirmDialog, ConfirmDialogData, boolean>(ConfirmDialog, {
        data: {
          title: 'Dismiss entry?',
          message: `“${entry.filmTitle}” will not be added. This cannot be undone.`,
          confirmLabel: 'Dismiss',
        },
      })
      .afterClosed()
      .subscribe((confirmed) => {
        if (confirmed) this.letterboxd.dismiss(entry.id);
      });
  }

  protected sync(): void {
    this.letterboxd.sync();
  }

  protected reload(): void {
    this.letterboxd.reload();
  }
}
```

`frontend/src/app/views/letterboxd/letterboxd.html`:

```html
<div class="letterboxd__toolbar">
  <p class="letterboxd__hint">New Letterboxd diary entries wait here until you approve them.</p>
  <button class="letterboxd__sync" matButton type="button" [disabled]="isBusy()" (click)="sync()">
    <mat-icon>sync</mat-icon>
    Sync now
  </button>
</div>

@if (isBusy() || isLoading()) {
  <mat-progress-bar mode="indeterminate" aria-hidden="true" />
}

@if (actionError()) {
  <p class="letterboxd__error" role="alert">{{ actionError() }}</p>
}

@if (loadFailed()) {
  <div class="letterboxd__state" role="alert">
    <p>The review list could not be loaded. Is the backend running?</p>
    <button matButton type="button" (click)="reload()">Try again</button>
  </div>
} @else if (!isLoading() && entries().length === 0) {
  <p class="letterboxd__state">Nothing to review.</p>
}

@for (entry of entries(); track entry.id) {
  <mat-card class="entry">
    <mat-card-header>
      <mat-card-title>
        <a class="entry__link" [href]="entry.filmUrl" target="_blank" rel="noopener">{{ entry.filmTitle }}</a>
        ({{ entry.filmYear }})
      </mat-card-title>
      <mat-card-subtitle>
        Watched {{ entry.watchedDate | date: 'd MMM y' }}
        @if (entry.rewatch) {
          · rewatch
        }
      </mat-card-subtitle>
    </mat-card-header>
    <mat-card-content>
      <p class="entry__rating" [attr.aria-label]="ratingLabel(entry.rating)">
        @if (stars(entry.rating); as icons) {
          @for (icon of icons; track $index) {
            <mat-icon aria-hidden="true">{{ icon }}</mat-icon>
          }
        } @else {
          Unrated
        }
      </p>
      @if (entry.suggestedFilm; as film) {
        <p class="entry__suggestion">
          Matches <a [routerLink]="['/film', film.id]">{{ film.title }}</a>
        </p>
      } @else {
        <p class="entry__suggestion">Not in your library yet.</p>
      }
    </mat-card-content>
    <mat-card-actions align="end">
      <button class="entry__dismiss destructive" matButton type="button" [disabled]="isBusy()" (click)="dismiss(entry)">
        Dismiss
      </button>
      <button class="entry__assign" matButton type="button" [disabled]="isBusy()" (click)="assign(entry)">
        Assign…
      </button>
      <a class="entry__create" matButton routerLink="/films/new" [queryParams]="createParams(entry)">Create film</a>
      @if (entry.suggestedFilm) {
        <button class="entry__approve" matButton="filled" type="button" [disabled]="isBusy()" (click)="approve(entry)">
          Approve
        </button>
      }
    </mat-card-actions>
  </mat-card>
}
```

If `ratingStarsFor(null)` returns something other than `null`, or `ratingLabelFor` is not the right a11y label helper, check `shared/rating-stars.ts` and the library/film-detail templates for how they render a rating row and follow that pattern instead.

`frontend/src/app/views/letterboxd/letterboxd.scss`:

```scss
:host {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.letterboxd__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.letterboxd__hint,
.letterboxd__state {
  margin: 0;
  color: var(--mat-sys-on-surface-variant);
}

.letterboxd__error {
  margin: 0;
  color: var(--mat-sys-error);
}

.entry__rating {
  display: flex;
  align-items: center;
  margin: 0;
  color: var(--mat-sys-primary);
}

.entry__suggestion {
  margin: 4px 0 0;
}

.entry mat-card-actions {
  flex-wrap: wrap;
}
```

- [ ] **Step 5: Run to verify pass, then the full frontend gate**

Run: `npm test` → all green. Then `npm run build`, `npm run lint`, `npm run format:check` → clean. (Lint includes template a11y; fix findings in the template, not by disabling rules.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/views/letterboxd frontend/src/app/core/route-registry.ts frontend/src/app/core/routes.registry.ts frontend/src/app/app.ts frontend/src/app/app.html frontend/src/app/app.spec.ts
git commit -m "feat(letterboxd): add the review view with a nav badge for open entries"
```

---

## Finish

After Task 9, from the repo root:

1. Backend gate: `cd backend && make typecheck && make lint && make format-check && make test`.
2. Frontend gate: `cd frontend && npm run build && npm test && npm run lint && npm run format:check`.
3. Tell the user to add `LETTERBOXD_USERNAME=janhy` to the root `.env` and rebuild the backend container (`docker compose up -d --build backend`); the first sync runs at startup.
