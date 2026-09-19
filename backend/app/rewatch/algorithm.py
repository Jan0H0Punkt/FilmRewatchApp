"""The pure rewatch scoring module (DESIGN §5.8, §3.3, FR-RW-01..04).

Imports nothing from ``app``: no ORM, no HTTP, no session. That isolation is the
point (FR-EXT-09) — replacing the scoring logic means replacing :func:`suggest`'s
body and nothing else, and a sibling algorithm selected by config (FR-EXT-10)
would live beside this file implementing the same signature.

The dataclasses below are the FR-RW-02 input row and the FR-RW-03 output row,
field for field. The names differ from the requirement tables in one place only:
the output is :class:`DueFilm`, because ``RewatchSuggestion`` is taken by the ORM
row in ``models.py`` that stores it.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

# The unit the rating-derived floor is counted in (OPEN_DECISIONS_V1 "M4 —
# Rewatch engine"). No leap-year handling: a floor measured in whole years is
# already a judgement call, and a day either way cannot matter to it.
DAYS_PER_YEAR = 365

# Ratings run 0.5..5.0 in half steps (``ratings.schemas``), while the scoring
# below is defined over 1..10 — doubling maps one onto the other exactly, with
# no half star lost to rounding.
RATING_SCALE_FACTOR = 2

# Where an unrated film sits on that 1..10 scale. A null average means no watch
# was rated (FR-RAT-11/12); scoring it below the lowest real rating — 0.5 stars
# scales to 1 — makes an unrated film wait longer than any rated one.
UNRATED_SCALED_RATING = 0


@dataclass(frozen=True)
class RewatchInput:
    """One film's algorithm input — the FR-RW-02 table, field for field."""

    film_id: UUID
    # ``None`` when no watch of the film was rated (FR-RAT-11/12), which is
    # distinct from a rating of zero — that cannot exist.
    average_rating: Decimal | None
    watch_count: int
    last_watched_date: date
    is_favorite: bool
    delay_days: int
    runtime_minutes: int


@dataclass(frozen=True)
class DueFilm:
    """One entry of the algorithm's output — the FR-RW-03 table.

    ``days_until_next_rewatch`` is always ``<= 0``: ``0`` is due today, a
    negative value is overdue by that many days.
    """

    film_id: UUID
    days_until_next_rewatch: int


def interval_days(item: RewatchInput) -> int:
    """How long after its last watch a film becomes due again.

    The rating drives all three terms. It sets the floor outright — one year per
    full star counted down from six, so five stars floor at one year and one star
    at five — and on top of that a lower average multiplies the runtime into a
    wider step *and* adds steps, so the spacing grows quadratically as the
    average falls. Each prior watch adds one step.

    Runtime is a multiplier rather than an addend, so it gates the spacing
    entirely: a film with no recorded runtime scores its floor and nothing more,
    however badly rated.

    Being a favourite halves the finished interval, base included, so a
    favourite floors at half the years its rating earned — a five-star favourite
    can come due in six months, the one place nothing holds it to a year.

    The result is deliberately unbounded above. A ceiling would collapse the
    bottom of the rating scale onto one value — every film at or below it due on
    the same day — and the growth is self-limiting anyway, because the step a
    watch adds only compounds for a film watched often enough to earn it.
    """
    scaled_rating = (
        UNRATED_SCALED_RATING
        if item.average_rating is None
        else round(item.average_rating * RATING_SCALE_FACTOR)
    )
    reverse_rating = max(10 - scaled_rating, 1)

    # Halving the 1..10 scale back to stars rounds a half step up to the full
    # star above it, so 4.5 floors where 5.0 does. An unrated film scales to 0
    # and so floors at six years, one past the worst rated film.
    base_days = (6 - (scaled_rating + 1) // 2) * DAYS_PER_YEAR

    step_count = item.watch_count + reverse_rating
    step_days = reverse_rating * item.runtime_minutes
    spacing = step_count * step_days

    total = base_days + spacing
    return math.ceil(total / 2) if item.is_favorite else total


def suggest(inputs: Sequence[RewatchInput], today: date) -> list[DueFilm]:
    """Return the currently-due films, most overdue first (FR-RW-03/04).

    Films that are not yet due are omitted rather than returned with a positive
    value. Ties are broken by film id so two runs over unchanged data produce
    the same order and the view does not reshuffle underneath the user.
    """
    due: list[DueFilm] = []
    for item in inputs:
        due_date = item.last_watched_date + timedelta(days=interval_days(item) + item.delay_days)
        days_until = (due_date - today).days
        if days_until <= 0:
            due.append(DueFilm(film_id=item.film_id, days_until_next_rewatch=days_until))
    due.sort(key=lambda item: (item.days_until_next_rewatch, item.film_id.bytes))
    return due
