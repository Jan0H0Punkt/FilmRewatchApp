"""The pure rewatch algorithm against its FR-RW-03/04 output contract (DESIGN §5.8).

No database and no app fixtures — the module under test imports nothing from
``app``, which is what makes the §3.3 isolation claim checkable.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.rewatch.algorithm import BASE_INTERVAL_DAYS, DueFilm, RewatchInput, suggest

TODAY = date(2026, 9, 14)


def _input(
    *,
    film_id: uuid.UUID | None = None,
    days_since_watch: int = 0,
    delay_days: int = 0,
    average_rating: Decimal | None = Decimal("4.0"),
    watch_count: int = 1,
    is_favorite: bool = False,
) -> RewatchInput:
    return RewatchInput(
        film_id=film_id or uuid.uuid4(),
        average_rating=average_rating,
        watch_count=watch_count,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=is_favorite,
        delay_days=delay_days,
    )


def test_a_film_watched_exactly_one_interval_ago_is_due_today() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [0]


def test_a_film_watched_longer_ago_is_overdue_by_the_difference() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS + 30)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-30]


def test_a_film_not_yet_due_is_omitted_entirely() -> None:
    # FR-RW-03: only films with a value <= 0 are returned.
    assert suggest([_input(days_since_watch=BASE_INTERVAL_DAYS - 1)], TODAY) == []


def test_delay_days_defers_a_film_that_would_otherwise_be_due() -> None:
    assert suggest([_input(days_since_watch=BASE_INTERVAL_DAYS, delay_days=10)], TODAY) == []


def test_delay_days_shortens_how_overdue_a_film_counts_as() -> None:
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS + 30, delay_days=10)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-20]


def test_the_most_overdue_film_comes_first() -> None:
    # FR-RW-04: ascending by days_until_next_rewatch, most negative first.
    inputs = [
        _input(days_since_watch=BASE_INTERVAL_DAYS),
        _input(days_since_watch=BASE_INTERVAL_DAYS + 100),
        _input(days_since_watch=BASE_INTERVAL_DAYS + 10),
    ]
    result = suggest(inputs, TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-100, -10, 0]


def test_films_tied_on_days_are_ordered_deterministically() -> None:
    # Two runs over the same data must not reshuffle the view (FR-RW-04).
    first, second = uuid.UUID(int=2), uuid.UUID(int=1)
    inputs = [
        _input(film_id=first, days_since_watch=BASE_INTERVAL_DAYS + 5),
        _input(film_id=second, days_since_watch=BASE_INTERVAL_DAYS + 5),
    ]
    assert suggest(inputs, TODAY) == suggest(list(reversed(inputs)), TODAY)
    assert [item.film_id for item in suggest(inputs, TODAY)] == [second, first]


def test_an_unrated_film_still_gets_a_verdict() -> None:
    # average_rating is null when no watch was rated (FR-RAT-11/12); the
    # algorithm must have a defined behaviour for it, not crash.
    result = suggest([_input(days_since_watch=BASE_INTERVAL_DAYS, average_rating=None)], TODAY)
    assert result == [DueFilm(film_id=result[0].film_id, days_until_next_rewatch=0)]


def test_an_empty_library_yields_an_empty_list() -> None:
    assert suggest([], TODAY) == []
