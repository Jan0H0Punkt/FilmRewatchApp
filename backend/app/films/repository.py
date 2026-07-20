"""Data-access layer for the films module (DESIGN §5.1, M1 PR4).

CRUD over the SQLAlchemy ORM behind a stable interface; no business rules, no
HTTP. The service depends on the
:class:`~app.films.service.FilmRepositoryProtocol` interface, which this class
satisfies structurally.

Transaction control belongs to the film service (the film flows' atomic unit
of work, FR-LIB-03/NFR-INT-02); :meth:`FilmRepository.commit` is the mechanics
it calls to seal one. Everything else only stages or reads.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.films.models import Film, Title


class FilmRepository:
    """SQLAlchemy-backed film data access (one instance per request session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_film(self, film: Film) -> None:
        """Stage a new film row in the unit of work."""
        self._session.add(film)

    def add_title(self, title: Title) -> None:
        """Stage a new title row in the unit of work."""
        self._session.add(title)

    def find_by_id(self, film_id: uuid.UUID) -> Film | None:
        """Primary-key lookup."""
        return self._session.get(Film, film_id)

    def find_by_natural_key(self, natural_key: str) -> Film | None:
        """Exact lookup on the derived duplicate-detection key (FR-LIB-05).

        The key is normalised at derivation time (service), so equality here is
        the case/whitespace-insensitive match the requirement asks for.
        """
        statement = select(Film).where(Film.natural_key == natural_key)
        return self._session.scalars(statement).one_or_none()

    def list_titles(self, film_id: uuid.UUID) -> Sequence[Title]:
        """One film's titles — primary first, then alphabetically (§7.3)."""
        statement = (
            select(Title)
            .where(Title.film_id == film_id)
            .order_by(Title.is_primary.desc(), func.lower(Title.value))
        )
        return self._session.scalars(statement).all()

    def delete_titles(self, film_id: uuid.UUID) -> None:
        """Remove every title for a film (the edit flow's titles replacement).

        Runs immediately as a Core DELETE rather than through the unit-of-work
        (M1 PR5, FR-LIB-06) — critically, *before* the replacement titles are
        staged, so a new primary/original title in the same unit of work never
        races the one-primary/one-original partial unique indexes (§5.2)
        against the row it is replacing.
        """
        self._session.execute(delete(Title).where(Title.film_id == film_id))

    def delete_film(self, film: Film) -> None:
        """Stage a film's removal in the unit of work (M1 PR6, FR-LIB-10..12).

        No ORM ``relationship()`` links ``Film`` to its titles, ratings, or
        label links, so this only ever emits ``DELETE FROM films WHERE id =
        ...`` on flush — the PR1 ``ON DELETE CASCADE`` foreign keys are what
        remove the dependent rows (NFR-INT-02), entirely database-side.
        """
        self._session.delete(film)

    def commit(self) -> None:
        """Seal the caller's unit of work (the service decides when)."""
        self._session.commit()
