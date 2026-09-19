"""Project the rewatch/new-film split for this year and the years after it.

Run from ``backend/``::

    uv run python -m simulate                 # measured rate, 10 years ahead
    uv run python -m simulate --rate 180      # override the watch rate
    uv run python -m simulate --years 20 --seeds 20

The scoring is imported, never restated: the projection calls the same
:func:`~app.rewatch.algorithm.suggest` the scheduler does, over the same rows
:meth:`~app.rewatch.repository.RewatchRepository.collect_inputs` assembles. Edit
``algorithm.py`` and the next run reflects it.

The modelled viewer is *rewatch-first*: every watch goes to the most overdue
film, and only a day with nothing due is spent on something new. That makes the
new-film column the interesting one — it counts the days the library ran dry.
"""

import argparse
import random
import statistics
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.db import session_scope
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import RewatchInput, suggest
from app.rewatch.repository import RewatchRepository

# Weighting the watch history so the last year counts double the one before it.
# Long enough to survive a quiet fortnight, short enough that 2021 does not
# outvote 2026.
HALF_LIFE_DAYS = 365

# Which film a dry day pulls in is random, so the per-year split is averaged
# over this many runs. The first dry day is identical in every run — nothing
# random happens before the backlog first empties.
DEFAULT_SEEDS = 10


def measure_watch_rate(watch_dates: Sequence[date], today: date) -> float:
    """Watches per day, with recent watches carrying the most weight.

    Both the watches and the days they could have fallen on are decayed, so the
    result is a rate rather than a decayed count: a gap in the history lowers it
    exactly as much as the missing watches do, and no more.
    """
    span = (today - min(watch_dates)).days + 1
    watched = sum(0.5 ** ((today - day).days / HALF_LIFE_DAYS) for day in watch_dates)
    available = sum(0.5 ** (age / HALF_LIFE_DAYS) for age in range(span))
    return watched / available


def _rewatched(film: RewatchInput, day: date) -> RewatchInput:
    """The same film one watch later — the step that lengthens its next wait."""
    return RewatchInput(
        film_id=film.film_id,
        average_rating=film.average_rating,
        watch_count=film.watch_count + 1,
        last_watched_date=day,
        is_favorite=film.is_favorite,
        delay_days=film.delay_days,
        runtime_minutes=film.runtime_minutes,
    )


def _newly_watched(profile: RewatchInput, day: date) -> RewatchInput:
    """A first watch of something new, shaped like a film already in the library.

    Rating and runtime are borrowed from an existing row rather than invented:
    what a future film scores is unknowable, and the library is the only
    evidence of what this viewer tends to watch and give.
    """
    return RewatchInput(
        film_id=uuid4(),
        average_rating=profile.average_rating,
        watch_count=1,
        last_watched_date=day,
        is_favorite=profile.is_favorite,
        delay_days=0,
        runtime_minutes=profile.runtime_minutes,
    )


def project(
    library: Sequence[RewatchInput], rate_per_day: float, today: date, years: int, seed: int
) -> tuple[dict[int, int], dict[int, int]]:
    """One run. Returns rewatches and new watches, both keyed by calendar year.

    ``budget`` turns a fractional daily rate into whole watches: it accrues every
    day and spends down whenever it clears 1.0, which spreads e.g. 0.55 watches a
    day into one watch every second day without ever losing a fraction.
    """
    state = {film.film_id: film for film in library}
    rng = random.Random(seed)
    rewatches: dict[int, int] = defaultdict(int)
    new_watches: dict[int, int] = defaultdict(int)
    budget = 0.0

    # Run to the last day of the final year rather than a day count, so the
    # closing year is whole however many leap years the span happens to hold.
    day = today
    final_day = date(today.year + years, 12, 31)
    while day <= final_day:
        due = suggest(list(state.values()), day)
        budget += rate_per_day
        while budget >= 1.0:
            if due:
                film = state[due[0].film_id]
                state[film.film_id] = _rewatched(film, day)
                # Drop it from today's list so a second watch today picks another.
                due = due[1:]
                rewatches[day.year] += 1
            else:
                fresh = _newly_watched(rng.choice(library), day)
                state[fresh.film_id] = fresh
                new_watches[day.year] += 1
            budget -= 1.0
        day += timedelta(days=1)

    return rewatches, new_watches


def _report(
    library: Sequence[RewatchInput], rate_per_day: float, today: date, years: int, seeds: int
) -> None:
    runs = [project(library, rate_per_day, today, years, seed) for seed in range(seeds)]

    print(f"\n{'year':<8}{'rewatches':>11}{'':>6}{'new films':>11}{'':>6}{'total':>8}")
    print("-" * 50)
    for year in range(today.year, today.year + years + 1):
        rewatches = statistics.mean(run[0].get(year, 0) for run in runs)
        new_watches = statistics.mean(run[1].get(year, 0) for run in runs)
        total = rewatches + new_watches
        if total < 1:
            continue
        label = f"{year}*" if year == today.year else str(year)
        print(
            f"{label:<8}{rewatches:>11.0f}{rewatches / total:>6.0%}"
            f"{new_watches:>11.0f}{new_watches / total:>6.0%}{total:>8.0f}"
        )
    print(f"\n* {today.year} covers {today:%-d %b} to 31 Dec only.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=10, help="years after this one (default 10)")
    parser.add_argument(
        "--rate", type=float, default=None, help="watches per year; default measured"
    )
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS, help="runs to average over")
    args = parser.parse_args()
    years: int = args.years
    seeds: int = args.seeds
    override: float | None = args.rate

    today = date.today()
    with session_scope() as session:
        library = RewatchRepository(session).collect_inputs()
        watch_dates = list(session.scalars(select(RatingEntry.watch_date)))

    if not library:
        print("No films with a watch to project from.")
        return

    measured = measure_watch_rate(watch_dates, today) * 365
    rate_per_year = measured if override is None else override

    print(f"Library:    {len(library)} films, {len(suggest(library, today))} due on {today}")
    print(
        f"Watch rate: {rate_per_year:.0f}/year"
        + (
            f" (measured over {len(watch_dates)} watches since {min(watch_dates)},"
            f" {HALF_LIFE_DAYS}-day half-life)"
            if override is None
            else f" (override; measured is {measured:.0f})"
        )
    )
    print("Policy:     rewatch whenever anything is due, otherwise watch something new")
    print(f"Averaged over {seeds} runs.")
    _report(library, rate_per_year / 365, today, years, seeds)


if __name__ == "__main__":
    main()
