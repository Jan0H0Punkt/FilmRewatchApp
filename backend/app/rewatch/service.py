"""Business-logic layer for the rewatch module (DESIGN §5.1, §5.8).

Assembles the FR-RW-02 payload, invokes the pure algorithm, and persists the
ordered result. It depends on the repository through
:class:`RewatchRepositoryProtocol`, so it is unit-testable against a fake (§9),
and it is deliberately unaware of what triggered it — ``scheduler.py`` calls
:meth:`RewatchService.recompute` on a timer, and a test calls it directly.
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

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None: ...

    def list_all(self) -> Sequence[RewatchSuggestion]: ...

    def commit(self) -> None: ...


class RewatchService:
    """Runs and serves the daily due-list (DESIGN §5.8)."""

    def __init__(self, repository: RewatchRepositoryProtocol) -> None:
        self._repository = repository

    def recompute(self, today: date) -> int:
        """Run the algorithm over the whole library and store its result.

        ``today`` is a parameter rather than read from the clock in here, so the
        boundary cases (a film due exactly today) are testable without freezing
        time. Returns how many films came back due — the scheduler logs it.
        """
        due = suggest(self._repository.collect_inputs(), today)
        self._repository.replace_all(due, utc_now())
        self._repository.commit()
        return len(due)

    def list_suggestions(self) -> Sequence[RewatchSuggestion]:
        """The stored due-list. Never recomputes — that is the daily job's alone (§5.8)."""
        return self._repository.list_all()
