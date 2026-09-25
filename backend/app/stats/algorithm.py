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
class TopName:
    name: str
    watches: int
    average_rating: float
    score: float


@dataclass(frozen=True, slots=True)
class TopFilm:
    film_id: UUID
    title: str
    watches: int
    average_rating: float
    score: float


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
    # All three rank by score = watches x average_rating of the RATED watches
    # only (a genre/director scores once per watch of a film carrying it); an
    # unrated watch is never imputed a value, so a name/film with no rated
    # watch in the block has no score and is absent from the list.
    top_genres: list[TopName]
    top_directors: list[TopName]
    top_films: list[TopFilm]
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
        top_genres=[
            TopName(name, watch_count, average, score)
            for name, watch_count, average, score in _top_scored(
                ((g, w) for w in watches for g in w.genres), str
            )
        ],
        top_directors=[
            TopName(name, watch_count, average, score)
            for name, watch_count, average, score in _top_scored(
                ((w.director, w) for w in watches), str
            )
        ],
        top_films=[
            TopFilm(film_id, titles[film_id], watch_count, average, score)
            for film_id, watch_count, average, score in _top_scored(
                ((w.film_id, w) for w in watches), titles.__getitem__
            )
        ],
        buckets=buckets,
    )


def _top_scored[K: Hashable](
    keyed_watches: Iterable[tuple[K, Watch]], name: Callable[[K], str]
) -> list[tuple[K, int, float, float]]:
    """Ranks each key by ``score = watches x average_rating`` of its RATED watches only.

    ``watches`` counts every occurrence of the key (unrated included); an
    unrated watch is never imputed a value, so a key with no rated watch here
    scores nothing and is dropped. Ties break by higher average, then by
    ``name``. Shared by top films, directors, and genres — a genre key
    appears once per watch of each film carrying it.
    """
    counts: Counter[K] = Counter()
    rated_values: dict[K, list[float]] = {}
    for key, watch in keyed_watches:
        counts[key] += 1
        if watch.value is not None:
            rated_values.setdefault(key, []).append(float(watch.value))

    ranked: list[tuple[K, int, float, float]] = []
    for key, values in rated_values.items():
        average = sum(values) / len(values)
        watch_count = counts[key]
        ranked.append((key, watch_count, average, watch_count * average))

    ranked.sort(key=lambda r: (-r[3], -r[2], name(r[0])))
    return [
        (key, watch_count, round(average, 2), round(score, 2))
        for key, watch_count, average, score in ranked[:TOP_N]
    ]
