"""Data-access layer for the rewatch module (DESIGN §5.1, §5.8).

Three reads and two writes, no business rules: the FR-RW-02 input assembly, the
staleness probe, the invalidation the write paths trigger, the whole-list
replacement of the projection, and the ordered read the router serves. Transaction control stays with the caller — only
:meth:`commit` commits.

:meth:`collect_inputs` returns :class:`~app.rewatch.algorithm.RewatchInput`
dataclasses rather than ORM rows or raw tuples. The mapping is mechanical, and
the alternative — leaking ``Row`` objects upward — would put the column-name
knowledge in the service instead, which is further from the SQL that produced
it. The algorithm module is dependency-free, so importing its types here costs
nothing.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.films.models import Film
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion

# The stamp :meth:`RewatchRepository.mark_stale` writes. Any instant before
# today would do; the epoch is picked because it is unmistakably not a real run
# and converts to a local date on every platform (``datetime.min`` does not —
# it overflows west of UTC).
STALE_COMPUTED_AT = datetime(1970, 1, 1, tzinfo=UTC)


class RewatchRepository:
    """SQLAlchemy-backed rewatch data access (one instance per session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def collect_inputs(self) -> list[RewatchInput]:
        """One aggregate query producing every film's FR-RW-02 payload.

        ``avg`` skips NULL scores on its own, so a film whose every watch went
        unrated reports ``None`` (FR-RAT-11/12) while ``count`` still counts
        those watches. The join is inner: a film with no rating cannot exist
        (FR-LIB-03), and one that somehow did would have no
        ``last_watched_date`` to reason about.
        """
        statement = (
            select(
                Film.id,
                func.avg(RatingEntry.value).label("average_rating"),
                func.count(RatingEntry.id).label("watch_count"),
                func.max(RatingEntry.watch_date).label("last_watched_date"),
                Film.is_favorite,
                Film.delay_days,
                Film.runtime_minutes,
            )
            .join(RatingEntry, RatingEntry.film_id == Film.id)
            .group_by(Film.id)
        )
        return [
            RewatchInput(
                film_id=row.id,
                average_rating=row.average_rating,
                watch_count=row.watch_count,
                last_watched_date=row.last_watched_date,
                is_favorite=row.is_favorite,
                delay_days=row.delay_days,
                runtime_minutes=row.runtime_minutes,
            )
            for row in self._session.execute(statement)
        ]

    def last_computed_at(self) -> datetime | None:
        """When the stored projection was last computed, or ``None`` if never.

        ``None`` also comes back when the last run stored no rows at all, since
        the timestamp lives on the rows — the caller cannot tell "never ran"
        from "ran, nothing was due", and treats both as stale.
        """
        return self._session.scalar(select(func.max(RewatchSuggestion.computed_at)))

    def mark_stale(self) -> None:
        """Age the stored projection out, so the next read recomputes it.

        The write paths call this instead of recomputing: a burst of writes
        then costs one cheap ``UPDATE`` each and a single run at the next read,
        where recomputing per write would run the algorithm once per write for
        a list nobody has asked for yet.

        The rows themselves survive, so a recompute that fails still leaves the
        client the last good list to show (FR-RW-07). An empty projection
        updates nothing and needs nothing — it already reads back as stale.
        """
        self._session.execute(update(RewatchSuggestion).values(computed_at=STALE_COMPUTED_AT))

    def replace_all(self, rows: Sequence[DueFilm], computed_at: datetime) -> None:
        """Swap the whole projection for ``rows``, keeping their order as ``position``.

        Delete-then-insert rather than an upsert: the projection *is* the last
        run's output, so a film absent from ``rows`` must not survive. Both
        statements share the caller's transaction, so a failure mid-run leaves
        the previous projection intact rather than an empty one.
        """
        self._session.execute(delete(RewatchSuggestion))
        self._session.add_all(
            [
                RewatchSuggestion(
                    film_id=row.film_id,
                    days_until_next_rewatch=row.days_until_next_rewatch,
                    position=position,
                    computed_at=computed_at,
                )
                for position, row in enumerate(rows)
            ]
        )

    def list_all(self) -> Sequence[RewatchSuggestion]:
        """The stored due-list in the algorithm's own order (FR-RW-04)."""
        statement = select(RewatchSuggestion).order_by(RewatchSuggestion.position)
        return self._session.scalars(statement).all()

    def commit(self) -> None:
        """Seal the unit of work (the service's call, mirroring ``FilmRepository``)."""
        self._session.commit()
