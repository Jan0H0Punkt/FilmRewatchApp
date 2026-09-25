# Statistics View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `/stats` page showing viewing statistics for all time and for each tracked year.

**Architecture:** A new backend feature module `app/stats/` loads all watches through a repository and computes the whole payload in a dependency-free pure function (`algorithm.py`, same pattern as `app/rewatch/algorithm.py`). `GET /api/v1/stats` serves it. The frontend adds `domain/stats/` (DTO → domain mapping, facade) and `views/stats/`, which is registered as the third navigation destination.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Pydantic v2 (pyright strict), Angular 22 + Angular Material M3 (strict TS), vitest.

**Spec:** `docs/superpowers/specs/2026-09-25-statistics-design.md`

## Global Constraints

- All code, comments and commit messages in English. UI copy is English too: nav label `Statistics`, scope chip `All time`, empty state `No watches this year`.
- Backend gate (from `backend/`): `make typecheck`, `make lint`, `make format-check`, `make test` (or `make test-offline` without Postgres). Run Python only via `uv run`.
- Frontend gate (from `frontend/`): `npm run build`, `npm test`, `npm run lint`, `npm run format:check`.
- Backend TestClient tests need `httpx2` (already in dev deps), not `httpx`.
- No new dependencies on either tier. Charts are plain CSS.
- Colours only through `var(--mat-sys-*)` tokens so Dark/Light/Auto keep working.
- Views call facades only (§6.1). New routes are added by appending to `frontend/src/app/core/routes.registry.ts`, never by editing `app.routes.ts` (FR-EXT-02).
- Undated watches: rating entries dated `EARLIER_WATCH_DATE` (`1888-01-01`, `app.ratings.service`). The repository maps them to `watch_date=None`; the algorithm never sees 1888.
- Top lists hold 5 entries; a tie breaks alphabetically (name, or film title).
- Commit via the `commit-changes` skill, one-line `<type>(<scope>): <description>` subjects, no trailers.

## Review Focus

1. **Empty library** — no rating entries at all: `total` is all zeros with `average_rating: null`, `years` is `[]`, and the page shows the All-time block without crashing. → Task 1 (`test_an_empty_library_yields_zeros_and_no_years`), Task 4 (`shows all time when there are no years`).
2. **A film seen only "before, date unknown"** — counts in all-time watches and minutes, is never a first watch, creates no year. → Task 1 (`test_an_undated_watch_counts_only_in_total`).
3. **Stats go stale after logging a watch** — reopening the page must refetch. → Task 3 (`refetches when the view is opened again`).
4. **January 1st, current year has no watches yet** — the preselected current-year chip exists and shows the empty state. → Task 1 (`test_years_run_through_the_current_year_even_when_empty`), Task 4 (`shows the empty state for a year without watches`).
5. **Same-day repeat watches** (FR-RAT-04) — both count as watches; the film counts once as a first watch, the second is a rewatch. → Task 1 (`test_a_same_day_repeat_is_one_first_watch_and_one_rewatch`).

---

### Task 1: Pure stats algorithm (backend)

**Files:**
- Create: `backend/app/stats/__init__.py` (empty)
- Create: `backend/app/stats/algorithm.py`
- Test: `backend/tests/test_stats_algorithm.py`

**Interfaces:**
- Consumes: nothing from `app` (the module must stay import-free of `app`, like `app/rewatch/algorithm.py`).
- Produces:
  - `Watch(film_id: UUID, title: str, release_year: int, director: str, runtime_minutes: int, genres: tuple[str, ...], watch_date: date | None, value: Decimal | None)`
  - `NamedCount(name: str, count: int)`, `FilmCount(film_id: UUID, title: str, count: int)`, `RatingCount(value: float, count: int)`, `Bucket(label: str, count: int)`
  - `StatsBlock(watches: int, first_watches: int, rewatches: int, films_released_that_year: int | None, distinct_films: int, minutes_watched: int, average_rating: float | None, rating_distribution: list[RatingCount], top_genres: list[NamedCount], top_directors: list[NamedCount], top_films: list[FilmCount], buckets: list[Bucket])`
  - `YearStats(year: int, block: StatsBlock)`, `Stats(total: StatsBlock, years: list[YearStats])`
  - `compute(watches: Sequence[Watch], today: date) -> Stats`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_stats_algorithm.py`:

```python
"""The pure stats algorithm against the spec's definitions (docs/superpowers/specs/2026-09-25-statistics-design.md).

No database and no app fixtures — the module under test imports nothing from ``app``.
"""

import uuid
from datetime import date
from decimal import Decimal

from app.stats.algorithm import Bucket, FilmCount, NamedCount, Watch, compute

TODAY = date(2026, 9, 25)
HEAT = uuid.uuid4()
ALIEN = uuid.uuid4()


def _watch(
    film_id: uuid.UUID = HEAT,
    watch_date: date | None = date(2026, 3, 1),
    *,
    title: str = "Heat",
    release_year: int = 1995,
    director: str = "Michael Mann",
    runtime_minutes: int = 170,
    genres: tuple[str, ...] = ("Crime",),
    value: Decimal | None = Decimal("4.0"),
) -> Watch:
    return Watch(
        film_id=film_id,
        title=title,
        release_year=release_year,
        director=director,
        runtime_minutes=runtime_minutes,
        genres=genres,
        watch_date=watch_date,
        value=value,
    )


def test_an_empty_library_yields_zeros_and_no_years() -> None:
    stats = compute([], TODAY)

    assert stats.years == []
    assert stats.total.watches == 0
    assert stats.total.first_watches == 0
    assert stats.total.average_rating is None
    assert stats.total.films_released_that_year is None
    assert [r.count for r in stats.total.rating_distribution] == [0] * 10


def test_the_first_dated_watch_is_the_first_watch_and_later_ones_are_rewatches() -> None:
    stats = compute([_watch(watch_date=date(2025, 5, 1)), _watch(watch_date=date(2026, 2, 1))], TODAY)

    [y2026, y2025] = stats.years
    assert (y2025.year, y2025.block.first_watches, y2025.block.rewatches) == (2025, 1, 0)
    assert (y2026.year, y2026.block.first_watches, y2026.block.rewatches) == (2026, 0, 1)
    assert (stats.total.watches, stats.total.first_watches, stats.total.rewatches) == (2, 1, 1)


def test_a_same_day_repeat_is_one_first_watch_and_one_rewatch() -> None:
    # FR-RAT-04 allows two entries on one day.
    stats = compute([_watch(), _watch()], TODAY)

    block = stats.years[0].block
    assert (block.watches, block.first_watches, block.rewatches) == (2, 1, 1)


def test_an_undated_watch_counts_only_in_total() -> None:
    # "Seen before, date unknown": every dated watch of that film is a rewatch.
    stats = compute([_watch(watch_date=None, value=None), _watch()], TODAY)

    assert (stats.total.watches, stats.total.first_watches, stats.total.rewatches) == (2, 0, 2)
    assert stats.total.minutes_watched == 340
    [year] = stats.years
    assert (year.block.watches, year.block.first_watches, year.block.rewatches) == (1, 0, 1)


def test_a_film_with_only_an_undated_watch_creates_no_year() -> None:
    stats = compute([_watch(watch_date=None)], TODAY)

    assert stats.years == []
    assert stats.total.watches == 1


def test_films_released_that_year_counts_distinct_films() -> None:
    new = uuid.uuid4()
    watches = [
        _watch(new, date(2026, 4, 1), title="New", release_year=2026),
        _watch(new, date(2026, 5, 1), title="New", release_year=2026),
        _watch(),
    ]

    assert compute(watches, TODAY).years[0].block.films_released_that_year == 1


def test_years_run_through_the_current_year_even_when_empty() -> None:
    stats = compute([_watch(watch_date=date(2024, 6, 1))], TODAY)

    assert [y.year for y in stats.years] == [2026, 2025, 2024]
    empty = stats.years[0].block
    assert (empty.watches, empty.average_rating, empty.top_films) == (0, None, [])


def test_average_and_distribution_skip_unrated_watches() -> None:
    watches = [_watch(value=Decimal("4.0")), _watch(value=Decimal("5.0")), _watch(value=None)]

    block = compute(watches, TODAY).total
    assert block.average_rating == 4.5
    assert {r.value: r.count for r in block.rating_distribution if r.count} == {4.0: 1, 5.0: 1}
    assert [r.value for r in block.rating_distribution] == [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


def test_top_lists_rank_by_watches_and_break_ties_alphabetically() -> None:
    watches = [
        _watch(),
        _watch(),
        _watch(ALIEN, title="Alien", director="Ridley Scott", genres=("Horror", "Sci-Fi")),
    ]

    block = compute(watches, TODAY).total
    assert block.top_films == [FilmCount(HEAT, "Heat", 2), FilmCount(ALIEN, "Alien", 1)]
    assert block.top_directors == [NamedCount("Michael Mann", 2), NamedCount("Ridley Scott", 1)]
    assert block.top_genres == [NamedCount("Crime", 2), NamedCount("Horror", 1), NamedCount("Sci-Fi", 1)]


def test_top_lists_hold_at_most_five() -> None:
    watches = [_watch(uuid.uuid4(), title=f"Film {i}") for i in range(7)]

    assert len(compute(watches, TODAY).total.top_films) == 5


def test_year_buckets_are_months_and_total_buckets_are_years() -> None:
    watches = [_watch(watch_date=date(2025, 1, 10)), _watch(watch_date=date(2026, 3, 1)), _watch(watch_date=date(2026, 3, 2))]

    stats = compute(watches, TODAY)
    assert stats.total.buckets == [Bucket("2025", 1), Bucket("2026", 2)]
    months = stats.years[0].block.buckets
    assert [b.label for b in months] == [str(m) for m in range(1, 13)]
    assert months[2] == Bucket("3", 2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_stats_algorithm.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stats'`

- [ ] **Step 3: Write the implementation**

Create an empty `backend/app/stats/__init__.py`. Then `backend/app/stats/algorithm.py`:

```python
"""The statistics computation (docs/superpowers/specs/2026-09-25-statistics-design.md).

Pure and dependency-free, like ``app.rewatch.algorithm``: it takes every watch
as a flat :class:`Watch` and returns the whole payload, so every definition is
testable without a database. An undated watch ("seen before, date unknown",
FR-RAT-04/12) arrives with ``watch_date=None``; it counts in the all-time block
only, and makes every dated watch of its film a rewatch.
"""

from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

TOP_N = 5
# 0.5-5.0 in half steps (REQ §5.4) — every bucket is reported, zeros included.
RATING_VALUES = [n / 2 for n in range(1, 11)]


@dataclass(frozen=True, slots=True)
class Watch:
    """One rating entry joined with the film data the statistics read."""

    film_id: UUID
    title: str
    release_year: int
    director: str
    runtime_minutes: int
    genres: tuple[str, ...]
    watch_date: date | None
    value: Decimal | None


@dataclass(frozen=True, slots=True)
class NamedCount:
    name: str
    count: int


@dataclass(frozen=True, slots=True)
class FilmCount:
    film_id: UUID
    title: str
    count: int


@dataclass(frozen=True, slots=True)
class RatingCount:
    value: float
    count: int


@dataclass(frozen=True, slots=True)
class Bucket:
    """A month (``"1"``-``"12"``) in a year block, a year in the all-time block."""

    label: str
    count: int


@dataclass(frozen=True, slots=True)
class StatsBlock:
    watches: int
    first_watches: int
    rewatches: int
    # ``None`` in the all-time block, where "released that year" has no year.
    films_released_that_year: int | None
    distinct_films: int
    minutes_watched: int
    average_rating: float | None
    rating_distribution: list[RatingCount]
    top_genres: list[NamedCount]
    top_directors: list[NamedCount]
    top_films: list[FilmCount]
    buckets: list[Bucket]


@dataclass(frozen=True, slots=True)
class YearStats:
    year: int
    block: StatsBlock


@dataclass(frozen=True, slots=True)
class Stats:
    total: StatsBlock
    years: list[YearStats]


def compute(watches: Sequence[Watch], today: date) -> Stats:
    """All-time block plus one block per year, newest year first."""
    undated_films = {w.film_id for w in watches if w.watch_date is None}
    dated = [(w, w.watch_date) for w in watches if w.watch_date is not None]

    # A film's first watch is its earliest dated entry — unless an undated
    # entry says it was seen before, in which case it has none.
    first_seen: dict[UUID, date] = {}
    for watch, watched in dated:
        if watch.film_id not in undated_films:
            first_seen[watch.film_id] = min(first_seen.get(watch.film_id, watched), watched)
    first_per_year = Counter(d.year for d in first_seen.values())

    per_year = Counter(watched.year for _, watched in dated)
    years = range(min(per_year), max(today.year, *per_year) + 1) if per_year else range(0)

    total = _block(
        watches,
        first_watches=len(first_seen),
        films_released_that_year=None,
        buckets=[Bucket(str(y), per_year[y]) for y in years],
    )
    return Stats(total=total, years=[_year(y, dated, first_per_year[y]) for y in reversed(years)])


def _year(year: int, dated: list[tuple[Watch, date]], first_watches: int) -> YearStats:
    in_year = [(w, d) for w, d in dated if d.year == year]
    months = Counter(d.month for _, d in in_year)
    watches = [w for w, _ in in_year]
    return YearStats(
        year=year,
        block=_block(
            watches,
            first_watches=first_watches,
            films_released_that_year=len({w.film_id for w in watches if w.release_year == year}),
            buckets=[Bucket(str(m), months[m]) for m in range(1, 13)],
        ),
    )


def _block(
    watches: Sequence[Watch],
    *,
    first_watches: int,
    films_released_that_year: int | None,
    buckets: list[Bucket],
) -> StatsBlock:
    rated = [float(w.value) for w in watches if w.value is not None]
    ratings = Counter(rated)
    titles = {w.film_id: w.title for w in watches}
    return StatsBlock(
        watches=len(watches),
        first_watches=first_watches,
        rewatches=len(watches) - first_watches,
        films_released_that_year=films_released_that_year,
        distinct_films=len(titles),
        minutes_watched=sum(w.runtime_minutes for w in watches),
        average_rating=round(sum(rated) / len(rated), 2) if rated else None,
        rating_distribution=[RatingCount(v, ratings[v]) for v in RATING_VALUES],
        top_genres=[NamedCount(n, c) for n, c in _top((g for w in watches for g in w.genres), str)],
        top_directors=[NamedCount(n, c) for n, c in _top((w.director for w in watches), str)],
        top_films=[
            FilmCount(f, titles[f], c) for f, c in _top((w.film_id for w in watches), titles.__getitem__)
        ],
        buckets=buckets,
    )


def _top[K: Hashable](keys: Iterable[K], name: Callable[[K], str]) -> list[tuple[K, int]]:
    """The ``TOP_N`` most frequent keys; a tie sorts alphabetically by ``name``."""
    counts = Counter(keys)
    return sorted(counts.items(), key=lambda item: (-item[1], name(item[0])))[:TOP_N]
```

- [ ] **Step 4: Run the tests and type-check**

Run (from `backend/`): `uv run pytest tests/test_stats_algorithm.py -q && make typecheck && make lint && make format-check`
Expected: all tests PASS, pyright `0 errors`, Ruff clean. If `make format-check` fails, run `make format` and re-run.

- [ ] **Step 5: Commit**

Via `commit-changes`. Suggested subject: `feat(stats): compute all-time and per-year viewing statistics`

---

### Task 2: Stats endpoint (backend)

**Files:**
- Create: `backend/app/stats/repository.py`, `backend/app/stats/service.py`, `backend/app/stats/dependencies.py`, `backend/app/stats/schemas.py`, `backend/app/stats/router.py`
- Modify: `backend/app/main.py` (import + one `include_router` line next to `rewatch_router`, ~line 25 and ~line 50)
- Test: `backend/tests/test_stats_api.py`, `backend/tests/test_stats_repository.py`

**Interfaces:**
- Consumes: `Watch`, `Stats`, `compute` from Task 1; `EARLIER_WATCH_DATE` from `app.ratings.service`; `Film`, `Title` (`app.films.models`), `RatingEntry` (`app.ratings.models`), `Genre`, `FilmGenre` (`app.genres.models`); `get_session` (`app.core.db`); `StrictSchema` (`app.core.schemas`).
- Produces: `GET /api/v1/stats` returning `StatsRead` JSON:
  ```
  { "total": StatsBlockRead, "years": [ { "year": int, ...StatsBlockRead } ] }
  StatsBlockRead = { watches, first_watches, rewatches, films_released_that_year (int|null),
    distinct_films, minutes_watched, average_rating (float|null),
    rating_distribution: [{value: float, count}], top_genres: [{name, count}],
    top_directors: [{name, count}], top_films: [{film_id: uuid-string, title, count}],
    buckets: [{label: str, count}] }
  ```

- [ ] **Step 1: Write the failing API test**

`backend/tests/test_stats_api.py`:

```python
"""``GET /stats`` end to end, offline: the service is stubbed with a real :class:`Stats`."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app
from app.stats.algorithm import Stats, Watch, compute
from app.stats.dependencies import get_stats_service

FILM = uuid.uuid4()


def _client(stats: Stats) -> TestClient:
    app = create_app()

    class StubService:
        def stats(self, today: date) -> Stats:
            return stats

    app.dependency_overrides[get_stats_service] = StubService
    return TestClient(app)


def test_the_payload_carries_total_and_flattened_years() -> None:
    watch = Watch(FILM, "Heat", 1995, "Michael Mann", 170, ("Crime",), date(2026, 3, 1), Decimal("4.5"))

    body = _client(compute([watch], date(2026, 9, 25))).get("/api/v1/stats").json()

    assert body["total"]["films_released_that_year"] is None
    assert body["total"]["average_rating"] == 4.5
    assert body["total"]["top_films"] == [{"film_id": str(FILM), "title": "Heat", "count": 1}]
    [year] = body["years"]
    assert year["year"] == 2026
    assert year["watches"] == 1
    assert year["buckets"][2] == {"label": "3", "count": 1}


def test_an_empty_library_is_a_normal_answer() -> None:
    response = _client(compute([], date(2026, 9, 25))).get("/api/v1/stats")

    assert response.status_code == 200
    assert response.json()["years"] == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_stats_api.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.stats.dependencies'`

- [ ] **Step 3: Write schemas, repository, service, dependencies, router and wiring**

`backend/app/stats/schemas.py`:

```python
"""Pydantic response schemas for the stats module (DESIGN §5.3).

Read-only. Built from the algorithm's dataclasses via ``from_attributes``; the
lists are ``list`` because strict mode rejects a tuple for a list field.
"""

from uuid import UUID

from pydantic import ConfigDict

from app.core.schemas import StrictSchema
from app.stats.algorithm import Stats


class _Read(StrictSchema):
    model_config = ConfigDict(from_attributes=True)


class NamedCountRead(_Read):
    name: str
    count: int


class FilmCountRead(_Read):
    film_id: UUID
    title: str
    count: int


class RatingCountRead(_Read):
    value: float
    count: int


class BucketRead(_Read):
    label: str
    count: int


class StatsBlockRead(_Read):
    watches: int
    first_watches: int
    rewatches: int
    films_released_that_year: int | None
    distinct_films: int
    minutes_watched: int
    average_rating: float | None
    rating_distribution: list[RatingCountRead]
    top_genres: list[NamedCountRead]
    top_directors: list[NamedCountRead]
    top_films: list[FilmCountRead]
    buckets: list[BucketRead]


class YearStatsRead(StatsBlockRead):
    year: int


class StatsRead(_Read):
    total: StatsBlockRead
    years: list[YearStatsRead]

    @classmethod
    def from_stats(cls, stats: Stats) -> "StatsRead":
        """Flattens each ``YearStats`` into its block plus ``year``, the wire shape."""
        return cls(
            total=StatsBlockRead.model_validate(stats.total),
            years=[
                YearStatsRead.model_validate({"year": y.year, **StatsBlockRead.model_validate(y.block).model_dump()})
                for y in stats.years
            ],
        )
```

`backend/app/stats/repository.py`:

```python
"""Data-access layer for the stats module (DESIGN §5.1).

Two reads, no rules: every rating entry joined with its film's primary title
and metadata, and every film's genres. Genres come from a second query because
joining them in would repeat each entry once per genre.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.ratings.service import EARLIER_WATCH_DATE
from app.stats.algorithm import Watch


class StatsRepository:
    """SQLAlchemy-backed stats data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def watches(self) -> list[Watch]:
        """Every rating entry as a :class:`Watch`; ``EARLIER_WATCH_DATE`` becomes ``None``."""
        genres: defaultdict[UUID, list[str]] = defaultdict(list)
        genre_rows = self._session.execute(
            select(FilmGenre.film_id, Genre.name)
            .join(Genre, Genre.id == FilmGenre.genre_id)
            .order_by(FilmGenre.position)
        )
        for film_id, name in genre_rows:
            genres[film_id].append(name)

        statement = (
            select(
                RatingEntry.film_id,
                RatingEntry.watch_date,
                RatingEntry.value,
                Title.value.label("title"),
                Film.release_year,
                Film.director,
                Film.runtime_minutes,
            )
            .join(Film, Film.id == RatingEntry.film_id)
            .join(Title, and_(Title.film_id == Film.id, Title.is_primary))
        )
        return [
            Watch(
                film_id=row.film_id,
                title=row.title,
                release_year=row.release_year,
                director=row.director,
                runtime_minutes=row.runtime_minutes,
                genres=tuple(genres[row.film_id]),
                watch_date=None if row.watch_date == EARLIER_WATCH_DATE else row.watch_date,
                value=row.value,
            )
            for row in self._session.execute(statement)
        ]
```

`backend/app/stats/service.py`:

```python
"""Business-logic layer for the stats module (DESIGN §5.1) — the seam the router depends on."""

from datetime import date

from app.stats.algorithm import Stats, compute
from app.stats.repository import StatsRepository


class StatsService:
    def __init__(self, repository: StatsRepository) -> None:
        self._repository = repository

    def stats(self, today: date) -> Stats:
        return compute(self._repository.watches(), today)
```

`backend/app/stats/dependencies.py`:

```python
"""FastAPI dependency providers for the stats module (DESIGN §5.1)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.stats.repository import StatsRepository
from app.stats.service import StatsService


def get_stats_repository(session: Annotated[Session, Depends(get_session)]) -> StatsRepository:
    """Repository bound to the request's session."""
    return StatsRepository(session)


def get_stats_service(
    repository: Annotated[StatsRepository, Depends(get_stats_repository)],
) -> StatsService:
    """Service over the request's repository (the seam tests override)."""
    return StatsService(repository)
```

`backend/app/stats/router.py`:

```python
"""Presentation layer for the stats module (DESIGN §5.1) — the single ``/api/v1/stats`` route."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.stats.dependencies import get_stats_service
from app.stats.schemas import StatsRead
from app.stats.service import StatsService

router = APIRouter()


@router.get(
    "",
    summary="Viewing statistics",
    description=(
        "All-time statistics plus one block per calendar year, from the earliest "
        "dated watch through the current year, **newest year first**. Watches "
        "recorded as 'seen before, date unknown' count in the all-time block only. "
        "An empty library is a normal answer: zeros and no years."
    ),
)
def get_stats(service: Annotated[StatsService, Depends(get_stats_service)]) -> StatsRead:
    return StatsRead.from_stats(service.stats(date.today()))
```

`backend/app/main.py`: add `from app.stats.router import router as stats_router` beside the other router imports, and in `build_api_router()` after the rewatch line:

```python
    api.include_router(stats_router, prefix="/stats", tags=["stats"])
```

- [ ] **Step 4: Run the API test and the OpenAPI contract test**

Run: `uv run pytest tests/test_stats_api.py tests/test_openapi_contract.py -q`
Expected: PASS. If the contract test fails, read its assertion message — it checks that every operation documents summary/description/error responses; add what it names to the `@router.get(...)` decorator (e.g. `responses=error_responses(...)` from `app.core.errors`, as `app/films/router.py` does).

- [ ] **Step 5: Write the repository test (needs Postgres)**

`backend/tests/test_stats_repository.py`:

```python
"""Stats data access against a real Postgres (DESIGN §9). ``db_session`` auto-marks these ``db``."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.films.models import Film, Title
from app.genres.models import FilmGenre, Genre
from app.ratings.models import RatingEntry
from app.ratings.service import EARLIER_WATCH_DATE
from app.stats.repository import StatsRepository


def test_watches_joins_primary_title_and_genres_and_undates_the_sentinel(db_session: Session) -> None:
    film = Film(natural_key="heat|1995|michael mann", release_year=1995, director="Michael Mann", runtime_minutes=170)
    db_session.add(film)
    db_session.flush()
    db_session.add(Title(film_id=film.id, value="Heat", is_primary=True, is_original=True))
    db_session.add(Title(film_id=film.id, value="Heat (alt)", is_primary=False, is_original=False))
    crime, thriller = Genre(name="Crime"), Genre(name="Thriller")
    db_session.add_all([crime, thriller])
    db_session.flush()
    db_session.add_all(
        [
            FilmGenre(film_id=film.id, genre_id=thriller.id, position=1),
            FilmGenre(film_id=film.id, genre_id=crime.id, position=0),
            RatingEntry(film_id=film.id, value=Decimal("4.5"), watch_date=date(2026, 3, 1)),
            RatingEntry(film_id=film.id, value=None, watch_date=EARLIER_WATCH_DATE),
        ]
    )
    db_session.commit()

    watches = sorted(StatsRepository(db_session).watches(), key=lambda w: w.watch_date is None)

    assert [w.watch_date for w in watches] == [date(2026, 3, 1), None]
    assert {w.title for w in watches} == {"Heat"}
    assert watches[0].genres == ("Crime", "Thriller")
    assert watches[0].value == Decimal("4.5")
```

- [ ] **Step 6: Run the full backend gate**

Run (from `backend/`): `make typecheck && make lint && make format-check && make test`
Expected: pyright `0 errors`, Ruff clean, all tests PASS. Without a running Postgres use `make test-offline` and say in the report that the `db` test was not run.

- [ ] **Step 7: Commit**

Via `commit-changes`. Suggested subject: `feat(stats): serve viewing statistics at GET /stats`

---

### Task 3: Stats domain layer (frontend)

**Files:**
- Create: `frontend/src/app/domain/stats/model.ts`, `api.ts`, `mapper.ts`, `facade.ts`, `README.md`
- Test: `frontend/src/app/domain/stats/stats-facade.spec.ts`

**Interfaces:**
- Consumes: `GET ${environment.apiBaseUrl}/stats` (shape from Task 2).
- Produces (`model.ts`):
  ```ts
  NamedCount { name: string; count: number }
  FilmCount { filmId: string; title: string; count: number }
  RatingCount { value: number; count: number }
  Bucket { label: string; count: number }
  StatsBlock { watches; firstWatches; rewatches; filmsReleasedThatYear: number | null; distinctFilms;
    minutesWatched; averageRating: number | null; ratingDistribution; topGenres; topDirectors; topFilms; buckets }
  YearStats extends StatsBlock { year: number }
  Stats { total: StatsBlock; years: readonly YearStats[] }
  ```
  `StatsFacade`: `stats: Signal<Stats | null>`, `isLoading: Signal<boolean>`, `error: Signal<unknown>`, `reload(): void`, `onViewOpened(): void`.

- [ ] **Step 1: Write the failing spec**

`frontend/src/app/domain/stats/stats-facade.spec.ts`:

```ts
/** DTO → domain mapping, month labels, error state, and refetch on reopen. */
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { environment } from '../../../environments/environment';
import type { StatsBlockDto, StatsDto } from './api';
import { StatsFacade } from './facade';

const URL = `${environment.apiBaseUrl}/stats`;

function block(overrides: Partial<StatsBlockDto> = {}): StatsBlockDto {
  return {
    watches: 3,
    first_watches: 1,
    rewatches: 2,
    films_released_that_year: null,
    distinct_films: 1,
    minutes_watched: 510,
    average_rating: 4.5,
    rating_distribution: [{ value: 4.5, count: 3 }],
    top_genres: [{ name: 'Crime', count: 3 }],
    top_directors: [{ name: 'Michael Mann', count: 3 }],
    top_films: [{ film_id: 'f1', title: 'Heat', count: 3 }],
    buckets: [{ label: '2026', count: 3 }],
    ...overrides,
  };
}

const PAYLOAD: StatsDto = {
  total: block(),
  years: [{ year: 2026, ...block({ films_released_that_year: 0, buckets: [{ label: '1', count: 0 }, { label: '3', count: 3 }] }) }],
};

describe('StatsFacade', () => {
  let facade: StatsFacade;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    facade = TestBed.inject(StatsFacade);
    http = TestBed.inject(HttpTestingController);
    TestBed.tick();
  });

  afterEach(() => http.verify());

  it('maps the payload to camelCase domain models', () => {
    http.expectOne(URL).flush(PAYLOAD);
    TestBed.tick();

    const stats = facade.stats();
    expect(stats?.total.firstWatches).toBe(1);
    expect(stats?.total.filmsReleasedThatYear).toBeNull();
    expect(stats?.total.topFilms).toEqual([{ filmId: 'f1', title: 'Heat', count: 3 }]);
    expect(stats?.years[0].year).toBe(2026);
    expect(stats?.years[0].filmsReleasedThatYear).toBe(0);
  });

  it('labels year buckets with month names and leaves all-time buckets as years', () => {
    http.expectOne(URL).flush(PAYLOAD);
    TestBed.tick();

    expect(facade.stats()?.years[0].buckets.map((b) => b.label)).toEqual(['Jan', 'Mar']);
    expect(facade.stats()?.total.buckets.map((b) => b.label)).toEqual(['2026']);
  });

  it('exposes an error and no stats when the request fails', () => {
    http.expectOne(URL).flush('down', { status: 500, statusText: 'Server Error' });
    TestBed.tick();

    expect(facade.stats()).toBeNull();
    expect(facade.error()).toBeTruthy();
  });

  it('refetches when the view is opened again', () => {
    facade.onViewOpened();
    http.expectOne(URL).flush(PAYLOAD);
    TestBed.tick();

    facade.onViewOpened();
    TestBed.tick();
    http.expectOne(URL).flush(PAYLOAD);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `frontend/`): `npm test -- --run src/app/domain/stats`
Expected: FAIL — cannot resolve `./api` / `./facade`.

- [ ] **Step 3: Write model, api, mapper, facade, README**

`frontend/src/app/domain/stats/model.ts`:

```ts
/** Statistics domain models (DESIGN §6.1) — see docs/superpowers/specs/2026-09-25-statistics-design.md. */
export interface NamedCount {
  readonly name: string;
  readonly count: number;
}

export interface FilmCount {
  readonly filmId: string;
  readonly title: string;
  readonly count: number;
}

export interface RatingCount {
  readonly value: number;
  readonly count: number;
}

/** A month (`Jan`…`Dec`) in a year block, a year in the all-time block. */
export interface Bucket {
  readonly label: string;
  readonly count: number;
}

export interface StatsBlock {
  readonly watches: number;
  readonly firstWatches: number;
  readonly rewatches: number;
  /** `null` in the all-time block, which has no single year. */
  readonly filmsReleasedThatYear: number | null;
  readonly distinctFilms: number;
  readonly minutesWatched: number;
  /** `null` when no watch in the block was rated (FR-RAT-12). */
  readonly averageRating: number | null;
  readonly ratingDistribution: readonly RatingCount[];
  readonly topGenres: readonly NamedCount[];
  readonly topDirectors: readonly NamedCount[];
  readonly topFilms: readonly FilmCount[];
  readonly buckets: readonly Bucket[];
}

export interface YearStats extends StatsBlock {
  readonly year: number;
}

export interface Stats {
  readonly total: StatsBlock;
  /** Newest year first, empty years included. */
  readonly years: readonly YearStats[];
}
```

`frontend/src/app/domain/stats/api.ts`:

```ts
/** Stats data access (DESIGN §6.1) — the only place that speaks the wire shape. */
import { httpResource } from '@angular/common/http';
import { Injectable } from '@angular/core';

import { environment } from '../../../environments/environment';

/** Mirrors the backend's `StatsBlockRead`. */
export interface StatsBlockDto {
  readonly watches: number;
  readonly first_watches: number;
  readonly rewatches: number;
  readonly films_released_that_year: number | null;
  readonly distinct_films: number;
  readonly minutes_watched: number;
  readonly average_rating: number | null;
  readonly rating_distribution: readonly { readonly value: number; readonly count: number }[];
  readonly top_genres: readonly { readonly name: string; readonly count: number }[];
  readonly top_directors: readonly { readonly name: string; readonly count: number }[];
  readonly top_films: readonly { readonly film_id: string; readonly title: string; readonly count: number }[];
  /** `"1"`…`"12"` in a year block, `"2025"` in the all-time block. */
  readonly buckets: readonly { readonly label: string; readonly count: number }[];
}

/** Mirrors the backend's `StatsRead`. */
export interface StatsDto {
  readonly total: StatsBlockDto;
  readonly years: readonly (StatsBlockDto & { readonly year: number })[];
}

@Injectable({ providedIn: 'root' })
export class StatsApi {
  /** `GET /stats` — an `httpResource` for its loading/error signals, as `RewatchApi.list`. */
  readonly stats = httpResource<StatsDto>(() => `${environment.apiBaseUrl}/stats`);
}
```

`frontend/src/app/domain/stats/mapper.ts`:

```ts
/** `StatsDto` → `Stats` (DESIGN §6.1). */
import type { StatsBlockDto, StatsDto } from './api';
import type { Stats, StatsBlock } from './model';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function toBlock(dto: StatsBlockDto, bucketLabel: (label: string) => string): StatsBlock {
  return {
    watches: dto.watches,
    firstWatches: dto.first_watches,
    rewatches: dto.rewatches,
    filmsReleasedThatYear: dto.films_released_that_year,
    distinctFilms: dto.distinct_films,
    minutesWatched: dto.minutes_watched,
    averageRating: dto.average_rating,
    ratingDistribution: dto.rating_distribution,
    topGenres: dto.top_genres,
    topDirectors: dto.top_directors,
    topFilms: dto.top_films.map((f) => ({ filmId: f.film_id, title: f.title, count: f.count })),
    buckets: dto.buckets.map((b) => ({ label: bucketLabel(b.label), count: b.count })),
  };
}

export function toStats(dto: StatsDto): Stats {
  return {
    total: toBlock(dto.total, (year) => year),
    // A year block's buckets are months `"1"`…`"12"`.
    years: dto.years.map((y) => ({ year: y.year, ...toBlock(y, (month) => MONTHS[Number(month) - 1]) })),
  };
}
```

`frontend/src/app/domain/stats/facade.ts`:

```ts
/** The stats facade (DESIGN §6.1) — the single API `views/stats/` calls. */
import { Injectable, computed, inject } from '@angular/core';

import { StatsApi } from './api';
import { toStats } from './mapper';
import type { Stats } from './model';

@Injectable({ providedIn: 'root' })
export class StatsFacade {
  private readonly api = inject(StatsApi);

  /** `null` until loaded and on error — `hasValue()` guards `value()`, which throws once the resource has errored. */
  readonly stats = computed<Stats | null>(() => (this.api.stats.hasValue() ? toStats(this.api.stats.value()) : null));
  readonly isLoading = computed(() => this.api.stats.isLoading());
  readonly error = computed(() => this.api.stats.error());

  reload(): void {
    this.api.stats.reload();
  }

  private hasOpened = false;

  /**
   * Refetches on every open after the first, so a watch logged elsewhere shows
   * up — `httpResource` in a root service fetches once, at construction. The
   * first open is that construction-time fetch. Same rule as `RewatchFacade.onViewOpened`.
   */
  onViewOpened(): void {
    if (this.hasOpened) this.api.stats.reload();
    this.hasOpened = true;
  }
}
```

`frontend/src/app/domain/stats/README.md`:

```markdown
# `domain/stats/` — viewing statistics

Data access and mapping for `GET /stats`. Every number is computed by the
backend (`backend/app/stats/algorithm.py`); this layer only renames fields and
turns a year block's month buckets (`"1"`…`"12"`) into `Jan`…`Dec`.
```

- [ ] **Step 4: Run the spec, build and lint**

Run (from `frontend/`): `npm test -- --run src/app/domain/stats && npm run build && npm run lint && npm run format:check`
Expected: 4 tests PASS, build clean, lint clean. If `format:check` fails, run `npm run format` and re-check. If `'refetches when the view is opened again'` sees no second request, add `TestBed.tick()` after the second `onViewOpened()` (already there) and check that `reload()` is called on the resource, not on a copy.

- [ ] **Step 5: Commit**

Via `commit-changes`. Suggested subject: `feat(stats): load viewing statistics in a stats domain facade`

---

### Task 4: Statistics view + navigation (frontend)

**Files:**
- Create: `frontend/src/app/views/stats/stats.ts`, `stats.html`, `stats.scss`, `README.md`
- Modify: `frontend/src/app/core/routes.registry.ts` (append loader + entry)
- Modify: `frontend/src/app/core/route-registry.spec.ts:38` (expected labels)
- Test: `frontend/src/app/views/stats/stats.spec.ts`

**Interfaces:**
- Consumes: `StatsFacade` (`stats`, `isLoading`, `error`, `reload`, `onViewOpened`) and the model types from Task 3.
- Produces: route `stats`, nav label `Statistics`, icon `bar_chart`.

- [ ] **Step 1: Write the failing view spec and update the registry spec**

In `frontend/src/app/core/route-registry.spec.ts` line 38, change the expectation to:

```ts
    expect(navDestinations(ROUTE_REGISTRY).map((item) => item.label)).toEqual(['Rewatch', 'Library', 'Statistics']);
```

`frontend/src/app/views/stats/stats.spec.ts`:

```ts
/** Scope switching and the empty states; the numbers themselves are the backend's. */
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { StatsFacade } from '../../domain/stats/facade';
import type { Stats, StatsBlock } from '../../domain/stats/model';
import { Stats as StatsView } from './stats';

const THIS_YEAR = new Date().getFullYear();

function block(watches: number): StatsBlock {
  return {
    watches,
    firstWatches: watches,
    rewatches: 0,
    filmsReleasedThatYear: null,
    distinctFilms: watches,
    minutesWatched: watches * 120,
    averageRating: watches ? 4 : null,
    ratingDistribution: [],
    topGenres: [],
    topDirectors: [],
    topFilms: watches ? [{ filmId: 'f1', title: 'Heat', count: watches }] : [],
    buckets: [],
  };
}

function render(stats: Stats): HTMLElement {
  TestBed.configureTestingModule({
    imports: [StatsView],
    providers: [
      provideRouter([]),
      {
        provide: StatsFacade,
        useValue: {
          stats: signal(stats),
          isLoading: signal(false),
          error: signal(undefined),
          reload: () => undefined,
          onViewOpened: () => undefined,
        },
      },
    ],
  });
  const fixture = TestBed.createComponent(StatsView);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('Stats view', () => {
  it('preselects the current year', () => {
    const el = render({ total: block(5), years: [{ year: THIS_YEAR, ...block(2) }] });

    expect(el.querySelector('[aria-selected="true"]')?.textContent).toContain(String(THIS_YEAR));
    expect(el.textContent).toContain('Heat');
  });

  it('shows the empty state for a year without watches', () => {
    const el = render({ total: block(5), years: [{ year: THIS_YEAR, ...block(0) }] });

    expect(el.textContent).toContain('No watches this year');
  });

  it('shows all time when there are no years', () => {
    const el = render({ total: block(0), years: [] });

    expect(el.querySelector('[aria-selected="true"]')?.textContent).toContain('All time');
    expect(el.textContent).not.toContain('No watches this year');
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `frontend/`): `npm test -- --run src/app/views/stats src/app/core/route-registry`
Expected: FAIL — `./stats` cannot be resolved; registry spec fails on the missing `Statistics` label.

- [ ] **Step 3: Write the view**

`frontend/src/app/views/stats/stats.ts`:

```ts
/**
 * The Statistics view — all-time and per-year viewing statistics
 * (docs/superpowers/specs/2026-09-25-statistics-design.md). Holds no rules:
 * every number comes from `StatsFacade`; the view only picks the block for
 * the selected scope and scales the bars.
 */
import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, linkedSignal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { StatsFacade } from '../../domain/stats/facade';
import type { StatsBlock } from '../../domain/stats/model';

type Scope = number | 'all';

@Component({
  selector: 'app-stats',
  imports: [DecimalPipe, MatButtonModule, MatCardModule, MatChipsModule, MatProgressBarModule, RouterLink],
  templateUrl: './stats.html',
  styleUrl: './stats.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Stats {
  private readonly facade = inject(StatsFacade);

  protected readonly stats = this.facade.stats;
  protected readonly isLoading = this.facade.isLoading;
  protected readonly error = this.facade.error;

  /** The current year once the data holds it, otherwise all time; the user's pick after that. */
  protected readonly scope = linkedSignal<Scope>(() => {
    const thisYear = new Date().getFullYear();
    return this.stats()?.years.some((y) => y.year === thisYear) ? thisYear : 'all';
  });

  protected readonly block = computed<StatsBlock | null>(() => {
    const stats = this.stats();
    const scope = this.scope();
    if (stats === null) return null;
    return scope === 'all' ? stats.total : (stats.years.find((y) => y.year === scope) ?? stats.total);
  });

  constructor() {
    this.facade.onViewOpened();
  }

  protected select(scope: Scope): void {
    this.scope.set(scope);
  }

  protected reload(): void {
    this.facade.reload();
  }

  /** Bar height in percent of the tallest bar in the same chart. */
  protected percent(count: number, all: readonly { readonly count: number }[]): number {
    return (count / Math.max(1, ...all.map((item) => item.count))) * 100;
  }
}
```

`frontend/src/app/views/stats/stats.html`:

```html
@if (isLoading()) {
  <p class="stats__state" role="status">Counting your watches…</p>
  <mat-progress-bar mode="indeterminate" aria-hidden="true" />
}

@if (error()) {
  <div class="stats__state stats__state--error" role="alert">
    <p>The statistics could not be loaded. Is the backend running?</p>
    <button matButton type="button" (click)="reload()">Try again</button>
  </div>
}

@if (stats(); as stats) {
  <!-- `[selectable]` is off on the selected chip so a second click cannot
       deselect it and leave no scope chosen. -->
  <mat-chip-listbox class="stats__scopes" aria-label="Period">
    <mat-chip-option [selected]="scope() === 'all'" [selectable]="scope() !== 'all'" (selectionChange)="select('all')">
      All time
    </mat-chip-option>
    @for (y of stats.years; track y.year) {
      <mat-chip-option [selected]="scope() === y.year" [selectable]="scope() !== y.year" (selectionChange)="select(y.year)">
        {{ y.year }}
      </mat-chip-option>
    }
  </mat-chip-listbox>

  @if (block(); as b) {
    @if (b.watches === 0 && scope() !== 'all') {
      <p class="stats__state">No watches this year</p>
    } @else {
      <ul class="stats__tiles">
        <li><mat-card><strong>{{ b.watches }}</strong> watches</mat-card></li>
        <li><mat-card><strong>{{ b.firstWatches }}</strong> first watches</mat-card></li>
        <li><mat-card><strong>{{ b.rewatches }}</strong> rewatches</mat-card></li>
        @if (b.filmsReleasedThatYear !== null) {
          <li><mat-card><strong>{{ b.filmsReleasedThatYear }}</strong> released this year</mat-card></li>
        }
        <li><mat-card><strong>{{ b.minutesWatched / 60 | number: '1.0-1' }}</strong> hours</mat-card></li>
        <li><mat-card><strong>{{ b.distinctFilms }}</strong> films</mat-card></li>
      </ul>

      <section>
        <h2>{{ scope() === 'all' ? 'Watches per year' : 'Watches per month' }}</h2>
        <ol class="stats__bars">
          @for (bucket of b.buckets; track bucket.label) {
            <li [attr.aria-label]="bucket.label + ': ' + bucket.count">
              <span class="stats__bar-count" aria-hidden="true">{{ bucket.count || '' }}</span>
              <span class="stats__bar" [style.height.%]="percent(bucket.count, b.buckets)" aria-hidden="true"></span>
              <span class="stats__bar-label" aria-hidden="true">{{ bucket.label }}</span>
            </li>
          }
        </ol>
      </section>

      <section>
        <h2>Ratings</h2>
        <p>Average: {{ b.averageRating === null ? 'no ratings' : (b.averageRating | number: '1.1-2') }}</p>
        <ol class="stats__bars">
          @for (r of b.ratingDistribution; track r.value) {
            <li [attr.aria-label]="r.value + ' stars: ' + r.count">
              <span class="stats__bar-count" aria-hidden="true">{{ r.count || '' }}</span>
              <span class="stats__bar" [style.height.%]="percent(r.count, b.ratingDistribution)" aria-hidden="true"></span>
              <span class="stats__bar-label" aria-hidden="true">{{ r.value }}</span>
            </li>
          }
        </ol>
      </section>

      <div class="stats__tops">
        <section>
          <h2>Top films</h2>
          <ol>
            @for (f of b.topFilms; track f.filmId) {
              <li><a [routerLink]="['/film', f.filmId]">{{ f.title }}</a> · {{ f.count }}</li>
            }
          </ol>
        </section>
        <section>
          <h2>Top directors</h2>
          <ol>
            @for (d of b.topDirectors; track d.name) {
              <li>{{ d.name }} · {{ d.count }}</li>
            }
          </ol>
        </section>
        <section>
          <h2>Top genres</h2>
          <ol>
            @for (g of b.topGenres; track g.name) {
              <li>{{ g.name }} · {{ g.count }}</li>
            }
          </ol>
        </section>
      </div>
    }
  }
}
```

`frontend/src/app/views/stats/stats.scss`:

```scss
:host {
  display: block;
  padding: 16px;
}

.stats__state--error {
  color: var(--mat-sys-error);
}

.stats__scopes {
  display: block;
  margin-block-end: 16px;
}

.stats__tiles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  padding: 0;
  list-style: none;

  mat-card {
    padding: 12px;
  }

  strong {
    display: block;
    font: var(--mat-sys-headline-medium);
    color: var(--mat-sys-primary);
  }
}

.stats__bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  block-size: 160px;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    flex: 1;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
    block-size: 100%;
    min-inline-size: 0;
  }
}

.stats__bar {
  inline-size: 100%;
  min-block-size: 2px;
  border-radius: 4px 4px 0 0;
  background: var(--mat-sys-primary);
}

.stats__bar-count,
.stats__bar-label {
  font: var(--mat-sys-label-small);
  color: var(--mat-sys-on-surface-variant);
}

.stats__tops {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
```

`frontend/src/app/views/stats/README.md`:

```markdown
# `views/stats/`

The Statistics view: all-time and per-year viewing statistics, switched by a
chip row (current year preselected). A primary navigation destination. Holds
no rules — `domain/stats/` delivers every number; the bars are plain CSS.
```

In `frontend/src/app/core/routes.registry.ts`, add after the `filmForm` loader:

```ts
const stats = (): Promise<typeof import('../views/stats/stats').Stats> =>
  import('../views/stats/stats').then((module) => module.Stats);
```

and append to `ROUTE_REGISTRY` directly after the `library` entry (registry order is nav order):

```ts
  { path: 'stats', title: 'Statistics', loadComponent: stats, navIcon: 'bar_chart', navLabel: 'Statistics' },
```

- [ ] **Step 4: Run the frontend gate**

Run (from `frontend/`): `npm test && npm run build && npm run lint && npm run format:check`
Expected: all specs PASS, build clean (no budget error), lint clean including template a11y. If `format:check` fails, run `npm run format` and re-check. If the preselect spec cannot find `[aria-selected="true"]`, check the rendered chip markup in the test and select on what `mat-chip-option` actually renders for a selected option.

- [ ] **Step 5: Look at it in the running app**

Start backend + `npm start`, open `http://localhost:4200/stats` at phone width (≈390px) and desktop width, in light and dark. Check: the chip row wraps, the bars don't overflow horizontally, and the nav shows three destinations.

- [ ] **Step 6: Commit**

Via `commit-changes`. Suggested subject: `feat(stats): add the statistics view as a third navigation destination`
