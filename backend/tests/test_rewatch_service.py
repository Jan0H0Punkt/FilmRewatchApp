"""The rewatch service's orchestration (DESIGN §5.8), against a fake repository (§9)."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.rewatch.algorithm import BASE_INTERVAL_DAYS, DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion
from app.rewatch.service import RewatchService

TODAY = date(2026, 9, 14)


class FakeRepository:
    """Records what the service asked of it (satisfies ``RewatchRepositoryProtocol``)."""

    def __init__(self, inputs: Sequence[RewatchInput]) -> None:
        self._inputs = list(inputs)
        self.stored: list[DueFilm] = []
        self.stored_at: datetime | None = None
        self.commits = 0

    def collect_inputs(self) -> list[RewatchInput]:
        return list(self._inputs)

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None:
        self.stored = list(rows)
        self.stored_at = computed_at

    def list_all(self) -> Sequence[RewatchSuggestion]:
        # Narrowed for pyright strict: ``computed_at`` is a non-optional column,
        # and nothing reads this back before ``replace_all`` has stamped it.
        assert self.stored_at is not None
        return [
            RewatchSuggestion(
                film_id=row.film_id,
                days_until_next_rewatch=row.days_until_next_rewatch,
                position=position,
                computed_at=self.stored_at,
            )
            for position, row in enumerate(self.stored)
        ]

    def commit(self) -> None:
        self.commits += 1


def _input(days_since_watch: int) -> RewatchInput:
    return RewatchInput(
        film_id=uuid.uuid4(),
        average_rating=Decimal("4.0"),
        watch_count=1,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=False,
        delay_days=0,
    )


def test_recompute_stores_only_the_due_films_and_reports_the_count() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS + 5), _input(0)])

    stored_count = RewatchService(repository).recompute(TODAY)

    assert stored_count == 1
    assert [row.days_until_next_rewatch for row in repository.stored] == [-5]


def test_recompute_commits_exactly_once() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.commits == 1


def test_recompute_stamps_every_row_with_one_timestamp() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.stored_at is not None


def test_recompute_over_an_empty_library_stores_nothing() -> None:
    repository = FakeRepository([])

    assert RewatchService(repository).recompute(TODAY) == 0
    assert repository.stored == []
    assert repository.commits == 1


def test_list_suggestions_passes_the_stored_order_through_untouched() -> None:
    repository = FakeRepository([_input(BASE_INTERVAL_DAYS + 40), _input(BASE_INTERVAL_DAYS)])
    service = RewatchService(repository)
    service.recompute(TODAY)

    assert [row.days_until_next_rewatch for row in service.list_suggestions()] == [-40, 0]
