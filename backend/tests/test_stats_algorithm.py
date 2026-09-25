"""The pure stats algorithm against the spec's definitions (docs/superpowers/specs/2026-09-25-statistics-design.md).

No database and no app fixtures — the module under test imports nothing from ``app``.
"""

import uuid
from datetime import date
from decimal import Decimal

from app.stats.algorithm import Bucket, TopFilm, TopName, Watch, compute

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
    stats = compute(
        [_watch(watch_date=date(2025, 5, 1)), _watch(watch_date=date(2026, 2, 1))], TODAY
    )

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


def test_an_undated_watch_makes_every_dated_year_a_rewatch() -> None:
    # The undated entry says the film was seen before, so both its dated
    # watches — in different years — are rewatches, not first watches.
    stats = compute(
        [
            _watch(watch_date=None, value=None),
            _watch(watch_date=date(2024, 6, 1)),
            _watch(watch_date=date(2025, 6, 1)),
        ],
        TODAY,
    )

    [y2026, y2025, y2024] = stats.years
    assert (y2026.block.first_watches, y2026.block.rewatches) == (0, 0)
    assert (y2025.block.first_watches, y2025.block.rewatches) == (0, 1)
    assert (y2024.block.first_watches, y2024.block.rewatches) == (0, 1)
    assert (stats.total.first_watches, stats.total.rewatches) == (0, 3)


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
    assert [r.value for r in block.rating_distribution] == [
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.5,
        4.0,
        4.5,
        5.0,
    ]


def test_top_lists_rank_by_score_and_break_ties_by_average_then_name() -> None:
    watches = [
        _watch(),
        _watch(),
        _watch(ALIEN, title="Alien", director="Ridley Scott", genres=("Horror", "Sci-Fi")),
    ]

    block = compute(watches, TODAY).total
    assert block.top_films == [
        TopFilm(HEAT, "Heat", 2, 4.0, 8.0),
        TopFilm(ALIEN, "Alien", 1, 4.0, 4.0),
    ]
    assert block.top_directors == [
        TopName("Michael Mann", 2, 4.0, 8.0),
        TopName("Ridley Scott", 1, 4.0, 4.0),
    ]
    assert block.top_genres == [
        TopName("Crime", 2, 4.0, 8.0),
        TopName("Horror", 1, 4.0, 4.0),
        TopName("Sci-Fi", 1, 4.0, 4.0),
    ]


def test_top_films_score_multiplies_watches_by_average_rating() -> None:
    watches = [_watch(value=Decimal("4.0")), _watch(value=Decimal("5.0")), _watch(value=None)]

    [film] = compute(watches, TODAY).total.top_films
    assert (film.watches, film.average_rating, film.score) == (3, 4.5, 13.5)


def test_a_film_with_only_unrated_watches_is_excluded_from_top_films_but_still_counted() -> None:
    watches = [_watch(value=None), _watch(value=None)]

    block = compute(watches, TODAY).total
    assert block.top_films == []
    assert block.watches == 2
    assert block.distinct_films == 1


def test_unrated_watches_count_toward_watches_but_not_average_rating() -> None:
    watches = [_watch(value=Decimal("5.0")), _watch(value=None), _watch(value=None)]

    [film] = compute(watches, TODAY).total.top_films
    assert (film.watches, film.average_rating) == (3, 5.0)


def test_top_films_tie_on_score_breaks_by_higher_average() -> None:
    zebra, alien = uuid.uuid4(), uuid.uuid4()
    watches = [
        _watch(zebra, title="Zebra", value=Decimal("4.0")),
        _watch(zebra, title="Zebra", value=Decimal("4.0")),
        _watch(alien, title="Alien", value=Decimal("2.0")),
        _watch(alien, title="Alien", value=Decimal("2.0")),
        _watch(alien, title="Alien", value=Decimal("2.0")),
        _watch(alien, title="Alien", value=Decimal("2.0")),
    ]

    top = compute(watches, TODAY).total.top_films
    assert [f.title for f in top] == ["Zebra", "Alien"]
    assert top[0].score == top[1].score == 8.0


def test_top_directors_use_the_same_score_rule_as_top_films() -> None:
    watches = [_watch(value=Decimal("4.0")), _watch(value=Decimal("5.0")), _watch(value=None)]

    [director] = compute(watches, TODAY).total.top_directors
    assert (director.name, director.watches, director.average_rating, director.score) == (
        "Michael Mann",
        3,
        4.5,
        13.5,
    )


def test_a_director_with_only_unrated_watches_is_excluded_from_top_directors() -> None:
    watches = [_watch(value=None), _watch(ALIEN, director="Ridley Scott", value=None)]

    assert compute(watches, TODAY).total.top_directors == []


def test_top_genres_use_the_same_score_rule_as_top_films() -> None:
    watches = [
        _watch(genres=("Crime", "Thriller"), value=Decimal("4.0")),
        _watch(genres=("Crime",), value=Decimal("2.0")),
    ]

    genres = {g.name: g for g in compute(watches, TODAY).total.top_genres}
    assert (genres["Crime"].watches, genres["Crime"].average_rating, genres["Crime"].score) == (
        2,
        3.0,
        6.0,
    )
    assert (
        genres["Thriller"].watches,
        genres["Thriller"].average_rating,
        genres["Thriller"].score,
    ) == (1, 4.0, 4.0)


def test_a_genre_with_only_unrated_watches_is_excluded_from_top_genres() -> None:
    watches = [_watch(genres=("Silent",), value=None)]

    assert compute(watches, TODAY).total.top_genres == []


def test_top_films_are_scoped_to_the_block_year() -> None:
    # Rated high in 2024, only unrated in 2025 — absent from 2025's top films
    # even though the film has an all-time score from 2024.
    watches = [
        _watch(watch_date=date(2024, 3, 1), value=Decimal("5.0")),
        _watch(watch_date=date(2025, 3, 1), value=None),
    ]

    stats = compute(watches, TODAY)
    year_2025 = next(y for y in stats.years if y.year == 2025).block
    year_2024 = next(y for y in stats.years if y.year == 2024).block
    assert year_2025.top_films == []
    assert year_2024.top_films == [TopFilm(HEAT, "Heat", 1, 5.0, 5.0)]


def test_top_lists_hold_at_most_five() -> None:
    watches = [_watch(uuid.uuid4(), title=f"Film {i}") for i in range(7)]

    assert len(compute(watches, TODAY).total.top_films) == 5


def test_year_buckets_are_months_and_total_buckets_are_years() -> None:
    watches = [
        _watch(watch_date=date(2025, 1, 10)),
        _watch(watch_date=date(2026, 3, 1)),
        _watch(watch_date=date(2026, 3, 2)),
    ]

    stats = compute(watches, TODAY)
    assert stats.total.buckets == [Bucket("2025", 1), Bucket("2026", 2)]
    months = stats.years[0].block.buckets
    assert [b.label for b in months] == [str(m) for m in range(1, 13)]
    assert months[2] == Bucket("3", 2)
