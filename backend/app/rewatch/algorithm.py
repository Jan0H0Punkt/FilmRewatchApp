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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

# The floor every film shares: nothing is suggested within a year of its last
# watch, however loved (OPEN_DECISIONS_V1 "M4 — Rewatch engine").
BASE_INTERVAL_DAYS = 365

# ponytail: a flat ceiling rather than a taper. Without it the quadratic term in
# :func:`interval_days` sends a long, badly-rated, often-watched film past 20
# years, which is indistinguishable from "never" but harder to reason about.
MAX_INTERVAL_DAYS = BASE_INTERVAL_DAYS * 5

# Ratings run 0.5..5.0 in half steps (``ratings.schemas``), while the scoring
# below is defined over 1..10 — doubling maps one onto the other exactly, with
# no half star lost to rounding.
RATING_SCALE_FACTOR = 2

# Where an unrated film sits on that 1..10 scale. A null average means no watch
# was rated (FR-RAT-11/12); scoring it below the lowest real rating — 0.5 stars
# scales to 1 — makes an unrated film wait longer than any rated one. The two
# only differ on short runtimes: at feature length both already clamp to
# :data:`MAX_INTERVAL_DAYS`.
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

    The rating dominates, because it drives both factors at once: a lower
    average widens each step (``10 * reverse_rating``) *and* adds steps, so the
    interval grows quadratically as a film's average falls. Each prior watch
    adds one step on top, and the runtime widens every step — a three-hour film
    is a bigger ask than a ninety-minute one at the same rating.

    Being a favourite halves the variable part but not ``BASE_INTERVAL_DAYS``,
    so the floor holds for every film.
    """
    scaled_rating = (
        UNRATED_SCALED_RATING
        if item.average_rating is None
        else round(item.average_rating * RATING_SCALE_FACTOR)
    )
    reverse_rating = max(10 - scaled_rating, 1)

    step_count = item.watch_count + reverse_rating
    step_days = 10 * reverse_rating + item.runtime_minutes
    spacing = step_count * step_days
    if item.is_favorite:
        spacing //= 2

    return min(BASE_INTERVAL_DAYS + spacing, MAX_INTERVAL_DAYS)


def suggest(inputs: Sequence[RewatchInput], today: date) -> list[DueFilm]:
    """Return the currently-due films, most overdue first (FR-RW-03/04).

    ``delay_days`` is added outside the :data:`MAX_INTERVAL_DAYS` clamp: the
    ceiling bounds what the scoring may invent, while a deferral is the user's
    own explicit instruction and must always push the film further out.

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
