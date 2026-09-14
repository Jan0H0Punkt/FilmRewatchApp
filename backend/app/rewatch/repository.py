"""Data-access layer for the rewatch module (DESIGN §5.1, §5.8).

Two reads and one write, no business rules: the FR-RW-02 input assembly, the
whole-list replacement of the projection, and the ordered read the router
serves. Transaction control stays with the caller — only :meth:`commit` commits.

:meth:`collect_inputs` returns :class:`~app.rewatch.algorithm.RewatchInput`
dataclasses rather than ORM rows or raw tuples. The mapping is mechanical, and
the alternative — leaking ``Row`` objects upward — would put the column-name
knowledge in the service instead, which is further from the SQL that produced
it. The algorithm module is dependency-free, so importing its types here costs
nothing.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.films.models import Film
from app.ratings.models import RatingEntry
from app.rewatch.algorithm import DueFilm, RewatchInput
from app.rewatch.models import RewatchSuggestion


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
            )
            for row in self._session.execute(statement)
        ]

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
