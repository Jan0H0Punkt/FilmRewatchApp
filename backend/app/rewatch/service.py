"""Business-logic layer for the rewatch module (DESIGN §5.1, §5.8).

Assembles the FR-RW-02 payload, invokes the pure algorithm, and persists the
ordered result. It depends on the repository through
:class:`RewatchRepositoryProtocol`, so it is unit-testable against a fake (§9).

The recompute is driven by reads, not by a timer (OPEN_DECISIONS_V1 "M4 —
Scheduler mechanism"): :meth:`RewatchService.list_suggestions` runs it when the
stored projection was not computed today. The algorithm costs milliseconds over
a personal library, so the projection exists to keep the order stable and the
route cheap, not because the computation is expensive.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol

from app.core.db import utc_now
from app.rewatch.algorithm import DueFilm, RewatchInput, suggest
from app.rewatch.models import RewatchSuggestion


class RewatchRepositoryProtocol(Protocol):
    """The data-access interface the service depends on (§5.1)."""

    def collect_inputs(self) -> list[RewatchInput]: ...

    def last_computed_at(self) -> datetime | None: ...

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None: ...

    def list_all(self) -> Sequence[RewatchSuggestion]: ...

    def commit(self) -> None: ...


class RewatchService:
    """Computes and serves the once-a-day due-list (DESIGN §5.8)."""

    def __init__(self, repository: RewatchRepositoryProtocol) -> None:
        self._repository = repository

    def recompute(self, today: date) -> int:
        """Run the algorithm over the whole library and store its result.

        ``today`` is a parameter rather than read from the clock in here, so the
        boundary cases (a film due exactly today) are testable without freezing
        time. Returns how many films came back due.
        """
        due = suggest(self._repository.collect_inputs(), today)
        self._repository.replace_all(due, utc_now())
        self._repository.commit()
        return len(due)

    def list_suggestions(self, today: date) -> Sequence[RewatchSuggestion]:
        """The due-list, recomputed first if the stored one predates ``today``.

        This is what keeps the §5.8 once-daily cadence without a scheduler: the
        first read of the day pays for the run, every later one is a plain
        select. A run that stored nothing reads back as never-computed
        (:meth:`RewatchRepositoryProtocol.last_computed_at`), so a library with
        nothing due recomputes on every read — cheap, and the alternative is a
        second table to hold one timestamp.

        The stamp is compared in local time, because ``today`` comes from the
        local clock: a UTC comparison would roll the day over at the wrong hour
        for anyone not on UTC. "Local" is the backend process's zone — the
        container sets no ``TZ``, so it is UTC there, and the day turns at
        01:00/02:00 for a viewer in Central Europe.
        """
        last = self._repository.last_computed_at()
        if last is None or last.astimezone().date() != today:
            self.recompute(today)
        return self._repository.list_all()
