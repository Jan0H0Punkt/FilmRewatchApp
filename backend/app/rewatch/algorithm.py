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

# ponytail: placeholder scoring — every film is simply due one year after its
# last watch, deferred by its delay_days. `average_rating`, `watch_count` and
# `is_favorite` are accepted and ignored. The repo owner supplies the real
# formula later; the upgrade path is this module's body, and the signature
# below must not change when it arrives (OPEN_DECISIONS_V1 "M4 — Rewatch
# engine / algorithm internals").
BASE_INTERVAL_DAYS = 365


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


@dataclass(frozen=True)
class DueFilm:
    """One entry of the algorithm's output — the FR-RW-03 table.

    ``days_until_next_rewatch`` is always ``<= 0``: ``0`` is due today, a
    negative value is overdue by that many days.
    """

    film_id: UUID
    days_until_next_rewatch: int


def suggest(inputs: Sequence[RewatchInput], today: date) -> list[DueFilm]:
    """Return the currently-due films, most overdue first (FR-RW-03/04).

    Films that are not yet due are omitted rather than returned with a positive
    value. Ties are broken by film id so two runs over unchanged data produce
    the same order and the view does not reshuffle underneath the user.
    """
    due = [
        DueFilm(film_id=item.film_id, days_until_next_rewatch=days_until)
        for item in inputs
        if (
            days_until := (
                item.last_watched_date
                + timedelta(days=BASE_INTERVAL_DAYS + item.delay_days)
                - today
            ).days
        )
        <= 0
    ]
    due.sort(key=lambda item: (item.days_until_next_rewatch, item.film_id.bytes))
    return due
