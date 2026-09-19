"""The pure rewatch algorithm against its FR-RW-03/04 output contract (DESIGN §5.8).

No database and no app fixtures — the module under test imports nothing from
``app``, which is what makes the §3.3 isolation claim checkable.

:func:`interval_days` is exercised directly: going through :func:`suggest`
would only reveal the interval by bisecting on which films come back, and the
day counts below are the whole point of the scoring.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.rewatch.algorithm import (
    DAYS_PER_YEAR,
    RewatchInput,
    interval_days,
    suggest,
)

TODAY = date(2026, 9, 14)

# What the defaults below score: five stars, so a one-year floor (reverse rating
# 1) plus two steps — one for the rating, one for the single prior watch — of
# 10 + 120 days.
REFERENCE_INTERVAL_DAYS = 1 * DAYS_PER_YEAR + 260


def _input(
    *,
    film_id: uuid.UUID | None = None,
    days_since_watch: int = 0,
    delay_days: int = 0,
    average_rating: Decimal | None = Decimal("5.0"),
    watch_count: int = 1,
    is_favorite: bool = False,
    runtime_minutes: int = 120,
) -> RewatchInput:
    return RewatchInput(
        film_id=film_id or uuid.uuid4(),
        average_rating=average_rating,
        watch_count=watch_count,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=is_favorite,
        delay_days=delay_days,
        runtime_minutes=runtime_minutes,
    )


def test_the_reference_film_scores_the_documented_interval() -> None:
    assert interval_days(_input()) == REFERENCE_INTERVAL_DAYS


def test_each_full_star_is_worth_a_year_of_floor() -> None:
    # Counted down from six: five stars floor at one year, one star at five.
    # Stripped of every other input — never rewatched, no runtime — what is left
    # on top of the floor is 10 * reverse_rating ** 2, which is why a low rating
    # clears its own floor by more than a year.
    for rating, years, spacing in (
        (Decimal("5.0"), 1, 10),
        (Decimal("4.0"), 2, 40),
        (Decimal("3.0"), 3, 160),
        (Decimal("2.0"), 4, 360),
        (Decimal("1.0"), 5, 640),
    ):
        bare = _input(average_rating=rating, watch_count=0, runtime_minutes=0)
        assert interval_days(bare) == years * DAYS_PER_YEAR + spacing


def test_a_half_step_floors_where_the_full_star_above_it_does() -> None:
    # 4.5 counts as 5 for the floor. It also shares reverse_rating with 5.0,
    # which max(10 - scaled, 1) pins at 1 — so at the top of the scale a half
    # star makes no difference to the interval at all.
    assert interval_days(_input(average_rating=Decimal("4.5"))) == interval_days(
        _input(average_rating=Decimal("5.0"))
    )


def test_a_lower_rating_pushes_a_film_quadratically_further_out() -> None:
    # Half the rating is four times the spacing: reverse rating 5 both widens
    # each step (50 + 120) and raises the step count (1 watch + 5). 2.5 rounds
    # up to 3 stars, so it floors at three years.
    assert interval_days(_input(average_rating=Decimal("2.5"))) == 3 * DAYS_PER_YEAR + 1020


def test_the_worst_rating_scores_reverse_rating_nine() -> None:
    # 0.5 stars scales to 1, the lowest a real rating reaches, leaving nine
    # steps of 90 + 30 days on top of the one-star floor it rounds up to.
    assert (
        interval_days(_input(average_rating=Decimal("0.5"), runtime_minutes=30))
        == 5 * DAYS_PER_YEAR + 10 * 120
    )


def test_half_stars_survive_the_scale_conversion() -> None:
    # 4.5 and 4.0 must not collapse onto the same reverse rating.
    assert interval_days(_input(average_rating=Decimal("4.5"))) != interval_days(
        _input(average_rating=Decimal("4.0"))
    )


def test_an_unrated_film_waits_longer_than_the_worst_rated_one() -> None:
    # A null average (FR-RAT-11/12) scores past the bottom of the 1..10 scale,
    # so it outlasts every rated film — at any runtime, nothing clamps the two
    # onto one value.
    unrated = interval_days(_input(average_rating=None))
    assert unrated > interval_days(_input(average_rating=Decimal("0.5")))
    assert unrated > interval_days(_input(average_rating=Decimal("2.5")))


def test_every_prior_watch_adds_one_step() -> None:
    assert interval_days(_input(watch_count=3)) == 1 * DAYS_PER_YEAR + 4 * 130


def test_a_longer_runtime_widens_every_step() -> None:
    assert interval_days(_input(runtime_minutes=180)) == 1 * DAYS_PER_YEAR + 2 * 190


def test_a_favourite_halves_the_whole_interval() -> None:
    # The floor is halved along with the spacing, and an odd total rounds up
    # rather than down into a shorter wait than the scoring asked for — the
    # reference film scores 625, which halves to 312.5.
    assert interval_days(_input(is_favorite=True)) == (REFERENCE_INTERVAL_DAYS + 1) // 2


def test_a_favourite_is_the_one_case_that_drops_below_its_rating_floor() -> None:
    # Halving the finished interval halves the floor with it, so a five-star
    # favourite can fall inside the year its rating bought. Deliberate: the
    # halving is the whole point of the flag (OPEN_DECISIONS_V1 "M4").
    best_favourite = _input(
        average_rating=Decimal("5.0"), watch_count=0, is_favorite=True, runtime_minutes=0
    )
    assert interval_days(best_favourite) < DAYS_PER_YEAR


def test_the_interval_has_no_upper_bound() -> None:
    # Nothing clamps the scoring, so a film the user keeps disliking keeps
    # moving further out instead of piling up on a shared ceiling date.
    intervals = [
        interval_days(_input(average_rating=Decimal("0.5"), runtime_minutes=180, watch_count=n))
        for n in (1, 10, 100)
    ]
    assert intervals == [
        5 * DAYS_PER_YEAR + 2700,
        5 * DAYS_PER_YEAR + 5130,
        5 * DAYS_PER_YEAR + 29430,
    ]


def test_a_film_watched_exactly_one_interval_ago_is_due_today() -> None:
    result = suggest([_input(days_since_watch=REFERENCE_INTERVAL_DAYS)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [0]


def test_a_film_watched_longer_ago_is_overdue_by_the_difference() -> None:
    result = suggest([_input(days_since_watch=REFERENCE_INTERVAL_DAYS + 30)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-30]


def test_a_film_not_yet_due_is_omitted_entirely() -> None:
    # FR-RW-03: only films with a value <= 0 are returned.
    assert suggest([_input(days_since_watch=REFERENCE_INTERVAL_DAYS - 1)], TODAY) == []


def test_delay_days_defers_a_film_that_would_otherwise_be_due() -> None:
    assert suggest([_input(days_since_watch=REFERENCE_INTERVAL_DAYS, delay_days=10)], TODAY) == []


def test_delay_days_shortens_how_overdue_a_film_counts_as() -> None:
    result = suggest([_input(days_since_watch=REFERENCE_INTERVAL_DAYS + 30, delay_days=10)], TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-20]


def test_delay_days_still_defers_a_film_with_a_long_scored_interval() -> None:
    # A deferral applies on top of the scoring however large that already is.
    scored = _input(average_rating=Decimal("0.5"), watch_count=100, runtime_minutes=180)
    due_today = _input(
        average_rating=Decimal("0.5"),
        watch_count=100,
        runtime_minutes=180,
        days_since_watch=interval_days(scored),
        delay_days=10,
    )
    assert suggest([due_today], TODAY) == []


def test_the_most_overdue_film_comes_first() -> None:
    # FR-RW-04: ascending by days_until_next_rewatch, most negative first.
    inputs = [
        _input(days_since_watch=REFERENCE_INTERVAL_DAYS),
        _input(days_since_watch=REFERENCE_INTERVAL_DAYS + 100),
        _input(days_since_watch=REFERENCE_INTERVAL_DAYS + 10),
    ]
    result = suggest(inputs, TODAY)
    assert [item.days_until_next_rewatch for item in result] == [-100, -10, 0]


def test_films_tied_on_days_are_ordered_deterministically() -> None:
    # Two runs over the same data must not reshuffle the view (FR-RW-04).
    first, second = uuid.UUID(int=2), uuid.UUID(int=1)
    inputs = [
        _input(film_id=first, days_since_watch=REFERENCE_INTERVAL_DAYS + 5),
        _input(film_id=second, days_since_watch=REFERENCE_INTERVAL_DAYS + 5),
    ]
    assert suggest(inputs, TODAY) == suggest(list(reversed(inputs)), TODAY)
    assert [item.film_id for item in suggest(inputs, TODAY)] == [second, first]


def test_scoring_the_same_film_twice_gives_the_same_answer() -> None:
    # The scoring is a pure function of the input row: no clock, no randomness,
    # so a film cannot be due one run and not the next.
    item = _input(days_since_watch=REFERENCE_INTERVAL_DAYS)
    assert suggest([item], TODAY) == suggest([item], TODAY)


def test_an_empty_library_yields_an_empty_list() -> None:
    assert suggest([], TODAY) == []
