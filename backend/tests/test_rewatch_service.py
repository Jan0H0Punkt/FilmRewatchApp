"""The rewatch service's orchestration (DESIGN §5.8), against a fake repository (§9)."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.rewatch.algorithm import DAYS_PER_YEAR, DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion
from app.rewatch.service import RewatchService

# The real clock's date, not a fixed one: ``list_suggestions`` compares the
# stamp ``recompute`` writes — always "now" — against the date it is given, so a
# frozen date here would read every run as yesterday's.
TODAY = date.today()

# What the :func:`_input` profile below scores: five stars, so a one-year floor
# (reverse rating 1) plus two steps of 1 * 90 days. These tests are about
# orchestration, not scoring — the number only has to be the helper's.
REFERENCE_INTERVAL_DAYS = 1 * DAYS_PER_YEAR + 2 * 90


class FakeRepository:
    """Records what the service asked of it (satisfies ``RewatchRepositoryProtocol``)."""

    def __init__(self, inputs: Sequence[RewatchInput]) -> None:
        self._inputs = list(inputs)
        self.stored: list[DueFilm] = []
        self.stored_at: datetime | None = None
        self.commits = 0
        self.collects = 0

    def collect_inputs(self) -> list[RewatchInput]:
        self.collects += 1
        return list(self._inputs)

    def last_computed_at(self) -> datetime | None:
        return self.stored_at if self.stored else None

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
        average_rating=Decimal("5.0"),
        watch_count=1,
        last_watched_date=TODAY - timedelta(days=days_since_watch),
        is_favorite=False,
        delay_days=0,
        runtime_minutes=90,
    )


def test_recompute_stores_only_the_due_films_and_reports_the_count() -> None:
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS + 5), _input(0)])

    stored_count = RewatchService(repository).recompute(TODAY)

    assert stored_count == 1
    assert [row.days_until_next_rewatch for row in repository.stored] == [-5]


def test_recompute_commits_exactly_once() -> None:
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.commits == 1


def test_recompute_stamps_every_row_with_one_timestamp() -> None:
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS)])

    RewatchService(repository).recompute(TODAY)

    assert repository.stored_at is not None


def test_recompute_over_an_empty_library_stores_nothing() -> None:
    repository = FakeRepository([])

    assert RewatchService(repository).recompute(TODAY) == 0
    assert repository.stored == []
    assert repository.commits == 1


def test_list_suggestions_passes_the_stored_order_through_untouched() -> None:
    repository = FakeRepository(
        [_input(REFERENCE_INTERVAL_DAYS + 40), _input(REFERENCE_INTERVAL_DAYS)]
    )
    service = RewatchService(repository)
    service.recompute(TODAY)

    assert [row.days_until_next_rewatch for row in service.list_suggestions(TODAY)] == [-40, 0]


def test_list_suggestions_recomputes_when_nothing_was_ever_stored() -> None:
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS)])

    assert [
        row.days_until_next_rewatch for row in RewatchService(repository).list_suggestions(TODAY)
    ] == [0]
    assert repository.commits == 1


def test_list_suggestions_recomputes_once_a_day_and_not_again_the_same_day() -> None:
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS)])
    service = RewatchService(repository)

    service.list_suggestions(TODAY)
    service.list_suggestions(TODAY)

    assert repository.collects == 1


def test_list_suggestions_recomputes_again_the_next_day() -> None:
    # The passage of time alone makes a film due, which is the whole reason the
    # stamp is checked rather than trusting the last write.
    repository = FakeRepository([_input(REFERENCE_INTERVAL_DAYS - 1)])
    service = RewatchService(repository)

    assert list(service.list_suggestions(TODAY)) == []
    assert [
        row.days_until_next_rewatch for row in service.list_suggestions(TODAY + timedelta(days=1))
    ] == [0]
